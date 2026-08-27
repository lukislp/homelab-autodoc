"""Kubernetes objects -> deterministic inventory.

build_app/build_namespace_inventory are pure (no API calls) and kind-agnostic -
they associate Services/Ingresses/Volumes with a NormalizedWorkload, not a
specific Deployment/StatefulSet. collect_cluster_inventory does the I/O.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from autodoc_core.models import (
    App,
    Autoscaler,
    ClusterInventory,
    IngressInfo,
    IngressRule,
    LimitRangeInfo,
    LimitRangeItemInfo,
    NamespaceInventory,
    NetworkPolicyInfo,
    NetworkPolicyPeerInfo,
    NetworkPolicyRule,
    NodeInfo,
    PodDisruptionBudgetInfo,
    ResourceQuotaInfo,
    RoleBindingInfo,
    ServiceAccountInfo,
    ServiceInfo,
    ServicePort,
    ServiceReference,
    StorageClassInfo,
    Volume,
    WarningEventInfo,
)
from kubernetes import client
from kubernetes.client.exceptions import ApiException

from .backups import collect_backup_info
from .k8s_apis import K8sApis
from .workloads import DEFAULT_WORKLOAD_COLLECTORS, NormalizedWorkload, WorkloadCollector

DEFAULT_SYSTEM_NAMESPACES = frozenset({"kube-system", "kube-public", "kube-node-lease"})

_HTTPROUTE_GROUP = "gateway.networking.k8s.io"
_HTTPROUTE_VERSION = "v1"
_HTTPROUTE_PLURAL = "httproutes"


def _selector_matches(selector: dict[str, str] | None, pod_labels: dict[str, str]) -> bool:
    if not selector:
        return False
    return all(pod_labels.get(key) == value for key, value in selector.items())


def _build_service(raw: client.V1Service) -> ServiceInfo:
    ports = [
        ServicePort(
            port=p.port,
            target_port=str(p.target_port),
            protocol=p.protocol,
            name=p.name,
        )
        for p in (raw.spec.ports or [])
    ]
    return ServiceInfo(
        name=raw.metadata.name,
        type=raw.spec.type,
        cluster_ip=raw.spec.cluster_ip,
        ports=ports,
    )


def _build_volume(raw: client.V1PersistentVolumeClaim) -> Volume:
    capacity = None
    if raw.status and raw.status.capacity:
        capacity = raw.status.capacity.get("storage")
    return Volume(
        claim_name=raw.metadata.name,
        storage_class=raw.spec.storage_class_name,
        capacity=capacity,
        access_modes=list(raw.spec.access_modes or []),
    )


def _build_ingress(raw: client.V1Ingress) -> IngressInfo:
    rules: list[IngressRule] = []
    for rule in raw.spec.rules or []:
        paths = rule.http.paths if rule.http else []
        for path in paths:
            backend_service = path.backend.service
            rules.append(
                IngressRule(
                    host=rule.host,
                    path=path.path or "/",
                    service_name=backend_service.name,
                    service_port=str(backend_service.port.number or backend_service.port.name),
                )
            )
    tls_hosts = [host for tls in (raw.spec.tls or []) for host in (tls.hosts or [])]
    return IngressInfo(name=raw.metadata.name, rules=rules, tls_hosts=tls_hosts)


def _ingress_targets_services(raw: client.V1Ingress, service_names: set[str]) -> bool:
    for rule in raw.spec.rules or []:
        paths = rule.http.paths if rule.http else []
        for path in paths:
            if path.backend.service and path.backend.service.name in service_names:
                return True
    return False


def _build_httproute(raw: dict) -> IngressInfo:
    """HTTPRoute (Gateway API) is a CRD, so this reads a plain dict from
    CustomObjectsApi, not a typed client.V1* object like _build_ingress does.
    Normalized into the same IngressInfo/IngressRule shape as classic Ingress -
    from a docs page's point of view, "how is this app reached externally" is
    the same question regardless of which K8s API answers it, so the existing
    facts table/diagram code needs no changes at all to show either. No
    tls_hosts: HTTPRoute doesn't declare TLS itself - that's on the Gateway's
    own listeners, a separate resource this collector doesn't read.
    """
    spec = raw.get("spec", {})
    hostnames = spec.get("hostnames") or [None]
    rules: list[IngressRule] = []
    for hostname in hostnames:
        for rule in spec.get("rules", []):
            matches = rule.get("matches") or [{}]
            paths = [m.get("path", {}).get("value", "/") for m in matches]
            for backend in rule.get("backendRefs", []):
                service_name = backend.get("name")
                if not service_name:
                    continue
                port = backend.get("port")
                for path in paths:
                    rules.append(
                        IngressRule(
                            host=hostname,
                            path=path,
                            service_name=service_name,
                            service_port=str(port) if port is not None else "",
                        )
                    )
    return IngressInfo(name=raw.get("metadata", {}).get("name", ""), rules=rules, tls_hosts=[])


def _httproute_targets_services(raw: dict, service_names: set[str]) -> bool:
    for rule in raw.get("spec", {}).get("rules", []):
        for backend in rule.get("backendRefs", []):
            if backend.get("name") in service_names:
                return True
    return False


def _build_autoscaler(raw: client.V2HorizontalPodAutoscaler) -> Autoscaler:
    cpu_percent = None
    memory_percent = None
    for metric in raw.spec.metrics or []:
        if metric.type != "Resource" or not metric.resource:
            continue
        utilization = metric.resource.target.average_utilization if metric.resource.target else None
        if metric.resource.name == "cpu":
            cpu_percent = utilization
        elif metric.resource.name == "memory":
            memory_percent = utilization
    return Autoscaler(
        min_replicas=raw.spec.min_replicas or 1,
        max_replicas=raw.spec.max_replicas,
        target_cpu_percent=cpu_percent,
        target_memory_percent=memory_percent,
    )


def _autoscaler_for_workload(
    hpas: list[client.V2HorizontalPodAutoscaler], workload: NormalizedWorkload
) -> Autoscaler | None:
    for hpa in hpas:
        ref = hpa.spec.scale_target_ref
        if ref.kind == workload.kind and ref.name == workload.name:
            return _build_autoscaler(hpa)
    return None


def _node_names_for_workload(pods: list[client.V1Pod], workload: NormalizedWorkload) -> list[str]:
    """Which node(s) an app's pods are actually scheduled on - not derivable
    from the workload spec itself (Deployment/StatefulSet/etc. don't carry a
    node), only from the live Pod objects. Matched the same way Services are:
    workload.pod_labels is a subset of the pod's own labels.
    """
    names = {
        pod.spec.node_name
        for pod in pods
        if pod.spec.node_name and _selector_matches(workload.pod_labels, pod.metadata.labels)
    }
    return sorted(names)


def _build_peer(peer: client.V1NetworkPolicyPeer) -> NetworkPolicyPeerInfo:
    """The structured peer the generator's network resolution consumes.
    matchExpressions are not modeled: a selector using them becomes None
    fields all around ("unknown"), never a guess.
    """
    if peer.ip_block is not None:
        return NetworkPolicyPeerInfo(ip_block=peer.ip_block.cidr)

    def match_labels(selector: client.V1LabelSelector | None) -> dict[str, str] | None:
        if selector is None:
            return None
        return dict(selector.match_labels or {})

    return NetworkPolicyPeerInfo(
        namespace_selector=match_labels(peer.namespace_selector),
        pod_selector=match_labels(peer.pod_selector),
    )


def _describe_peer(info: NetworkPolicyPeerInfo) -> str:
    """Display string DERIVED from the structured peer - one source of
    truth. A peer may combine namespaceSelector AND podSelector; both
    halves survive, joined with "+". Older generators parse this shape as a
    fallback for inventories predating peer_selectors.
    """
    if info.ip_block is not None:
        return f"ipBlock:{info.ip_block}"

    def describe(selector: dict[str, str] | None) -> str:
        return ",".join(f"{k}={v}" for k, v in sorted((selector or {}).items())) or "all"

    parts = []
    if info.namespace_selector is not None:
        parts.append(f"namespaces:{describe(info.namespace_selector)}")
    if info.pod_selector is not None:
        parts.append(f"pods:{describe(info.pod_selector)}")
    return "+".join(parts) or "unknown"


def _describe_port(port: client.V1NetworkPolicyPort) -> str:
    protocol = port.protocol or "TCP"
    return f"{protocol}/{port.port}" if port.port is not None else protocol


def _build_network_policy_rule(
    peers: list[client.V1NetworkPolicyPeer] | None, ports: list[client.V1NetworkPolicyPort] | None
) -> NetworkPolicyRule:
    structured = [_build_peer(p) for p in (peers or [])]
    return NetworkPolicyRule(
        peers=[_describe_peer(info) for info in structured],
        ports=[_describe_port(p) for p in (ports or [])],
        peer_selectors=structured,
    )


def _build_network_policy(raw: client.V1NetworkPolicy) -> NetworkPolicyInfo:
    return NetworkPolicyInfo(
        name=raw.metadata.name,
        policy_types=list(raw.spec.policy_types or []),
        ingress=[_build_network_policy_rule(r._from, r.ports) for r in (raw.spec.ingress or [])],
        egress=[_build_network_policy_rule(r.to, r.ports) for r in (raw.spec.egress or [])],
    )


def _backup_volumes(template_annotations: dict[str, str]) -> list[str]:
    """The pod template's Velero file-system-backup opt-in, split into the
    volume names it lists - the raw fact the no-backup findings reason over.
    """
    raw = template_annotations.get("backup.velero.io/backup-volumes", "")
    return [part.strip() for part in raw.split(",") if part.strip()]


def _network_policy_matches_workload(
    raw: client.V1NetworkPolicy, workload: NormalizedWorkload
) -> bool:
    """Only matchLabels is evaluated - the same simplification already used
    for Service selectors (always plain dict selectors). A podSelector using
    matchExpressions is skipped rather than guessed at, to avoid claiming a
    policy applies to an app it might not.
    """
    selector = raw.spec.pod_selector
    if selector and selector.match_expressions:
        return False
    match_labels = selector.match_labels if selector else None
    if not match_labels:
        return True  # empty/absent podSelector selects every pod in the namespace
    return _selector_matches(match_labels, workload.pod_labels)


def _role_binding_info(
    binding: client.V1RoleBinding | client.V1ClusterRoleBinding,
) -> RoleBindingInfo:
    return RoleBindingInfo(
        name=binding.metadata.name,
        role_kind=binding.role_ref.kind,
        role_name=binding.role_ref.name,
    )


def _service_account_role_bindings(
    role_bindings: list[client.V1RoleBinding],
    cluster_role_bindings: list[client.V1ClusterRoleBinding],
    namespace: str,
) -> dict[str, list[RoleBindingInfo]]:
    """Groups RoleBinding/ClusterRoleBinding objects by the ServiceAccount name
    each one's subjects target, computed once per namespace rather than once
    per app - cheap either way, but this avoids rescanning the same handful of
    bindings for every app in a namespace that shares them.

    A subject's `namespace` field is optional on a (namespace-scoped)
    RoleBinding - unset there implicitly means "this binding's own namespace",
    which the caller already knows since role_bindings was fetched scoped to
    it. A ClusterRoleBinding has no such implicit namespace to fall back to,
    so its subjects must name one explicitly to match at all.
    """
    result: dict[str, list[RoleBindingInfo]] = {}
    for rb in role_bindings:
        info = _role_binding_info(rb)
        for subject in rb.subjects or []:
            if subject.kind == "ServiceAccount" and subject.namespace in (None, namespace):
                result.setdefault(subject.name, []).append(info)
    for crb in cluster_role_bindings:
        info = _role_binding_info(crb)
        for subject in crb.subjects or []:
            if subject.kind == "ServiceAccount" and subject.namespace == namespace:
                result.setdefault(subject.name, []).append(info)
    return result


def _build_pdb(raw: client.V1PodDisruptionBudget) -> PodDisruptionBudgetInfo:
    return PodDisruptionBudgetInfo(
        name=raw.metadata.name,
        min_available=str(raw.spec.min_available) if raw.spec.min_available is not None else None,
        max_unavailable=str(raw.spec.max_unavailable)
        if raw.spec.max_unavailable is not None
        else None,
    )


def _pdb_matches_workload(raw: client.V1PodDisruptionBudget, workload: NormalizedWorkload) -> bool:
    """Only matchLabels is evaluated, same simplification as NetworkPolicy's
    podSelector - and for the same reason: a podSelector using
    matchExpressions is skipped rather than guessed at, since a wrong match
    here would misleadingly claim a PDB protects an app it might not.

    PDB documents its own selector semantics as the inverse of what you'd
    expect from a generic LabelSelector: a null selector matches NO pods,
    while an empty ({}) selector matches EVERY pod in the namespace - the
    two are deliberately distinguished below, not collapsed into one case.
    """
    selector = raw.spec.selector
    if selector is None:
        return False
    if selector.match_expressions:
        return False
    if not selector.match_labels:
        return True
    return _selector_matches(selector.match_labels, workload.pod_labels)


def _build_resource_quota(raw: client.V1ResourceQuota) -> ResourceQuotaInfo:
    hard = raw.status.hard if raw.status and raw.status.hard else (raw.spec.hard or {})
    used = raw.status.used if raw.status and raw.status.used else {}
    return ResourceQuotaInfo(name=raw.metadata.name, hard=dict(hard), used=dict(used))


def _build_limit_range_item(raw: client.V1LimitRangeItem) -> LimitRangeItemInfo:
    return LimitRangeItemInfo(
        kind=raw.type,
        min=dict(raw.min or {}),
        max=dict(raw.max or {}),
        default=dict(raw.default or {}),
        default_request=dict(raw.default_request or {}),
    )


def _build_limit_range(raw: client.V1LimitRange) -> LimitRangeInfo:
    return LimitRangeInfo(
        name=raw.metadata.name,
        limits=[_build_limit_range_item(item) for item in (raw.spec.limits or [])],
    )


# Enough to show what's currently unhealthy without turning the inventory into
# an event log - events are transient by nature (the API server prunes them
# after ~1h anyway) and only the most recent ones carry signal.
_MAX_WARNING_EVENTS_PER_NAMESPACE = 20


def _build_warning_event(raw: client.CoreV1Event) -> WarningEventInfo:
    # An event carries up to three timestamps depending on how it was emitted
    # (series-compressed events use last_timestamp, one-shots event_time);
    # creation_timestamp is the always-present fallback.
    timestamp = raw.last_timestamp or raw.event_time
    if timestamp is None and raw.metadata is not None:
        timestamp = raw.metadata.creation_timestamp
    involved = raw.involved_object
    object_ref = f"{involved.kind}/{involved.name}" if involved else "unknown"
    return WarningEventInfo(
        reason=raw.reason or "Unknown",
        object_ref=object_ref,
        message=(raw.message or "").strip(),
        count=raw.count or 1,
        last_seen=timestamp.isoformat() if timestamp else None,
    )


def _list_warning_events(apis: K8sApis, namespace: str) -> list[WarningEventInfo] | None:
    """Same None-on-403 semantics as _list_configmap_names: the ClusterRole
    may predate the events grant, and "unknown" must stay distinguishable
    from "no warnings".
    """
    try:
        raw = apis.core_v1.list_namespaced_event(namespace, field_selector="type=Warning").items
    except ApiException as e:
        if e.status == 403:
            return None
        raise
    events = sorted(
        (_build_warning_event(ev) for ev in raw), key=lambda ev: ev.last_seen or "", reverse=True
    )
    return events[:_MAX_WARNING_EVENTS_PER_NAMESPACE]


def _list_configmaps(apis: K8sApis, namespace: str) -> list[client.V1ConfigMap] | None:
    """The names feed the dangling-reference check; the CONTENTS are scanned
    in memory for service-endpoint references (_service_references) and then
    dropped - never persisted into the inventory. Secrets are deliberately
    not listed at all, not even for names: the API returns full secret
    values on a list, and the collector's no-secret-access guarantee (see
    the RBAC manifest) is worth more than either check. None (not []) when
    RBAC denies the read: this collector may run against a cluster whose
    ClusterRole predates the configmaps grant, and "unknown" must stay
    distinguishable from "there are none".
    """
    try:
        return apis.core_v1.list_namespaced_config_map(namespace).items
    except ApiException as e:
        if e.status == 403:
            return None
        raise


# Kept in sync with the generator's _ACCEPT_ANNOTATION_PREFIX (findings.py):
# the collector strips the prefix so the inventory carries plain rule names.
_ACCEPT_ANNOTATION_PREFIX = "autodoc.homelab/accept-"


def _list_namespace_objects(apis: K8sApis) -> list[client.V1Namespace] | None:
    """Same None-on-403 semantics as _list_configmaps: a collector run with
    an explicit namespace list may lack the cluster-wide namespaces grant,
    and "unknown" must stay distinguishable from "no annotations".
    """
    try:
        return apis.core_v1.list_namespace().items
    except ApiException as e:
        if e.status == 403:
            return None
        raise


def _accept_annotations(annotations: dict[str, str] | None) -> dict[str, str]:
    """Rule name -> reason from a Namespace object's accept annotations.
    Only the accept-prefixed keys are kept - the namespace's other
    annotations never enter the inventory. Empty reasons are dropped here
    the same way the generator drops them for workloads: an annotation
    without a stated reason must not silently accept anything.
    """
    accepted = {}
    for key, value in (annotations or {}).items():
        if not key.startswith(_ACCEPT_ANNOTATION_PREFIX):
            continue
        rule = key.removeprefix(_ACCEPT_ANNOTATION_PREFIX)
        reason = value.strip()
        if rule and reason:
            accepted[rule] = reason
    return accepted


# Candidate host[:port] tokens inside config values. Lowercase DNS-1123 shapes
# only, hard-bounded so URLs/connection strings tokenize cleanly.
_HOST_CANDIDATE = re.compile(
    r"(?<![A-Za-z0-9_.-])"
    r"([a-z0-9][a-z0-9-]{0,62}(?:\.[a-z0-9][a-z0-9-]{0,62})*)"
    r"(?::([0-9]{1,5}))?"
    r"(?![A-Za-z0-9-])"
)


def _service_refs_in_text(text: str, via: str, service_names: set[str]) -> set[ServiceReference]:
    """Deterministic service-endpoint detection in one plain-text value.
    Three shapes count, everything else is ignored rather than guessed at:
    full cluster DNS (name.namespace.svc[...]), a bare token exactly matching
    a Service in the app's own namespace, and headless-StatefulSet pod DNS
    (<pod>.<service>). Bare words can only ever match real local Services,
    so prose-like config values produce no false edges.
    """
    refs: set[ServiceReference] = set()
    for match in _HOST_CANDIDATE.finditer(text):
        host, port_text = match.group(1), match.group(2)
        port = int(port_text) if port_text else None
        labels = host.split(".")
        if "svc" in labels:
            i = labels.index("svc")
            if i >= 2:
                refs.add(
                    ServiceReference(
                        service=labels[i - 2], namespace=labels[i - 1], port=port, via=via
                    )
                )
            continue
        if host in service_names:
            refs.add(ServiceReference(service=host, port=port, via=via))
        elif len(labels) == 2 and labels[1] in service_names:
            refs.add(ServiceReference(service=labels[1], port=port, via=via))
    return refs


def _service_references(
    workload: NormalizedWorkload,
    configmap_data: dict[str, dict[str, str]] | None,
    service_names: set[str],
) -> list[ServiceReference]:
    """What this app is CONFIGURED to talk to - from its plain env values and
    the contents of the ConfigMaps it references (scanned in memory here,
    never persisted). Secret-held connection strings stay invisible by
    design. Deduplicated per (service, namespace, port), keeping the first
    via alphabetically for a stable inventory.
    """
    refs: set[ServiceReference] = set()
    for container in workload.containers:
        for env in container.env:
            if env.value:
                refs |= _service_refs_in_text(env.value, f"env {env.name}", service_names)
    if configmap_data:
        referenced = {r.name for r in workload.config_refs if r.kind == "ConfigMap"}
        for cm_name in sorted(referenced):
            for key, value in sorted((configmap_data.get(cm_name) or {}).items()):
                refs |= _service_refs_in_text(value, f"ConfigMap {cm_name}/{key}", service_names)
    deduped: dict[tuple, ServiceReference] = {}
    for ref in sorted(refs, key=lambda r: (r.service, r.namespace or "", r.port or 0, r.via)):
        deduped.setdefault((ref.service, ref.namespace, ref.port), ref)
    return list(deduped.values())


def build_app(
    workload: NormalizedWorkload,
    services: list[client.V1Service],
    ingresses: list[client.V1Ingress],
    pvcs: list[client.V1PersistentVolumeClaim],
    httproutes: list[dict] | None = None,
    hpas: list[client.V2HorizontalPodAutoscaler] | None = None,
    pods: list[client.V1Pod] | None = None,
    network_policies: list[client.V1NetworkPolicy] | None = None,
    service_account_role_bindings: dict[str, list[RoleBindingInfo]] | None = None,
    pdbs: list[client.V1PodDisruptionBudget] | None = None,
    configmap_data: dict[str, dict[str, str]] | None = None,
) -> App:
    matched_services = [
        svc for svc in services if _selector_matches(svc.spec.selector, workload.pod_labels)
    ]
    matched_service_names = {svc.metadata.name for svc in matched_services}
    matched_ingresses = [
        ing for ing in ingresses if _ingress_targets_services(ing, matched_service_names)
    ]
    matched_httproutes = [
        route
        for route in (httproutes or [])
        if _httproute_targets_services(route, matched_service_names)
    ]
    matched_pvcs = [pvc for pvc in pvcs if pvc.metadata.name in workload.claim_names]

    service_account = None
    if workload.service_account_name:
        service_account = ServiceAccountInfo(
            name=workload.service_account_name,
            role_bindings=(service_account_role_bindings or {}).get(
                workload.service_account_name, []
            ),
        )

    return App(
        name=workload.name,
        kind=workload.kind,
        replicas=workload.replicas,
        ready_replicas=workload.ready_replicas,
        containers=workload.containers,
        volumes=[_build_volume(pvc) for pvc in matched_pvcs],
        backup_volumes=_backup_volumes(workload.template_annotations),
        services=[_build_service(svc) for svc in matched_services],
        ingresses=[_build_ingress(ing) for ing in matched_ingresses]
        + [_build_httproute(route) for route in matched_httproutes],
        labels=workload.labels,
        annotations=workload.annotations,
        pod_labels=workload.pod_labels,
        created_at=workload.created_at,
        owners=workload.owners,
        config_refs=sorted(workload.config_refs, key=lambda c: (c.kind, c.name, c.via)),
        service_references=_service_references(
            workload, configmap_data, {svc.metadata.name for svc in services}
        ),
        autoscaler=_autoscaler_for_workload(hpas or [], workload),
        nodes=_node_names_for_workload(pods or [], workload),
        network_policies=[
            _build_network_policy(np)
            for np in (network_policies or [])
            if _network_policy_matches_workload(np, workload)
        ],
        service_account=service_account,
        pod_disruption_budgets=[
            _build_pdb(pdb) for pdb in (pdbs or []) if _pdb_matches_workload(pdb, workload)
        ],
        node_selector=workload.node_selector,
        node_affinity=workload.node_affinity,
        tolerations=workload.tolerations,
        rollout_strategy=workload.rollout_strategy,
        image_pull_secrets=sorted(workload.image_pull_secrets),
    )


def build_namespace_inventory(
    namespace: str,
    workloads: list[NormalizedWorkload],
    services: list[client.V1Service],
    ingresses: list[client.V1Ingress],
    pvcs: list[client.V1PersistentVolumeClaim],
    httproutes: list[dict] | None = None,
    hpas: list[client.V2HorizontalPodAutoscaler] | None = None,
    pods: list[client.V1Pod] | None = None,
    network_policies: list[client.V1NetworkPolicy] | None = None,
    service_account_role_bindings: dict[str, list[RoleBindingInfo]] | None = None,
    pdbs: list[client.V1PodDisruptionBudget] | None = None,
    resource_quotas: list[client.V1ResourceQuota] | None = None,
    limit_ranges: list[client.V1LimitRange] | None = None,
    configmap_names: list[str] | None = None,
    warning_events: list[WarningEventInfo] | None = None,
    configmap_data: dict[str, dict[str, str]] | None = None,
    accepted_rules: dict[str, str] | None = None,
) -> NamespaceInventory:
    apps = [
        build_app(
            workload,
            services,
            ingresses,
            pvcs,
            httproutes,
            hpas,
            pods,
            network_policies,
            service_account_role_bindings,
            pdbs,
            configmap_data,
        )
        for workload in workloads
    ]
    return NamespaceInventory(
        name=namespace,
        apps=apps,
        resource_quotas=[_build_resource_quota(rq) for rq in (resource_quotas or [])],
        limit_ranges=[_build_limit_range(lr) for lr in (limit_ranges or [])],
        # None stays None here ("not collected"), unlike the or-[] fields
        # above - see the model's own comment on the distinction.
        configmap_names=configmap_names,
        warning_events=warning_events,
        accepted_rules=accepted_rules,
    )


def _list_httproutes(apis: K8sApis, namespace: str) -> list[dict]:
    """Cluster-invariant: a cluster without the Gateway API CRDs installed
    (or too old a version to have this one) 404s here - that's expected, not
    an error, so this collector works the same whether or not Gateway API is
    present at all.
    """
    try:
        result = apis.custom_objects.list_namespaced_custom_object(
            group=_HTTPROUTE_GROUP,
            version=_HTTPROUTE_VERSION,
            namespace=namespace,
            plural=_HTTPROUTE_PLURAL,
        )
    except ApiException as e:
        if e.status == 404:
            return []
        raise
    return result.get("items", [])


def _list_hpas(apis: K8sApis, namespace: str) -> list[client.V2HorizontalPodAutoscaler]:
    """Cluster-invariant like _list_httproutes: autoscaling/v2 has been a
    stable built-in API since Kubernetes 1.23 (Dec 2021), not a CRD, so this
    is expected to always work - but an old or unusually minimal API server
    could still 404 it, and that must degrade to "no autoscalers", not crash
    the whole run.
    """
    try:
        return apis.autoscaling_v2.list_namespaced_horizontal_pod_autoscaler(namespace).items
    except ApiException as e:
        if e.status == 404:
            return []
        raise


def _build_storage_class(raw: client.V1StorageClass) -> StorageClassInfo:
    return StorageClassInfo(
        name=raw.metadata.name,
        provisioner=raw.provisioner,
        reclaim_policy=raw.reclaim_policy,
        volume_binding_mode=raw.volume_binding_mode,
        allow_volume_expansion=raw.allow_volume_expansion,
    )


def _build_node(raw: client.V1Node) -> NodeInfo:
    ready = any(c.type == "Ready" and c.status == "True" for c in (raw.status.conditions or []))
    return NodeInfo(
        name=raw.metadata.name,
        architecture=raw.status.node_info.architecture,
        kubelet_version=raw.status.node_info.kubelet_version,
        os_image=raw.status.node_info.os_image,
        capacity_cpu=raw.status.capacity.get("cpu", ""),
        capacity_memory=raw.status.capacity.get("memory", ""),
        allocatable_cpu=raw.status.allocatable.get("cpu", ""),
        allocatable_memory=raw.status.allocatable.get("memory", ""),
        ready=ready,
    )


def collect_cluster_inventory(
    cluster_name: str,
    namespaces: list[str] | None = None,
    include_system: bool = False,
    workload_collectors: tuple[WorkloadCollector, ...] = DEFAULT_WORKLOAD_COLLECTORS,
) -> ClusterInventory:
    """I/O step: fetch live objects from the cluster and shape them into an inventory."""
    apis = K8sApis.build()

    # One namespace list serves both the default namespace discovery and the
    # namespace-level accept annotations (autodoc.homelab/accept-<rule> on
    # the Namespace object) - None on 403 keeps the "unknown, not empty"
    # semantics for accepted_rules when the ClusterRole predates the grant.
    namespace_objects = _list_namespace_objects(apis)

    if namespaces is None:
        if namespace_objects is None:
            raise RuntimeError(
                "cannot list namespaces (RBAC) and no explicit namespace list was given"
            )
        namespaces = [
            ns.metadata.name
            for ns in namespace_objects
            if include_system or ns.metadata.name not in DEFAULT_SYSTEM_NAMESPACES
        ]
    namespace_accepts = (
        {ns.metadata.name: _accept_annotations(ns.metadata.annotations) for ns in namespace_objects}
        if namespace_objects is not None
        else None
    )

    # Cluster-scoped, so fetched once for the whole run rather than re-fetched
    # identically for every namespace - a ClusterRoleBinding's subjects can
    # name a ServiceAccount from any namespace.
    cluster_role_bindings = apis.rbac_v1.list_cluster_role_binding().items

    namespace_inventories = []
    for namespace in namespaces:
        workloads = [
            workload
            for collector in workload_collectors
            for workload in collector.list(apis, namespace)
        ]
        if not workloads:
            continue
        services = apis.core_v1.list_namespaced_service(namespace).items
        ingresses = apis.networking_v1.list_namespaced_ingress(namespace).items
        pvcs = apis.core_v1.list_namespaced_persistent_volume_claim(namespace).items
        httproutes = _list_httproutes(apis, namespace)
        hpas = _list_hpas(apis, namespace)
        pods = apis.core_v1.list_namespaced_pod(namespace).items
        network_policies = apis.networking_v1.list_namespaced_network_policy(namespace).items
        role_bindings = apis.rbac_v1.list_namespaced_role_binding(namespace).items
        service_account_role_bindings = _service_account_role_bindings(
            role_bindings, cluster_role_bindings, namespace
        )
        pdbs = apis.policy_v1.list_namespaced_pod_disruption_budget(namespace).items
        resource_quotas = apis.core_v1.list_namespaced_resource_quota(namespace).items
        limit_ranges = apis.core_v1.list_namespaced_limit_range(namespace).items
        configmaps = _list_configmaps(apis, namespace)
        configmap_names = (
            sorted(cm.metadata.name for cm in configmaps) if configmaps is not None else None
        )
        configmap_data = (
            {cm.metadata.name: dict(cm.data or {}) for cm in configmaps}
            if configmaps is not None
            else None
        )
        warning_events = _list_warning_events(apis, namespace)
        namespace_inventories.append(
            build_namespace_inventory(
                namespace,
                workloads,
                services,
                ingresses,
                pvcs,
                httproutes,
                hpas,
                pods,
                network_policies,
                service_account_role_bindings,
                pdbs,
                resource_quotas,
                limit_ranges,
                configmap_names,
                warning_events,
                configmap_data,
                # dict (possibly empty) when namespaces were listable, None
                # ("unknown") when RBAC denied the list.
                namespace_accepts.get(namespace, {}) if namespace_accepts is not None else None,
            )
        )

    # Cluster-scoped, so fetched once for the whole run rather than per namespace.
    storage_classes = [
        _build_storage_class(sc) for sc in apis.storage_v1.list_storage_class().items
    ]
    nodes = [_build_node(n) for n in apis.core_v1.list_node().items]

    return ClusterInventory(
        cluster_name=cluster_name,
        collected_at=datetime.now(UTC).isoformat(),
        namespaces=namespace_inventories,
        storage_classes=storage_classes,
        nodes=nodes,
        backups=collect_backup_info(apis),
    )

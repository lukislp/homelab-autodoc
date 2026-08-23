"""Kubernetes objects -> deterministic inventory.

build_app/build_namespace_inventory are pure (no API calls) and kind-agnostic -
they associate Services/Ingresses/Volumes with a NormalizedWorkload, not a
specific Deployment/StatefulSet. collect_cluster_inventory does the I/O.
"""

from __future__ import annotations

from datetime import UTC, datetime

from autodoc_core.models import (
    App,
    Autoscaler,
    ClusterInventory,
    IngressInfo,
    IngressRule,
    NamespaceInventory,
    NetworkPolicyInfo,
    NetworkPolicyRule,
    NodeInfo,
    PodDisruptionBudgetInfo,
    RoleBindingInfo,
    ServiceAccountInfo,
    ServiceInfo,
    ServicePort,
    StorageClassInfo,
    Volume,
)
from kubernetes import client
from kubernetes.client.exceptions import ApiException

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


def _describe_selector(selector: dict[str, str] | None) -> str:
    return ",".join(f"{k}={v}" for k, v in sorted((selector or {}).items())) or "all"


def _describe_peer(peer: client.V1NetworkPolicyPeer) -> str:
    if peer.ip_block is not None:
        return f"ipBlock:{peer.ip_block.cidr}"
    if peer.namespace_selector is not None:
        return f"namespaces:{_describe_selector(peer.namespace_selector.match_labels)}"
    if peer.pod_selector is not None:
        return f"pods:{_describe_selector(peer.pod_selector.match_labels)}"
    return "unknown"


def _describe_port(port: client.V1NetworkPolicyPort) -> str:
    protocol = port.protocol or "TCP"
    return f"{protocol}/{port.port}" if port.port is not None else protocol


def _build_network_policy_rule(
    peers: list[client.V1NetworkPolicyPeer] | None, ports: list[client.V1NetworkPolicyPort] | None
) -> NetworkPolicyRule:
    return NetworkPolicyRule(
        peers=[_describe_peer(p) for p in (peers or [])],
        ports=[_describe_port(p) for p in (ports or [])],
    )


def _build_network_policy(raw: client.V1NetworkPolicy) -> NetworkPolicyInfo:
    return NetworkPolicyInfo(
        name=raw.metadata.name,
        policy_types=list(raw.spec.policy_types or []),
        ingress=[_build_network_policy_rule(r._from, r.ports) for r in (raw.spec.ingress or [])],
        egress=[_build_network_policy_rule(r.to, r.ports) for r in (raw.spec.egress or [])],
    )


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
        services=[_build_service(svc) for svc in matched_services],
        ingresses=[_build_ingress(ing) for ing in matched_ingresses]
        + [_build_httproute(route) for route in matched_httproutes],
        labels=workload.labels,
        annotations=workload.annotations,
        created_at=workload.created_at,
        owners=workload.owners,
        config_refs=sorted(workload.config_refs, key=lambda c: (c.kind, c.name, c.via)),
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
        )
        for workload in workloads
    ]
    return NamespaceInventory(name=namespace, apps=apps)


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

    if namespaces is None:
        namespaces = [
            ns.metadata.name
            for ns in apis.core_v1.list_namespace().items
            if include_system or ns.metadata.name not in DEFAULT_SYSTEM_NAMESPACES
        ]

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
    )

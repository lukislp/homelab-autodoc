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
    ServiceInfo,
    ServicePort,
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


def build_app(
    workload: NormalizedWorkload,
    services: list[client.V1Service],
    ingresses: list[client.V1Ingress],
    pvcs: list[client.V1PersistentVolumeClaim],
    httproutes: list[dict] | None = None,
    hpas: list[client.V2HorizontalPodAutoscaler] | None = None,
    pods: list[client.V1Pod] | None = None,
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
) -> NamespaceInventory:
    apps = [
        build_app(workload, services, ingresses, pvcs, httproutes, hpas, pods)
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
        namespace_inventories.append(
            build_namespace_inventory(
                namespace, workloads, services, ingresses, pvcs, httproutes, hpas, pods
            )
        )

    return ClusterInventory(
        cluster_name=cluster_name,
        collected_at=datetime.now(UTC).isoformat(),
        namespaces=namespace_inventories,
    )

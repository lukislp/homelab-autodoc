"""Kubernetes objects -> deterministic inventory.

build_app/build_namespace_inventory are pure (no API calls) and kind-agnostic -
they associate Services/Ingresses/Volumes with a NormalizedWorkload, not a
specific Deployment/StatefulSet. collect_cluster_inventory does the I/O.
"""

from __future__ import annotations

from datetime import UTC, datetime

from autodoc_core.models import (
    App,
    ClusterInventory,
    IngressInfo,
    IngressRule,
    NamespaceInventory,
    ServiceInfo,
    ServicePort,
    Volume,
)
from kubernetes import client

from .k8s_apis import K8sApis
from .workloads import DEFAULT_WORKLOAD_COLLECTORS, NormalizedWorkload, WorkloadCollector

DEFAULT_SYSTEM_NAMESPACES = frozenset({"kube-system", "kube-public", "kube-node-lease"})


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


def build_app(
    workload: NormalizedWorkload,
    services: list[client.V1Service],
    ingresses: list[client.V1Ingress],
    pvcs: list[client.V1PersistentVolumeClaim],
) -> App:
    matched_services = [
        svc for svc in services if _selector_matches(svc.spec.selector, workload.pod_labels)
    ]
    matched_service_names = {svc.metadata.name for svc in matched_services}
    matched_ingresses = [
        ing for ing in ingresses if _ingress_targets_services(ing, matched_service_names)
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
        ingresses=[_build_ingress(ing) for ing in matched_ingresses],
        labels=workload.labels,
    )


def build_namespace_inventory(
    namespace: str,
    workloads: list[NormalizedWorkload],
    services: list[client.V1Service],
    ingresses: list[client.V1Ingress],
    pvcs: list[client.V1PersistentVolumeClaim],
) -> NamespaceInventory:
    apps = [build_app(workload, services, ingresses, pvcs) for workload in workloads]
    return NamespaceInventory(name=namespace, apps=apps)


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
        namespace_inventories.append(
            build_namespace_inventory(namespace, workloads, services, ingresses, pvcs)
        )

    return ClusterInventory(
        cluster_name=cluster_name,
        collected_at=datetime.now(UTC).isoformat(),
        namespaces=namespace_inventories,
    )

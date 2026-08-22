"""build_app/build_namespace_inventory, tested against NormalizedWorkload
directly since the association logic is kind-agnostic. Adapter normalization
itself is covered in test_workloads.py.
"""

from __future__ import annotations

from autodoc_core.models import Container
from kubernetes import client

from autodoc_collector.collect import build_app, build_namespace_inventory
from autodoc_collector.workloads import NormalizedWorkload


def _workload(
    name: str = "web",
    kind: str = "Deployment",
    pod_labels: dict[str, str] | None = None,
    claim_names: frozenset[str] = frozenset(),
) -> NormalizedWorkload:
    return NormalizedWorkload(
        kind=kind,
        name=name,
        replicas=2,
        ready_replicas=2,
        pod_labels=pod_labels or {"app": name},
        containers=[Container(name=name, image=f"{name}:1.0", ports=[8080])],
        claim_names=claim_names,
        labels={},
    )


def _service(name: str, selector: dict[str, str], port: int = 80) -> client.V1Service:
    return client.V1Service(
        metadata=client.V1ObjectMeta(name=name),
        spec=client.V1ServiceSpec(
            type="ClusterIP",
            cluster_ip="10.0.0.1",
            selector=selector,
            ports=[client.V1ServicePort(port=port, target_port=8080, protocol="TCP", name="http")],
        ),
    )


def _ingress(name: str, service_name: str, host: str = "app.example.com") -> client.V1Ingress:
    return client.V1Ingress(
        metadata=client.V1ObjectMeta(name=name),
        spec=client.V1IngressSpec(
            rules=[
                client.V1IngressRule(
                    host=host,
                    http=client.V1HTTPIngressRuleValue(
                        paths=[
                            client.V1HTTPIngressPath(
                                path="/",
                                path_type="Prefix",
                                backend=client.V1IngressBackend(
                                    service=client.V1IngressServiceBackend(
                                        name=service_name,
                                        port=client.V1ServiceBackendPort(number=80),
                                    )
                                ),
                            )
                        ]
                    ),
                )
            ],
            tls=[client.V1IngressTLS(hosts=[host])],
        ),
    )


def _pvc(name: str, size: str = "1Gi") -> client.V1PersistentVolumeClaim:
    return client.V1PersistentVolumeClaim(
        metadata=client.V1ObjectMeta(name=name),
        spec=client.V1PersistentVolumeClaimSpec(
            storage_class_name="local-path", access_modes=["ReadWriteOnce"]
        ),
        status=client.V1PersistentVolumeClaimStatus(capacity={"storage": size}),
    )


def test_builds_app_with_matching_service_ingress_and_volume():
    workload = _workload(claim_names=frozenset({"web-data"}))
    service = _service("web-svc", selector={"app": "web"})
    ingress = _ingress("web-ingress", service_name="web-svc")
    pvc = _pvc("web-data")

    app = build_app(workload, [service], [ingress], [pvc])

    assert app.name == "web"
    assert app.kind == "Deployment"
    assert app.replicas == 2
    assert app.ready_replicas == 2
    assert app.containers == [Container(name="web", image="web:1.0", ports=[8080])]
    assert [s.name for s in app.services] == ["web-svc"]
    assert [i.name for i in app.ingresses] == ["web-ingress"]
    assert app.ingresses[0].rules[0].service_name == "web-svc"
    assert app.ingresses[0].tls_hosts == ["app.example.com"]
    assert [v.claim_name for v in app.volumes] == ["web-data"]
    assert app.volumes[0].capacity == "1Gi"


def test_service_with_non_matching_selector_is_excluded():
    workload = _workload()
    unrelated_service = _service("other-svc", selector={"app": "other"})

    app = build_app(workload, [unrelated_service], [], [])

    assert app.services == []


def test_ingress_not_targeting_app_service_is_excluded():
    workload = _workload()
    service = _service("web-svc", selector={"app": "web"})
    unrelated_ingress = _ingress("other-ingress", service_name="some-other-svc")

    app = build_app(workload, [service], [unrelated_ingress], [])

    assert app.ingresses == []


def test_multiple_workloads_of_different_kinds_produce_multiple_apps():
    deployment_workload = _workload(name="web", kind="Deployment")
    statefulset_workload = _workload(name="db", kind="StatefulSet")

    inventory = build_namespace_inventory(
        "demo", [deployment_workload, statefulset_workload], [], [], []
    )

    assert [(app.name, app.kind) for app in inventory.apps] == [
        ("web", "Deployment"),
        ("db", "StatefulSet"),
    ]

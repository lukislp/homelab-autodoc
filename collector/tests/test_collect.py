"""build_app/build_namespace_inventory, tested against NormalizedWorkload
directly since the association logic is kind-agnostic. Adapter normalization
itself is covered in test_workloads.py.
"""

from __future__ import annotations

import pytest
from autodoc_core.models import ConfigReference, Container
from kubernetes import client
from kubernetes.client.exceptions import ApiException

from autodoc_collector.collect import (
    _autoscaler_for_workload,
    _build_autoscaler,
    _build_network_policy,
    _build_node,
    _build_pdb,
    _list_hpas,
    _list_httproutes,
    _network_policy_matches_workload,
    _node_names_for_workload,
    _pdb_matches_workload,
    build_app,
    build_namespace_inventory,
)
from autodoc_collector.k8s_apis import K8sApis
from autodoc_collector.workloads import NormalizedWorkload


def _workload(
    name: str = "web",
    kind: str = "Deployment",
    pod_labels: dict[str, str] | None = None,
    claim_names: frozenset[str] = frozenset(),
    annotations: dict[str, str] | None = None,
    created_at: str | None = None,
    owners: list[str] | None = None,
    config_refs: frozenset[ConfigReference] = frozenset(),
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
        annotations=annotations or {},
        created_at=created_at,
        owners=owners or [],
        config_refs=config_refs,
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


def _httproute(name: str, service_name: str, hostnames: list[str], port: int = 8080) -> dict:
    return {
        "metadata": {"name": name},
        "spec": {
            "hostnames": hostnames,
            "rules": [
                {
                    "matches": [{"path": {"value": "/"}}],
                    "backendRefs": [{"name": service_name, "port": port}],
                }
            ],
        },
    }


def _pod(node_name: str | None, labels: dict[str, str] | None = None) -> client.V1Pod:
    return client.V1Pod(
        metadata=client.V1ObjectMeta(labels=labels or {"app": "web"}),
        spec=client.V1PodSpec(node_name=node_name, containers=[]),
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


def test_builds_app_with_matching_httproute():
    workload = _workload()
    service = _service("web-svc", selector={"app": "web"})
    route = _httproute(
        "web-route", service_name="web-svc", hostnames=["web.heim.lan", "web.example.com"]
    )

    app = build_app(workload, [service], [], [], httproutes=[route])

    assert [i.name for i in app.ingresses] == ["web-route"]
    hosts = sorted({rule.host for rule in app.ingresses[0].rules})
    assert hosts == ["web.example.com", "web.heim.lan"]
    assert all(rule.service_name == "web-svc" for rule in app.ingresses[0].rules)
    assert all(rule.service_port == "8080" for rule in app.ingresses[0].rules)
    # HTTPRoute doesn't declare TLS itself - that's on the Gateway's listeners.
    assert app.ingresses[0].tls_hosts == []


def test_httproute_and_classic_ingress_can_coexist_on_the_same_app():
    workload = _workload()
    service = _service("web-svc", selector={"app": "web"})
    ingress = _ingress("web-ingress", service_name="web-svc")
    route = _httproute("web-route", service_name="web-svc", hostnames=["web.heim.lan"])

    app = build_app(workload, [service], [ingress], [], httproutes=[route])

    assert sorted(i.name for i in app.ingresses) == ["web-ingress", "web-route"]


def test_httproute_not_targeting_app_service_is_excluded():
    workload = _workload()
    service = _service("web-svc", selector={"app": "web"})
    unrelated_route = _httproute(
        "other-route", service_name="some-other-svc", hostnames=["other.heim.lan"]
    )

    app = build_app(workload, [service], [], [], httproutes=[unrelated_route])

    assert app.ingresses == []


def test_list_httproutes_returns_empty_when_gateway_api_crd_is_missing():
    class FakeCustomObjects:
        def list_namespaced_custom_object(self, **kwargs):
            raise ApiException(status=404)

    apis = K8sApis(
        core_v1=None,
        apps_v1=None,
        networking_v1=None,
        batch_v1=None,
        custom_objects=FakeCustomObjects(),
        autoscaling_v2=None,
        policy_v1=None,
    )

    assert _list_httproutes(apis, "demo") == []


def test_list_httproutes_reraises_non_404_errors():
    class FakeCustomObjects:
        def list_namespaced_custom_object(self, **kwargs):
            raise ApiException(status=403)

    apis = K8sApis(
        core_v1=None,
        apps_v1=None,
        networking_v1=None,
        batch_v1=None,
        custom_objects=FakeCustomObjects(),
        autoscaling_v2=None,
        policy_v1=None,
    )

    with pytest.raises(ApiException):
        _list_httproutes(apis, "demo")


def test_builds_app_with_metadata_and_config_refs():
    workload = _workload(
        annotations={"kustomize.toolkit.fluxcd.io/name": "web-deploy"},
        created_at="2026-08-01T12:00:00+00:00",
        owners=["ReplicaSet/web-abc"],
        config_refs=frozenset({ConfigReference(kind="Secret", name="web-secrets", via="env")}),
    )

    app = build_app(workload, [], [], [])

    assert app.annotations == {"kustomize.toolkit.fluxcd.io/name": "web-deploy"}
    assert app.created_at == "2026-08-01T12:00:00+00:00"
    assert app.owners == ["ReplicaSet/web-abc"]
    assert app.config_refs == [ConfigReference(kind="Secret", name="web-secrets", via="env")]


def _hpa(
    target_kind: str,
    target_name: str,
    min_replicas: int = 2,
    max_replicas: int = 5,
    cpu_percent: int | None = 70,
    memory_percent: int | None = None,
) -> client.V2HorizontalPodAutoscaler:
    metrics = []
    if cpu_percent is not None:
        metrics.append(
            client.V2MetricSpec(
                type="Resource",
                resource=client.V2ResourceMetricSource(
                    name="cpu",
                    target=client.V2MetricTarget(
                        type="Utilization", average_utilization=cpu_percent
                    ),
                ),
            )
        )
    if memory_percent is not None:
        metrics.append(
            client.V2MetricSpec(
                type="Resource",
                resource=client.V2ResourceMetricSource(
                    name="memory",
                    target=client.V2MetricTarget(
                        type="Utilization", average_utilization=memory_percent
                    ),
                ),
            )
        )
    return client.V2HorizontalPodAutoscaler(
        metadata=client.V1ObjectMeta(name=f"{target_name}-hpa"),
        spec=client.V2HorizontalPodAutoscalerSpec(
            scale_target_ref=client.V2CrossVersionObjectReference(
                kind=target_kind, name=target_name
            ),
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            metrics=metrics,
        ),
    )


def test_build_autoscaler_reads_cpu_and_memory_targets():
    hpa = _hpa(
        "Deployment", "web", min_replicas=2, max_replicas=5, cpu_percent=70, memory_percent=80
    )

    autoscaler = _build_autoscaler(hpa)

    assert autoscaler.min_replicas == 2
    assert autoscaler.max_replicas == 5
    assert autoscaler.target_cpu_percent == 70
    assert autoscaler.target_memory_percent == 80


def test_build_autoscaler_defaults_min_replicas_to_one_when_unset():
    hpa = _hpa("Deployment", "web", min_replicas=None, cpu_percent=None)

    autoscaler = _build_autoscaler(hpa)

    assert autoscaler.min_replicas == 1
    assert autoscaler.target_cpu_percent is None
    assert autoscaler.target_memory_percent is None


def test_autoscaler_for_workload_matches_by_kind_and_name():
    workload = _workload(name="web", kind="Deployment")
    matching_hpa = _hpa("Deployment", "web")
    other_hpa = _hpa("Deployment", "other")

    autoscaler = _autoscaler_for_workload([other_hpa, matching_hpa], workload)

    assert autoscaler is not None
    assert autoscaler.max_replicas == 5


def test_autoscaler_for_workload_returns_none_when_no_hpa_targets_it():
    workload = _workload(name="web", kind="Deployment")

    autoscaler = _autoscaler_for_workload([_hpa("Deployment", "other")], workload)

    assert autoscaler is None


def test_build_app_wires_matching_autoscaler():
    workload = _workload(name="web", kind="Deployment")

    app = build_app(workload, [], [], [], hpas=[_hpa("Deployment", "web")])

    assert app.autoscaler is not None
    assert app.autoscaler.min_replicas == 2
    assert app.autoscaler.max_replicas == 5


def test_build_app_without_hpas_leaves_autoscaler_none():
    workload = _workload()

    app = build_app(workload, [], [], [])

    assert app.autoscaler is None


class _FakeAutoscalingV2Api:
    def __init__(self, exception: ApiException | None = None):
        self._exception = exception

    def list_namespaced_horizontal_pod_autoscaler(self, namespace: str):
        if self._exception:
            raise self._exception
        return client.V2HorizontalPodAutoscalerList(items=[_hpa("Deployment", "web")])


class _FakeApis:
    def __init__(self, autoscaling_v2):
        self.autoscaling_v2 = autoscaling_v2


def test_list_hpas_returns_empty_when_autoscaling_v2_is_missing():
    apis = _FakeApis(_FakeAutoscalingV2Api(ApiException(status=404)))

    assert _list_hpas(apis, "demo") == []


def test_list_hpas_reraises_non_404_errors():
    apis = _FakeApis(_FakeAutoscalingV2Api(ApiException(status=500)))

    with pytest.raises(ApiException):
        _list_hpas(apis, "demo")


def test_list_hpas_returns_items_on_success():
    apis = _FakeApis(_FakeAutoscalingV2Api())

    hpas = _list_hpas(apis, "demo")

    assert [h.spec.scale_target_ref.name for h in hpas] == ["web"]


def test_node_names_for_workload_matches_pods_by_label_subset():
    workload = _workload(name="web", pod_labels={"app": "web"})
    matching_pod = _pod("node-1", labels={"app": "web", "pod-template-hash": "abc"})
    other_pod = _pod("node-2", labels={"app": "other"})

    nodes = _node_names_for_workload([matching_pod, other_pod], workload)

    assert nodes == ["node-1"]


def test_node_names_for_workload_dedupes_and_sorts():
    workload = _workload(name="web", pod_labels={"app": "web"})
    pods = [
        _pod("node-2", labels={"app": "web"}),
        _pod("node-1", labels={"app": "web"}),
        _pod("node-1", labels={"app": "web"}),
    ]

    nodes = _node_names_for_workload(pods, workload)

    assert nodes == ["node-1", "node-2"]


def test_node_names_for_workload_skips_unscheduled_pods():
    workload = _workload(name="web", pod_labels={"app": "web"})
    pending_pod = _pod(None, labels={"app": "web"})

    nodes = _node_names_for_workload([pending_pod], workload)

    assert nodes == []


def test_build_app_wires_matching_node_names():
    workload = _workload(name="web", pod_labels={"app": "web"})

    app = build_app(workload, [], [], [], pods=[_pod("node-1", labels={"app": "web"})])

    assert app.nodes == ["node-1"]


def test_build_app_without_pods_leaves_nodes_empty():
    workload = _workload()

    app = build_app(workload, [], [], [])

    assert app.nodes == []


def _network_policy(
    name: str,
    pod_selector_labels: dict[str, str] | None = None,
    pod_selector_expressions: list[client.V1LabelSelectorRequirement] | None = None,
    policy_types: list[str] | None = None,
    ingress: list[client.V1NetworkPolicyIngressRule] | None = None,
    egress: list[client.V1NetworkPolicyEgressRule] | None = None,
) -> client.V1NetworkPolicy:
    return client.V1NetworkPolicy(
        metadata=client.V1ObjectMeta(name=name),
        spec=client.V1NetworkPolicySpec(
            pod_selector=client.V1LabelSelector(
                match_labels=pod_selector_labels, match_expressions=pod_selector_expressions
            ),
            policy_types=policy_types,
            ingress=ingress,
            egress=egress,
        ),
    )


def test_network_policy_matches_workload_by_pod_selector_labels():
    workload = _workload(name="web", pod_labels={"app": "web"})
    policy = _network_policy("allow-web", pod_selector_labels={"app": "web"})

    assert _network_policy_matches_workload(policy, workload) is True


def test_network_policy_with_non_matching_selector_is_excluded():
    workload = _workload(name="web", pod_labels={"app": "web"})
    policy = _network_policy("allow-other", pod_selector_labels={"app": "other"})

    assert _network_policy_matches_workload(policy, workload) is False


def test_network_policy_with_empty_pod_selector_matches_every_workload():
    workload = _workload(name="web", pod_labels={"app": "web"})
    policy = _network_policy("deny-all")

    assert _network_policy_matches_workload(policy, workload) is True


def test_network_policy_with_match_expressions_is_not_evaluated():
    workload = _workload(name="web", pod_labels={"app": "web"})
    policy = _network_policy(
        "allow-expr",
        pod_selector_expressions=[
            client.V1LabelSelectorRequirement(key="app", operator="In", values=["web"])
        ],
    )

    assert _network_policy_matches_workload(policy, workload) is False


def test_build_network_policy_describes_pod_namespace_and_ip_block_peers():
    policy = _network_policy(
        "allow-web",
        pod_selector_labels={"app": "web"},
        policy_types=["Ingress", "Egress"],
        ingress=[
            client.V1NetworkPolicyIngressRule(
                _from=[
                    client.V1NetworkPolicyPeer(
                        pod_selector=client.V1LabelSelector(match_labels={"app": "traefik"})
                    ),
                    client.V1NetworkPolicyPeer(
                        namespace_selector=client.V1LabelSelector(
                            match_labels={"kubernetes.io/metadata.name": "monitoring"}
                        )
                    ),
                    client.V1NetworkPolicyPeer(ip_block=client.V1IPBlock(cidr="10.0.0.0/8")),
                ],
                ports=[client.V1NetworkPolicyPort(protocol="TCP", port=8080)],
            )
        ],
        egress=[client.V1NetworkPolicyEgressRule(to=[])],
    )

    info = _build_network_policy(policy)

    assert info.name == "allow-web"
    assert info.policy_types == ["Ingress", "Egress"]
    assert info.ingress[0].peers == [
        "pods:app=traefik",
        "namespaces:kubernetes.io/metadata.name=monitoring",
        "ipBlock:10.0.0.0/8",
    ]
    assert info.ingress[0].ports == ["TCP/8080"]
    assert info.egress[0].peers == []  # empty `to` list means "all destinations"


def test_build_app_wires_matching_network_policies():
    workload = _workload(name="web", pod_labels={"app": "web"})
    matching_policy = _network_policy("allow-web", pod_selector_labels={"app": "web"})
    other_policy = _network_policy("allow-other", pod_selector_labels={"app": "other"})

    app = build_app(workload, [], [], [], network_policies=[matching_policy, other_policy])

    assert [np.name for np in app.network_policies] == ["allow-web"]


def test_build_app_without_network_policies_leaves_list_empty():
    workload = _workload()

    app = build_app(workload, [], [], [])

    assert app.network_policies == []


def _pdb(
    name: str,
    selector_labels: dict[str, str] | None = None,
    selector_expressions: list[client.V1LabelSelectorRequirement] | None = None,
    min_available: object | None = None,
    max_unavailable: object | None = None,
    no_selector: bool = False,
) -> client.V1PodDisruptionBudget:
    selector = None
    if not no_selector:
        selector = client.V1LabelSelector(
            match_labels=selector_labels, match_expressions=selector_expressions
        )
    return client.V1PodDisruptionBudget(
        metadata=client.V1ObjectMeta(name=name),
        spec=client.V1PodDisruptionBudgetSpec(
            selector=selector, min_available=min_available, max_unavailable=max_unavailable
        ),
    )


def _node(
    name: str = "pi-node-1",
    architecture: str = "arm64",
    kubelet_version: str = "v1.31.2+k3s1",
    os_image: str = "Debian GNU/Linux 12 (bookworm)",
    capacity: dict[str, str] | None = None,
    allocatable: dict[str, str] | None = None,
    ready: bool = True,
) -> client.V1Node:
    return client.V1Node(
        metadata=client.V1ObjectMeta(name=name),
        status=client.V1NodeStatus(
            node_info=client.V1NodeSystemInfo(
                architecture=architecture,
                boot_id="boot-1",
                container_runtime_version="containerd://1.7.0",
                kernel_version="6.6.0",
                kube_proxy_version=kubelet_version,
                kubelet_version=kubelet_version,
                machine_id="machine-1",
                operating_system="linux",
                os_image=os_image,
                system_uuid="uuid-1",
            ),
            capacity=capacity or {"cpu": "4", "memory": "8065700Ki"},
            allocatable=allocatable or {"cpu": "3900m", "memory": "7500000Ki"},
            conditions=[client.V1NodeCondition(type="Ready", status="True" if ready else "False")],
        ),
    )


def test_build_pdb_reads_min_available():
    pdb = _pdb("web-pdb", selector_labels={"app": "web"}, min_available=1)

    info = _build_pdb(pdb)

    assert info.name == "web-pdb"
    assert info.min_available == "1"
    assert info.max_unavailable is None


def test_build_pdb_reads_max_unavailable_percentage():
    pdb = _pdb("web-pdb", selector_labels={"app": "web"}, max_unavailable="50%")

    info = _build_pdb(pdb)

    assert info.max_unavailable == "50%"
    assert info.min_available is None


def test_pdb_matches_workload_by_selector_labels():
    workload = _workload(name="web", pod_labels={"app": "web"})
    pdb = _pdb("web-pdb", selector_labels={"app": "web"})

    assert _pdb_matches_workload(pdb, workload) is True


def test_pdb_with_non_matching_selector_is_excluded():
    workload = _workload(name="web", pod_labels={"app": "web"})
    pdb = _pdb("other-pdb", selector_labels={"app": "other"})

    assert _pdb_matches_workload(pdb, workload) is False


def test_pdb_with_empty_selector_matches_every_workload():
    workload = _workload(name="web", pod_labels={"app": "web"})
    pdb = _pdb("blanket-pdb", selector_labels=None)

    assert _pdb_matches_workload(pdb, workload) is True


def test_pdb_with_null_selector_matches_no_workload():
    workload = _workload(name="web", pod_labels={"app": "web"})
    pdb = _pdb("no-selector-pdb", no_selector=True)

    assert _pdb_matches_workload(pdb, workload) is False


def test_pdb_with_match_expressions_is_not_evaluated():
    workload = _workload(name="web", pod_labels={"app": "web"})
    pdb = _pdb(
        "expr-pdb",
        selector_expressions=[
            client.V1LabelSelectorRequirement(key="app", operator="In", values=["web"])
        ],
    )

    assert _pdb_matches_workload(pdb, workload) is False


def test_build_app_wires_matching_pdbs():
    workload = _workload(name="web", pod_labels={"app": "web"})
    matching_pdb = _pdb("web-pdb", selector_labels={"app": "web"}, min_available=1)
    other_pdb = _pdb("other-pdb", selector_labels={"app": "other"})

    app = build_app(workload, [], [], [], pdbs=[matching_pdb, other_pdb])

    assert [pdb.name for pdb in app.pod_disruption_budgets] == ["web-pdb"]


def test_build_app_without_pdbs_leaves_list_empty():
    workload = _workload()

    app = build_app(workload, [], [], [])

    assert app.pod_disruption_budgets == []


def test_build_node_extracts_spec_and_capacity():
    node = _node(name="pi-node-1", ready=True)

    info = _build_node(node)

    assert info.name == "pi-node-1"
    assert info.architecture == "arm64"
    assert info.kubelet_version == "v1.31.2+k3s1"
    assert info.os_image == "Debian GNU/Linux 12 (bookworm)"
    assert info.capacity_cpu == "4"
    assert info.capacity_memory == "8065700Ki"
    assert info.allocatable_cpu == "3900m"
    assert info.allocatable_memory == "7500000Ki"
    assert info.ready is True


def test_build_node_not_ready_when_ready_condition_is_false():
    node = _node(ready=False)

    info = _build_node(node)

    assert info.ready is False


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

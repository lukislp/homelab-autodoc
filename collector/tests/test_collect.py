"""build_app/build_namespace_inventory, tested against NormalizedWorkload
directly since the association logic is kind-agnostic. Adapter normalization
itself is covered in test_workloads.py.
"""

from __future__ import annotations

import pytest
from autodoc_core.models import ConfigReference, Container, EnvVar, RolloutStrategyInfo
from kubernetes import client
from kubernetes.client.exceptions import ApiException

from autodoc_collector.collect import (
    _autoscaler_for_workload,
    _build_autoscaler,
    _build_limit_range,
    _build_limit_range_item,
    _build_network_policy,
    _build_node,
    _build_pdb,
    _build_resource_quota,
    _build_storage_class,
    _build_warning_event,
    _list_configmaps,
    _list_hpas,
    _list_httproutes,
    _list_warning_events,
    _network_policy_matches_workload,
    _node_names_for_workload,
    _pdb_matches_workload,
    _service_account_role_bindings,
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
    template_annotations: dict[str, str] | None = None,
    created_at: str | None = None,
    owners: list[str] | None = None,
    config_refs: frozenset[ConfigReference] = frozenset(),
    service_account_name: str | None = None,
    node_selector: dict[str, str] | None = None,
    node_affinity: list[str] | None = None,
    tolerations: list[str] | None = None,
    rollout_strategy: RolloutStrategyInfo | None = None,
    image_pull_secrets: frozenset[str] = frozenset(),
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
        template_annotations=template_annotations or {},
        created_at=created_at,
        owners=owners or [],
        config_refs=config_refs,
        service_account_name=service_account_name,
        node_selector=node_selector or {},
        node_affinity=node_affinity or [],
        tolerations=tolerations or [],
        rollout_strategy=rollout_strategy,
        image_pull_secrets=image_pull_secrets,
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
        storage_v1=None,
        rbac_v1=None,
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
        storage_v1=None,
        rbac_v1=None,
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


def test_build_storage_class_extracts_provisioner_and_policy():
    raw = client.V1StorageClass(
        metadata=client.V1ObjectMeta(name="local-path"),
        provisioner="rancher.io/local-path",
        reclaim_policy="Delete",
        volume_binding_mode="WaitForFirstConsumer",
        allow_volume_expansion=False,
    )

    info = _build_storage_class(raw)

    assert info.name == "local-path"
    assert info.provisioner == "rancher.io/local-path"
    assert info.reclaim_policy == "Delete"
    assert info.volume_binding_mode == "WaitForFirstConsumer"
    assert info.allow_volume_expansion is False


def test_build_app_copies_scheduling_constraints_from_workload():
    workload = _workload(
        node_selector={"kubernetes.io/arch": "arm64"},
        node_affinity=["required: kubernetes.io/arch In (arm64)"],
        tolerations=["node-role.kubernetes.io/master Exists:NoSchedule"],
    )

    app = build_app(workload, [], [], [])

    assert app.node_selector == {"kubernetes.io/arch": "arm64"}
    assert app.node_affinity == ["required: kubernetes.io/arch In (arm64)"]
    assert app.tolerations == ["node-role.kubernetes.io/master Exists:NoSchedule"]


def test_build_app_without_scheduling_constraints_leaves_empty_defaults():
    workload = _workload()

    app = build_app(workload, [], [], [])

    assert app.node_selector == {}
    assert app.node_affinity == []
    assert app.tolerations == []


def _sa_subject(name: str, namespace: str | None = None) -> client.RbacV1Subject:
    return client.RbacV1Subject(kind="ServiceAccount", name=name, namespace=namespace)


def _role_binding(
    name: str, role_kind: str, role_name: str, subjects: list[client.RbacV1Subject]
) -> client.V1RoleBinding:
    return client.V1RoleBinding(
        metadata=client.V1ObjectMeta(name=name),
        role_ref=client.V1RoleRef(
            api_group="rbac.authorization.k8s.io", kind=role_kind, name=role_name
        ),
        subjects=subjects,
    )


def _cluster_role_binding(
    name: str, role_name: str, subjects: list[client.RbacV1Subject]
) -> client.V1ClusterRoleBinding:
    return client.V1ClusterRoleBinding(
        metadata=client.V1ObjectMeta(name=name),
        role_ref=client.V1RoleRef(
            api_group="rbac.authorization.k8s.io", kind="ClusterRole", name=role_name
        ),
        subjects=subjects,
    )


def test_service_account_role_bindings_matches_role_binding_with_explicit_namespace():
    rb = _role_binding("web-view", "Role", "view", [_sa_subject("web-sa", namespace="demo")])

    result = _service_account_role_bindings([rb], [], "demo")

    assert [b.name for b in result["web-sa"]] == ["web-view"]
    assert result["web-sa"][0].role_kind == "Role"
    assert result["web-sa"][0].role_name == "view"


def test_service_account_role_bindings_matches_role_binding_without_namespace():
    rb = _role_binding("web-view", "Role", "view", [_sa_subject("web-sa", namespace=None)])

    result = _service_account_role_bindings([rb], [], "demo")

    assert "web-sa" in result


def test_service_account_role_bindings_ignores_role_binding_subject_in_other_namespace():
    rb = _role_binding("web-view", "Role", "view", [_sa_subject("web-sa", namespace="other")])

    result = _service_account_role_bindings([rb], [], "demo")

    assert result == {}


def test_service_account_role_bindings_matches_cluster_role_binding_with_explicit_namespace():
    crb = _cluster_role_binding(
        "web-admin", "cluster-admin", [_sa_subject("web-sa", namespace="demo")]
    )

    result = _service_account_role_bindings([], [crb], "demo")

    assert [b.name for b in result["web-sa"]] == ["web-admin"]
    assert result["web-sa"][0].role_kind == "ClusterRole"


def test_service_account_role_bindings_ignores_cluster_role_binding_without_namespace():
    crb = _cluster_role_binding(
        "web-admin", "cluster-admin", [_sa_subject("web-sa", namespace=None)]
    )

    result = _service_account_role_bindings([], [crb], "demo")

    assert result == {}


def test_service_account_role_bindings_ignores_non_service_account_subjects():
    user_subject = client.RbacV1Subject(kind="User", name="alice")
    rb = _role_binding("alice-view", "Role", "view", [user_subject])

    result = _service_account_role_bindings([rb], [], "demo")

    assert result == {}


def test_build_app_wires_matching_service_account():
    workload = _workload(name="web", service_account_name="web-sa")
    rb = _role_binding("web-view", "Role", "view", [_sa_subject("web-sa", namespace="demo")])
    bindings_by_sa = _service_account_role_bindings([rb], [], "demo")

    app = build_app(workload, [], [], [], service_account_role_bindings=bindings_by_sa)

    assert app.service_account is not None
    assert app.service_account.name == "web-sa"
    assert [b.name for b in app.service_account.role_bindings] == ["web-view"]


def test_build_app_without_service_account_name_leaves_service_account_none():
    workload = _workload()

    app = build_app(workload, [], [], [])

    assert app.service_account is None


def test_build_app_service_account_with_no_matching_bindings_has_empty_list():
    workload = _workload(name="web", service_account_name="web-sa")

    app = build_app(workload, [], [], [])

    assert app.service_account is not None
    assert app.service_account.name == "web-sa"
    assert app.service_account.role_bindings == []


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


def test_build_app_copies_rollout_strategy_from_workload():
    strategy = RolloutStrategyInfo(strategy_type="RollingUpdate", max_surge="25%")
    workload = _workload(rollout_strategy=strategy)

    app = build_app(workload, [], [], [])

    assert app.rollout_strategy == strategy


def test_build_app_without_rollout_strategy_leaves_it_none():
    workload = _workload()

    app = build_app(workload, [], [], [])

    assert app.rollout_strategy is None


def test_build_app_copies_image_pull_secrets_from_workload():
    workload = _workload(image_pull_secrets=frozenset({"ghcr-pull-secret"}))

    app = build_app(workload, [], [], [])

    assert app.image_pull_secrets == ["ghcr-pull-secret"]


def test_build_app_without_image_pull_secrets_leaves_list_empty():
    workload = _workload()

    app = build_app(workload, [], [], [])

    assert app.image_pull_secrets == []


def _resource_quota(
    name: str = "demo-quota",
    hard: dict[str, str] | None = None,
    used: dict[str, str] | None = None,
) -> client.V1ResourceQuota:
    return client.V1ResourceQuota(
        metadata=client.V1ObjectMeta(name=name),
        spec=client.V1ResourceQuotaSpec(hard=hard or {"requests.cpu": "4", "pods": "20"}),
        status=client.V1ResourceQuotaStatus(
            hard=hard or {"requests.cpu": "4", "pods": "20"},
            used=used or {"requests.cpu": "1500m", "pods": "6"},
        ),
    )


def _limit_range(name: str = "demo-limits") -> client.V1LimitRange:
    return client.V1LimitRange(
        metadata=client.V1ObjectMeta(name=name),
        spec=client.V1LimitRangeSpec(
            limits=[
                client.V1LimitRangeItem(
                    type="Container",
                    default={"cpu": "500m", "memory": "256Mi"},
                    default_request={"cpu": "100m", "memory": "128Mi"},
                )
            ]
        ),
    )


def test_build_resource_quota_reads_hard_and_used_from_status():
    quota = _resource_quota(
        hard={"requests.cpu": "4", "pods": "20"}, used={"requests.cpu": "1500m", "pods": "6"}
    )

    info = _build_resource_quota(quota)

    assert info.name == "demo-quota"
    assert info.hard == {"requests.cpu": "4", "pods": "20"}
    assert info.used == {"requests.cpu": "1500m", "pods": "6"}


def test_build_resource_quota_falls_back_to_spec_hard_when_status_missing():
    quota = client.V1ResourceQuota(
        metadata=client.V1ObjectMeta(name="demo-quota"),
        spec=client.V1ResourceQuotaSpec(hard={"pods": "20"}),
        status=None,
    )

    info = _build_resource_quota(quota)

    assert info.hard == {"pods": "20"}
    assert info.used == {}


def test_build_limit_range_item_reads_min_max_default():
    item = client.V1LimitRangeItem(
        type="Container",
        min={"cpu": "50m"},
        max={"cpu": "2"},
        default={"cpu": "500m", "memory": "256Mi"},
        default_request={"cpu": "100m", "memory": "128Mi"},
    )

    info = _build_limit_range_item(item)

    assert info.kind == "Container"
    assert info.min == {"cpu": "50m"}
    assert info.max == {"cpu": "2"}
    assert info.default == {"cpu": "500m", "memory": "256Mi"}
    assert info.default_request == {"cpu": "100m", "memory": "128Mi"}


def test_build_limit_range_collects_its_items():
    limit_range = _limit_range()

    info = _build_limit_range(limit_range)

    assert info.name == "demo-limits"
    assert [item.kind for item in info.limits] == ["Container"]


def test_build_namespace_inventory_wires_resource_quotas_and_limit_ranges():
    workload = _workload()

    inventory = build_namespace_inventory(
        "demo",
        [workload],
        [],
        [],
        [],
        resource_quotas=[_resource_quota()],
        limit_ranges=[_limit_range()],
    )

    assert [rq.name for rq in inventory.resource_quotas] == ["demo-quota"]
    assert [lr.name for lr in inventory.limit_ranges] == ["demo-limits"]


def test_build_namespace_inventory_without_quotas_or_limit_ranges_leaves_lists_empty():
    workload = _workload()

    inventory = build_namespace_inventory("demo", [workload], [], [], [])

    assert inventory.resource_quotas == []
    assert inventory.limit_ranges == []


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


class _FakeCoreV1ConfigMaps:
    def __init__(self, names: list[str] | None = None, exception: ApiException | None = None):
        self._names = names or []
        self._exception = exception

    def list_namespaced_config_map(self, namespace: str):
        if self._exception:
            raise self._exception
        items = [
            client.V1ConfigMap(metadata=client.V1ObjectMeta(name=name)) for name in self._names
        ]
        return client.V1ConfigMapList(items=items)


class _FakeApisWithCoreV1:
    def __init__(self, core_v1):
        self.core_v1 = core_v1


def test_list_configmaps_returns_the_items():
    apis = _FakeApisWithCoreV1(_FakeCoreV1ConfigMaps(names=["zeta", "alpha"]))

    items = _list_configmaps(apis, "demo")

    assert sorted(cm.metadata.name for cm in items) == ["alpha", "zeta"]


def test_list_configmaps_returns_none_when_rbac_denies():
    # The ClusterRole may predate the configmaps grant - "unknown" (None)
    # must stay distinguishable from "there are none" ([]).
    apis = _FakeApisWithCoreV1(_FakeCoreV1ConfigMaps(exception=ApiException(status=403)))

    assert _list_configmaps(apis, "demo") is None


def test_list_configmaps_reraises_non_403_errors():
    apis = _FakeApisWithCoreV1(_FakeCoreV1ConfigMaps(exception=ApiException(status=500)))

    with pytest.raises(ApiException):
        _list_configmaps(apis, "demo")


def test_build_namespace_inventory_wires_configmap_names():
    inventory = build_namespace_inventory(
        "demo", [_workload()], [], [], [], configmap_names=["app-config"]
    )

    assert inventory.configmap_names == ["app-config"]


def test_build_namespace_inventory_keeps_uncollected_configmap_names_none():
    inventory = build_namespace_inventory("demo", [_workload()], [], [], [])

    assert inventory.configmap_names is None


def _event(
    reason: str = "BackOff",
    last_timestamp=None,
    event_time=None,
    creation=None,
    count: int | None = 3,
) -> client.CoreV1Event:
    return client.CoreV1Event(
        metadata=client.V1ObjectMeta(name="evt", creation_timestamp=creation),
        involved_object=client.V1ObjectReference(kind="Pod", name="web-abc"),
        reason=reason,
        message="Back-off restarting failed container",
        count=count,
        last_timestamp=last_timestamp,
        event_time=event_time,
    )


class _FakeCoreV1Events:
    def __init__(self, events=None, exception: ApiException | None = None):
        self._events = events or []
        self._exception = exception
        self.received_field_selector: str | None = None

    def list_namespaced_event(self, namespace: str, field_selector: str | None = None):
        if self._exception:
            raise self._exception
        self.received_field_selector = field_selector
        return client.CoreV1EventList(items=self._events)


def test_build_warning_event_prefers_last_timestamp():
    from datetime import UTC, datetime

    event = _event(
        last_timestamp=datetime(2026, 8, 23, 1, 0, tzinfo=UTC),
        event_time=datetime(2026, 8, 23, 2, 0, tzinfo=UTC),
    )

    info = _build_warning_event(event)

    assert info.last_seen == "2026-08-23T01:00:00+00:00"
    assert info.reason == "BackOff"
    assert info.object_ref == "Pod/web-abc"
    assert info.count == 3


def test_build_warning_event_falls_back_to_creation_timestamp():
    from datetime import UTC, datetime

    event = _event(creation=datetime(2026, 8, 23, 3, 0, tzinfo=UTC))

    info = _build_warning_event(event)

    assert info.last_seen == "2026-08-23T03:00:00+00:00"


def test_build_warning_event_defaults_count_to_one():
    info = _build_warning_event(_event(count=None))

    assert info.count == 1


def test_list_warning_events_filters_sorts_and_caps():
    from datetime import UTC, datetime

    events = [
        _event(last_timestamp=datetime(2026, 8, 23, hour, 0, tzinfo=UTC)) for hour in range(23)
    ]
    core_v1 = _FakeCoreV1Events(events=events)

    result = _list_warning_events(_FakeApisWithCoreV1(core_v1), "demo")

    assert core_v1.received_field_selector == "type=Warning"
    assert len(result) == 20  # capped
    assert result[0].last_seen == "2026-08-23T22:00:00+00:00"  # newest first


def test_list_warning_events_returns_none_when_rbac_denies():
    apis = _FakeApisWithCoreV1(_FakeCoreV1Events(exception=ApiException(status=403)))

    assert _list_warning_events(apis, "demo") is None


def test_list_warning_events_reraises_non_403_errors():
    apis = _FakeApisWithCoreV1(_FakeCoreV1Events(exception=ApiException(status=500)))

    with pytest.raises(ApiException):
        _list_warning_events(apis, "demo")


def test_build_namespace_inventory_wires_warning_events():
    from autodoc_core.models import WarningEventInfo

    event = WarningEventInfo(reason="BackOff", object_ref="Pod/x", message="m", count=1)

    inventory = build_namespace_inventory("demo", [_workload()], [], [], [], warning_events=[event])

    assert inventory.warning_events == [event]


def test_build_namespace_inventory_keeps_uncollected_warning_events_none():
    inventory = build_namespace_inventory("demo", [_workload()], [], [], [])

    assert inventory.warning_events is None


def test_describe_peer_keeps_both_namespace_and_pod_selector_halves():
    # The generator's network module parses this exact string contract - a
    # combined peer ("prometheus pods in the monitoring namespace") must keep
    # both halves, joined with "+".
    peer = client.V1NetworkPolicyPeer(
        namespace_selector=client.V1LabelSelector(
            match_labels={"kubernetes.io/metadata.name": "monitoring"}
        ),
        pod_selector=client.V1LabelSelector(match_labels={"app": "prometheus"}),
    )

    from autodoc_collector.collect import _describe_peer

    assert (
        _describe_peer(peer)
        == "namespaces:kubernetes.io/metadata.name=monitoring+pods:app=prometheus"
    )


def test_app_carries_the_pod_template_labels():
    workload = _workload(name="web", pod_labels={"app": "web", "tier": "frontend"})

    app = build_namespace_inventory("demo", [workload], [], [], []).apps[0]

    assert app.pod_labels == {"app": "web", "tier": "frontend"}


def test_backup_volumes_parsed_from_the_pod_template_annotation():
    workload = _workload(
        name="web",
        template_annotations={"backup.velero.io/backup-volumes": "data, config"},
    )

    app = build_namespace_inventory("demo", [workload], [], [], []).apps[0]

    assert app.backup_volumes == ["data", "config"]


def _refs(app):
    return {(r.service, r.namespace, r.port, r.via) for r in app.service_references}


def test_service_references_from_env_and_configmap_values():
    workload = _workload(
        name="web",
        config_refs=frozenset(
            {ConfigReference(kind="ConfigMap", name="web-config", via="envFrom")}
        ),
    )
    workload.containers[0].env.append(
        EnvVar(name="AI_URL", value="http://studylife-ai.studylife-ai.svc.cluster.local:8000")
    )
    configmap_data = {
        "web-config": {
            # headless StatefulSet pod DNS - must resolve to the redis service
            "Cache__ConnectionString": (
                "redis-cluster-0.redis-cluster:6380,redis-cluster-1.redis-cluster:6380"
            ),
            "Cache__Provider": "Redis",  # prose-like value - no false edge
        },
        "unrelated-config": {"OTHER": "postgres:5432"},  # not referenced by the app - ignored
    }
    services = [_service("redis-cluster", {"app": "redis"}), _service("postgres", {"app": "pg"})]

    app = build_app(workload, services, [], [], configmap_data=configmap_data)

    assert _refs(app) == {
        ("studylife-ai", "studylife-ai", 8000, "env AI_URL"),
        ("redis-cluster", None, 6380, "ConfigMap web-config/Cache__ConnectionString"),
    }


def test_bare_token_only_counts_when_it_matches_a_local_service():
    workload = _workload(name="web")
    workload.containers[0].env.append(EnvVar(name="DB_HOST", value="postgres"))
    workload.containers[0].env.append(EnvVar(name="MODE", value="production"))

    app = build_app(workload, [_service("postgres", {"app": "pg"})], [], [])

    assert _refs(app) == {("postgres", None, None, "env DB_HOST")}

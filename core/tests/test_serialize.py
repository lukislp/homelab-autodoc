from __future__ import annotations

import json

from autodoc_core.models import (
    App,
    Autoscaler,
    ClusterInventory,
    ConfigReference,
    Container,
    EnvVar,
    IngressInfo,
    IngressRule,
    NamespaceInventory,
    NetworkPolicyInfo,
    NetworkPolicyRule,
    NodeInfo,
    PodDisruptionBudgetInfo,
    ProbeInfo,
    RoleBindingInfo,
    RolloutStrategyInfo,
    ServiceAccountInfo,
    ServiceInfo,
    ServicePort,
    StorageClassInfo,
    Volume,
)
from autodoc_core.serialize import from_text, to_text


def _sample_inventory() -> ClusterInventory:
    return ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-22T00:00:00+00:00",
        namespaces=[
            NamespaceInventory(
                name="demo",
                apps=[
                    App(
                        name="web",
                        kind="Deployment",
                        replicas=2,
                        ready_replicas=2,
                        containers=[
                            Container(
                                name="init-migrate",
                                image="migrate:1.0",
                                is_init=True,
                            ),
                            Container(
                                name="web",
                                image="nginx:1.25.3",
                                ports=[8080],
                                resource_requests={"cpu": "100m", "memory": "128Mi"},
                                resource_limits={"cpu": "500m", "memory": "256Mi"},
                                env=[
                                    EnvVar(name="LOG_LEVEL", value="info"),
                                    EnvVar(
                                        name="API_KEY",
                                        value_from="Secret:web-secrets/API_KEY",
                                    ),
                                ],
                                probes=[
                                    ProbeInfo(
                                        kind="liveness",
                                        check="HTTP :8080/healthz",
                                        period_seconds=10,
                                    )
                                ],
                            ),
                        ],
                        volumes=[
                            Volume(
                                claim_name="web-data",
                                storage_class="local-path",
                                capacity="1Gi",
                                access_modes=["ReadWriteOnce"],
                            )
                        ],
                        services=[
                            ServiceInfo(
                                name="web-svc",
                                type="ClusterIP",
                                cluster_ip="10.0.0.1",
                                ports=[ServicePort(port=80, target_port="8080", protocol="TCP")],
                            )
                        ],
                        ingresses=[
                            IngressInfo(
                                name="web-ingress",
                                rules=[
                                    IngressRule(path="/", service_name="web-svc", service_port="80")
                                ],
                                tls_hosts=["app.example.com"],
                            )
                        ],
                        labels={"tier": "frontend"},
                        annotations={"kustomize.toolkit.fluxcd.io/name": "homelab-autodoc-deploy"},
                        created_at="2026-08-01T12:00:00+00:00",
                        owners=["ReplicaSet/web-abc123"],
                        config_refs=[
                            ConfigReference(kind="Secret", name="web-secrets", via="env"),
                            ConfigReference(kind="ConfigMap", name="web-config", via="volume"),
                        ],
                        autoscaler=Autoscaler(
                            min_replicas=2, max_replicas=5, target_cpu_percent=70
                        ),
                        nodes=["pi-node-1", "pi-node-2"],
                        network_policies=[
                            NetworkPolicyInfo(
                                name="web-allow-ingress",
                                policy_types=["Ingress"],
                                ingress=[
                                    NetworkPolicyRule(
                                        peers=["namespaces:kubernetes.io/metadata.name=traefik"],
                                        ports=["TCP/8080"],
                                    )
                                ],
                            )
                        ],
                        service_account=ServiceAccountInfo(
                            name="web-sa",
                            role_bindings=[
                                RoleBindingInfo(
                                    name="web-sa-reader", role_kind="ClusterRole", role_name="view"
                                )
                            ],
                        ),
                        pod_disruption_budgets=[
                            PodDisruptionBudgetInfo(name="web-pdb", min_available="1")
                        ],
                        node_selector={"kubernetes.io/arch": "arm64"},
                        node_affinity=["required: kubernetes.io/arch In (arm64)"],
                        tolerations=["node-role.kubernetes.io/master:NoSchedule"],
                        rollout_strategy=RolloutStrategyInfo(
                            strategy_type="RollingUpdate",
                            max_surge="25%",
                            max_unavailable="0",
                        ),
                        image_pull_secrets=["ghcr-pull-secret"],
                    )
                ],
            )
        ],
        storage_classes=[
            StorageClassInfo(
                name="local-path",
                provisioner="rancher.io/local-path",
                reclaim_policy="Delete",
                volume_binding_mode="WaitForFirstConsumer",
                allow_volume_expansion=False,
            )
        ],
        nodes=[
            NodeInfo(
                name="pi-node-1",
                architecture="arm64",
                kubelet_version="v1.31.2+k3s1",
                os_image="Debian GNU/Linux 12 (bookworm)",
                capacity_cpu="4",
                capacity_memory="8065700Ki",
                allocatable_cpu="3900m",
                allocatable_memory="7500000Ki",
                ready=True,
            )
        ],
    )


def test_to_text_json_round_trips():
    text = to_text(_sample_inventory(), fmt="json")
    data = json.loads(text)

    assert data["cluster_name"] == "homelab"
    assert data["namespaces"][0]["apps"][0]["containers"][1]["image"] == "nginx:1.25.3"


def test_to_text_json_compact_has_no_indentation():
    text = to_text(_sample_inventory(), fmt="json", pretty=False)

    assert "\n" not in text
    assert json.loads(text)["cluster_name"] == "homelab"


def test_to_text_yaml_round_trips():
    text = to_text(_sample_inventory(), fmt="yaml")
    data = from_text(text, fmt="yaml")

    assert data == _sample_inventory()


def test_from_text_json_reconstructs_full_dataclass_tree():
    original = _sample_inventory()

    reconstructed = from_text(to_text(original, fmt="json"), fmt="json")

    assert reconstructed == original


def test_app_without_autoscaler_round_trips_as_none():
    bare_app = App(name="worker", kind="Deployment", replicas=1, ready_replicas=1)
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-22T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=[bare_app])],
    )

    reconstructed = from_text(to_text(inventory, fmt="json"), fmt="json")

    assert reconstructed.namespaces[0].apps[0].autoscaler is None


def test_app_without_nodes_round_trips_as_empty_list():
    bare_app = App(name="worker", kind="Deployment", replicas=1, ready_replicas=1)
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-22T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=[bare_app])],
    )

    reconstructed = from_text(to_text(inventory, fmt="json"), fmt="json")

    assert reconstructed.namespaces[0].apps[0].nodes == []


def test_app_without_network_policies_round_trips_as_empty_list():
    bare_app = App(name="worker", kind="Deployment", replicas=1, ready_replicas=1)
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-22T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=[bare_app])],
    )

    reconstructed = from_text(to_text(inventory, fmt="json"), fmt="json")

    assert reconstructed.namespaces[0].apps[0].network_policies == []


def test_container_without_init_flag_or_probes_round_trips_to_defaults():
    bare_app = App(
        name="worker",
        kind="Deployment",
        replicas=1,
        ready_replicas=1,
        containers=[Container(name="worker", image="worker:1.0")],
    )
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-22T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=[bare_app])],
    )

    reconstructed = from_text(to_text(inventory, fmt="json"), fmt="json")

    container = reconstructed.namespaces[0].apps[0].containers[0]
    assert container.is_init is False
    assert container.probes == []


def test_app_without_service_account_round_trips_as_none():
    bare_app = App(name="worker", kind="Deployment", replicas=1, ready_replicas=1)
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-22T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=[bare_app])],
    )

    reconstructed = from_text(to_text(inventory, fmt="json"), fmt="json")

    assert reconstructed.namespaces[0].apps[0].service_account is None


def test_app_without_pod_disruption_budgets_round_trips_as_empty_list():
    bare_app = App(name="worker", kind="Deployment", replicas=1, ready_replicas=1)
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-22T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=[bare_app])],
    )

    reconstructed = from_text(to_text(inventory, fmt="json"), fmt="json")

    assert reconstructed.namespaces[0].apps[0].pod_disruption_budgets == []


def test_app_without_scheduling_constraints_round_trips_to_empty_defaults():
    bare_app = App(name="worker", kind="Deployment", replicas=1, ready_replicas=1)
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-22T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=[bare_app])],
    )

    reconstructed = from_text(to_text(inventory, fmt="json"), fmt="json")

    app = reconstructed.namespaces[0].apps[0]
    assert app.node_selector == {}
    assert app.node_affinity == []
    assert app.tolerations == []


def test_cluster_inventory_without_storage_classes_round_trips_as_empty_list():
    inventory = ClusterInventory(cluster_name="homelab", collected_at="2026-08-22T00:00:00+00:00")

    reconstructed = from_text(to_text(inventory, fmt="json"), fmt="json")

    assert reconstructed.storage_classes == []


def test_cluster_inventory_without_nodes_round_trips_as_empty_list():
    inventory = ClusterInventory(cluster_name="homelab", collected_at="2026-08-22T00:00:00+00:00")

    reconstructed = from_text(to_text(inventory, fmt="json"), fmt="json")

    assert reconstructed.nodes == []


def test_app_without_rollout_strategy_round_trips_as_none():
    bare_app = App(name="worker", kind="Deployment", replicas=1, ready_replicas=1)
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-22T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=[bare_app])],
    )

    reconstructed = from_text(to_text(inventory, fmt="json"), fmt="json")

    assert reconstructed.namespaces[0].apps[0].rollout_strategy is None


def test_app_without_image_pull_secrets_round_trips_as_empty_list():
    bare_app = App(name="worker", kind="Deployment", replicas=1, ready_replicas=1)
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-22T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=[bare_app])],
    )

    reconstructed = from_text(to_text(inventory, fmt="json"), fmt="json")

    assert reconstructed.namespaces[0].apps[0].image_pull_secrets == []

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
    RolloutStrategyInfo,
    ServiceInfo,
    ServicePort,
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
                            )
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
                        rollout_strategy=RolloutStrategyInfo(
                            strategy_type="RollingUpdate",
                            max_surge="25%",
                            max_unavailable="0",
                        ),
                    )
                ],
            )
        ],
    )


def test_to_text_json_round_trips():
    text = to_text(_sample_inventory(), fmt="json")
    data = json.loads(text)

    assert data["cluster_name"] == "homelab"
    assert data["namespaces"][0]["apps"][0]["containers"][0]["image"] == "nginx:1.25.3"


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


def test_app_without_rollout_strategy_round_trips_as_none():
    bare_app = App(name="worker", kind="Deployment", replicas=1, ready_replicas=1)
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-22T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=[bare_app])],
    )

    reconstructed = from_text(to_text(inventory, fmt="json"), fmt="json")

    assert reconstructed.namespaces[0].apps[0].rollout_strategy is None

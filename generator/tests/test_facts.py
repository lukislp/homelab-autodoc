from __future__ import annotations

from autodoc_core.models import App, Container, NetworkPolicyInfo, NetworkPolicyRule

from autodoc_generator.facts import (
    autoscaler_table,
    containers_table,
    dependencies_table,
    env_table,
    image_pull_secrets_table,
    ingresses_table,
    metadata_table,
    network_policies_table,
    nodes_table,
    registries_table,
    resources_table,
    services_table,
    volumes_table,
)


def test_containers_table_lists_image_and_ports(sample_app):
    table = containers_table(sample_app)

    assert "| web | `nginx:1.25.3` | 8080 |" in table


def test_services_table_lists_port_mapping(sample_app):
    table = services_table(sample_app)

    assert "| web-svc | ClusterIP | 80->8080/TCP |" in table


def test_ingresses_table_lists_host_path_and_target(sample_app):
    table = ingresses_table(sample_app)

    assert "| web-ingress | web.example.com | / | web-svc |" in table


def test_volumes_table_lists_storage_details(sample_app):
    table = volumes_table(sample_app)

    assert "| web-data | local-path | 1Gi | ReadWriteOnce |" in table


def test_resources_table_lists_requests_and_limits(sample_app):
    table = resources_table(sample_app)

    assert "| web | 100m | 500m | 128Mi | 256Mi |" in table


def test_env_table_never_shows_a_literal_value(sample_app):
    table = env_table(sample_app)

    assert "| web | LOG_LEVEL | literal |" in table
    assert "| web | API_KEY | Secret:web-secrets/API_KEY |" in table
    assert "info" not in table


def test_dependencies_table_lists_config_refs(sample_app):
    table = dependencies_table(sample_app)

    assert "| Secret | web-secrets | env |" in table
    assert "| ConfigMap | web-config | volume |" in table


def test_autoscaler_table_lists_replica_bounds_and_cpu_target(sample_app):
    table = autoscaler_table(sample_app)

    assert "| Min Replicas | 2 |" in table
    assert "| Max Replicas | 5 |" in table
    assert "| Target CPU | 70% |" in table
    assert "| Target Memory | - |" in table


def test_autoscaler_table_empty_when_app_has_no_autoscaler(bare_app):
    assert autoscaler_table(bare_app) == ""


def test_registries_table_lists_docker_hub_for_unqualified_image(sample_app):
    table = registries_table(sample_app)

    assert "| web | `nginx:1.25.3` | docker.io |" in table


def test_registries_table_lists_explicit_registry_host():
    app = App(
        name="server",
        kind="Deployment",
        replicas=1,
        ready_replicas=1,
        containers=[
            Container(name="server", image="ghcr.io/lukislp/homelab-autodoc-server:1.20.1")
        ],
    )

    table = registries_table(app)

    assert "| server | `ghcr.io/lukislp/homelab-autodoc-server:1.20.1` | ghcr.io |" in table


def test_registries_table_empty_when_app_has_no_containers(bare_app):
    assert registries_table(bare_app) == ""


def test_image_pull_secrets_table_lists_sorted_secret_names(sample_app):
    table = image_pull_secrets_table(sample_app)

    assert "| ghcr-pull-secret |" in table


def test_image_pull_secrets_table_empty_when_app_has_no_pull_secrets(bare_app):
    assert image_pull_secrets_table(bare_app) == ""


def test_nodes_table_lists_sorted_node_names(sample_app):
    table = nodes_table(sample_app)

    assert "| pi-node-1 |" in table
    assert "| pi-node-2 |" in table


def test_nodes_table_empty_when_app_has_no_nodes(bare_app):
    assert nodes_table(bare_app) == ""


def test_network_policies_table_describes_ingress_peers_and_unrestricted_egress(sample_app):
    table = network_policies_table(sample_app)

    assert "| web-allow-ingress | Ingress | pods:app=traefik | not restricted |" in table


def test_network_policies_table_shows_deny_all_when_direction_has_no_rules():
    app = App(
        name="worker",
        kind="Deployment",
        replicas=1,
        ready_replicas=1,
        network_policies=[NetworkPolicyInfo(name="deny-ingress", policy_types=["Ingress"])],
    )

    table = network_policies_table(app)

    assert "| deny-ingress | Ingress | deny all | not restricted |" in table


def test_network_policies_table_shows_all_sources_for_rule_with_no_peers():
    app = App(
        name="worker",
        kind="Deployment",
        replicas=1,
        ready_replicas=1,
        network_policies=[
            NetworkPolicyInfo(
                name="allow-all-ingress",
                policy_types=["Ingress"],
                ingress=[NetworkPolicyRule()],
            )
        ],
    )

    table = network_policies_table(app)

    assert "| allow-all-ingress | Ingress | all sources | not restricted |" in table


def test_network_policies_table_empty_when_app_has_no_policies(bare_app):
    assert network_policies_table(bare_app) == ""


def test_metadata_table_lists_created_owners_and_annotations(sample_app):
    table = metadata_table(sample_app)

    assert "| Created | 2026-08-01 12:00 UTC |" in table
    assert "| Owners | ReplicaSet/web-abc123 |" in table
    assert "`kustomize.toolkit.fluxcd.io/name`" in table


def test_metadata_table_drops_noisy_last_applied_configuration_annotation():
    app = App(
        name="worker",
        kind="Deployment",
        replicas=1,
        ready_replicas=1,
        annotations={"kubectl.kubernetes.io/last-applied-configuration": "{...huge json...}"},
    )

    table = metadata_table(app)

    assert "last-applied-configuration" not in table


def test_all_tables_empty_for_bare_app(bare_app):
    assert containers_table(bare_app) == ""
    assert registries_table(bare_app) == ""
    assert image_pull_secrets_table(bare_app) == ""
    assert services_table(bare_app) == ""
    assert ingresses_table(bare_app) == ""
    assert volumes_table(bare_app) == ""
    assert resources_table(bare_app) == ""
    assert autoscaler_table(bare_app) == ""
    assert nodes_table(bare_app) == ""
    assert network_policies_table(bare_app) == ""
    assert env_table(bare_app) == ""
    assert dependencies_table(bare_app) == ""
    assert metadata_table(bare_app) == ""

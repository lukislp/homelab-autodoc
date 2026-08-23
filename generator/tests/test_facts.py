from __future__ import annotations

from autodoc_core.models import (
    App,
    NetworkPolicyInfo,
    NetworkPolicyRule,
    NodeInfo,
    ServiceAccountInfo,
)

from autodoc_generator.facts import (
    autoscaler_table,
    containers_table,
    dependencies_table,
    env_table,
    ingresses_table,
    metadata_table,
    network_policies_table,
    node_specs_table,
    nodes_table,
    pod_disruption_budgets_table,
    resources_table,
    service_account_table,
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


def test_service_account_table_lists_name_and_roles(sample_app):
    table = service_account_table(sample_app)

    assert "| ServiceAccount | web-sa |" in table
    assert "| Roles | ClusterRole/view |" in table


def test_service_account_table_omits_roles_row_when_no_bindings():
    app = App(
        name="worker",
        kind="Deployment",
        replicas=1,
        ready_replicas=1,
        service_account=ServiceAccountInfo(name="worker-sa"),
    )

    table = service_account_table(app)

    assert "| ServiceAccount | worker-sa |" in table
    assert "Roles" not in table


def test_service_account_table_empty_when_app_has_no_service_account(bare_app):
    assert service_account_table(bare_app) == ""


def test_pod_disruption_budgets_table_lists_min_available(sample_app):
    table = pod_disruption_budgets_table(sample_app)

    assert "| web-pdb | 1 | - |" in table


def test_pod_disruption_budgets_table_empty_when_app_has_no_pdbs(bare_app):
    assert pod_disruption_budgets_table(bare_app) == ""


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
    assert services_table(bare_app) == ""
    assert ingresses_table(bare_app) == ""
    assert volumes_table(bare_app) == ""
    assert resources_table(bare_app) == ""
    assert autoscaler_table(bare_app) == ""
    assert nodes_table(bare_app) == ""
    assert network_policies_table(bare_app) == ""
    assert service_account_table(bare_app) == ""
    assert pod_disruption_budgets_table(bare_app) == ""
    assert env_table(bare_app) == ""
    assert dependencies_table(bare_app) == ""
    assert metadata_table(bare_app) == ""


def test_node_specs_table_lists_capacity_and_allocatable():
    nodes = [
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
    ]

    table = node_specs_table(nodes)

    assert (
        "| pi-node-1 | Ready | arm64 | Debian GNU/Linux 12 (bookworm) | v1.31.2+k3s1 "
        "| 4 | 3900m | 8065700Ki | 7500000Ki |" in table
    )


def test_node_specs_table_shows_not_ready_status():
    nodes = [
        NodeInfo(
            name="pi-node-2",
            architecture="arm64",
            kubelet_version="v1.31.2+k3s1",
            os_image="Debian GNU/Linux 12 (bookworm)",
            capacity_cpu="4",
            capacity_memory="8065700Ki",
            allocatable_cpu="3900m",
            allocatable_memory="7500000Ki",
            ready=False,
        )
    ]

    table = node_specs_table(nodes)

    assert "| pi-node-2 | NotReady |" in table


def test_node_specs_table_empty_for_no_nodes():
    assert node_specs_table([]) == ""

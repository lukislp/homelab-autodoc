from __future__ import annotations

from autodoc_core.models import (
    App,
    ClusterInventory,
    ConfigReference,
    Container,
    ContainerSecurityInfo,
    LimitRangeInfo,
    LimitRangeItemInfo,
    NamespaceInventory,
    NetworkPolicyInfo,
    NetworkPolicyRule,
    NodeInfo,
    ResourceQuotaInfo,
    ServiceAccountInfo,
    StorageClassInfo,
    WarningEventInfo,
)

from autodoc_generator.facts import (
    app_is_fully_ready,
    autoscaler_table,
    cluster_card_facts,
    cluster_images_table,
    cluster_stat_chips,
    collection_freshness,
    containers_table,
    dependencies_table,
    dependency_usage_table,
    env_table,
    image_pull_secrets_table,
    ingresses_table,
    limit_ranges_table,
    metadata_table,
    namespace_stat_chips,
    network_policies_table,
    node_specs_table,
    nodes_table,
    pod_disruption_budgets_table,
    probes_table,
    registries_table,
    resource_quotas_table,
    resources_table,
    rollout_strategy_table,
    scheduling_table,
    security_table,
    service_account_table,
    services_table,
    storage_classes_table,
    volumes_table,
    warning_events_table,
)


def test_containers_table_lists_image_and_ports(sample_app):
    table = containers_table(sample_app)

    assert "| web | - | `nginx:1.25.3` | 8080 |" in table


def test_containers_table_marks_init_containers_and_lists_them_first(sample_app):
    table = containers_table(sample_app)

    assert "| init-migrate | Yes | `migrate:1.0` | - |" in table
    init_line = table.index("init-migrate")
    web_line = table.index("| web |")
    assert init_line < web_line


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


def test_probes_table_lists_type_check_and_period(sample_app):
    table = probes_table(sample_app)

    assert "| web | liveness | HTTP :8080/healthz | 10s |" in table


def test_probes_table_empty_when_no_container_has_probes(bare_app):
    assert probes_table(bare_app) == ""


def test_security_table_lists_effective_flags_and_capabilities(sample_app):
    table = security_table(sample_app)

    assert "| web | yes | yes | no | -ALL | RuntimeDefault |" in table


def test_security_table_shows_dashes_for_container_without_security_context():
    app = App(
        name="worker",
        kind="Deployment",
        replicas=1,
        ready_replicas=1,
        containers=[
            Container(name="secured", image="a:1.0", security=ContainerSecurityInfo()),
            Container(name="plain", image="b:1.0"),
        ],
    )

    table = security_table(app)

    assert "| plain | - | - | - | - | - |" in table


def test_security_table_empty_when_no_container_has_security_context(bare_app):
    assert security_table(bare_app) == ""


def test_env_table_never_shows_a_literal_value(sample_app):
    table = env_table(sample_app)

    assert "| web | LOG_LEVEL | literal |" in table
    assert "| web | API_KEY | Secret:web-secrets/API_KEY |" in table
    assert "info" not in table


def test_dependencies_table_lists_config_refs(sample_app):
    table = dependencies_table(sample_app)

    assert "| Secret | web-secrets | env |" in table
    assert "| ConfigMap | web-config | volume |" in table


def test_dependency_usage_table_lists_apps_referencing_each_config_ref():
    app_a = App(
        name="web",
        kind="Deployment",
        replicas=1,
        ready_replicas=1,
        config_refs=[ConfigReference(kind="Secret", name="shared-secret", via="env")],
    )
    app_b = App(
        name="worker",
        kind="Deployment",
        replicas=1,
        ready_replicas=1,
        config_refs=[ConfigReference(kind="Secret", name="shared-secret", via="envFrom")],
    )
    namespace = NamespaceInventory(name="demo", apps=[app_a, app_b])

    table = dependency_usage_table(namespace)

    assert "| Secret | shared-secret | web (env), worker (envFrom) |" in table


def test_dependency_usage_table_empty_for_namespace_with_no_config_refs():
    namespace = NamespaceInventory(
        name="demo",
        apps=[App(name="worker", kind="Deployment", replicas=1, ready_replicas=1)],
    )

    assert dependency_usage_table(namespace) == ""


def test_resource_quotas_table_lists_hard_and_used_per_resource():
    namespace = NamespaceInventory(
        name="demo",
        resource_quotas=[
            ResourceQuotaInfo(
                name="demo-quota",
                hard={"requests.cpu": "4", "pods": "20"},
                used={"requests.cpu": "1500m", "pods": "6"},
            )
        ],
    )

    table = resource_quotas_table(namespace)

    assert "| demo-quota | pods | 20 | 6 |" in table
    assert "| demo-quota | requests.cpu | 4 | 1500m |" in table


def test_resource_quotas_table_empty_for_namespace_without_quotas():
    namespace = NamespaceInventory(name="demo")

    assert resource_quotas_table(namespace) == ""


def test_limit_ranges_table_lists_min_max_default_per_resource():
    namespace = NamespaceInventory(
        name="demo",
        limit_ranges=[
            LimitRangeInfo(
                name="demo-limits",
                limits=[
                    LimitRangeItemInfo(
                        kind="Container",
                        min={"cpu": "50m"},
                        max={"cpu": "2"},
                        default={"cpu": "500m", "memory": "256Mi"},
                        default_request={"cpu": "100m", "memory": "128Mi"},
                    )
                ],
            )
        ],
    )

    table = limit_ranges_table(namespace)

    assert "| demo-limits | Container | cpu | 50m | 2 | 500m | 100m |" in table
    assert "| demo-limits | Container | memory | - | - | 256Mi | 128Mi |" in table


def test_limit_ranges_table_empty_for_namespace_without_limit_ranges():
    namespace = NamespaceInventory(name="demo")

    assert limit_ranges_table(namespace) == ""


def test_app_is_fully_ready_true_when_ready_equals_replicas():
    app = App(name="web", kind="Deployment", replicas=2, ready_replicas=2)

    assert app_is_fully_ready(app) is True


def test_app_is_fully_ready_false_when_under_ready():
    app = App(name="web", kind="Deployment", replicas=2, ready_replicas=1)

    assert app_is_fully_ready(app) is False


def test_cluster_stat_chips_counts_namespaces_nodes_and_storage_classes():
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-23T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo")],
        storage_classes=[StorageClassInfo(name="local-path", provisioner="rancher.io/local-path")],
        nodes=[
            NodeInfo(
                name="pi-node-1",
                architecture="arm64",
                kubelet_version="v1.31.2+k3s1",
                os_image="Debian",
                capacity_cpu="4",
                capacity_memory="8Gi",
                allocatable_cpu="3900m",
                allocatable_memory="7Gi",
                ready=True,
            )
        ],
    )

    chips = cluster_stat_chips(inventory, drift_count=0, findings_count=0)

    assert '<span class="stat-num">1</span><span class="stat-label">Namespaces</span>' in chips
    assert '<span class="stat-num">1</span><span class="stat-label">Nodes</span>' in chips
    assert '<span class="stat-num">1</span><span class="stat-label">Storage Classes</span>' in chips
    assert '<span class="stat-num">0</span><span class="stat-label">Findings</span>' in chips
    assert '<span class="stat-num">0</span><span class="stat-label">Drift, Last Run</span>' in chips


def test_cluster_stat_chips_highlights_nonzero_drift():
    inventory = ClusterInventory(cluster_name="homelab", collected_at="2026-08-23T00:00:00+00:00")

    chips = cluster_stat_chips(inventory, drift_count=4, findings_count=0)

    assert '<span class="stat-num stat-num--warn">4</span>' in chips


def test_cluster_stat_chips_highlights_nonzero_findings():
    inventory = ClusterInventory(cluster_name="homelab", collected_at="2026-08-23T00:00:00+00:00")

    chips = cluster_stat_chips(inventory, drift_count=0, findings_count=7)

    assert (
        '<span class="stat-num stat-num--warn">7</span><span class="stat-label">Findings</span>'
        in chips
    )


def test_namespace_stat_chips_shows_raw_quota_values_without_computing_a_percentage():
    namespace = NamespaceInventory(
        name="demo",
        apps=[App(name="web", kind="Deployment", replicas=1, ready_replicas=1)],
        resource_quotas=[
            ResourceQuotaInfo(
                name="demo-quota",
                hard={"requests.cpu": "2", "pods": "20"},
                used={"requests.cpu": "900m", "pods": "4"},
            )
        ],
    )

    chips = namespace_stat_chips(namespace, drift_count=0)

    assert '<span class="stat-num">1</span><span class="stat-label">Applications</span>' in chips
    assert '<span class="stat-num">4/20</span><span class="stat-label">Pods (Quota)</span>' in chips
    assert (
        '<span class="stat-num">900m / 2</span><span class="stat-label">CPU (Requests)</span>'
        in chips
    )


def test_namespace_stat_chips_shows_dash_when_no_resource_quota():
    namespace = NamespaceInventory(name="demo")

    chips = namespace_stat_chips(namespace, drift_count=0)

    assert '<span class="stat-num">-</span><span class="stat-label">Pods (Quota)</span>' in chips
    assert '<span class="stat-num">-</span><span class="stat-label">CPU (Requests)</span>' in chips


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


def test_rollout_strategy_table_lists_strategy_and_surge_settings(sample_app):
    table = rollout_strategy_table(sample_app)

    assert "| Strategy | RollingUpdate |" in table
    assert "| Max Surge | 25% |" in table
    assert "| Max Unavailable | 0 |" in table
    assert "| Partition | - |" in table


def test_rollout_strategy_table_empty_when_app_has_no_rollout_strategy(bare_app):
    assert rollout_strategy_table(bare_app) == ""


def test_nodes_table_lists_sorted_node_names(sample_app):
    table = nodes_table(sample_app)

    assert "| pi-node-1 |" in table
    assert "| pi-node-2 |" in table


def test_nodes_table_empty_when_app_has_no_nodes(bare_app):
    assert nodes_table(bare_app) == ""


def test_scheduling_table_lists_selector_affinity_and_tolerations(sample_app):
    table = scheduling_table(sample_app)

    assert "| Node Selector | kubernetes.io/arch=arm64 |" in table
    assert "| Node Affinity | required: kubernetes.io/arch In (arm64) |" in table
    assert "| Toleration | node-role.kubernetes.io/master Exists:NoSchedule |" in table


def test_scheduling_table_empty_when_app_has_no_constraints(bare_app):
    assert scheduling_table(bare_app) == ""


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
    assert probes_table(bare_app) == ""
    assert security_table(bare_app) == ""
    assert registries_table(bare_app) == ""
    assert image_pull_secrets_table(bare_app) == ""
    assert services_table(bare_app) == ""
    assert ingresses_table(bare_app) == ""
    assert volumes_table(bare_app) == ""
    assert resources_table(bare_app) == ""
    assert autoscaler_table(bare_app) == ""
    assert rollout_strategy_table(bare_app) == ""
    assert nodes_table(bare_app) == ""
    assert scheduling_table(bare_app) == ""
    assert network_policies_table(bare_app) == ""
    assert service_account_table(bare_app) == ""
    assert pod_disruption_budgets_table(bare_app) == ""
    assert env_table(bare_app) == ""
    assert dependencies_table(bare_app) == ""
    assert metadata_table(bare_app) == ""


def test_storage_classes_table_lists_provisioner_and_policy():
    storage_classes = [
        StorageClassInfo(
            name="local-path",
            provisioner="rancher.io/local-path",
            reclaim_policy="Delete",
            volume_binding_mode="WaitForFirstConsumer",
            allow_volume_expansion=False,
        )
    ]

    table = storage_classes_table(storage_classes)

    assert "| local-path | rancher.io/local-path | Delete | WaitForFirstConsumer | False |" in table


def test_storage_classes_table_empty_for_no_storage_classes():
    assert storage_classes_table([]) == ""


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


def test_collection_freshness_carries_iso_stamp_and_absolute_fallback():
    stamp = collection_freshness("2026-08-23T02:00:00+00:00")

    # freshness.js reads the raw ISO value; the rendered text is the no-JS
    # fallback and must already be human-readable on its own.
    assert 'data-collected-at="2026-08-23T02:00:00+00:00"' in stamp
    assert "collected 2026-08-23 02:00 UTC" in stamp
    assert stamp.startswith('<span class="freshness"')


def test_cluster_images_table_dedupes_across_namespaces_and_lists_users():
    def app_with_image(name: str, image: str) -> App:
        return App(
            name=name,
            kind="Deployment",
            replicas=1,
            ready_replicas=1,
            containers=[Container(name=name, image=image)],
        )

    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-23T00:00:00+00:00",
        namespaces=[
            NamespaceInventory(
                name="demo",
                apps=[
                    app_with_image("web", "ghcr.io/acme/web:1.2.0"),
                    app_with_image("db", "postgres:16.3"),
                ],
            ),
            NamespaceInventory(name="other", apps=[app_with_image("api", "postgres:16.3")]),
        ],
    )

    table = cluster_images_table(inventory)

    assert table.splitlines()[0] == "| Image | Registry | Used By |"
    assert "| `postgres:16.3` | docker.io | demo/db, other/api |" in table
    assert "| `ghcr.io/acme/web:1.2.0` | ghcr.io | demo/web |" in table


def test_cluster_images_table_includes_init_containers():
    app = App(
        name="web",
        kind="Deployment",
        replicas=1,
        ready_replicas=1,
        containers=[
            Container(name="init-migrate", image="migrate:1.0", is_init=True),
            Container(name="web", image="nginx:1.25.3"),
        ],
    )
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-23T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=[app])],
    )

    table = cluster_images_table(inventory)

    assert "`migrate:1.0`" in table
    assert "`nginx:1.25.3`" in table


def test_cluster_images_table_empty_without_containers():
    inventory = ClusterInventory(cluster_name="homelab", collected_at="2026-08-23T00:00:00+00:00")

    assert cluster_images_table(inventory) == ""


def test_cluster_card_facts_lists_scale_versions_and_health():
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-23T00:00:00+00:00",
        namespaces=[
            NamespaceInventory(
                name="demo",
                apps=[App(name="web", kind="Deployment", replicas=1, ready_replicas=1)],
            )
        ],
        nodes=[
            NodeInfo(
                name="pi-node-1",
                architecture="arm64",
                kubelet_version="v1.31.2+k3s1",
                os_image="Debian",
                capacity_cpu="4",
                capacity_memory="8Gi",
                allocatable_cpu="3900m",
                allocatable_memory="7Gi",
                ready=True,
            )
        ],
    )

    card = cluster_card_facts(inventory, drift_count=0, findings_count=3)

    assert "1 namespace · 1 app · 1 node · v1.31.2+k3s1" in card
    assert "3 findings · 0 drift last run" in card
    assert "card-facts--warn" not in card


def test_cluster_card_facts_warn_tints_nonzero_drift_only():
    inventory = ClusterInventory(cluster_name="homelab", collected_at="2026-08-23T00:00:00+00:00")

    card = cluster_card_facts(inventory, drift_count=2, findings_count=0)

    assert '<span class="card-facts card-facts--warn">0 findings · 2 drift last run</span>' in card


def test_cluster_card_facts_shows_disagreeing_kubelet_versions():
    def node(name: str, version: str) -> NodeInfo:
        return NodeInfo(
            name=name,
            architecture="arm64",
            kubelet_version=version,
            os_image="Debian",
            capacity_cpu="4",
            capacity_memory="8Gi",
            allocatable_cpu="4",
            allocatable_memory="8Gi",
            ready=True,
        )

    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-23T00:00:00+00:00",
        nodes=[node("a", "v1.31.2+k3s1"), node("b", "v1.30.4+k3s1")],
    )

    card = cluster_card_facts(inventory, drift_count=0, findings_count=0)

    assert "v1.30.4+k3s1 / v1.31.2+k3s1" in card


def test_warning_events_table_renders_rows_and_truncates_messages():
    namespace = NamespaceInventory(
        name="demo",
        warning_events=[
            WarningEventInfo(
                reason="BackOff",
                object_ref="Pod/web-abc",
                message="x" * 200,
                count=12,
                last_seen="2026-08-21T23:55:00+00:00",
            ),
            WarningEventInfo(
                reason="FailedScheduling", object_ref="Pod/db-xyz", message="no nodes", count=1
            ),
        ],
    )

    table = warning_events_table(namespace)

    assert table.splitlines()[0] == "| Last Seen | Object | Reason | Count | Message |"
    assert "| 2026-08-21 23:55 UTC | Pod/web-abc | BackOff | 12 | " in table
    assert "x" * 160 + "…" in table
    assert "x" * 161 not in table
    assert "| - | Pod/db-xyz | FailedScheduling | 1 | no nodes |" in table


def test_warning_events_table_empty_for_none_and_for_no_events():
    assert warning_events_table(NamespaceInventory(name="demo")) == ""
    assert warning_events_table(NamespaceInventory(name="demo", warning_events=[])) == ""

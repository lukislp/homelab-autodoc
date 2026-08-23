from __future__ import annotations

from autodoc_core.models import App

from autodoc_generator.facts import (
    autoscaler_table,
    containers_table,
    dependencies_table,
    env_table,
    ingresses_table,
    metadata_table,
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
    assert env_table(bare_app) == ""
    assert dependencies_table(bare_app) == ""
    assert metadata_table(bare_app) == ""

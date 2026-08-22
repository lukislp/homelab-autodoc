from __future__ import annotations

from autodoc_generator.facts import (
    containers_table,
    ingresses_table,
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


def test_all_tables_empty_for_bare_app(bare_app):
    assert containers_table(bare_app) == ""
    assert services_table(bare_app) == ""
    assert ingresses_table(bare_app) == ""
    assert volumes_table(bare_app) == ""

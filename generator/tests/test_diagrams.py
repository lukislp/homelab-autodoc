from __future__ import annotations

from autodoc_core.models import App, ClusterInventory, Container, NamespaceInventory, ServiceInfo

from autodoc_generator.diagrams import (
    build_app_diagram,
    build_cluster_diagram,
    build_namespace_diagram,
)


def test_diagram_includes_app_service_ingress_and_volume_nodes(sample_app):
    diagram = build_app_diagram(sample_app)

    assert 'app[["web (Deployment)"]]' in diagram
    assert 'svc_web_svc("web-svc")' in diagram
    assert 'ing_web_ingress{{"web-ingress"}}' in diagram
    assert 'vol_web_data[("web-data")]' in diagram
    assert "app --> svc_web_svc" in diagram
    assert "svc_web_svc --> ing_web_ingress" in diagram
    assert "app --> vol_web_data" in diagram


def test_diagram_includes_config_ref_nodes(sample_app):
    diagram = build_app_diagram(sample_app)

    assert 'cfg_Secret_web_secrets[/"Secret: web-secrets"/]' in diagram
    assert "app --> cfg_Secret_web_secrets" in diagram
    assert 'cfg_ConfigMap_web_config[/"ConfigMap: web-config"/]' in diagram


def test_diagram_for_bare_app_has_only_the_app_node(bare_app):
    diagram = build_app_diagram(bare_app)

    assert diagram == 'flowchart LR\n  app[["worker (Deployment)"]]'


def test_diagram_output_is_deterministic(sample_app):
    assert build_app_diagram(sample_app) == build_app_diagram(sample_app)


def test_namespace_diagram_distinguishes_apps_of_different_kinds(sample_app):
    other_app = App(name="web", kind="StatefulSet", replicas=1, ready_replicas=1)
    namespace = NamespaceInventory(name="demo", apps=[sample_app, other_app])

    diagram = build_namespace_diagram(namespace)

    assert 'app_Deployment_web[["web (Deployment)"]]' in diagram
    assert 'app_StatefulSet_web[["web (StatefulSet)"]]' in diagram


def test_cluster_diagram_groups_namespaces_in_subgraphs_without_id_collisions():
    app_a = App(
        name="web",
        kind="Deployment",
        replicas=1,
        ready_replicas=1,
        containers=[Container(name="web", image="nginx:1.25.3")],
        services=[ServiceInfo(name="web", type="ClusterIP", cluster_ip="10.0.0.1")],
    )
    app_b = App(
        name="web",
        kind="Deployment",
        replicas=1,
        ready_replicas=1,
        containers=[Container(name="web", image="nginx:1.25.3")],
        services=[ServiceInfo(name="web", type="ClusterIP", cluster_ip="10.0.0.2")],
    )
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-22T00:00:00+00:00",
        namespaces=[
            NamespaceInventory(name="team-a", apps=[app_a]),
            NamespaceInventory(name="team-b", apps=[app_b]),
        ],
    )

    diagram = build_cluster_diagram(inventory)

    assert 'subgraph ns_team_a ["team-a"]' in diagram
    assert 'subgraph ns_team_b ["team-b"]' in diagram
    assert "ns_team_a_app_Deployment_web" in diagram
    assert "ns_team_b_app_Deployment_web" in diagram
    assert "ns_team_a_svc_web" in diagram
    assert "ns_team_b_svc_web" in diagram
    # every node id line is unique - no cross-namespace collision
    node_lines = [line for line in diagram.splitlines() if "[" in line or "{" in line]
    assert len(node_lines) == len(set(node_lines))


def test_cluster_diagram_output_is_deterministic():
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-22T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=[])],
    )

    assert build_cluster_diagram(inventory) == build_cluster_diagram(inventory)

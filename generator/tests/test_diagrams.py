from __future__ import annotations

from autodoc_generator.diagrams import build_app_diagram


def test_diagram_includes_app_service_ingress_and_volume_nodes(sample_app):
    diagram = build_app_diagram(sample_app)

    assert 'app[["web (Deployment)"]]' in diagram
    assert 'svc_web_svc("web-svc")' in diagram
    assert 'ing_web_ingress{{"web-ingress"}}' in diagram
    assert 'vol_web_data[("web-data")]' in diagram
    assert "app --> svc_web_svc" in diagram
    assert "svc_web_svc --> ing_web_ingress" in diagram
    assert "app --> vol_web_data" in diagram


def test_diagram_for_bare_app_has_only_the_app_node(bare_app):
    diagram = build_app_diagram(bare_app)

    assert diagram == 'flowchart LR\n  app[["worker (Deployment)"]]'


def test_diagram_output_is_deterministic(sample_app):
    assert build_app_diagram(sample_app) == build_app_diagram(sample_app)

from __future__ import annotations

from autodoc_core.models import NamespaceInventory

from autodoc_generator.render import render_app_page, render_namespace_index


def test_render_app_page_without_summary_omits_the_summary_section(sample_app):
    page = render_app_page(sample_app, namespace="demo", summary=None)

    assert "# web" in page
    assert "Deployment in `demo`" in page
    assert "## Summary (AI-generated)" not in page
    assert "### Containers" in page
    assert "### Probes" in page
    assert "### Security Context" in page
    assert "### Image Registry" in page
    assert "### Image Pull Secrets" in page
    assert "### Network Policies" in page
    assert "### Nodes" in page
    assert "### Scheduling" in page
    assert "### Resources" in page
    assert "### Autoscaling" in page
    assert "### Disruption Budget" in page
    assert "### Rollout Strategy" in page
    assert "### Environment" in page
    assert "### Dependencies" in page
    assert "### Service Account" in page
    assert "### Metadata" in page
    assert "```mermaid" in page


def test_render_app_page_with_summary_includes_it(sample_app):
    page = render_app_page(sample_app, namespace="demo", summary="A short summary.")

    assert "## Summary (AI-generated)" in page
    assert "A short summary." in page


def test_render_app_page_for_bare_app_omits_empty_fact_sections(bare_app):
    page = render_app_page(bare_app, namespace="demo", summary=None)

    assert "### Containers" not in page
    assert "### Probes" not in page
    assert "### Security Context" not in page
    assert "### Image Registry" not in page
    assert "### Image Pull Secrets" not in page
    assert "### Services" not in page
    assert "### Ingress" not in page
    assert "### Volumes" not in page
    assert "### Network Policies" not in page
    assert "### Nodes" not in page
    assert "### Scheduling" not in page
    assert "### Resources" not in page
    assert "### Autoscaling" not in page
    assert "### Disruption Budget" not in page
    assert "### Rollout Strategy" not in page
    assert "### Environment" not in page
    assert "### Dependencies" not in page
    assert "### Service Account" not in page
    assert "### Metadata" not in page


def test_render_namespace_index_links_each_app(sample_app):
    namespace = NamespaceInventory(name="demo", apps=[sample_app])

    index = render_namespace_index(namespace)

    assert "# demo" in index
    assert "[web](web.md)" in index
    assert "Deployment" in index

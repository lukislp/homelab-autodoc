from __future__ import annotations

from autodoc_core.models import App, NamespaceInventory, WarningEventInfo

from autodoc_generator.render import render_app_page, render_namespace_index


def test_render_app_page_without_summary_omits_the_summary_section(sample_app):
    namespace = NamespaceInventory(name="demo", apps=[sample_app])
    page = render_app_page(sample_app, namespace, "homelab", summary=None)

    assert "# web" in page
    assert '<span class="kind-badge">Deployment</span>' in page
    assert '<span class="pill">2/2 ready</span>' in page
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
    namespace = NamespaceInventory(name="demo", apps=[sample_app])
    page = render_app_page(sample_app, namespace, "homelab", summary="A short summary.")

    assert "## Summary (AI-generated)" in page
    assert "A short summary." in page


def test_render_app_page_for_bare_app_omits_empty_fact_sections(bare_app):
    namespace = NamespaceInventory(name="demo", apps=[bare_app])
    page = render_app_page(bare_app, namespace, "homelab", summary=None)

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


def test_render_app_page_hides_global_navigation(sample_app):
    namespace = NamespaceInventory(name="demo", apps=[sample_app])
    page = render_app_page(sample_app, namespace, "homelab", summary=None)

    assert page.startswith("---\nhide:\n  - navigation\n---")


def test_render_app_page_shows_breadcrumb_and_scoped_sidenav():
    web = App(name="web", kind="Deployment", replicas=1, ready_replicas=1)
    worker = App(name="worker", kind="Deployment", replicas=1, ready_replicas=1)
    namespace = NamespaceInventory(name="demo", apps=[web, worker])

    page = render_app_page(web, namespace, "homelab", summary=None)

    crumb = (
        "[homelab-autodoc](../../index.md) · [homelab](../index.md) · [demo](index.md) · **web**"
    )
    assert crumb in page
    active = '<span class="ns-active"><span class="ns-list-dot ns-list-dot--ok"></span>web</span>'
    assert active in page
    assert "worker.md)" in page


def test_render_app_page_shows_warn_pill_for_a_not_fully_ready_app():
    degraded = App(name="web", kind="Deployment", replicas=3, ready_replicas=1)
    namespace = NamespaceInventory(name="demo", apps=[degraded])

    page = render_app_page(degraded, namespace, "homelab", summary=None)

    assert '<span class="pill pill--warn">1/3 ready</span>' in page


def test_render_namespace_index_links_each_app(sample_app):
    namespace = NamespaceInventory(name="demo", apps=[sample_app])

    index = render_namespace_index(namespace, "homelab")

    assert "# demo" in index
    assert "__web__" in index
    assert "](web.md)" in index
    assert '<span class="ns-dot ns-dot--ok">' in index
    assert "Deployment" in index
    assert "2/2 ready" in index
    assert "[Resource Governance](resource-governance.md){: .chip-link }" in index


def test_render_namespace_index_shows_stat_chips_including_drift_count(sample_app):
    namespace = NamespaceInventory(name="demo", apps=[sample_app])

    index = render_namespace_index(namespace, "homelab", drift_count=3)

    assert '<span class="stat-num">1</span><span class="stat-label">Applications</span>' in index
    assert '<span class="stat-num stat-num--warn">3</span>' in index
    assert '<span class="stat-label">Drift, Last Run</span>' in index


def test_render_namespace_index_marks_not_fully_ready_app_with_warn_dot():
    degraded = App(name="worker", kind="Deployment", replicas=3, ready_replicas=1)
    namespace = NamespaceInventory(name="demo", apps=[degraded])

    index = render_namespace_index(namespace, "homelab")

    assert '<span class="ns-dot ns-dot--warn">' in index


def test_render_namespace_index_hides_global_navigation_and_shows_breadcrumb(sample_app):
    namespace = NamespaceInventory(name="demo", apps=[sample_app])

    index = render_namespace_index(namespace, "homelab")

    assert index.startswith("---\nhide:\n  - navigation\n---")
    assert "[homelab-autodoc](../../index.md) · [homelab](../index.md) · **demo**" in index


def test_namespace_index_shows_recent_warnings_section_when_present():
    namespace = NamespaceInventory(
        name="demo",
        apps=[App(name="web", kind="Deployment", replicas=1, ready_replicas=1)],
        warning_events=[
            WarningEventInfo(
                reason="BackOff",
                object_ref="Pod/web-abc",
                message="restarting",
                count=2,
                last_seen="2026-08-23T01:00:00+00:00",
            )
        ],
    )

    index = render_namespace_index(namespace, "homelab")

    assert '<p class="section-label">Recent Warnings</p>' in index
    assert "| 2026-08-23 01:00 UTC | Pod/web-abc | BackOff | 2 | restarting |" in index


def test_namespace_index_has_no_warnings_section_without_events():
    namespace = NamespaceInventory(
        name="demo",
        apps=[App(name="web", kind="Deployment", replicas=1, ready_replicas=1)],
    )

    index = render_namespace_index(namespace, "homelab")

    assert "Recent Warnings" not in index

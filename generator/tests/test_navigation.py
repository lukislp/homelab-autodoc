from __future__ import annotations

from autodoc_core.models import App, NamespaceInventory

from autodoc_generator.navigation import breadcrumb, cluster_page_links, namespace_sidenav


def test_breadcrumb_for_cluster_level_page():
    assert breadcrumb("homelab") == "[homelab-autodoc](../index.md) · **homelab**"


def test_breadcrumb_for_namespace_level_page():
    assert breadcrumb("homelab", "demo") == (
        "[homelab-autodoc](../../index.md) · [homelab](../index.md) · **demo**"
    )


def test_breadcrumb_for_cluster_content_page_appends_the_looked_up_page_label():
    assert breadcrumb("homelab", current="storage-classes") == (
        "[homelab-autodoc](../index.md) · [homelab](index.md) · **Storage Classes**"
    )


def test_breadcrumb_for_namespace_content_page_appends_the_looked_up_page_label():
    assert breadcrumb("homelab", "demo", current="resource-governance") == (
        "[homelab-autodoc](../../index.md) · [homelab](../index.md) · "
        "[demo](index.md) · **Resource Governance**"
    )


def test_breadcrumb_for_app_page_appends_the_app_name_verbatim():
    assert breadcrumb("homelab", "demo", current="web") == (
        "[homelab-autodoc](../../index.md) · [homelab](../index.md) · [demo](index.md) · **web**"
    )


def test_namespace_sidenav_links_sibling_apps_and_marks_current_app_active():
    namespace = NamespaceInventory(
        name="demo",
        apps=[
            App(name="web", kind="Deployment", replicas=1, ready_replicas=1),
            App(name="worker", kind="Deployment", replicas=1, ready_replicas=1),
        ],
    )

    sidenav = namespace_sidenav(namespace, current="web")

    active = '<span class="ns-active"><span class="ns-list-dot ns-list-dot--ok"></span>web</span>'
    assert active in sidenav
    assert "worker](worker.md)" in sidenav
    assert "[web](web.md)" not in sidenav


def test_namespace_sidenav_marks_a_not_fully_ready_app_with_a_warn_dot():
    namespace = NamespaceInventory(
        name="demo", apps=[App(name="worker", kind="Deployment", replicas=3, ready_replicas=1)]
    )

    sidenav = namespace_sidenav(namespace, current="web")

    assert '<span class="ns-list-dot ns-list-dot--warn"></span>' in sidenav


def test_namespace_sidenav_marks_current_namespace_page_active():
    namespace = NamespaceInventory(name="demo", apps=[])

    sidenav = namespace_sidenav(namespace, current="dependencies")

    assert '<span class="ns-active">Dependencies</span>' in sidenav
    assert "[Topology](topology.md)" in sidenav
    assert "[Resource Governance](resource-governance.md)" in sidenav
    assert "[Dependencies](dependencies.md)" not in sidenav


def test_namespace_sidenav_links_back_to_namespace_index():
    namespace = NamespaceInventory(name="demo", apps=[])

    sidenav = namespace_sidenav(namespace, current="topology")

    assert "[demo →](index.md)" in sidenav


def test_cluster_page_links_marks_current_page_inert():
    links = cluster_page_links("nodes")

    assert '<span class="chip-link chip-link--active">Nodes</span>' in links
    assert "[Nodes](nodes.md)" not in links
    assert "[Topology](topology.md){: .chip-link }" in links
    assert "[Storage Classes](storage-classes.md){: .chip-link }" in links
    assert "[Changelog](changelog.md){: .chip-link }" in links


def test_cluster_page_links_all_links_when_no_current_page():
    links = cluster_page_links()

    assert "[Topology](topology.md){: .chip-link }" in links
    assert "chip-link--active" not in links

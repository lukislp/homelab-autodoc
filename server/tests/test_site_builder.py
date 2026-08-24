from __future__ import annotations

import shutil

from autodoc_core.models import ClusterInventory

from autodoc_server.logic import pages, site_builder
from autodoc_server.logic.storage import Storage


def test_regenerate_cluster_docs_writes_app_and_index_pages(tmp_path, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", sample_inventory)

    site_builder.regenerate_cluster_docs(storage, "homelab", llm=None)

    app_page = (storage.docs_dir / "homelab" / "demo" / "web.md").read_text(encoding="utf-8")
    namespace_index = (storage.docs_dir / "homelab" / "demo" / "index.md").read_text(
        encoding="utf-8"
    )
    namespace_topology = (storage.docs_dir / "homelab" / "demo" / "topology.md").read_text(
        encoding="utf-8"
    )
    namespace_dependencies = (storage.docs_dir / "homelab" / "demo" / "dependencies.md").read_text(
        encoding="utf-8"
    )
    namespace_resource_governance = (
        storage.docs_dir / "homelab" / "demo" / "resource-governance.md"
    ).read_text(encoding="utf-8")
    cluster_index = (storage.docs_dir / "homelab" / "index.md").read_text(encoding="utf-8")
    cluster_topology = (storage.docs_dir / "homelab" / "topology.md").read_text(encoding="utf-8")
    storage_classes_page = (storage.docs_dir / "homelab" / "storage-classes.md").read_text(
        encoding="utf-8"
    )
    nodes_page = (storage.docs_dir / "homelab" / "nodes.md").read_text(encoding="utf-8")
    root_index = (storage.docs_dir / "index.md").read_text(encoding="utf-8")

    assert "# web" in app_page
    assert "nginx:1.25.3" in app_page
    assert "__web__" in namespace_index
    assert "](web.md)" in namespace_index
    assert '<span class="ns-dot ns-dot--ok">' in namespace_index
    assert "[Topology](topology.md){: .chip-link }" in namespace_index
    assert "[Dependencies](dependencies.md){: .chip-link }" in namespace_index
    assert "[Resource Governance](resource-governance.md){: .chip-link }" in namespace_index
    assert '<div class="stat-row">' in namespace_index
    assert "# demo - Topology" in namespace_topology
    assert "```mermaid" in namespace_topology
    assert "# demo - Dependencies" in namespace_dependencies
    assert "| Secret | web-secrets | web (env) |" in namespace_dependencies
    assert "# demo - Resource Governance" in namespace_resource_governance
    assert "| demo-quota | pods | 20 | 6 |" in namespace_resource_governance
    assert (
        "| demo-limits | Container | cpu | - | - | 500m | 100m |" in namespace_resource_governance
    )
    assert 'data-collected-at="2026-08-22T00:00:00+00:00"' in cluster_index
    assert "__demo__" in cluster_index
    assert "](demo/index.md)" in cluster_index
    assert '<span class="ns-dot ns-dot--ok">' in cluster_index
    assert '<div class="stat-row">' in cluster_index
    assert "[Topology](topology.md){: .chip-link }" in cluster_index
    assert "[Storage Classes](storage-classes.md){: .chip-link }" in cluster_index
    assert "[Nodes](nodes.md){: .chip-link }" in cluster_index
    assert "[Changelog](changelog.md){: .chip-link }" in cluster_index
    assert "[Findings](findings.md){: .chip-link }" in cluster_index
    # Its front matter carries the title instead of the plain hide-only block.
    assert cluster_topology.startswith('---\ntitle: "homelab - Topology"')
    # The cluster topology drops its visible H1 (breadcrumb + active chip
    # already locate the page; the heading's height came straight out of the
    # diagram's viewport budget) but keeps the title for the browser tab.
    assert "# homelab - Topology" not in cluster_topology
    assert 'title: "homelab - Topology"' in cluster_topology
    # The chip row sits above the diagram, not below it.
    assert cluster_topology.index('chip-link--active">Topology') < cluster_topology.index(
        "```mermaid"
    )
    assert '<span class="chip-link chip-link--active">Topology</span>' in cluster_topology
    assert "[Nodes](nodes.md){: .chip-link }" in cluster_topology
    assert "[homelab-autodoc](../index.md) · [homelab](index.md) · **Topology**" in cluster_topology
    assert "# homelab - Storage Classes" in storage_classes_page
    assert "local-path" in storage_classes_page
    assert "rancher.io/local-path" in storage_classes_page
    assert (
        '<span class="chip-link chip-link--active">Storage Classes</span>' in storage_classes_page
    )
    assert (
        "[homelab-autodoc](../index.md) · [homelab](index.md) · **Storage Classes**"
        in storage_classes_page
    )
    assert "# homelab - Nodes" in nodes_page
    assert "pi-node-1" in nodes_page
    assert "arm64" in nodes_page
    assert '<span class="chip-link chip-link--active">Nodes</span>' in nodes_page
    assert "[homelab-autodoc](../index.md) · [homelab](index.md) · **Nodes**" in nodes_page
    assert "[Open Admin →](/admin/)" in root_index
    assert "[Browse →](homelab/index.md)" in root_index
    # The sample cluster: one namespace, one app, one node - shown as fleet
    # facts on the card, with the findings count computed live.
    assert "1 namespace · 1 app · 1 node · v1.31.2+k3s1" in root_index
    assert "drift last run" in root_index
    assert 'data-collected-at="2026-08-22T00:00:00+00:00"' in root_index
    assert '<div class="grid cards" markdown>' in root_index

    # Every generated page hides Material's global nav tree in favor of a
    # breadcrumb, plus - on namespace-scoped content pages - a compact
    # sidebar scoped to just that namespace.
    for page in (
        app_page,
        namespace_index,
        namespace_topology,
        namespace_dependencies,
        namespace_resource_governance,
        cluster_index,
        storage_classes_page,
        nodes_page,
        root_index,
    ):
        assert page.startswith("---\nhide:\n  - navigation\n---")

    assert (
        "[homelab-autodoc](../../index.md) · [homelab](../index.md) · "
        "[demo](index.md) · **web**" in app_page
    )
    assert (
        "[homelab-autodoc](../../index.md) · [homelab](../index.md) · **demo**" in namespace_index
    )
    assert "[homelab-autodoc](../index.md) · **homelab**" in cluster_index
    active = '<span class="ns-active"><span class="ns-list-dot ns-list-dot--ok"></span>web</span>'
    assert active in app_page
    assert '<span class="kind-badge">Deployment</span>' in app_page
    assert '<span class="pill">2/2 ready</span>' in app_page
    assert 'class="ns-sidenav"' in app_page
    assert 'class="ns-sidenav"' in namespace_topology
    assert 'class="ns-sidenav"' in namespace_dependencies
    assert 'class="ns-sidenav"' in namespace_resource_governance
    assert '<span class="ns-active">Topology</span>' in namespace_topology
    assert '<span class="ns-active">Dependencies</span>' in namespace_dependencies
    assert '<span class="ns-active">Resource Governance</span>' in namespace_resource_governance
    # Hub pages (root, cluster, namespace index) show cards, not the sidebar.
    assert "ns-sidenav" not in namespace_index
    assert "ns-sidenav" not in cluster_index
    assert "ns-sidenav" not in root_index


def test_regenerate_cluster_docs_nodes_page_without_nodes(tmp_path):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory(
        "homelab",
        ClusterInventory(cluster_name="homelab", collected_at="2026-08-22T00:00:00+00:00"),
    )

    site_builder.regenerate_cluster_docs(storage, "homelab", llm=None)

    nodes_page = (storage.docs_dir / "homelab" / "nodes.md").read_text(encoding="utf-8")
    assert "No node data collected yet." in nodes_page


def test_write_root_index_admin_tile_present_even_with_no_clusters(tmp_path):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")

    pages.write_root_index(storage)

    root_index = (storage.docs_dir / "index.md").read_text(encoding="utf-8")
    assert "[Open Admin →](/admin/)" in root_index
    assert root_index.startswith("---\nhide:\n  - navigation\n---")


def test_regenerate_cluster_docs_writes_findings_page(tmp_path, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", sample_inventory)

    site_builder.regenerate_cluster_docs(storage, "homelab", llm=None)

    findings_page = (storage.docs_dir / "homelab" / "findings.md").read_text(encoding="utf-8")
    assert "# homelab - Findings" in findings_page
    assert '<span class="chip-link chip-link--active">Findings</span>' in findings_page
    # The sample app has no probes at all - that exact gap must surface,
    # attributed and linked to the app.
    assert "| [demo](demo/index.md) | [web](demo/web.md) | `missing-probes` |" in findings_page
    assert "no liveness or readiness probe configured" in findings_page


def test_regenerate_cluster_docs_writes_images_page(tmp_path, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", sample_inventory)

    site_builder.regenerate_cluster_docs(storage, "homelab", llm=None)

    images_page = (storage.docs_dir / "homelab" / "images.md").read_text(encoding="utf-8")
    assert "# homelab - Images" in images_page
    assert '<span class="chip-link chip-link--active">Images</span>' in images_page
    assert "| `nginx:1.25.3` | docker.io | demo/web |" in images_page


class _FakeLLM:
    """regenerate_cluster_docs drives every LLM prompt through one client -
    the drift-summary prompt is recognized by its own instruction text."""

    def generate(self, prompt: str) -> str:
        if "configuration drift" in prompt:
            assert "demo/web" in prompt  # the drift facts actually reach the LLM
            return "The web app scaled up."
        return "App summary prose."


def test_changelog_page_gets_an_llm_summary_over_recent_drift(tmp_path, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", sample_inventory)
    storage.append_changelog_entry(
        "homelab",
        "2026-08-22T02:00:00+00:00",
        [
            {
                "kind": "app_changed",
                "namespace": "demo",
                "app_name": "web",
                "details": ["replicas: 2 -> 3"],
            }
        ],
    )

    site_builder.regenerate_cluster_docs(storage, "homelab", llm=_FakeLLM())

    changelog_page = (storage.docs_dir / "homelab" / "changelog.md").read_text(encoding="utf-8")
    assert "## Summary (AI-generated)" in changelog_page
    assert "The web app scaled up." in changelog_page
    # The deterministic entry still renders in full below the prose.
    assert "replicas: 2 -> 3" in changelog_page


def test_changelog_page_without_drift_entries_skips_the_llm_summary(tmp_path, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", sample_inventory)

    site_builder.regenerate_cluster_docs(storage, "homelab", llm=_FakeLLM())

    changelog_page = (storage.docs_dir / "homelab" / "changelog.md").read_text(encoding="utf-8")
    assert "Summary (AI-generated)" not in changelog_page


def test_regenerate_cluster_docs_writes_changelog_page(tmp_path, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", sample_inventory)
    change = {
        "kind": "app_changed",
        "namespace": "demo",
        "app_name": "web",
        "details": ["replicas: 2 -> 3"],
    }
    storage.append_changelog_entry("homelab", "2026-08-22T01:00:00+00:00", [change])

    site_builder.regenerate_cluster_docs(storage, "homelab", llm=None)

    changelog_page = (storage.docs_dir / "homelab" / "changelog.md").read_text(encoding="utf-8")
    assert changelog_page.startswith("---\nhide:\n  - navigation\n---")
    assert "[homelab-autodoc](../index.md) · [homelab](index.md) · **Changelog**" in changelog_page
    assert "# homelab - Changelog" in changelog_page
    assert "replicas: 2 -> 3" in changelog_page
    assert '<span class="chip-link chip-link--active">Changelog</span>' in changelog_page


def test_regenerate_cluster_docs_changelog_page_without_entries(tmp_path, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", sample_inventory)

    site_builder.regenerate_cluster_docs(storage, "homelab", llm=None)

    changelog_page = (storage.docs_dir / "homelab" / "changelog.md").read_text(encoding="utf-8")
    assert "No drift detected yet." in changelog_page


def test_build_static_site_produces_html(tmp_path, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", sample_inventory)
    site_builder.regenerate_cluster_docs(storage, "homelab", llm=None)

    config_path = tmp_path / "mkdocs.yml"
    site_dir = tmp_path / "site"
    config_path.write_text(
        f"site_name: test\ndocs_dir: {storage.docs_dir}\nsite_dir: {site_dir}\n",
        encoding="utf-8",
    )

    site_builder.build_static_site(config_path)

    assert (site_dir / "index.html").exists()
    assert (site_dir / "homelab" / "demo" / "web" / "index.html").exists()


def test_rebuild_all_sites_regenerates_docs_and_builds_site(tmp_path, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", sample_inventory)
    site_dir = tmp_path / "site"
    config_path = tmp_path / "mkdocs.yml"
    config_path.write_text(
        f"site_name: test\ndocs_dir: {storage.docs_dir}\nsite_dir: {site_dir}\n",
        encoding="utf-8",
    )

    site_builder.rebuild_all_sites(storage, llm=None, mkdocs_config_path=config_path)

    assert (storage.docs_dir / "homelab" / "demo" / "web.md").exists()
    assert (site_dir / "homelab" / "demo" / "web" / "index.html").exists()


def test_deleting_the_last_cluster_and_rebuilding_drops_it_from_the_built_site(
    tmp_path, sample_inventory
):
    # Exercises the exact sequence routes_clusters.py's delete endpoint runs:
    # remove the data + generated docs, then rebuild_site_after_cluster_delete
    # (root index rewrite + one static build - deliberately NOT the full
    # rebuild_all_sites, which would also skip the build with zero clusters
    # left).
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", sample_inventory)
    site_dir = tmp_path / "site"
    config_path = tmp_path / "mkdocs.yml"
    config_path.write_text(
        f"site_name: test\ndocs_dir: {storage.docs_dir}\nsite_dir: {site_dir}\n",
        encoding="utf-8",
    )
    site_builder.rebuild_all_sites(storage, llm=None, mkdocs_config_path=config_path)
    assert (site_dir / "homelab" / "demo" / "web" / "index.html").exists()

    storage.delete_cluster("homelab")
    shutil.rmtree(storage.docs_dir / "homelab", ignore_errors=True)
    site_builder.rebuild_site_after_cluster_delete(storage, config_path)

    assert not (storage.docs_dir / "homelab").exists()
    assert not (site_dir / "homelab").exists()
    root_index_html = (site_dir / "index.html").read_text(encoding="utf-8")
    assert "homelab/index.md" not in root_index_html


def test_rebuild_all_sites_with_no_clusters_still_writes_a_root_index(tmp_path):
    # A fresh install (nothing registered yet) still needs a working root
    # index rather than a missing one. The actual mkdocs build is skipped in
    # this case (see the function's own docstring - it also runs eagerly at
    # server startup, where mkdocs_config_path may not point at a real file
    # yet in some environments) - a nonexistent config_path here proves the
    # build never even attempts to touch it.
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    config_path = tmp_path / "mkdocs.yml"

    site_builder.rebuild_all_sites(storage, llm=None, mkdocs_config_path=config_path)

    root_index = (storage.docs_dir / "index.md").read_text(encoding="utf-8")
    assert "[Open Admin →](/admin/)" in root_index
    assert not config_path.exists()


def test_regenerate_cluster_docs_survives_a_broken_llm(tmp_path, sample_inventory):
    class BrokenLLM:
        def generate(self, prompt: str) -> str:
            raise RuntimeError("boom")

    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", sample_inventory)

    site_builder.regenerate_cluster_docs(storage, "homelab", llm=BrokenLLM())

    app_page = (storage.docs_dir / "homelab" / "demo" / "web.md").read_text(encoding="utf-8")
    assert "# web" in app_page
    assert "nginx:1.25.3" in app_page


def test_root_index_carries_an_about_card_and_the_page_exists(tmp_path):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")

    pages.write_root_index(storage)

    root_index = (storage.docs_dir / "index.md").read_text(encoding="utf-8")
    about_page = (storage.docs_dir / "about.md").read_text(encoding="utf-8")
    assert "[Read →](about.md)" in root_index
    assert "# About this site" in about_page
    assert "hallucination boundary" in about_page
    assert "github.com/lukislp/homelab-autodoc" in about_page


def test_empty_governance_and_dependency_states_say_none_exist(tmp_path):
    # "collected yet" would wrongly suggest a collector gap - these objects
    # are always collected, so an empty page means none exist.
    from autodoc_core.models import App, NamespaceInventory

    bare = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-23T00:00:00+00:00",
        namespaces=[
            NamespaceInventory(
                name="empty-ns",
                apps=[App(name="web", kind="Deployment", replicas=1, ready_replicas=1)],
            )
        ],
    )
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", bare)

    site_builder.regenerate_cluster_docs(storage, "homelab", llm=None)

    governance = (storage.docs_dir / "homelab" / "empty-ns" / "resource-governance.md").read_text(
        encoding="utf-8"
    )
    dependencies = (storage.docs_dir / "homelab" / "empty-ns" / "dependencies.md").read_text(
        encoding="utf-8"
    )
    assert "No ResourceQuotas exist in this namespace." in governance
    assert "No LimitRanges exist in this namespace." in governance
    assert "No workload in this namespace references a ConfigMap or Secret." in dependencies
    assert "collected yet" not in governance
    assert "collected yet" not in dependencies


class _CountingLLM:
    """Records every prompt - the prose-cache tests assert on call COUNTS,
    which is the whole point of the cache."""

    def __init__(self):
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "Drift prose." if "configuration drift" in prompt else "App prose."


def _two_app_inventory(web_image: str = "nginx:1.25.3") -> ClusterInventory:
    from autodoc_core.models import App, Container, NamespaceInventory

    return ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-22T00:00:00+00:00",
        namespaces=[
            NamespaceInventory(
                name="demo",
                apps=[
                    App(
                        name="web",
                        kind="Deployment",
                        replicas=1,
                        ready_replicas=1,
                        containers=[Container(name="web", image=web_image)],
                    ),
                    App(
                        name="api",
                        kind="Deployment",
                        replicas=1,
                        ready_replicas=1,
                        containers=[Container(name="api", image="api:1.0.0")],
                    ),
                ],
            )
        ],
    )


def test_unchanged_inventory_rebuild_makes_zero_llm_calls(tmp_path):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", _two_app_inventory())
    storage.append_changelog_entry(
        "homelab",
        "2026-08-22T02:00:00+00:00",
        [{"kind": "app_changed", "namespace": "demo", "app_name": "web", "details": ["x"]}],
    )
    first = _CountingLLM()
    site_builder.regenerate_cluster_docs(storage, "homelab", llm=first)
    assert len(first.prompts) == 3  # two app summaries + one drift summary

    second = _CountingLLM()
    site_builder.regenerate_cluster_docs(storage, "homelab", llm=second)

    assert second.prompts == []
    # ...and the cached prose still renders on the pages.
    app_page = (storage.docs_dir / "homelab" / "demo" / "web.md").read_text(encoding="utf-8")
    changelog_page = (storage.docs_dir / "homelab" / "changelog.md").read_text(encoding="utf-8")
    assert "App prose." in app_page
    assert "Drift prose." in changelog_page


def test_changed_app_regenerates_only_its_own_summary(tmp_path):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", _two_app_inventory())
    site_builder.regenerate_cluster_docs(storage, "homelab", llm=_CountingLLM())

    storage.save_inventory("homelab", _two_app_inventory(web_image="nginx:1.26.0"))
    llm = _CountingLLM()
    site_builder.regenerate_cluster_docs(storage, "homelab", llm=llm)

    assert len(llm.prompts) == 1
    assert "nginx:1.26.0" in llm.prompts[0]


def test_failed_summary_is_not_cached_and_retried_next_rebuild(tmp_path):
    class _BrokenLLM:
        def generate(self, prompt: str) -> str:
            raise RuntimeError("rate limited")

    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", _two_app_inventory())
    site_builder.regenerate_cluster_docs(storage, "homelab", llm=_BrokenLLM())

    llm = _CountingLLM()
    site_builder.regenerate_cluster_docs(storage, "homelab", llm=llm)

    assert len(llm.prompts) == 2  # both summaries retried, nothing pinned as a permanent gap


def test_deleted_app_is_pruned_from_the_prose_cache(tmp_path):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", _two_app_inventory())
    site_builder.regenerate_cluster_docs(storage, "homelab", llm=_CountingLLM())
    assert set(storage.load_prose_cache("homelab")["apps"]) == {"demo/web", "demo/api"}

    inventory = _two_app_inventory()
    trimmed = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-22T01:00:00+00:00",
        namespaces=[
            type(inventory.namespaces[0])(name="demo", apps=[inventory.namespaces[0].apps[0]])
        ],
    )
    storage.save_inventory("homelab", trimmed)
    site_builder.regenerate_cluster_docs(storage, "homelab", llm=_CountingLLM())

    assert set(storage.load_prose_cache("homelab")["apps"]) == {"demo/web"}


def test_topology_pages_carry_both_responsive_variants(tmp_path, sample_inventory):
    # Desktop gets the sideways-spread diagram, phones the classic stack -
    # both pre-rendered, a CSS breakpoint picks one. No tile grid.
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", sample_inventory)

    site_builder.regenerate_cluster_docs(storage, "homelab", llm=None)

    cluster_page = (storage.docs_dir / "homelab" / "topology.md").read_text(encoding="utf-8")
    ns_page = (storage.docs_dir / "homelab" / "demo" / "topology.md").read_text(encoding="utf-8")
    for page in (cluster_page, ns_page):
        assert page.count("```mermaid") == 2
        assert 'class="topology-variant topology-variant--wide"' in page
        assert 'class="topology-variant topology-variant--stacked"' in page
    assert "topology-grid" not in cluster_page

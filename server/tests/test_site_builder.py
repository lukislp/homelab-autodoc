from __future__ import annotations

from autodoc_core.models import ClusterInventory

from autodoc_server.logic import site_builder
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
    cluster_index = (storage.docs_dir / "homelab" / "index.md").read_text(encoding="utf-8")
    cluster_topology = (storage.docs_dir / "homelab" / "topology.md").read_text(encoding="utf-8")
    nodes_page = (storage.docs_dir / "homelab" / "nodes.md").read_text(encoding="utf-8")
    root_index = (storage.docs_dir / "index.md").read_text(encoding="utf-8")

    assert "# web" in app_page
    assert "nginx:1.25.3" in app_page
    assert "[web](web.md)" in namespace_index
    assert "[Topology](topology.md)" in namespace_index
    assert "[Dependencies](dependencies.md)" in namespace_index
    assert "# demo - Topology" in namespace_topology
    assert "```mermaid" in namespace_topology
    assert "# demo - Dependencies" in namespace_dependencies
    assert "| Secret | web-secrets | web (env) |" in namespace_dependencies
    assert "[demo](demo/index.md)" in cluster_index
    assert "[Topology](topology.md)" in cluster_index
    assert "[Nodes](nodes.md)" in cluster_index
    assert "[Changelog](changelog.md)" in cluster_index
    assert "# homelab - Topology" in cluster_topology
    assert "# homelab - Nodes" in nodes_page
    assert "pi-node-1" in nodes_page
    assert "arm64" in nodes_page
    assert "[Open Admin →](/admin/)" in root_index
    assert "[Browse →](homelab/index.md)" in root_index
    assert '<div class="grid cards" markdown>' in root_index


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

    site_builder._write_root_index(storage)

    root_index = (storage.docs_dir / "index.md").read_text(encoding="utf-8")
    assert "[Open Admin →](/admin/)" in root_index


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
    assert "# homelab - Changelog" in changelog_page
    assert "replicas: 2 -> 3" in changelog_page


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


def test_rebuild_all_sites_no_clusters_is_a_noop(tmp_path):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    config_path = tmp_path / "mkdocs.yml"

    site_builder.rebuild_all_sites(storage, llm=None, mkdocs_config_path=config_path)

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

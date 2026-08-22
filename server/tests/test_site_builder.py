from __future__ import annotations

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
    cluster_index = (storage.docs_dir / "homelab" / "index.md").read_text(encoding="utf-8")
    root_index = (storage.docs_dir / "index.md").read_text(encoding="utf-8")

    assert "# web" in app_page
    assert "nginx:1.25.3" in app_page
    assert "[web](web.md)" in namespace_index
    assert "[demo](demo/index.md)" in cluster_index
    assert "[Changelog](changelog.md)" in cluster_index
    assert "[homelab](homelab/index.md)" in root_index


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

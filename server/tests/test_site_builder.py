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
    assert "[homelab](homelab/index.md)" in root_index


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

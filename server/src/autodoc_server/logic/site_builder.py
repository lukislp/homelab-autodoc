"""Stored inventory -> MkDocs source tree -> built static site. No web framework import here."""

from __future__ import annotations

from pathlib import Path

from autodoc_core.models import ClusterInventory
from autodoc_generator import render
from autodoc_generator.llm import LLMClient
from autodoc_generator.prose import generate_summary

from .storage import Storage


def regenerate_cluster_docs(storage: Storage, cluster_name: str, llm: LLMClient | None) -> None:
    inventory = storage.load_inventory(cluster_name)
    cluster_dir = storage.docs_dir / cluster_name

    for namespace in inventory.namespaces:
        namespace_dir = cluster_dir / namespace.name
        namespace_dir.mkdir(parents=True, exist_ok=True)
        namespace_dir.joinpath("index.md").write_text(
            render.render_namespace_index(namespace), encoding="utf-8"
        )
        for app in namespace.apps:
            summary = generate_summary(app, llm) if llm else None
            namespace_dir.joinpath(f"{app.name}.md").write_text(
                render.render_app_page(app, namespace.name, summary), encoding="utf-8"
            )

    _write_cluster_index(storage, cluster_name, inventory)
    _write_root_index(storage)


def _write_cluster_index(storage: Storage, cluster_name: str, inventory: ClusterInventory) -> None:
    lines = [f"# {cluster_name}", "", "| Namespace | Apps |", "|---|---|"]
    for namespace in sorted(inventory.namespaces, key=lambda n: n.name):
        lines.append(f"| [{namespace.name}]({namespace.name}/index.md) | {len(namespace.apps)} |")
    (storage.docs_dir / cluster_name / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _write_root_index(storage: Storage) -> None:
    lines = ["# homelab-autodoc", "", "| Cluster |", "|---|"]
    for cluster_name in storage.list_clusters():
        lines.append(f"| [{cluster_name}]({cluster_name}/index.md) |")
    storage.docs_dir.mkdir(parents=True, exist_ok=True)
    (storage.docs_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def build_static_site(mkdocs_config_path: Path) -> None:
    from mkdocs.commands.build import build
    from mkdocs.config import load_config

    build(load_config(str(mkdocs_config_path)))

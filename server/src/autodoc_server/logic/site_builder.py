"""Stored inventory -> MkDocs source tree -> built static site. No web framework import here."""

from __future__ import annotations

import logging
from pathlib import Path

from autodoc_core.diff import Change
from autodoc_core.models import App, ClusterInventory, NamespaceInventory
from autodoc_generator import changelog as changelog_render
from autodoc_generator import diagrams, facts, render
from autodoc_generator.llm import LLMClient
from autodoc_generator.prose import generate_summary

from .storage import Storage

logger = logging.getLogger(__name__)


def regenerate_cluster_docs(storage: Storage, cluster_name: str, llm: LLMClient | None) -> None:
    inventory = storage.load_inventory(cluster_name)
    cluster_dir = storage.docs_dir / cluster_name
    cluster_dir.mkdir(parents=True, exist_ok=True)

    for namespace in inventory.namespaces:
        namespace_dir = cluster_dir / namespace.name
        namespace_dir.mkdir(parents=True, exist_ok=True)
        namespace_dir.joinpath("index.md").write_text(
            render.render_namespace_index(namespace), encoding="utf-8"
        )
        for app in namespace.apps:
            summary = _safe_generate_summary(app, llm) if llm else None
            namespace_dir.joinpath(f"{app.name}.md").write_text(
                render.render_app_page(app, namespace.name, summary), encoding="utf-8"
            )
        _write_namespace_diagram(storage, cluster_name, namespace)

    _write_cluster_index(storage, cluster_name, inventory)
    _write_cluster_diagram(storage, cluster_name, inventory)
    _write_nodes_page(storage, cluster_name, inventory)
    _write_changelog_page(storage, cluster_name)
    _write_root_index(storage)


def _safe_generate_summary(app: App, llm: LLMClient) -> str | None:
    """Facts and diagrams always render regardless - prose is the only optional
    part of the hallucination boundary, so a broken LLM call (bad params, auth,
    rate limit, network) must degrade to no summary, never block doc generation
    or crash server startup (rebuild_all_sites calls this at import time).
    """
    try:
        return generate_summary(app, llm)
    except Exception:
        logger.warning("LLM summary generation failed for app %r, continuing without it", app.name)
        return None


def _write_cluster_index(storage: Storage, cluster_name: str, inventory: ClusterInventory) -> None:
    lines = [
        f"# {cluster_name}",
        "",
        "[Topology](topology.md) · [Nodes](nodes.md) · [Changelog](changelog.md)",
        "",
        "| Namespace | Apps |",
        "|---|---|",
    ]
    for namespace in sorted(inventory.namespaces, key=lambda n: n.name):
        lines.append(f"| [{namespace.name}]({namespace.name}/index.md) | {len(namespace.apps)} |")
    (storage.docs_dir / cluster_name / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _write_namespace_diagram(
    storage: Storage, cluster_name: str, namespace: NamespaceInventory
) -> None:
    diagram = diagrams.build_namespace_diagram(namespace)
    page = f"# {namespace.name} - Topology\n\n```mermaid\n{diagram}\n```"
    (storage.docs_dir / cluster_name / namespace.name / "topology.md").write_text(
        page, encoding="utf-8"
    )


def _write_cluster_diagram(
    storage: Storage, cluster_name: str, inventory: ClusterInventory
) -> None:
    diagram = diagrams.build_cluster_diagram(inventory)
    page = f"# {cluster_name} - Topology\n\n```mermaid\n{diagram}\n```"
    (storage.docs_dir / cluster_name / "topology.md").write_text(page, encoding="utf-8")


def _write_nodes_page(storage: Storage, cluster_name: str, inventory: ClusterInventory) -> None:
    table = facts.node_specs_table(inventory.nodes)
    lines = [f"# {cluster_name} - Nodes", ""]
    lines.append(table if table else "No node data collected yet.")
    (storage.docs_dir / cluster_name / "nodes.md").write_text("\n".join(lines), encoding="utf-8")


def _write_changelog_page(storage: Storage, cluster_name: str) -> None:
    entries = storage.load_changelog_entries(cluster_name)
    rendered = [
        changelog_render.render_changelog_entry(
            entry["collected_at"], [Change(**c) for c in entry["changes"]]
        )
        for entry in reversed(entries)
    ]
    page = changelog_render.render_changelog_page(cluster_name, rendered)
    (storage.docs_dir / cluster_name / "changelog.md").write_text(page, encoding="utf-8")


def _write_root_index(storage: Storage) -> None:
    # Material's "grid cards" layout (attr_list + md_in_html, see mkdocs.yml) - plain
    # Markdown inside a styled div, no icon shortcodes so no extra extension is needed.
    lines = [
        "# homelab-autodoc",
        "",
        '<div class="grid cards" markdown>',
        "",
        "-   __Admin__",
        "",
        "    ---",
        "",
        "    Manage cluster registrations and server setup.",
        "",
        "    [Open Admin →](/admin/)",
        "",
    ]
    for cluster_name in storage.list_clusters():
        lines += [
            f"-   __{cluster_name}__",
            "",
            "    ---",
            "",
            f"    Living documentation for the `{cluster_name}` cluster.",
            "",
            f"    [Browse →]({cluster_name}/index.md)",
            "",
        ]
    lines.append("</div>")
    storage.docs_dir.mkdir(parents=True, exist_ok=True)
    (storage.docs_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def rebuild_all_sites(storage: Storage, llm: LLMClient | None, mkdocs_config_path: Path) -> None:
    """Regenerates every cluster's docs from the persisted inventory and rebuilds
    the static site. Meant to run on server startup: docs_dir/site_dir live on
    the container's ephemeral filesystem, not a persistent volume, so a pod
    restart wipes them - this makes recovery instant instead of waiting for the
    next inventory push.
    """
    clusters = storage.list_clusters()
    for cluster_name in clusters:
        regenerate_cluster_docs(storage, cluster_name, llm)
    if clusters:
        build_static_site(mkdocs_config_path)


def build_static_site(mkdocs_config_path: Path) -> None:
    from mkdocs.commands.build import build
    from mkdocs.config import load_config

    build(load_config(str(mkdocs_config_path)))

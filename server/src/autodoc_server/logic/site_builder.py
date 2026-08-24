"""Stored inventory -> MkDocs source tree -> built static site. No web
framework import here. This module is the thin ORCHESTRATOR: which pages a
rebuild produces and in what order, plus the prose-cache lifecycle - every
actual page lives in logic/pages/, the caching in logic/prose_cache.py.
"""

from __future__ import annotations

from pathlib import Path

from autodoc_generator.llm import LLMClient
from autodoc_generator.render import render_app_page, render_namespace_index

from . import drift, pages, prose_cache
from .storage import Storage


def regenerate_cluster_docs(storage: Storage, cluster_name: str, llm: LLMClient | None) -> None:
    inventory = storage.load_inventory(cluster_name)
    cluster_dir = storage.docs_dir / cluster_name
    cluster_dir.mkdir(parents=True, exist_ok=True)
    last_changes = drift.last_run_changes(storage, cluster_name)

    # Prompt-hash memoization for all LLM prose: a prompt is a pure function of
    # exactly the facts the prose is allowed to mention, so an identical prompt
    # means regeneration could only restate the same facts - pure cost, skipped.
    # Writing back only the entries touched this rebuild prunes deleted apps
    # for free. This is what keeps a push (and the import-time rebuild of every
    # site on server start) from paying one LLM call per app when almost
    # nothing changed.
    old_cache = storage.load_prose_cache(cluster_name)
    new_cache: dict = {"apps": {}, "drift": None}

    for namespace in inventory.namespaces:
        namespace_dir = cluster_dir / namespace.name
        namespace_dir.mkdir(parents=True, exist_ok=True)
        namespace_drift = drift.drift_count(last_changes, namespace.name)
        namespace_dir.joinpath("index.md").write_text(
            render_namespace_index(namespace, cluster_name, namespace_drift),
            encoding="utf-8",
        )
        for app in namespace.apps:
            summary = (
                prose_cache.summary_with_cache(
                    app, namespace.name, llm, old_cache.get("apps", {}), new_cache["apps"]
                )
                if llm
                else None
            )
            namespace_dir.joinpath(f"{app.name}.md").write_text(
                render_app_page(app, namespace, cluster_name, summary), encoding="utf-8"
            )
        pages.write_namespace_diagram(storage, cluster_name, namespace)
        pages.write_namespace_network_page(storage, cluster_name, namespace, inventory)
        pages.write_namespace_connections_page(storage, cluster_name, namespace, inventory)
        pages.write_namespace_dependencies_page(storage, cluster_name, namespace)
        pages.write_namespace_resource_governance_page(storage, cluster_name, namespace)

    pages.write_cluster_index(storage, cluster_name, inventory, drift.drift_count(last_changes))
    pages.write_cluster_diagram(storage, cluster_name, inventory)
    pages.write_cluster_network_page(storage, cluster_name, inventory)
    pages.write_cluster_connections_page(storage, cluster_name, inventory)
    pages.write_findings_page(storage, cluster_name, inventory)
    pages.write_backups_page(storage, cluster_name, inventory)
    pages.write_images_page(storage, cluster_name, inventory)
    pages.write_storage_classes_page(storage, cluster_name, inventory)
    pages.write_nodes_page(storage, cluster_name, inventory)
    pages.write_changelog_page(storage, cluster_name, llm, old_cache.get("drift"), new_cache)
    pages.write_root_index(storage)
    storage.save_prose_cache(cluster_name, new_cache)


def rebuild_site_after_cluster_delete(storage: Storage, mkdocs_config_path: Path) -> None:
    """The cheap counterpart to rebuild_all_sites for the delete endpoint
    (routes_clusters.py): every remaining cluster's generated pages are still
    on disk and unchanged (written at startup and on every push), and the
    deleted cluster's pages are already removed by the caller - only the root
    index still references the deleted cluster. Rewriting it plus one static
    build is all that's needed. A full rebuild_all_sites here would redo the
    LLM prose for every remaining cluster; in production that took close to a
    minute, long enough for the admin to reload the docs index mid-rebuild and
    see the deleted cluster's card still there (and for a reverse proxy to
    time the DELETE request out).
    """
    pages.write_root_index(storage)
    build_static_site(mkdocs_config_path)


def rebuild_all_sites(storage: Storage, llm: LLMClient | None, mkdocs_config_path: Path) -> None:
    """Regenerates every cluster's docs from the persisted inventory and rebuilds
    the static site. Meant to run on server startup: docs_dir/site_dir live on
    the container's ephemeral filesystem, not a persistent volume, so a pod
    restart wipes them - this makes recovery instant instead of waiting for the
    next inventory push.

    The root index is always rewritten, even with zero clusters (a fresh
    install, or the last cluster having just been deleted) - cheap and always
    correct, no mkdocs_config_path dependency. build_static_site is still
    skipped in that case: this function runs eagerly at server startup
    (app.py module import), where mkdocs_config_path may not point at a real
    file yet in some environments, and there is nothing to build anyway.
    Callers that need the static site guaranteed rebuilt after dropping to
    zero clusters (routes_clusters.py's delete endpoint) call
    build_static_site themselves afterward, the same way push_inventory
    already does.
    """
    clusters = storage.list_clusters()
    for cluster_name in clusters:
        regenerate_cluster_docs(storage, cluster_name, llm)
    pages.write_root_index(storage)
    if clusters:
        build_static_site(mkdocs_config_path)


def build_static_site(mkdocs_config_path: Path) -> None:
    from mkdocs.commands.build import build
    from mkdocs.config import load_config

    build(load_config(str(mkdocs_config_path)))

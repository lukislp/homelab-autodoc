"""Stored inventory -> MkDocs source tree -> built static site. No web framework import here."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from autodoc_core.diff import Change
from autodoc_core.models import App, ClusterInventory, NamespaceInventory
from autodoc_generator import changelog as changelog_render
from autodoc_generator import diagrams, facts, findings, navigation, network, render
from autodoc_generator.llm import LLMClient
from autodoc_generator.prose import (
    build_drift_prompt,
    build_prompt,
    generate_drift_summary,
    generate_summary,
)

from .about import ABOUT_PAGE
from .storage import Storage

logger = logging.getLogger(__name__)

# Every generated page hides Material's global nav tree in favor of a
# breadcrumb (every page) plus, on namespace-scoped content pages, a compact
# sidebar scoped to just that namespace - see navigation.py and
# _namespace_content_page/_cluster_content_page below.
_HIDE_NAV_FRONTMATTER = "---\nhide:\n  - navigation\n---"


def _last_run_changes(storage: Storage, cluster_name: str) -> list[dict]:
    """The most recent collector run's drift, or [] if none yet/no changelog
    entries exist - the "Drift, Last Run" stat chip on the cluster and
    namespace hub pages, and _drift_count below, both read from this.
    """
    entries = storage.load_changelog_entries(cluster_name)
    return entries[-1]["changes"] if entries else []


def _drift_count(last_changes: list[dict], namespace_name: str | None = None) -> int:
    if namespace_name is None:
        return len(last_changes)
    return sum(1 for c in last_changes if c["namespace"] == namespace_name)


def regenerate_cluster_docs(storage: Storage, cluster_name: str, llm: LLMClient | None) -> None:
    inventory = storage.load_inventory(cluster_name)
    cluster_dir = storage.docs_dir / cluster_name
    cluster_dir.mkdir(parents=True, exist_ok=True)
    last_changes = _last_run_changes(storage, cluster_name)

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
        namespace_drift = _drift_count(last_changes, namespace.name)
        namespace_dir.joinpath("index.md").write_text(
            render.render_namespace_index(namespace, cluster_name, namespace_drift),
            encoding="utf-8",
        )
        for app in namespace.apps:
            summary = (
                _summary_with_cache(
                    app, namespace.name, llm, old_cache.get("apps", {}), new_cache["apps"]
                )
                if llm
                else None
            )
            namespace_dir.joinpath(f"{app.name}.md").write_text(
                render.render_app_page(app, namespace, cluster_name, summary), encoding="utf-8"
            )
        _write_namespace_diagram(storage, cluster_name, namespace)
        _write_namespace_network_page(storage, cluster_name, namespace, inventory)
        _write_namespace_dependencies_page(storage, cluster_name, namespace)
        _write_namespace_resource_governance_page(storage, cluster_name, namespace)

    _write_cluster_index(storage, cluster_name, inventory, _drift_count(last_changes))
    _write_cluster_diagram(storage, cluster_name, inventory)
    _write_cluster_network_page(storage, cluster_name, inventory)
    _write_findings_page(storage, cluster_name, inventory)
    _write_backups_page(storage, cluster_name, inventory)
    _write_images_page(storage, cluster_name, inventory)
    _write_storage_classes_page(storage, cluster_name, inventory)
    _write_nodes_page(storage, cluster_name, inventory)
    _write_changelog_page(storage, cluster_name, llm, old_cache.get("drift"), new_cache)
    _write_root_index(storage)
    storage.save_prose_cache(cluster_name, new_cache)


def _prompt_sha(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _summary_with_cache(
    app: App, namespace_name: str, llm: LLMClient, cached_apps: dict, new_apps: dict
) -> str | None:
    """Reuse the cached summary when the app's prompt is byte-identical to the
    one its cached prose was generated from. Only successful generations are
    cached: a failed LLM call leaves no entry, so it is retried on the next
    rebuild instead of pinning a permanent gap.
    """
    key = f"{namespace_name}/{app.name}"
    prompt_sha = _prompt_sha(build_prompt(app))
    cached = cached_apps.get(key)
    if cached and cached.get("prompt_sha") == prompt_sha:
        new_apps[key] = cached
        return cached.get("summary")
    summary = _safe_generate_summary(app, llm)
    if summary is not None:
        new_apps[key] = {"prompt_sha": prompt_sha, "summary": summary}
    return summary


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


def _cluster_content_page(
    cluster_name: str, current: str, heading: str, body: str, show_heading: bool = True
) -> str:
    """Shared shape for cluster-scoped content pages (topology, findings,
    images, storage classes, nodes): front matter + breadcrumb + the same
    chip row the cluster hub shows, marking `current` inert. The chips sit
    ABOVE the content: they are navigation, and below a long table (or the
    viewport-sized topology box) they were effectively invisible - on the
    topology page they were also the one element still forcing a scroll.

    show_heading=False drops the visible H1 (the topology page: breadcrumb
    and active chip already say where you are, and the heading's height came
    straight out of the diagram's viewport budget); the heading then goes
    into the front matter as `title:` so the browser tab and search keep it.
    """
    crumb = navigation.breadcrumb(cluster_name, current=current)
    front_matter = (
        _HIDE_NAV_FRONTMATTER
        if show_heading
        else f'---\ntitle: "{heading}"\nhide:\n  - navigation\n---'
    )
    lines = [
        front_matter,
        "",
        f'<p class="ns-breadcrumb" markdown>{crumb}</p>',
        "",
        navigation.cluster_page_links(current),
        "",
    ]
    if show_heading:
        lines += [f"# {heading}", ""]
    lines.append(body)
    return "\n".join(lines)


def _namespace_content_page(
    cluster_name: str, namespace: NamespaceInventory, current: str, heading: str, body: str
) -> str:
    """Shared shape for namespace-scoped content pages (topology, dependencies,
    resource governance): front matter + breadcrumb + the same compact,
    namespace-scoped sidebar app pages use (see navigation.py).
    """
    crumb = navigation.breadcrumb(cluster_name, namespace.name, current=current)
    lines = [
        _HIDE_NAV_FRONTMATTER,
        "",
        f'<p class="ns-breadcrumb" markdown>{crumb}</p>',
        "",
        '<div class="ns-layout" markdown>',
        '<div class="ns-sidenav" markdown>',
        "",
        navigation.namespace_sidenav(namespace, current),
        "",
        "</div>",
        '<div class="ns-content" markdown>',
        "",
        f"# {heading}",
        "",
        body,
        "",
        "</div>",
        "</div>",
    ]
    return "\n".join(lines)


def _write_cluster_index(
    storage: Storage, cluster_name: str, inventory: ClusterInventory, drift_count: int
) -> None:
    # Hub page: namespaces are shown as cards (same "grid cards" layout as the
    # root index - attr_list + md_in_html, see mkdocs.yml), not a table - a
    # hub is a "which of these" moment, nothing to scan yet. The card's own
    # title is the link (no separate "Browse ->" line) - unlike the root
    # index's Admin/cluster tiles, which stay as they were.
    lines = [
        _HIDE_NAV_FRONTMATTER,
        "",
        f'<p class="ns-breadcrumb" markdown>{navigation.breadcrumb(cluster_name)}</p>',
        "",
        f"# {cluster_name}",
        "",
        facts.cluster_stat_chips(
            inventory,
            drift_count,
            findings_count=len(findings.evaluate_cluster(inventory)),
            accepted_count=len(findings.evaluate_cluster_accepted(inventory)),
        ),
        "",
        facts.collection_freshness(inventory.collected_at),
        "",
        '<p class="section-label">Namespaces</p>',
        "",
        '<div class="grid cards" markdown>',
        "",
    ]
    for namespace in sorted(inventory.namespaces, key=lambda n: n.name):
        app_count = len(namespace.apps)
        all_ready = all(facts.app_is_fully_ready(app) for app in namespace.apps)
        dot_class = "ns-dot ns-dot--ok" if all_ready else "ns-dot ns-dot--warn"
        lines += [
            f'-   [__{namespace.name}__ <span class="{dot_class}"></span>]'
            f"({namespace.name}/index.md)",
            "",
            f"    {app_count} app{'' if app_count == 1 else 's'}",
            "",
        ]
    lines += [
        "</div>",
        "",
        '<p class="section-label">Cluster</p>',
        "",
        navigation.cluster_page_links(),
    ]
    (storage.docs_dir / cluster_name / "index.md").write_text("\n".join(lines), encoding="utf-8")


def _write_namespace_diagram(
    storage: Storage, cluster_name: str, namespace: NamespaceInventory
) -> None:
    diagram = diagrams.build_namespace_diagram(namespace)
    page = _namespace_content_page(
        cluster_name,
        namespace,
        "topology",
        f"{namespace.name} - Topology",
        f"```mermaid\n{diagram}\n```",
    )
    (storage.docs_dir / cluster_name / namespace.name / "topology.md").write_text(
        page, encoding="utf-8"
    )


def _write_namespace_dependencies_page(
    storage: Storage, cluster_name: str, namespace: NamespaceInventory
) -> None:
    table = facts.dependency_usage_table(namespace)
    body = table if table else "No workload in this namespace references a ConfigMap or Secret."
    page = _namespace_content_page(
        cluster_name, namespace, "dependencies", f"{namespace.name} - Dependencies", body
    )
    (storage.docs_dir / cluster_name / namespace.name / "dependencies.md").write_text(
        page, encoding="utf-8"
    )


def _write_namespace_resource_governance_page(
    storage: Storage, cluster_name: str, namespace: NamespaceInventory
) -> None:
    quotas_table = facts.resource_quotas_table(namespace)
    limits_table = facts.limit_ranges_table(namespace)
    body = "\n\n".join(
        [
            "## Resource Quotas",
            quotas_table if quotas_table else "No ResourceQuotas exist in this namespace.",
            "## Limit Ranges",
            limits_table if limits_table else "No LimitRanges exist in this namespace.",
        ]
    )
    page = _namespace_content_page(
        cluster_name,
        namespace,
        "resource-governance",
        f"{namespace.name} - Resource Governance",
        body,
    )
    (storage.docs_dir / cluster_name / namespace.name / "resource-governance.md").write_text(
        page, encoding="utf-8"
    )


def _write_cluster_diagram(
    storage: Storage, cluster_name: str, inventory: ClusterInventory
) -> None:
    diagram = diagrams.build_cluster_diagram(inventory)
    page = _cluster_content_page(
        cluster_name,
        "topology",
        f"{cluster_name} - Topology",
        f"```mermaid\n{diagram}\n```",
        show_heading=False,
    )
    (storage.docs_dir / cluster_name / "topology.md").write_text(page, encoding="utf-8")


def _write_namespace_network_page(
    storage: Storage, cluster_name: str, namespace: NamespaceInventory, inventory: ClusterInventory
) -> None:
    """The namespace's allowed-traffic view - deliberately its own page next
    to (not inside) Topology: topology shows what exists, this shows what may
    talk to what, resolved from the collected NetworkPolicies.
    """
    diagram = network.build_namespace_network_diagram(namespace, inventory)
    body = "\n\n".join(
        [
            "Every allowed ingress flow into this namespace's apps, resolved from the "
            "collected NetworkPolicies. Solid edges are explicit policy allowances "
            "(labeled with their ports, unlabeled = all ports); dashed edges mark apps "
            "no policy selects - unrestricted by Kubernetes default.",
            f"```mermaid\n{diagram}\n```",
        ]
    )
    page = _namespace_content_page(
        cluster_name, namespace, "network", f"{namespace.name} - Network", body
    )
    (storage.docs_dir / cluster_name / namespace.name / "network.md").write_text(
        page, encoding="utf-8"
    )


def _write_cluster_network_page(
    storage: Storage, cluster_name: str, inventory: ClusterInventory
) -> None:
    diagram = network.build_cluster_network_diagram(inventory)
    body = "\n\n".join(
        [
            "Which namespaces (and generic actors) may reach into which - every edge "
            "aggregates the allowed ingress flows between two namespaces, labeled with "
            "how many app-level flows it summarizes. Flows WITHIN a namespace live on "
            "that namespace's own Network page.",
            f"```mermaid\n{diagram}\n```",
        ]
    )
    page = _cluster_content_page(cluster_name, "network", f"{cluster_name} - Network", body)
    (storage.docs_dir / cluster_name / "network.md").write_text(page, encoding="utf-8")


def _write_findings_page(storage: Storage, cluster_name: str, inventory: ClusterInventory) -> None:
    table = findings.cluster_findings_table(inventory)
    parts = [
        "Deterministic best-practice checks over the collected inventory - "
        "review hints, not failures. Every finding links back to the app it fired on.",
        table if table else "No open findings - every collected fact passed all checks.",
    ]
    accepted_table = findings.cluster_accepted_findings_table(inventory)
    if accepted_table:
        parts += [
            "## Accepted Findings",
            "Acknowledged in the workload's own manifest via "
            "`autodoc.homelab/accept-<rule>` annotations - deliberate, reviewed decisions "
            "with a documented reason, listed here so they stay visible without counting "
            "as open items.",
            accepted_table,
        ]
    body = "\n\n".join(parts)
    page = _cluster_content_page(cluster_name, "findings", f"{cluster_name} - Findings", body)
    (storage.docs_dir / cluster_name / "findings.md").write_text(page, encoding="utf-8")


def _write_backups_page(storage: Storage, cluster_name: str, inventory: ClusterInventory) -> None:
    """Offsite backup posture straight from the collected Velero/CNPG custom
    resources. `backups is None` means this run could not gather it (older
    collector, denied RBAC) - rendered as exactly that, never as "no backups".
    """
    backups = inventory.backups
    if backups is None:
        body = (
            "Backup posture was not collected on the last run - an older collector, or its "
            "RBAC does not grant reading the Velero/CNPG custom resources. Unknown renders "
            "as unknown, never as an empty backup story."
        )
    else:
        sections = [
            "Offsite backup posture as collected from the Velero and CNPG custom resources - "
            "status facts only (schedules, phases, timestamps); the data itself lives in "
            "object storage.",
            "## Velero Schedules",
            facts.velero_schedules_table(backups) or "No Velero Schedules exist in this cluster.",
            "## Recent Velero Backups",
            facts.velero_backups_table(backups) or "No Velero backups recorded yet.",
            "## CNPG Scheduled Backups",
            facts.cnpg_scheduled_backups_table(backups) or "No CNPG ScheduledBackups exist.",
            "## Recent CNPG Backups",
            facts.cnpg_backups_table(backups) or "No CNPG backups recorded yet.",
        ]
        body = "\n\n".join(sections)
    page = _cluster_content_page(cluster_name, "backups", f"{cluster_name} - Backups", body)
    (storage.docs_dir / cluster_name / "backups.md").write_text(page, encoding="utf-8")


def _write_images_page(storage: Storage, cluster_name: str, inventory: ClusterInventory) -> None:
    table = facts.cluster_images_table(inventory)
    body = table if table else "No container images collected yet."
    page = _cluster_content_page(cluster_name, "images", f"{cluster_name} - Images", body)
    (storage.docs_dir / cluster_name / "images.md").write_text(page, encoding="utf-8")


def _write_storage_classes_page(
    storage: Storage, cluster_name: str, inventory: ClusterInventory
) -> None:
    table = facts.storage_classes_table(inventory.storage_classes)
    body = table if table else "No StorageClasses exist in this cluster."
    page = _cluster_content_page(
        cluster_name, "storage-classes", f"{cluster_name} - Storage Classes", body
    )
    (storage.docs_dir / cluster_name / "storage-classes.md").write_text(page, encoding="utf-8")


def _write_nodes_page(storage: Storage, cluster_name: str, inventory: ClusterInventory) -> None:
    table = facts.node_specs_table(inventory.nodes)
    body = table if table else "No node data collected yet."
    page = _cluster_content_page(cluster_name, "nodes", f"{cluster_name} - Nodes", body)
    (storage.docs_dir / cluster_name / "nodes.md").write_text(page, encoding="utf-8")


# How many of the most recent collector runs feed the changelog's LLM
# summary - enough for a "what happened lately" paragraph, small enough that
# one prompt never grows with the changelog's full history.
_DRIFT_SUMMARY_RECENT_RUNS = 5


def _safe_generate_drift_summary(
    cluster_name: str, recent: list[tuple[str, list[Change]]], llm: LLMClient
) -> str | None:
    """Same degradation contract as _safe_generate_summary: the deterministic
    changelog entries always render regardless, prose is optional.
    """
    try:
        return generate_drift_summary(recent, llm)
    except Exception:
        logger.warning(
            "LLM drift summary failed for cluster %r, continuing without it", cluster_name
        )
        return None


def _write_changelog_page(
    storage: Storage,
    cluster_name: str,
    llm: LLMClient | None,
    cached_drift: dict | None = None,
    new_cache: dict | None = None,
) -> None:
    entries = storage.load_changelog_entries(cluster_name)
    rendered = [
        changelog_render.render_changelog_entry(
            entry["collected_at"], [Change(**c) for c in entry["changes"]]
        )
        for entry in reversed(entries)
    ]
    summary = None
    recent = [
        (entry["collected_at"], [Change(**c) for c in entry["changes"]])
        for entry in entries[-_DRIFT_SUMMARY_RECENT_RUNS:]
        if entry["changes"]
    ]
    if llm and recent:
        # Same prompt-hash memoization as the app summaries: a push without
        # drift (and the import-time rebuild on every server start) leaves the
        # recent-runs window unchanged, so the summary would come out of the
        # same facts.
        prompt_sha = _prompt_sha(build_drift_prompt(recent))
        if cached_drift and cached_drift.get("prompt_sha") == prompt_sha:
            summary = cached_drift.get("summary")
            if new_cache is not None:
                new_cache["drift"] = cached_drift
        else:
            summary = _safe_generate_drift_summary(cluster_name, recent, llm)
            if summary is not None and new_cache is not None:
                new_cache["drift"] = {"prompt_sha": prompt_sha, "summary": summary}
    # render_changelog_page already builds its own "# {cluster} - Changelog"
    # heading, so this only prepends front matter + breadcrumb + the chip row
    # rather than going through _cluster_content_page (which would add a
    # second heading). Chips sit above the content, same as every other
    # cluster page - below a long changelog they were effectively invisible.
    page = "\n".join(
        [
            _HIDE_NAV_FRONTMATTER,
            "",
            f'<p class="ns-breadcrumb" markdown>'
            f"{navigation.breadcrumb(cluster_name, current='changelog')}</p>",
            "",
            navigation.cluster_page_links("changelog"),
            "",
            changelog_render.render_changelog_page(cluster_name, rendered, summary),
        ]
    )
    (storage.docs_dir / cluster_name / "changelog.md").write_text(page, encoding="utf-8")


def _write_root_index(storage: Storage) -> None:
    # Material's "grid cards" layout (attr_list + md_in_html, see mkdocs.yml) - plain
    # Markdown inside a styled div, no icon shortcodes so no extra extension is needed.
    lines = [
        _HIDE_NAV_FRONTMATTER,
        "",
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
        # list_clusters only names clusters whose inventory.json exists, so
        # this load can't 404; the inventory feeds the card's fleet facts and
        # freshness stamp - the card is a dashboard tile, not just a link.
        inventory = storage.load_inventory(cluster_name)
        drift_count = len(_last_run_changes(storage, cluster_name))
        findings_count = len(findings.evaluate_cluster(inventory))
        accepted_count = len(findings.evaluate_cluster_accepted(inventory))
        card_facts = facts.cluster_card_facts(
            inventory, drift_count, findings_count, accepted_count
        )
        lines += [
            f"-   __{cluster_name}__",
            "",
            "    ---",
            "",
            f"    {card_facts}",
            "",
            f"    {facts.collection_freshness(inventory.collected_at)}",
            "",
            f"    [Browse →]({cluster_name}/index.md)",
            "",
        ]
    lines += [
        "-   __About__",
        "",
        "    ---",
        "",
        "    How this site documents itself - and where the LLM is fenced in.",
        "",
        "    [Read →](about.md)",
        "",
        "</div>",
    ]
    storage.docs_dir.mkdir(parents=True, exist_ok=True)
    (storage.docs_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")
    # The About card just linked there, so the page must exist whenever the
    # index does - written here rather than by a separate call site for that
    # reason. The only page on the site that is written, not generated.
    (storage.docs_dir / "about.md").write_text(ABOUT_PAGE, encoding="utf-8")


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
    _write_root_index(storage)
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
    _write_root_index(storage)
    if clusters:
        build_static_site(mkdocs_config_path)


def build_static_site(mkdocs_config_path: Path) -> None:
    from mkdocs.commands.build import build
    from mkdocs.config import load_config

    build(load_config(str(mkdocs_config_path)))

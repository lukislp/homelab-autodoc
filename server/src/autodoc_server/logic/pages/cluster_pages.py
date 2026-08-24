"""Cluster-scoped content pages: hub index, topology, network,
connections, findings, backups, images, storage classes, nodes and the
changelog."""

from __future__ import annotations

from autodoc_core.diff import Change
from autodoc_core.models import ClusterInventory
from autodoc_generator import changelog as changelog_render
from autodoc_generator import connections, diagrams, facts, findings, navigation, network
from autodoc_generator.llm import LLMClient
from autodoc_generator.prose import build_drift_prompt

from .. import prose_cache
from ..storage import Storage
from .chrome import HIDE_NAV_FRONTMATTER, cluster_content_page, responsive_diagram


def write_cluster_index(
    storage: Storage, cluster_name: str, inventory: ClusterInventory, drift_count: int
) -> None:
    # Hub page: namespaces are shown as cards (same "grid cards" layout as the
    # root index - attr_list + md_in_html, see mkdocs.yml), not a table - a
    # hub is a "which of these" moment, nothing to scan yet. The card's own
    # title is the link (no separate "Browse ->" line) - unlike the root
    # index's Admin/cluster tiles, which stay as they were.
    lines = [
        HIDE_NAV_FRONTMATTER,
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


def write_cluster_diagram(storage: Storage, cluster_name: str, inventory: ClusterInventory) -> None:
    """One diagram in one pan/zoom box - the wide-screen layout happens
    INSIDE the Mermaid source (build_cluster_diagram chains namespace
    subgraphs into rows with invisible links), not by splitting the page
    into tiles: a tile grid was tried and rejected, the plan is one graph
    that spreads sideways.
    """
    body = responsive_diagram(
        wide=diagrams.build_cluster_diagram(inventory, spread=True),
        stacked=diagrams.build_cluster_diagram(inventory, spread=False),
    )
    page = cluster_content_page(
        cluster_name,
        "topology",
        f"{cluster_name} - Topology",
        body,
        show_heading=False,
    )
    (storage.docs_dir / cluster_name / "topology.md").write_text(page, encoding="utf-8")


def write_cluster_network_page(
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
    page = cluster_content_page(cluster_name, "network", f"{cluster_name} - Network", body)
    (storage.docs_dir / cluster_name / "network.md").write_text(page, encoding="utf-8")


def write_cluster_connections_page(
    storage: Storage, cluster_name: str, inventory: ClusterInventory
) -> None:
    diagram = connections.build_cluster_connections_diagram(inventory)
    body = "\n\n".join(
        [
            "Every declared application connection cluster-wide, grouped per namespace - "
            "the complete who-uses-whom picture from each app's own plain-text "
            "configuration, cross-namespace edges included. Only apps with at least one "
            "connection appear; Secret-held connection strings are invisible by design.",
            f"```mermaid\n{diagram}\n```"
            if diagram
            else "No cross-namespace connections found in any collected configuration.",
        ]
    )
    page = cluster_content_page(cluster_name, "connections", f"{cluster_name} - Connections", body)
    (storage.docs_dir / cluster_name / "connections.md").write_text(page, encoding="utf-8")


def write_findings_page(storage: Storage, cluster_name: str, inventory: ClusterInventory) -> None:
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
    page = cluster_content_page(cluster_name, "findings", f"{cluster_name} - Findings", body)
    (storage.docs_dir / cluster_name / "findings.md").write_text(page, encoding="utf-8")


def write_backups_page(storage: Storage, cluster_name: str, inventory: ClusterInventory) -> None:
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
    page = cluster_content_page(cluster_name, "backups", f"{cluster_name} - Backups", body)
    (storage.docs_dir / cluster_name / "backups.md").write_text(page, encoding="utf-8")


def write_images_page(storage: Storage, cluster_name: str, inventory: ClusterInventory) -> None:
    table = facts.cluster_images_table(inventory)
    body = table if table else "No container images collected yet."
    page = cluster_content_page(cluster_name, "images", f"{cluster_name} - Images", body)
    (storage.docs_dir / cluster_name / "images.md").write_text(page, encoding="utf-8")


def write_storage_classes_page(
    storage: Storage, cluster_name: str, inventory: ClusterInventory
) -> None:
    table = facts.storage_classes_table(inventory.storage_classes)
    body = table if table else "No StorageClasses exist in this cluster."
    page = cluster_content_page(
        cluster_name, "storage-classes", f"{cluster_name} - Storage Classes", body
    )
    (storage.docs_dir / cluster_name / "storage-classes.md").write_text(page, encoding="utf-8")


def write_nodes_page(storage: Storage, cluster_name: str, inventory: ClusterInventory) -> None:
    table = facts.node_specs_table(inventory.nodes)
    body = table if table else "No node data collected yet."
    page = cluster_content_page(cluster_name, "nodes", f"{cluster_name} - Nodes", body)
    (storage.docs_dir / cluster_name / "nodes.md").write_text(page, encoding="utf-8")


# How many of the most recent collector runs feed the changelog's LLM
# summary - enough for a "what happened lately" paragraph, small enough that
# one prompt never grows with the changelog's full history.
_DRIFT_SUMMARY_RECENT_RUNS = 5


def write_changelog_page(
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
        prompt_sha = prose_cache.prompt_sha(build_drift_prompt(recent))
        if cached_drift and cached_drift.get("prompt_sha") == prompt_sha:
            summary = cached_drift.get("summary")
            if new_cache is not None:
                new_cache["drift"] = cached_drift
        else:
            summary = prose_cache.safe_generate_drift_summary(cluster_name, recent, llm)
            if summary is not None and new_cache is not None:
                new_cache["drift"] = {"prompt_sha": prompt_sha, "summary": summary}
    # render_changelog_page already builds its own "# {cluster} - Changelog"
    # heading, so this only prepends front matter + breadcrumb + the chip row
    # rather than going through _cluster_content_page (which would add a
    # second heading). Chips sit above the content, same as every other
    # cluster page - below a long changelog they were effectively invisible.
    page = "\n".join(
        [
            HIDE_NAV_FRONTMATTER,
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

"""The fleet root index (one card per cluster) and the About page."""

from __future__ import annotations

from autodoc_generator import facts, findings

from ..about import ABOUT_PAGE
from ..drift import last_run_changes
from ..storage import Storage
from .chrome import HIDE_NAV_FRONTMATTER


def write_root_index(storage: Storage) -> None:
    # Material's "grid cards" layout (attr_list + md_in_html, see mkdocs.yml) - plain
    # Markdown inside a styled div, no icon shortcodes so no extra extension is needed.
    lines = [
        HIDE_NAV_FRONTMATTER,
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
        drift_count = len(last_run_changes(storage, cluster_name))
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

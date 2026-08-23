"""Renders persisted drift entries into a changelog page. Deterministic,
templated straight from autodoc_core.diff.Change - the only LLM touchpoint is
the optional, clearly labeled summary paragraph passed in by the caller
(generated in prose.py, never here).
"""

from __future__ import annotations

from autodoc_core.diff import Change

from .formatting import format_timestamp

# Shared with prose.build_drift_prompt - the LLM reads the same labels the
# rendered changelog shows.
KIND_LABELS = {
    "app_added": "added",
    "app_removed": "removed",
    "app_changed": "changed",
}


def render_changelog_entry(collected_at: str, changes: list[Change]) -> str:
    lines = [f"## {format_timestamp(collected_at)}", ""]
    for change in changes:
        label = KIND_LABELS.get(change.kind, change.kind)
        lines.append(f"- **{change.namespace}/{change.app_name}** {label}")
        for detail in change.details:
            lines.append(f"    - {detail}")
    return "\n".join(lines)


def render_changelog_page(cluster_name: str, entries: list[str], summary: str | None = None) -> str:
    """`summary` is optional LLM prose over the most recent entries - same
    labeling convention as the app pages, and the deterministic entries
    always follow in full, so the prose never replaces the facts.
    """
    lines = [f"# {cluster_name} - Changelog", ""]
    if summary:
        lines += ["## Summary (AI-generated)", "", summary, ""]
    if not entries:
        lines.append("No drift detected yet.")
    else:
        lines.append("\n\n".join(entries))
    return "\n".join(lines)

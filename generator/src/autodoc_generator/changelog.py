"""Renders persisted drift entries into a changelog page. Deterministic,
templated straight from autodoc_core.diff.Change - no LLM involved.
"""

from __future__ import annotations

from autodoc_core.diff import Change

from .formatting import format_timestamp

_KIND_LABELS = {
    "app_added": "added",
    "app_removed": "removed",
    "app_changed": "changed",
}


def render_changelog_entry(collected_at: str, changes: list[Change]) -> str:
    lines = [f"## {format_timestamp(collected_at)}", ""]
    for change in changes:
        label = _KIND_LABELS.get(change.kind, change.kind)
        lines.append(f"- **{change.namespace}/{change.app_name}** {label}")
        for detail in change.details:
            lines.append(f"    - {detail}")
    return "\n".join(lines)


def render_changelog_page(cluster_name: str, entries: list[str]) -> str:
    lines = [f"# {cluster_name} - Changelog", ""]
    if not entries:
        lines.append("No drift detected yet.")
    else:
        lines.append("\n\n".join(entries))
    return "\n".join(lines)

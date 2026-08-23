from __future__ import annotations

from autodoc_core.diff import Change

from autodoc_generator import changelog


def test_render_changelog_entry_lists_changes_and_details():
    changes = [
        Change(kind="app_changed", namespace="demo", app_name="web", details=["replicas: 2 -> 3"]),
        Change(kind="app_added", namespace="demo", app_name="api"),
    ]

    text = changelog.render_changelog_entry("2026-08-22T00:00:00+00:00", changes)

    assert "## 2026-08-22 00:00 UTC" in text
    assert "**demo/web** changed" in text
    assert "replicas: 2 -> 3" in text
    assert "**demo/api** added" in text


def test_render_changelog_page_without_entries():
    text = changelog.render_changelog_page("homelab", [])

    assert "No drift detected yet." in text


def test_render_changelog_page_with_entries():
    text = changelog.render_changelog_page("homelab", ["## entry-1", "## entry-2"])

    assert "# homelab - Changelog" in text
    assert "## entry-1" in text
    assert "## entry-2" in text


def test_render_changelog_page_with_summary_labels_it_and_keeps_entries():
    page = changelog.render_changelog_page("homelab", ["## entry"], summary="Web scaled up.")

    assert "## Summary (AI-generated)" in page
    assert "Web scaled up." in page
    # The deterministic entries always follow in full - prose never replaces facts.
    assert page.index("Web scaled up.") < page.index("## entry")


def test_render_changelog_page_without_summary_has_no_summary_heading():
    page = changelog.render_changelog_page("homelab", ["## entry"])

    assert "Summary (AI-generated)" not in page

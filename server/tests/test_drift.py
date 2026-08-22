from __future__ import annotations

from dataclasses import replace

from autodoc_server.logic import drift
from autodoc_server.logic.storage import Storage


def test_record_drift_first_push_has_no_changes(tmp_path, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")

    changes = drift.record_drift(storage, "homelab", sample_inventory)

    assert changes == []
    assert storage.load_changelog_entries("homelab") == []


def test_record_drift_persists_changelog_entry_on_change(tmp_path, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", sample_inventory)

    changed_app = replace(sample_inventory.namespaces[0].apps[0], replicas=3)
    changed_inventory = replace(
        sample_inventory,
        collected_at="2026-08-22T01:00:00+00:00",
        namespaces=[replace(sample_inventory.namespaces[0], apps=[changed_app])],
    )

    changes = drift.record_drift(storage, "homelab", changed_inventory)

    assert len(changes) == 1
    entries = storage.load_changelog_entries("homelab")
    assert len(entries) == 1
    assert entries[0]["collected_at"] == "2026-08-22T01:00:00+00:00"


def test_record_drift_no_entry_when_nothing_changed(tmp_path, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", sample_inventory)

    changes = drift.record_drift(storage, "homelab", sample_inventory)

    assert changes == []
    assert storage.load_changelog_entries("homelab") == []

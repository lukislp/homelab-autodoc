"""Diffs a newly pushed inventory against the previously stored one and
persists a changelog entry when something changed. Must run before the new
inventory overwrites the old one. No web framework import here.
"""

from __future__ import annotations

from dataclasses import asdict

from autodoc_core.diff import Change, diff_inventories
from autodoc_core.models import ClusterInventory

from .storage import Storage


def record_drift(
    storage: Storage, cluster_name: str, new_inventory: ClusterInventory
) -> list[Change]:
    old_inventory = (
        storage.load_inventory(cluster_name) if storage.has_inventory(cluster_name) else None
    )
    changes = diff_inventories(old_inventory, new_inventory)
    if changes:
        storage.append_changelog_entry(
            cluster_name, new_inventory.collected_at, [asdict(c) for c in changes]
        )
    return changes


def last_run_changes(storage: Storage, cluster_name: str) -> list[dict]:
    """The most recent collector run's drift, or [] if none yet/no changelog
    entries exist - the "Drift, Last Run" stat chip on the cluster and
    namespace hub pages, and drift_count below, both read from this.
    """
    entries = storage.load_changelog_entries(cluster_name)
    return entries[-1]["changes"] if entries else []


def drift_count(last_changes: list[dict], namespace_name: str | None = None) -> int:
    if namespace_name is None:
        return len(last_changes)
    return sum(1 for c in last_changes if c["namespace"] == namespace_name)

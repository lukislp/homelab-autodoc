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

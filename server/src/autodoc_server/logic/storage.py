"""Filesystem-backed storage for raw inventories. No web framework import here."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from autodoc_core.models import ClusterInventory
from autodoc_core.serialize import from_text, to_text


@dataclass(frozen=True, slots=True)
class Storage:
    data_dir: Path
    docs_dir: Path

    def save_inventory(self, cluster_name: str, inventory: ClusterInventory) -> None:
        cluster_dir = self.data_dir / cluster_name
        cluster_dir.mkdir(parents=True, exist_ok=True)
        cluster_dir.joinpath("inventory.json").write_text(
            to_text(inventory, fmt="json"), encoding="utf-8"
        )

    def load_inventory(self, cluster_name: str) -> ClusterInventory:
        path = self.data_dir / cluster_name / "inventory.json"
        return from_text(path.read_text(encoding="utf-8"), fmt="json")

    def list_clusters(self) -> list[str]:
        if not self.data_dir.exists():
            return []
        return sorted(
            p.name
            for p in self.data_dir.iterdir()
            if p.is_dir() and (p / "inventory.json").exists()
        )

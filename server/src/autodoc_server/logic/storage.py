"""Filesystem-backed storage for raw inventories and per-cluster push tokens.
No web framework import here.
"""

from __future__ import annotations

import hmac
import json
import shutil
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

    def has_inventory(self, cluster_name: str) -> bool:
        return (self.data_dir / cluster_name / "inventory.json").exists()

    def append_changelog_entry(
        self, cluster_name: str, collected_at: str, changes: list[dict]
    ) -> None:
        cluster_dir = self.data_dir / cluster_name
        cluster_dir.mkdir(parents=True, exist_ok=True)
        entry = json.dumps({"collected_at": collected_at, "changes": changes})
        with cluster_dir.joinpath("changelog.jsonl").open("a", encoding="utf-8") as f:
            f.write(entry + "\n")

    def load_changelog_entries(self, cluster_name: str) -> list[dict]:
        path = self.data_dir / cluster_name / "changelog.jsonl"
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def delete_cluster(self, cluster_name: str) -> bool:
        """Removes a cluster's data (inventory, changelog, push token)
        entirely. Returns False for a cluster that was never registered,
        rather than silently no-opping - the caller (routes_clusters.py)
        turns that into a 404.
        """
        cluster_dir = self.data_dir / cluster_name
        if not cluster_dir.exists():
            return False
        shutil.rmtree(cluster_dir)
        return True

    def list_clusters(self) -> list[str]:
        if not self.data_dir.exists():
            return []
        return sorted(
            p.name
            for p in self.data_dir.iterdir()
            if p.is_dir() and (p / "inventory.json").exists()
        )

    def save_push_token(self, cluster_name: str, token: str) -> None:
        cluster_dir = self.data_dir / cluster_name
        cluster_dir.mkdir(parents=True, exist_ok=True)
        cluster_dir.joinpath("push_token").write_text(token, encoding="utf-8")

    def verify_push_token(self, cluster_name: str, token: str) -> bool:
        path = self.data_dir / cluster_name / "push_token"
        if not path.exists():
            return False
        expected = path.read_text(encoding="utf-8")
        return hmac.compare_digest(token, expected)

    def load_prose_cache(self, cluster_name: str) -> dict:
        """The per-cluster LLM prose cache (see site_builder's prompt-hash
        memoization). A missing or unreadable file is an empty cache, never an
        error - the cache is a pure cost optimization, docs must build without
        it.
        """
        path = self.data_dir / cluster_name / "prose_cache.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def save_prose_cache(self, cluster_name: str, cache: dict) -> None:
        cluster_dir = self.data_dir / cluster_name
        cluster_dir.mkdir(parents=True, exist_ok=True)
        cluster_dir.joinpath("prose_cache.json").write_text(json.dumps(cache), encoding="utf-8")

    def list_registered_clusters(self) -> list[dict]:
        """Every cluster the server knows about, including approved-but-
        never-pushed ones (push_token exists, no inventory yet) - so the
        admin UI can show a just-approved cluster immediately instead of it
        staying invisible until its first push, which for a CronJob-based
        collector can be a day away.
        """
        if not self.data_dir.exists():
            return []
        entries = []
        for p in sorted(self.data_dir.iterdir()):
            if not p.is_dir():
                continue
            has_inventory = (p / "inventory.json").exists()
            if has_inventory or (p / "push_token").exists():
                entries.append({"name": p.name, "has_inventory": has_inventory})
        return entries

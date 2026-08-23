from __future__ import annotations

from autodoc_server.logic.storage import Storage


def test_save_and_load_inventory_round_trips(tmp_path, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")

    storage.save_inventory("homelab", sample_inventory)
    loaded = storage.load_inventory("homelab")

    assert loaded == sample_inventory


def test_list_clusters_empty_when_no_data_dir(tmp_path):
    storage = Storage(data_dir=tmp_path / "missing", docs_dir=tmp_path / "docs_src")

    assert storage.list_clusters() == []


def test_list_clusters_returns_only_dirs_with_an_inventory(tmp_path, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("cluster-b", sample_inventory)
    storage.save_inventory("cluster-a", sample_inventory)
    (storage.data_dir / "not-a-cluster").mkdir(parents=True)

    assert storage.list_clusters() == ["cluster-a", "cluster-b"]


def test_has_inventory(tmp_path, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")

    assert storage.has_inventory("homelab") is False
    storage.save_inventory("homelab", sample_inventory)
    assert storage.has_inventory("homelab") is True


def test_delete_cluster_removes_its_data(tmp_path, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("homelab", sample_inventory)
    storage.save_push_token("homelab", "secret-token")

    assert storage.delete_cluster("homelab") is True

    assert storage.has_inventory("homelab") is False
    assert storage.verify_push_token("homelab", "secret-token") is False
    assert not (storage.data_dir / "homelab").exists()


def test_delete_cluster_returns_false_for_unknown_cluster(tmp_path):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")

    assert storage.delete_cluster("does-not-exist") is False


def test_delete_cluster_leaves_other_clusters_untouched(tmp_path, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_inventory("cluster-a", sample_inventory)
    storage.save_inventory("cluster-b", sample_inventory)

    storage.delete_cluster("cluster-a")

    assert storage.list_clusters() == ["cluster-b"]


def test_append_and_load_changelog_entries(tmp_path):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")

    assert storage.load_changelog_entries("homelab") == []

    storage.append_changelog_entry("homelab", "2026-08-22T00:00:00+00:00", [{"kind": "app_added"}])
    storage.append_changelog_entry(
        "homelab", "2026-08-22T01:00:00+00:00", [{"kind": "app_removed"}]
    )

    entries = storage.load_changelog_entries("homelab")
    assert len(entries) == 2
    assert entries[0]["collected_at"] == "2026-08-22T00:00:00+00:00"
    assert entries[1]["changes"] == [{"kind": "app_removed"}]

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

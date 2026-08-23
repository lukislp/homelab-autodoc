from __future__ import annotations

import pytest
from autodoc_core.serialize import to_text
from fastapi.testclient import TestClient

from autodoc_server.logic import site_builder
from autodoc_server.logic.storage import Storage
from autodoc_server.web.app import app
from autodoc_server.web.deps import get_llm, get_storage


@pytest.fixture
def client(tmp_path, monkeypatch, sample_inventory):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    storage.save_push_token("homelab", "test-token")
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_llm] = lambda: None
    monkeypatch.setattr(site_builder, "build_static_site", lambda _path: None)

    yield TestClient(app), storage

    app.dependency_overrides.clear()


def test_healthz():
    response = TestClient(app).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_push_inventory_without_token_is_rejected(client):
    test_client, _ = client

    response = test_client.post(
        "/api/clusters/homelab/inventory", json={"format": "json", "text": "{}"}
    )

    assert response.status_code in (401, 422)


def test_push_inventory_with_wrong_token_is_rejected(client):
    test_client, _ = client

    response = test_client.post(
        "/api/clusters/homelab/inventory",
        json={"format": "json", "text": "{}"},
        headers={"X-Push-Token": "wrong"},
    )

    assert response.status_code == 401


def test_push_inventory_stores_and_regenerates_docs(client, sample_inventory):
    test_client, storage = client

    response = test_client.post(
        "/api/clusters/homelab/inventory",
        json={"format": "json", "text": to_text(sample_inventory, fmt="json")},
        headers={"X-Push-Token": "test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "cluster": "homelab",
        "namespaces": 1,
        "drift_changes": 0,
    }
    assert storage.load_inventory("homelab") == sample_inventory
    assert (storage.docs_dir / "homelab" / "demo" / "web.md").exists()
    assert (storage.docs_dir / "homelab" / "changelog.md").exists()


def test_push_inventory_second_push_records_drift(client, sample_inventory):
    test_client, storage = client
    test_client.post(
        "/api/clusters/homelab/inventory",
        json={"format": "json", "text": to_text(sample_inventory, fmt="json")},
        headers={"X-Push-Token": "test-token"},
    )
    from dataclasses import replace

    changed_app = replace(sample_inventory.namespaces[0].apps[0], replicas=3)
    changed_inventory = replace(
        sample_inventory,
        collected_at="2026-08-22T01:00:00+00:00",
        namespaces=[replace(sample_inventory.namespaces[0], apps=[changed_app])],
    )

    response = test_client.post(
        "/api/clusters/homelab/inventory",
        json={"format": "json", "text": to_text(changed_inventory, fmt="json")},
        headers={"X-Push-Token": "test-token"},
    )

    assert response.json()["drift_changes"] == 1
    changelog_page = (storage.docs_dir / "homelab" / "changelog.md").read_text(encoding="utf-8")
    assert "replicas: 2 -> 3" in changelog_page


def test_site_version_reports_zero_before_any_build(client):
    test_client, _ = client

    response = test_client.get("/api/site/version")

    assert response.status_code == 200
    assert response.json() == {"version": "0"}


def test_site_version_changes_when_a_new_build_lands(client):
    test_client, storage = client
    site_index = storage.docs_dir.parent / "site" / "index.html"
    site_index.parent.mkdir(parents=True)
    site_index.write_text("<html>build one</html>", encoding="utf-8")

    first = test_client.get("/api/site/version").json()["version"]
    assert first != "0"

    # A rebuild rewrites the root index - simulate it with a bumped mtime.
    import os

    stat = site_index.stat()
    os.utime(site_index, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

    second = test_client.get("/api/site/version").json()["version"]
    assert second != first

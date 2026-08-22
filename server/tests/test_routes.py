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
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_llm] = lambda: None
    monkeypatch.setattr(site_builder, "build_static_site", lambda _path: None)
    monkeypatch.setenv("AUTODOC_PUSH_TOKEN", "test-token")

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
    assert response.json() == {"status": "ok", "cluster": "homelab", "namespaces": 1}
    assert storage.load_inventory("homelab") == sample_inventory
    assert (storage.docs_dir / "homelab" / "demo" / "web.md").exists()

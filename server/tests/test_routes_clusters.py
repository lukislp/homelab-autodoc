from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from autodoc_server.logic import site_builder
from autodoc_server.logic.storage import Storage
from autodoc_server.web.app import app
from autodoc_server.web.deps import get_llm, get_storage
from autodoc_server.web.session import require_admin_session


@pytest.fixture
def client(tmp_path, monkeypatch):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_llm] = lambda: None
    monkeypatch.setattr(site_builder, "build_static_site", lambda _path: None)

    yield TestClient(app), storage

    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(client):
    app.dependency_overrides[require_admin_session] = lambda: "admin@example.com"
    return client


def test_admin_endpoints_require_a_session(client):
    test_client, storage = client
    storage.save_push_token("homelab", "unused")

    assert test_client.get("/api/admin/clusters").status_code == 401
    assert test_client.delete("/api/admin/clusters/homelab").status_code == 401


def test_admin_can_list_registered_clusters(admin_client, sample_inventory):
    test_client, storage = admin_client
    storage.save_inventory("cluster-a", sample_inventory)
    storage.save_inventory("cluster-b", sample_inventory)

    response = test_client.get("/api/admin/clusters")

    assert response.status_code == 200
    assert response.json() == ["cluster-a", "cluster-b"]


def test_admin_can_delete_a_cluster(admin_client, sample_inventory):
    test_client, storage = admin_client
    storage.save_inventory("homelab", sample_inventory)
    site_builder.regenerate_cluster_docs(storage, "homelab", llm=None)
    assert (storage.docs_dir / "homelab" / "demo" / "web.md").exists()

    response = test_client.delete("/api/admin/clusters/homelab")

    assert response.status_code == 200
    assert response.json() == {"status": "deleted", "cluster": "homelab"}
    assert storage.has_inventory("homelab") is False
    assert not (storage.docs_dir / "homelab").exists()
    assert test_client.get("/api/admin/clusters").json() == []


def test_delete_unknown_cluster_is_404(admin_client):
    test_client, _ = admin_client

    response = test_client.delete("/api/admin/clusters/does-not-exist")

    assert response.status_code == 404

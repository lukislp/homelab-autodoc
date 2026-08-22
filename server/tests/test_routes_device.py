from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from autodoc_server.logic.device_grant import DeviceGrantStore
from autodoc_server.logic.storage import Storage
from autodoc_server.web.app import app
from autodoc_server.web.deps import get_device_grant_store, get_storage
from autodoc_server.web.session import require_admin_session


@pytest.fixture
def client(tmp_path):
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    store = DeviceGrantStore()
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_device_grant_store] = lambda: store

    yield TestClient(app), storage, store

    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(client):
    app.dependency_overrides[require_admin_session] = lambda: "admin@example.com"
    return client


def test_request_device_code_returns_codes_and_verification_uri(client):
    test_client, _, _ = client

    response = test_client.post("/device/code", json={"cluster_name": "homelab"})

    assert response.status_code == 200
    body = response.json()
    assert len(body["device_code"]) > 20
    assert "-" in body["user_code"]
    assert body["verification_uri"].endswith("/admin")
    assert body["user_code"] in body["verification_uri_complete"]
    assert body["expires_in"] > 0


def test_poll_token_for_unknown_device_code_is_expired_token(client):
    test_client, _, _ = client

    response = test_client.post("/device/token", json={"device_code": "unknown"})

    assert response.status_code == 400
    assert response.json()["detail"] == "expired_token"


def test_poll_token_while_pending_returns_authorization_pending(client):
    test_client, _, store = client
    registration = store.create("homelab")

    response = test_client.post("/device/token", json={"device_code": registration.device_code})

    assert response.status_code == 400
    assert response.json()["detail"] == "authorization_pending"


def test_admin_endpoints_require_a_session(client):
    test_client, _, store = client
    registration = store.create("homelab")

    assert test_client.get("/api/admin/devices").status_code == 401
    assert (
        test_client.post(f"/api/admin/devices/{registration.user_code}/approve").status_code == 401
    )


def test_admin_can_list_and_approve_a_pending_registration(admin_client):
    test_client, storage, store = admin_client
    registration = store.create("homelab")

    pending = test_client.get("/api/admin/devices").json()
    assert pending == [{"user_code": registration.user_code, "cluster_name": "homelab"}]

    approve_response = test_client.post(f"/api/admin/devices/{registration.user_code}/approve")
    assert approve_response.status_code == 200
    assert approve_response.json() == {"status": "approved", "cluster_name": "homelab"}

    poll_response = test_client.post(
        "/device/token", json={"device_code": registration.device_code}
    )
    assert poll_response.status_code == 200
    body = poll_response.json()
    assert body["status"] == "approved"
    assert body["cluster_name"] == "homelab"
    assert storage.verify_push_token("homelab", body["push_token"])

    # approved registrations no longer show up as pending
    assert test_client.get("/api/admin/devices").json() == []


def test_admin_can_deny_a_pending_registration(admin_client):
    test_client, _, store = admin_client
    registration = store.create("homelab")

    deny_response = test_client.post(f"/api/admin/devices/{registration.user_code}/deny")
    assert deny_response.status_code == 200

    poll_response = test_client.post(
        "/device/token", json={"device_code": registration.device_code}
    )
    assert poll_response.status_code == 400
    assert poll_response.json()["detail"] == "access_denied"


def test_approve_unknown_user_code_is_404(admin_client):
    test_client, _, _ = admin_client

    response = test_client.post("/api/admin/devices/NOPE-NOPE/approve")

    assert response.status_code == 404

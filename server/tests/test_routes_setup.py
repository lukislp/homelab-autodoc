from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from autodoc_server.logic.auth_config import AuthConfigStore, AuthProviderConfig
from autodoc_server.web.app import app
from autodoc_server.web.deps import get_auth_config_store
from autodoc_server.web.routes_setup import require_session_if_already_configured

SETUP_PAYLOAD = {
    "provider": "github",
    "client_id": "abc",
    "client_secret": "secret",
    "allowed_identity": "lukislp",
}


@pytest.fixture
def client(tmp_path):
    store = AuthConfigStore(config_dir=tmp_path / "config")
    app.dependency_overrides[get_auth_config_store] = lambda: store

    yield TestClient(app), store

    app.dependency_overrides.clear()


def test_status_reports_not_configured_initially(client):
    test_client, _ = client

    response = test_client.get("/api/auth/status")

    assert response.status_code == 200
    assert response.json() == {"configured": False, "identity": None}


def test_setup_succeeds_when_not_yet_configured(client):
    test_client, store = client

    response = test_client.post("/api/setup", json=SETUP_PAYLOAD)

    assert response.status_code == 200
    assert store.is_configured() is True
    assert test_client.get("/api/auth/status").json()["configured"] is True


def test_setup_without_a_session_is_rejected_once_already_configured(client):
    test_client, store = client
    store.save(AuthProviderConfig(**SETUP_PAYLOAD))

    response = test_client.post("/api/setup", json={**SETUP_PAYLOAD, "client_id": "changed"})

    assert response.status_code == 401
    assert store.load().client_id == "abc"


def test_setup_with_a_session_can_reconfigure(client):
    test_client, store = client
    store.save(AuthProviderConfig(**SETUP_PAYLOAD))
    app.dependency_overrides[require_session_if_already_configured] = lambda: None

    response = test_client.post(
        "/api/setup",
        json={
            "provider": "oidc",
            "client_id": "new",
            "client_secret": "new",
            "allowed_identity": "me@example.com",
            "issuer_url": "https://auth.example.com",
        },
    )

    assert response.status_code == 200
    assert store.load().provider == "oidc"

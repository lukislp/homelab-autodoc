from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from autodoc_server.logic.auth_config import AuthConfigStore, AuthProviderConfig
from autodoc_server.web.app import app
from autodoc_server.web.deps import get_auth_config_store

GITHUB_CONFIG = AuthProviderConfig(
    provider="github",
    client_id="client-id",
    client_secret="client-secret",
    allowed_identity="lukislp",
)


@pytest.fixture
def client(tmp_path):
    store = AuthConfigStore(config_dir=tmp_path / "config")
    app.dependency_overrides[get_auth_config_store] = lambda: store

    yield TestClient(app), store

    app.dependency_overrides.clear()


def test_login_redirects_to_setup_when_not_configured(client):
    test_client, _ = client

    response = test_client.get("/auth/login", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/setup"


def test_login_redirects_to_provider_authorize_url_with_a_state(client):
    test_client, store = client
    store.save(GITHUB_CONFIG)

    response = test_client.get("/auth/login", follow_redirects=False)

    location = response.headers["location"]
    assert location.startswith("https://github.com/login/oauth/authorize?")
    query = parse_qs(urlparse(location).query)
    assert query["client_id"] == ["client-id"]
    assert "state" in query


def test_callback_with_wrong_state_is_rejected(client):
    test_client, store = client
    store.save(GITHUB_CONFIG)
    test_client.get("/auth/login", follow_redirects=False)  # seeds session["oauth_state"]

    response = test_client.get(
        "/auth/callback", params={"code": "x", "state": "not-the-real-state"}
    )

    assert response.status_code == 400


def test_callback_with_mismatched_identity_is_forbidden(client, monkeypatch):
    test_client, store = client
    store.save(GITHUB_CONFIG)
    login_response = test_client.get("/auth/login", follow_redirects=False)
    state = parse_qs(urlparse(login_response.headers["location"]).query)["state"][0]

    monkeypatch.setattr(
        "autodoc_server.web.routes_auth.oauth_client.exchange_code_for_identity",
        lambda *a, **k: "someone-else",
    )

    response = test_client.get("/auth/callback", params={"code": "x", "state": state})

    assert response.status_code == 403


def test_callback_with_matching_identity_logs_in_and_redirects_to_admin(client, monkeypatch):
    test_client, store = client
    store.save(GITHUB_CONFIG)
    login_response = test_client.get("/auth/login", follow_redirects=False)
    state = parse_qs(urlparse(login_response.headers["location"]).query)["state"][0]

    monkeypatch.setattr(
        "autodoc_server.web.routes_auth.oauth_client.exchange_code_for_identity",
        lambda *a, **k: "lukislp",
    )

    response = test_client.get(
        "/auth/callback", params={"code": "x", "state": state}, follow_redirects=False
    )

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/admin"
    assert test_client.get("/api/auth/status").json() == {"configured": True, "identity": "lukislp"}


def test_logout_clears_the_session(client, monkeypatch):
    test_client, store = client
    store.save(GITHUB_CONFIG)
    login_response = test_client.get("/auth/login", follow_redirects=False)
    state = parse_qs(urlparse(login_response.headers["location"]).query)["state"][0]
    monkeypatch.setattr(
        "autodoc_server.web.routes_auth.oauth_client.exchange_code_for_identity",
        lambda *a, **k: "lukislp",
    )
    test_client.get("/auth/callback", params={"code": "x", "state": state})
    assert test_client.get("/api/auth/status").json()["identity"] == "lukislp"

    test_client.get("/auth/logout", follow_redirects=False)

    assert test_client.get("/api/auth/status").json()["identity"] is None

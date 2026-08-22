from __future__ import annotations

import httpx
import pytest

from autodoc_server.logic import oauth_client
from autodoc_server.logic.auth_config import AuthProviderConfig

GITHUB_CONFIG = AuthProviderConfig(
    provider="github",
    client_id="client-id",
    client_secret="client-secret",
    allowed_identity="lukislp",
)
OIDC_CONFIG = AuthProviderConfig(
    provider="oidc",
    client_id="client-id",
    client_secret="client-secret",
    allowed_identity="me@example.com",
    issuer_url="https://auth.example.com/",
)


class _FakeResponse:
    def __init__(self, json_data: dict, status_code: int = 200) -> None:
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self) -> dict:
        return self._json_data


def test_resolve_endpoints_github_are_static_no_network(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError))

    endpoints = oauth_client.resolve_endpoints(GITHUB_CONFIG)

    assert endpoints.authorize_url == oauth_client.GITHUB_AUTHORIZE_URL
    assert endpoints.token_url == oauth_client.GITHUB_TOKEN_URL
    assert endpoints.userinfo_url == oauth_client.GITHUB_USERINFO_URL


def test_resolve_endpoints_oidc_fetches_discovery_document(monkeypatch):
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return _FakeResponse(
            {
                "authorization_endpoint": "https://auth.example.com/authorize",
                "token_endpoint": "https://auth.example.com/token",
                "userinfo_endpoint": "https://auth.example.com/userinfo",
            }
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    endpoints = oauth_client.resolve_endpoints(OIDC_CONFIG)

    assert calls == ["https://auth.example.com/.well-known/openid-configuration"]
    assert endpoints.authorize_url == "https://auth.example.com/authorize"
    assert endpoints.scope == "openid email profile"


def test_build_authorize_url_includes_state_client_id_and_redirect_uri():
    url = oauth_client.build_authorize_url(GITHUB_CONFIG, "https://server/auth/callback", "xyz")

    assert url.startswith(oauth_client.GITHUB_AUTHORIZE_URL + "?")
    assert "client_id=client-id" in url
    assert "state=xyz" in url
    assert "redirect_uri=https%3A%2F%2Fserver%2Fauth%2Fcallback" in url


def test_exchange_code_for_identity_github_returns_login(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse({"access_token": "gho_abc"}))
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResponse({"login": "lukislp"}))

    identity = oauth_client.exchange_code_for_identity(
        GITHUB_CONFIG, "https://server/callback", "code"
    )

    assert identity == "lukislp"


def test_exchange_code_for_identity_oidc_returns_email(monkeypatch):
    def fake_get(url, **kwargs):
        if url.endswith("openid-configuration"):
            return _FakeResponse(
                {
                    "authorization_endpoint": "https://auth.example.com/authorize",
                    "token_endpoint": "https://auth.example.com/token",
                    "userinfo_endpoint": "https://auth.example.com/userinfo",
                }
            )
        return _FakeResponse({"email": "me@example.com"})

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse({"access_token": "tok"}))

    identity = oauth_client.exchange_code_for_identity(
        OIDC_CONFIG, "https://server/callback", "code"
    )

    assert identity == "me@example.com"


def test_exchange_code_for_identity_returns_none_without_access_token(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse({}))

    identity = oauth_client.exchange_code_for_identity(
        GITHUB_CONFIG, "https://server/callback", "code"
    )

    assert identity is None


@pytest.mark.parametrize("status_code", [401, 500])
def test_exchange_code_for_identity_propagates_token_errors(monkeypatch, status_code):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse({}, status_code=status_code))

    with pytest.raises(httpx.HTTPStatusError):
        oauth_client.exchange_code_for_identity(GITHUB_CONFIG, "https://server/callback", "code")

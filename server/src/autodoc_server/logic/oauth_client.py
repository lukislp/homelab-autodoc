"""Minimal OAuth 2.0 Authorization Code client for the two supported admin
login providers - GitHub (plain OAuth2, static endpoints) and any
OIDC-compliant issuer (endpoints discovered via
.well-known/openid-configuration). Hand-rolled rather than pulled in from a
client library: the Authorization Code flow is small and well-specified
(RFC 6749 + OIDC Discovery), and owning every HTTP call keeps it fully
testable by monkeypatching httpx, without mocking a third-party client's
internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from .auth_config import AuthProviderConfig

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USERINFO_URL = "https://api.github.com/user"


@dataclass(frozen=True, slots=True)
class ProviderEndpoints:
    authorize_url: str
    token_url: str
    userinfo_url: str
    scope: str


def resolve_endpoints(config: AuthProviderConfig) -> ProviderEndpoints:
    if config.provider == "github":
        return ProviderEndpoints(
            authorize_url=GITHUB_AUTHORIZE_URL,
            token_url=GITHUB_TOKEN_URL,
            userinfo_url=GITHUB_USERINFO_URL,
            scope="read:user",
        )

    discovery_url = f"{config.issuer_url.rstrip('/')}/.well-known/openid-configuration"
    response = httpx.get(discovery_url, timeout=10.0)
    response.raise_for_status()
    metadata = response.json()
    return ProviderEndpoints(
        authorize_url=metadata["authorization_endpoint"],
        token_url=metadata["token_endpoint"],
        userinfo_url=metadata["userinfo_endpoint"],
        scope="openid email profile",
    )


def build_authorize_url(config: AuthProviderConfig, redirect_uri: str, state: str) -> str:
    endpoints = resolve_endpoints(config)
    params = {
        "client_id": config.client_id,
        "redirect_uri": redirect_uri,
        "scope": endpoints.scope,
        "state": state,
        "response_type": "code",
    }
    return f"{endpoints.authorize_url}?{urlencode(params)}"


def exchange_code_for_identity(
    config: AuthProviderConfig, redirect_uri: str, code: str
) -> str | None:
    """Exchanges the auth code for a token, fetches the identity, returns it (or None)."""
    endpoints = resolve_endpoints(config)

    token_response = httpx.post(
        endpoints.token_url,
        data={
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        headers={"Accept": "application/json"},
        timeout=10.0,
    )
    token_response.raise_for_status()
    access_token = token_response.json().get("access_token")
    if not access_token:
        return None

    userinfo_response = httpx.get(
        endpoints.userinfo_url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10.0,
    )
    userinfo_response.raise_for_status()
    userinfo = userinfo_response.json()

    if config.provider == "github":
        return userinfo.get("login")
    return userinfo.get("email")

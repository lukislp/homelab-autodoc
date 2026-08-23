"""First-run (or admin-initiated) setup: pick a provider, save its config.

Pure JSON API - the React admin app (frontend/) renders the actual form.
Once a provider is configured, saving again requires an active admin
session - otherwise anyone reaching the server before the real admin logs in
could hijack the configuration. Recovery if you lock yourself out: delete
the config file (AUTODOC_CONFIG_DIR/auth.json) and restart - documented in
the README, not built as extra UI.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..logic.auth_config import AuthConfigStore, AuthProviderConfig
from .deps import get_auth_config_store

router = APIRouter(prefix="/api")


class AuthStatus(BaseModel):
    configured: bool
    # Which login provider is configured ("github" / "oidc") - the login
    # prompt uses it to label its button; null until setup has run. The
    # provider name is not a secret (the login redirect exposes it anyway).
    provider: str | None = None
    identity: str | None = None


@router.get("/auth/status", response_model=AuthStatus)
def auth_status(request: Request, store: AuthConfigStore = Depends(get_auth_config_store)):
    config = store.load()
    return AuthStatus(
        configured=config is not None,
        provider=config.provider if config else None,
        identity=request.session.get("identity"),
    )


def require_session_if_already_configured(
    request: Request, store: AuthConfigStore = Depends(get_auth_config_store)
) -> None:
    """First-run setup needs no session; reconfiguring an existing setup does."""
    if store.is_configured() and not request.session.get("identity"):
        raise HTTPException(status_code=401, detail="log in before changing the configuration")


class SetupRequest(BaseModel):
    provider: str
    client_id: str
    client_secret: str
    allowed_identity: str
    issuer_url: str | None = None


@router.post("/setup", dependencies=[Depends(require_session_if_already_configured)])
def save_setup(payload: SetupRequest, store: AuthConfigStore = Depends(get_auth_config_store)):
    store.save(
        AuthProviderConfig(
            provider=payload.provider,
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            allowed_identity=payload.allowed_identity,
            issuer_url=payload.issuer_url,
        )
    )
    return {"status": "ok"}

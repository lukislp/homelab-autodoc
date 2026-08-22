"""Admin login: GitHub or a generic OIDC provider, per the persisted
AuthProviderConfig. See logic/oauth_client.py for the actual OAuth calls.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import RedirectResponse

from ..logic import oauth_client
from ..logic.auth_config import AuthConfigStore
from .deps import get_auth_config_store

router = APIRouter(prefix="/auth")


@router.get("/login")
def login(request: Request, store: AuthConfigStore = Depends(get_auth_config_store)):
    config = store.load()
    if config is None:
        return RedirectResponse("/setup")

    state = secrets.token_urlsafe(24)
    request.session["oauth_state"] = state
    redirect_uri = str(request.url_for("auth_callback"))
    return RedirectResponse(oauth_client.build_authorize_url(config, redirect_uri, state))


@router.get("/callback", name="auth_callback")
def callback(
    request: Request,
    code: str,
    state: str,
    store: AuthConfigStore = Depends(get_auth_config_store),
):
    config = store.load()
    if config is None:
        raise HTTPException(status_code=400, detail="auth not configured")

    expected_state = request.session.pop("oauth_state", None)
    if not expected_state or state != expected_state:
        raise HTTPException(status_code=400, detail="invalid state")

    redirect_uri = str(request.url_for("auth_callback"))
    identity = oauth_client.exchange_code_for_identity(config, redirect_uri, code)
    if identity is None or identity != config.allowed_identity:
        raise HTTPException(status_code=403, detail="identity not allowed")

    request.session["identity"] = identity
    return RedirectResponse("/admin")


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")

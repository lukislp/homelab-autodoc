"""FastAPI app factory - the only place the web framework meets the logic layer."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse

from .deps import get_session_secret, get_storage
from .routes import router as inventory_router
from .routes_auth import router as auth_router
from .routes_device import router as device_router
from .routes_setup import router as setup_router


def create_app() -> FastAPI:
    app = FastAPI(title="homelab-autodoc server")
    app.add_middleware(SessionMiddleware, secret_key=get_session_secret(), same_site="lax")

    app.include_router(inventory_router)
    app.include_router(device_router)
    app.include_router(auth_router)
    app.include_router(setup_router)

    # React admin app (frontend/), built separately - see frontend/README.md.
    # StaticFiles only matches paths under the mount prefix WITH a trailing slash
    # ("/admin/..."), so a bare "/admin" request falls through and 404s without this.
    @app.get("/admin", include_in_schema=False)
    def redirect_to_admin_ui() -> RedirectResponse:
        return RedirectResponse(url="/admin/")

    admin_dir = Path(os.environ.get("AUTODOC_ADMIN_UI_DIR", "../frontend/dist"))
    admin_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/admin", StaticFiles(directory=admin_dir, html=True), name="admin-ui")

    # The generated MkDocs site - the public documentation, mounted last (catch-all).
    site_dir = get_storage().docs_dir.parent / "site"
    site_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/", StaticFiles(directory=site_dir, html=True), name="site")

    return app


app = create_app()

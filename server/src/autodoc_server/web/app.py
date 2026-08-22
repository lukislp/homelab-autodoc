"""FastAPI app factory - the only place the web framework meets the logic layer."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .deps import get_storage
from .routes import router as inventory_router
from .routes_device import router as device_router


def create_app() -> FastAPI:
    app = FastAPI(title="homelab-autodoc server")
    app.include_router(inventory_router)
    app.include_router(device_router)

    site_dir = get_storage().docs_dir.parent / "site"
    site_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/", StaticFiles(directory=site_dir, html=True), name="site")

    return app


app = create_app()

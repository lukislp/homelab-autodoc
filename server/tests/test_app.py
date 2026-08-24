from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from autodoc_server.web.app import app


def test_admin_without_trailing_slash_redirects_to_admin_ui():
    response = TestClient(app).get("/admin", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/admin/"


def test_lifespan_rebuilds_the_site_before_serving(monkeypatch):
    # The rebuild moved from import time into the lifespan - uvicorn runs it
    # before accepting connections, and TestClient's context manager is the
    # test-side equivalent. Importing the module must NOT rebuild.
    calls = []
    monkeypatch.setattr(
        "autodoc_server.web.app.site_builder",
        SimpleNamespace(rebuild_all_sites=lambda *args: calls.append(args)),
    )

    assert calls == []
    with TestClient(app):
        assert len(calls) == 1

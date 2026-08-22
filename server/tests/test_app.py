from __future__ import annotations

from fastapi.testclient import TestClient

from autodoc_server.web.app import app


def test_admin_without_trailing_slash_redirects_to_admin_ui():
    response = TestClient(app).get("/admin", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/admin/"

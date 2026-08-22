from __future__ import annotations

import httpx
import pytest

from autodoc_collector.push import (
    RegistrationDenied,
    RegistrationExpired,
    poll_for_push_token,
    push_inventory,
    request_device_code,
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


def test_request_device_code_posts_the_cluster_name(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse(
            {
                "device_code": "dc",
                "user_code": "ABCD-1234",
                "verification_uri": "http://server/admin",
                "verification_uri_complete": "http://server/admin?user_code=ABCD-1234",
                "expires_in": 600,
                "interval": 5,
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    device = request_device_code("http://server/", "homelab")

    assert captured["url"] == "http://server/device/code"
    assert captured["json"] == {"cluster_name": "homelab"}
    assert device.user_code == "ABCD-1234"
    assert device.interval == 5


def test_poll_for_push_token_returns_immediately_once_approved(monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _FakeResponse({"status": "approved", "push_token": "tok"})
    )

    token = poll_for_push_token("http://server", "dc", interval=5, expires_in=60)

    assert token == "tok"


def test_poll_for_push_token_sleeps_while_pending_then_succeeds(monkeypatch):
    responses = iter(
        [
            _FakeResponse({"detail": "authorization_pending"}, status_code=400),
            _FakeResponse({"detail": "authorization_pending"}, status_code=400),
            _FakeResponse({"status": "approved", "push_token": "tok"}),
        ]
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **k: next(responses))
    sleeps = []
    clock = {"now": 0.0}

    token = poll_for_push_token(
        "http://server",
        "dc",
        interval=5,
        expires_in=60,
        sleep=lambda s: sleeps.append(s),
        clock=lambda: clock["now"],
    )

    assert token == "tok"
    assert sleeps == [5, 5]


def test_poll_for_push_token_raises_on_denial(monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _FakeResponse({"detail": "access_denied"}, status_code=400)
    )

    with pytest.raises(RegistrationDenied):
        poll_for_push_token("http://server", "dc", interval=5, expires_in=60)


def test_poll_for_push_token_raises_on_expired_token_detail(monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _FakeResponse({"detail": "expired_token"}, status_code=400)
    )

    with pytest.raises(RegistrationExpired):
        poll_for_push_token("http://server", "dc", interval=5, expires_in=60)


def test_poll_for_push_token_raises_when_deadline_passes(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: _FakeResponse({"detail": "authorization_pending"}, status_code=400),
    )
    clock = {"now": 0.0}

    def fake_sleep(seconds):
        clock["now"] += seconds

    with pytest.raises(RegistrationExpired):
        poll_for_push_token(
            "http://server",
            "dc",
            interval=10,
            expires_in=25,
            sleep=fake_sleep,
            clock=lambda: clock["now"],
        )


def test_push_inventory_sends_the_token_header_and_payload(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _FakeResponse({"status": "ok", "cluster": "homelab", "namespaces": 1})

    monkeypatch.setattr(httpx, "post", fake_post)

    result = push_inventory("http://server", "homelab", "tok", "{}", "json")

    assert captured["url"] == "http://server/api/clusters/homelab/inventory"
    assert captured["json"] == {"format": "json", "text": "{}"}
    assert captured["headers"] == {"X-Push-Token": "tok"}
    assert result["status"] == "ok"

from __future__ import annotations

import pytest
from autodoc_core.models import ClusterInventory

import autodoc_collector.cli as cli
from autodoc_collector.push import DeviceCode, RegistrationDenied


@pytest.fixture(autouse=True)
def no_real_cluster_access(monkeypatch):
    monkeypatch.setattr(cli, "load_kube_config", lambda **kwargs: None)
    monkeypatch.setattr(cli, "resolve_cluster_name", lambda explicit: explicit or "homelab")
    monkeypatch.setattr(
        cli,
        "collect_cluster_inventory",
        lambda **kwargs: ClusterInventory(
            cluster_name="homelab", collected_at="2026-08-22T00:00:00+00:00", namespaces=[]
        ),
    )


def test_prints_inventory_without_push(capsys):
    exit_code = cli.main(["--cluster-name", "homelab"])

    assert exit_code == 0
    assert "homelab" in capsys.readouterr().out


def test_push_with_cached_token_skips_registration(tmp_path, monkeypatch, capsys):
    token_file = tmp_path / "token"
    token_file.write_text("cached-token", encoding="utf-8")

    def fail_if_called(*a, **k):
        raise AssertionError("should not register when a token is already cached")

    monkeypatch.setattr(cli, "request_device_code", fail_if_called)
    pushed = {}
    monkeypatch.setattr(
        cli,
        "push_inventory",
        lambda server_url, cluster_name, token, text, fmt: (
            pushed.update(server_url=server_url, cluster_name=cluster_name, token=token)
            or {"status": "ok"}
        ),
    )

    exit_code = cli.main(
        ["--cluster-name", "homelab", "--push", "http://server", "--token-file", str(token_file)]
    )

    assert exit_code == 0
    assert pushed == {
        "server_url": "http://server",
        "cluster_name": "homelab",
        "token": "cached-token",
    }
    assert "homelab" not in capsys.readouterr().out  # quiet stdout while pushing


def test_push_without_cached_token_registers_polls_caches_and_pushes(tmp_path, monkeypatch):
    token_file = tmp_path / "token"

    monkeypatch.setattr(
        cli,
        "request_device_code",
        lambda server_url, cluster_name: DeviceCode(
            device_code="dc",
            user_code="ABCD-1234",
            verification_uri="http://server/admin",
            verification_uri_complete="http://server/admin?user_code=ABCD-1234",
            expires_in=600,
            interval=5,
        ),
    )
    monkeypatch.setattr(cli, "poll_for_push_token", lambda *a, **k: "fresh-token")
    pushed = {}
    monkeypatch.setattr(
        cli,
        "push_inventory",
        lambda server_url, cluster_name, token, text, fmt: (
            pushed.update(token=token) or {"status": "ok"}
        ),
    )

    exit_code = cli.main(
        ["--cluster-name", "homelab", "--push", "http://server", "--token-file", str(token_file)]
    )

    assert exit_code == 0
    assert token_file.read_text(encoding="utf-8") == "fresh-token"
    assert pushed == {"token": "fresh-token"}


def test_push_returns_error_when_registration_is_denied(tmp_path, monkeypatch):
    token_file = tmp_path / "token"
    monkeypatch.setattr(
        cli,
        "request_device_code",
        lambda server_url, cluster_name: DeviceCode(
            device_code="dc",
            user_code="ABCD-1234",
            verification_uri="http://server/admin",
            verification_uri_complete="http://server/admin?user_code=ABCD-1234",
            expires_in=600,
            interval=5,
        ),
    )

    def deny(*a, **k):
        raise RegistrationDenied("denied")

    monkeypatch.setattr(cli, "poll_for_push_token", deny)

    exit_code = cli.main(
        ["--cluster-name", "homelab", "--push", "http://server", "--token-file", str(token_file)]
    )

    assert exit_code == 1
    assert not token_file.exists()

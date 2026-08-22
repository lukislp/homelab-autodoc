from __future__ import annotations

from autodoc_server.logic.auth_config import AuthConfigStore, AuthProviderConfig


def test_is_configured_false_when_no_file(tmp_path):
    store = AuthConfigStore(config_dir=tmp_path / "config")

    assert store.is_configured() is False
    assert store.load() is None


def test_save_and_load_round_trips_github_config(tmp_path):
    store = AuthConfigStore(config_dir=tmp_path / "config")
    config = AuthProviderConfig(
        provider="github",
        client_id="abc",
        client_secret="secret",
        allowed_identity="lukislp",
    )

    store.save(config)

    assert store.is_configured() is True
    assert store.load() == config


def test_save_and_load_round_trips_oidc_config_with_issuer(tmp_path):
    store = AuthConfigStore(config_dir=tmp_path / "config")
    config = AuthProviderConfig(
        provider="oidc",
        client_id="abc",
        client_secret="secret",
        allowed_identity="me@example.com",
        issuer_url="https://auth.example.com",
    )

    store.save(config)

    assert store.load() == config


def test_save_overwrites_previous_config(tmp_path):
    store = AuthConfigStore(config_dir=tmp_path / "config")
    store.save(
        AuthProviderConfig(
            provider="github", client_id="a", client_secret="a", allowed_identity="a"
        )
    )

    store.save(
        AuthProviderConfig(
            provider="oidc",
            client_id="b",
            client_secret="b",
            allowed_identity="b@example.com",
            issuer_url="https://auth.example.com",
        )
    )

    loaded = store.load()
    assert loaded.provider == "oidc"
    assert loaded.client_id == "b"

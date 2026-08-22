from __future__ import annotations

from autodoc_collector.token_cache import load_cached_token, save_cached_token


def test_load_cached_token_returns_none_when_file_missing(tmp_path):
    assert load_cached_token(tmp_path / "missing-token") is None


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "nested" / "token"

    save_cached_token(path, "abc123")

    assert load_cached_token(path) == "abc123"


def test_load_cached_token_strips_whitespace(tmp_path):
    path = tmp_path / "token"
    path.write_text("  abc123  \n", encoding="utf-8")

    assert load_cached_token(path) == "abc123"


def test_load_cached_token_treats_blank_file_as_no_token(tmp_path):
    path = tmp_path / "token"
    path.write_text("   \n", encoding="utf-8")

    assert load_cached_token(path) is None

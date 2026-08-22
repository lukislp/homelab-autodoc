"""Local cache for a cluster's push token, so a scheduled run doesn't need to
re-register (and wait for admin approval) on every invocation.
"""

from __future__ import annotations

from pathlib import Path


def load_cached_token(path: Path) -> str | None:
    if not path.exists():
        return None
    token = path.read_text(encoding="utf-8").strip()
    return token or None


def save_cached_token(path: Path, token: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")

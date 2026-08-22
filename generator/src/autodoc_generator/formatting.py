"""Shared display formatting - deterministic, no LLM."""

from __future__ import annotations

from datetime import datetime


def format_timestamp(iso: str) -> str:
    """A stored ISO 8601 timestamp (often with microseconds, e.g.
    collected_at) shown as e.g. "2026-08-22 22:54 UTC". Falls back to the raw
    string for anything that doesn't parse, rather than raising - a display
    nicety is never worth failing a page render over.
    """
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    return dt.strftime("%Y-%m-%d %H:%M UTC")

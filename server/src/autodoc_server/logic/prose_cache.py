"""LLM-prose memoization: prompt-hash keyed caches for the app summaries
and the changelog drift summary, plus the degrade-to-no-prose guards.
Split out of site_builder: caching is its own concern, and both the
orchestrator and the changelog page consume it."""

from __future__ import annotations

import hashlib
import logging

from autodoc_core.diff import Change
from autodoc_core.models import App
from autodoc_generator.llm import LLMClient
from autodoc_generator.prose import build_prompt, generate_drift_summary, generate_summary

logger = logging.getLogger(__name__)


def prompt_sha(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def summary_with_cache(
    app: App, namespace_name: str, llm: LLMClient, cached_apps: dict, new_apps: dict
) -> str | None:
    """Reuse the cached summary when the app's prompt is byte-identical to the
    one its cached prose was generated from. Only successful generations are
    cached: a failed LLM call leaves no entry, so it is retried on the next
    rebuild instead of pinning a permanent gap.
    """
    key = f"{namespace_name}/{app.name}"
    sha = prompt_sha(build_prompt(app))
    cached = cached_apps.get(key)
    if cached and cached.get("prompt_sha") == sha:
        new_apps[key] = cached
        return cached.get("summary")
    summary = safe_generate_summary(app, llm)
    if summary is not None:
        new_apps[key] = {"prompt_sha": sha, "summary": summary}
    return summary


def safe_generate_summary(app: App, llm: LLMClient) -> str | None:
    """Facts and diagrams always render regardless - prose is the only optional
    part of the hallucination boundary, so a broken LLM call (bad params, auth,
    rate limit, network) must degrade to no summary, never block doc generation
    or crash server startup (rebuild_all_sites calls this at import time).
    """
    try:
        return generate_summary(app, llm)
    except Exception:
        logger.warning("LLM summary generation failed for app %r, continuing without it", app.name)
        return None


def safe_generate_drift_summary(
    cluster_name: str, recent: list[tuple[str, list[Change]]], llm: LLMClient
) -> str | None:
    """Same degradation contract as _safe_generate_summary: the deterministic
    changelog entries always render regardless, prose is optional.
    """
    try:
        return generate_drift_summary(recent, llm)
    except Exception:
        logger.warning(
            "LLM drift summary failed for cluster %r, continuing without it", cluster_name
        )
        return None

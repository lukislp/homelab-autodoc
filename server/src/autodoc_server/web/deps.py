"""FastAPI dependency providers, configured via environment variables."""

from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path

from autodoc_generator.llm import LiteLLMClient, LLMClient

from ..logic.auth_config import AuthConfigStore
from ..logic.device_grant import DeviceGrantStore
from ..logic.storage import Storage


@lru_cache
def get_storage() -> Storage:
    return Storage(
        data_dir=Path(os.environ.get("AUTODOC_DATA_DIR", "data")),
        docs_dir=Path(os.environ.get("AUTODOC_DOCS_DIR", "docs_src")),
    )


@lru_cache
def get_llm() -> LLMClient | None:
    model = os.environ.get("AUTODOC_LLM_MODEL")
    if not model:
        return None
    return LiteLLMClient(
        model=model,
        api_key=os.environ.get("AUTODOC_LLM_API_KEY"),
        api_base=os.environ.get("AUTODOC_LLM_API_BASE"),
        reasoning_effort=os.environ.get("AUTODOC_LLM_REASONING_EFFORT"),
    )


@lru_cache
def get_mkdocs_config_path() -> Path:
    return Path(os.environ.get("AUTODOC_MKDOCS_CONFIG", "mkdocs.yml"))


@lru_cache
def get_device_grant_store() -> DeviceGrantStore:
    return DeviceGrantStore()


@lru_cache
def get_auth_config_store() -> AuthConfigStore:
    return AuthConfigStore(config_dir=Path(os.environ.get("AUTODOC_CONFIG_DIR", "config")))


@lru_cache
def get_session_secret() -> str:
    """AUTODOC_SESSION_SECRET if set; otherwise a random per-process secret -
    sessions just won't survive a restart. Never a hardcoded fallback value.
    """
    return os.environ.get("AUTODOC_SESSION_SECRET") or secrets.token_urlsafe(32)

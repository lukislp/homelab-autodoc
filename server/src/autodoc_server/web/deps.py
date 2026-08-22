"""FastAPI dependency providers, configured via environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from autodoc_generator.llm import LiteLLMClient, LLMClient

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
    )


@lru_cache
def get_mkdocs_config_path() -> Path:
    return Path(os.environ.get("AUTODOC_MKDOCS_CONFIG", "mkdocs.yml"))

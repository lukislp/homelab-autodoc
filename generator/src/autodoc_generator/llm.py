"""LLM access via LiteLLM - one client, ~100 providers (Ollama, OpenAI, Anthropic, ...)
selected by the `model` string and optional api_key/api_base. A provider switch is a
config change (what the setup wizard will offer later), not a new adapter class.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import litellm


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str: ...


@dataclass(frozen=True, slots=True)
class LiteLLMClient:
    model: str = "ollama/llama3.1"
    api_key: str | None = None
    api_base: str | None = None
    timeout: float = 60.0

    def generate(self, prompt: str) -> str:
        response = litellm.completion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            api_key=self.api_key,
            api_base=self.api_base,
            timeout=self.timeout,
        )
        return response.choices[0].message.content.strip()

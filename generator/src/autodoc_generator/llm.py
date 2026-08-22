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
    # Reasoning models only (e.g. openai/gpt-5.6-luna) - rejected/ignored by non-reasoning
    # models. Left unset, a reasoning model still spends real, billed tokens "thinking" before
    # any visible output, even for a trivial reply (found in studylife-ai, a sibling project
    # using the same model). LiteLLM strips None completion kwargs before sending the request,
    # so leaving this None is equivalent to not passing it at all - correct for non-reasoning
    # models.
    reasoning_effort: str | None = None

    def generate(self, prompt: str) -> str:
        response = litellm.completion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            api_key=self.api_key,
            api_base=self.api_base,
            timeout=self.timeout,
            reasoning_effort=self.reasoning_effort,
        )
        return response.choices[0].message.content.strip()

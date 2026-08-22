from __future__ import annotations

from types import SimpleNamespace

from autodoc_generator.llm import LiteLLMClient


def test_generate_returns_stripped_content(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        message = SimpleNamespace(content="  hello world  ")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr("litellm.completion", fake_completion)
    client = LiteLLMClient(model="openai/gpt-5.6-luna", reasoning_effort="minimal")

    result = client.generate("say hi")

    assert result == "hello world"
    assert captured["model"] == "openai/gpt-5.6-luna"
    assert captured["messages"] == [{"role": "user", "content": "say hi"}]
    assert captured["reasoning_effort"] == "minimal"


def test_generate_omits_reasoning_effort_by_default(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        message = SimpleNamespace(content="ok")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr("litellm.completion", fake_completion)
    client = LiteLLMClient(model="ollama/llama3.1")

    client.generate("say hi")

    assert captured["reasoning_effort"] is None

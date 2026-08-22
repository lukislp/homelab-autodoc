from __future__ import annotations

from autodoc_generator.prose import build_prompt, generate_summary


class _FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.received_prompt: str | None = None

    def generate(self, prompt: str) -> str:
        self.received_prompt = prompt
        return self.response


def test_build_prompt_includes_only_the_apps_own_facts(sample_app):
    prompt = build_prompt(sample_app)

    assert "Name: web" in prompt
    assert "Kind: Deployment" in prompt
    assert "Replicas: 2/2 ready" in prompt
    assert "nginx:1.25.3" in prompt
    assert "web-svc" in prompt
    assert "web.example.com" in prompt
    assert "web-data" in prompt


def test_build_prompt_omits_empty_sections(bare_app):
    prompt = build_prompt(bare_app)

    assert "Images:" not in prompt
    assert "Services:" not in prompt
    assert "Exposed hosts:" not in prompt
    assert "Volumes:" not in prompt


def test_generate_summary_sends_the_built_prompt_and_returns_the_llm_response(sample_app):
    llm = _FakeLLM(response="Runs nginx behind an Ingress with persistent storage.")

    summary = generate_summary(sample_app, llm)

    assert summary == "Runs nginx behind an Ingress with persistent storage."
    assert llm.received_prompt == build_prompt(sample_app)

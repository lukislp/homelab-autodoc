from __future__ import annotations

from autodoc_core.diff import Change

from autodoc_generator.prose import (
    build_drift_prompt,
    build_prompt,
    generate_drift_summary,
    generate_summary,
)


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


def test_build_drift_prompt_lists_changes_with_shared_labels():
    entries = [
        (
            "2026-08-22T02:00:00+00:00",
            [
                Change(
                    kind="app_changed",
                    namespace="demo",
                    app_name="web",
                    details=["replicas: 2 -> 3"],
                )
            ],
        ),
        ("2026-08-23T02:00:00+00:00", [Change(kind="app_added", namespace="demo", app_name="api")]),
    ]

    prompt = build_drift_prompt(entries)

    assert "2026-08-22T02:00:00+00:00: demo/web changed" in prompt
    assert "  - replicas: 2 -> 3" in prompt
    assert "2026-08-23T02:00:00+00:00: demo/api added" in prompt
    assert "Use ONLY the changes listed below" in prompt


def test_generate_drift_summary_sends_the_drift_prompt():
    llm = _FakeLLM("Two apps changed.")
    entries = [
        ("2026-08-23T02:00:00+00:00", [Change(kind="app_added", namespace="d", app_name="a")])
    ]

    summary = generate_drift_summary(entries, llm)

    assert summary == "Two apps changed."
    assert llm.received_prompt == build_drift_prompt(entries)

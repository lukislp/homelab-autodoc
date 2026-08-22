"""The only module allowed to talk to an LLM. build_prompt is pure and testable
on its own; generate_summary is the thin call on top of it.
"""

from __future__ import annotations

from autodoc_core.models import App

from .llm import LLMClient

_INSTRUCTIONS = (
    "You are writing a short documentation summary for a Kubernetes application. "
    "Use ONLY the facts listed below - never invent replicas, ports, hostnames, "
    "dependencies, or anything else not explicitly given. Skip anything not listed. "
    "Write 2-4 plain sentences, no headings, no lists."
)


def build_prompt(app: App) -> str:
    facts = [
        f"Name: {app.name}",
        f"Kind: {app.kind}",
        f"Replicas: {app.ready_replicas}/{app.replicas} ready",
    ]
    if app.containers:
        facts.append("Images: " + ", ".join(c.image for c in app.containers))
    if app.services:
        facts.append("Services: " + ", ".join(s.name for s in app.services))

    hosts = sorted({rule.host for i in app.ingresses for rule in i.rules if rule.host})
    if hosts:
        facts.append("Exposed hosts: " + ", ".join(hosts))
    if app.volumes:
        facts.append("Volumes: " + ", ".join(v.claim_name for v in app.volumes))

    return _INSTRUCTIONS + "\n\n" + "\n".join(facts)


def generate_summary(app: App, llm: LLMClient) -> str:
    return llm.generate(build_prompt(app))

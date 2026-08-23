"""The only module allowed to talk to an LLM. The build_*_prompt functions are
pure and testable on their own; the generate_* functions are thin calls on top.
"""

from __future__ import annotations

from autodoc_core.diff import Change
from autodoc_core.models import App

from .changelog import KIND_LABELS
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


_DRIFT_INSTRUCTIONS = (
    "You are summarizing recent configuration drift in a Kubernetes cluster for "
    "its documentation changelog. Use ONLY the changes listed below - never invent "
    "resources, causes, or effects not explicitly given. Group related changes "
    "rather than repeating each line. Write 2-4 plain sentences, no headings, no lists."
)


def build_drift_prompt(entries: list[tuple[str, list[Change]]]) -> str:
    """`entries` is (collected_at, changes) per collector run, oldest first -
    the caller decides how many recent runs are worth summarizing. The lines
    use the same labels the rendered changelog shows (KIND_LABELS), so the
    prose and the facts below it speak the same language.
    """
    lines = []
    for collected_at, changes in entries:
        for change in changes:
            label = KIND_LABELS.get(change.kind, change.kind)
            lines.append(f"{collected_at}: {change.namespace}/{change.app_name} {label}")
            lines.extend(f"  - {detail}" for detail in change.details)
    return _DRIFT_INSTRUCTIONS + "\n\n" + "\n".join(lines)


def generate_drift_summary(entries: list[tuple[str, list[Change]]], llm: LLMClient) -> str:
    return llm.generate(build_drift_prompt(entries))

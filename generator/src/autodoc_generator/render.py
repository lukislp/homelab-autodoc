"""Combines facts + diagram + an already-generated summary into Markdown pages.

Never calls the LLM itself - `summary` is a plain string (or None), so this
module is fully testable without prose.py or any LLMClient.
"""

from __future__ import annotations

from pathlib import Path

from autodoc_core.models import App, NamespaceInventory
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import diagrams, facts

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(disabled_extensions=(".j2",)),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_app_page(app: App, namespace: str, summary: str | None = None) -> str:
    template = _env.get_template("app.md.j2")
    return template.render(
        app=app,
        namespace=namespace,
        summary=summary,
        diagram=diagrams.build_app_diagram(app),
        containers_table=facts.containers_table(app),
        services_table=facts.services_table(app),
        ingresses_table=facts.ingresses_table(app),
        volumes_table=facts.volumes_table(app),
    )


def render_namespace_index(namespace: NamespaceInventory) -> str:
    template = _env.get_template("namespace_index.md.j2")
    return template.render(namespace=namespace)

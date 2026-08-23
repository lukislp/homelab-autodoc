"""Combines facts + diagram + an already-generated summary into Markdown pages.

Never calls the LLM itself - `summary` is a plain string (or None), so this
module is fully testable without prose.py or any LLMClient.
"""

from __future__ import annotations

from pathlib import Path

from autodoc_core.models import App, NamespaceInventory
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import diagrams, facts, findings, navigation

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(disabled_extensions=(".j2",)),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_app_page(
    app: App, namespace: NamespaceInventory, cluster_name: str, summary: str | None = None
) -> str:
    template = _env.get_template("app.md.j2")
    return template.render(
        app=app,
        namespace=namespace,
        breadcrumb=navigation.breadcrumb(cluster_name, namespace.name, current=app.name),
        sidenav=navigation.namespace_sidenav(namespace, current=app.name),
        summary=summary,
        managed_by=facts.managed_by(app),
        findings_table=findings.findings_table(findings.evaluate_app(app, namespace)),
        diagram=diagrams.build_app_diagram(app),
        containers_table=facts.containers_table(app),
        probes_table=facts.probes_table(app),
        security_table=facts.security_table(app),
        services_table=facts.services_table(app),
        ingresses_table=facts.ingresses_table(app),
        volumes_table=facts.volumes_table(app),
        resources_table=facts.resources_table(app),
        autoscaler_table=facts.autoscaler_table(app),
        env_table=facts.env_table(app),
        dependencies_table=facts.dependencies_table(app),
        metadata_table=facts.metadata_table(app),
        nodes_table=facts.nodes_table(app),
        network_policies_table=facts.network_policies_table(app),
        service_account_table=facts.service_account_table(app),
        pod_disruption_budgets_table=facts.pod_disruption_budgets_table(app),
        scheduling_table=facts.scheduling_table(app),
        rollout_strategy_table=facts.rollout_strategy_table(app),
        registries_table=facts.registries_table(app),
        image_pull_secrets_table=facts.image_pull_secrets_table(app),
    )


def render_namespace_index(
    namespace: NamespaceInventory, cluster_name: str, drift_count: int = 0
) -> str:
    template = _env.get_template("namespace_index.md.j2")
    return template.render(
        namespace=namespace,
        breadcrumb=navigation.breadcrumb(cluster_name, namespace.name),
        stat_chips=facts.namespace_stat_chips(namespace, drift_count),
        warning_events_table=facts.warning_events_table(namespace),
    )

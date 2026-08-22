"""Deterministic Mermaid diagram for one app, built only from the inventory - never the LLM."""

from __future__ import annotations

import re

from autodoc_core.models import App


def _node_id(prefix: str, name: str) -> str:
    return f"{prefix}_{re.sub(r'[^a-zA-Z0-9_]', '_', name)}"


def build_app_diagram(app: App) -> str:
    lines = ["flowchart LR", f'  app[["{app.name} ({app.kind})"]]']

    service_ids = {}
    for service in sorted(app.services, key=lambda s: s.name):
        svc_id = _node_id("svc", service.name)
        service_ids[service.name] = svc_id
        lines.append(f'  {svc_id}("{service.name}")')
        lines.append(f"  app --> {svc_id}")

    for ingress in sorted(app.ingresses, key=lambda i: i.name):
        ing_id = _node_id("ing", ingress.name)
        lines.append(f'  {ing_id}{{{{"{ingress.name}"}}}}')
        for service_name in sorted({rule.service_name for rule in ingress.rules}):
            svc_id = service_ids.get(service_name)
            if svc_id:
                lines.append(f"  {svc_id} --> {ing_id}")

    for volume in sorted(app.volumes, key=lambda v: v.claim_name):
        vol_id = _node_id("vol", volume.claim_name)
        lines.append(f'  {vol_id}[("{volume.claim_name}")]')
        lines.append(f"  app --> {vol_id}")

    return "\n".join(lines)

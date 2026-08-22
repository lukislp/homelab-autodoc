"""Deterministic Mermaid diagrams built only from the inventory - never the LLM.

build_app_diagram/build_namespace_diagram/build_cluster_diagram all share
_app_nodes_and_edges for a single app's nodes/edges. Namespace-scoped resource
names (Service/Ingress/PVC/ConfigMap/Secret) are unique within a namespace by
Kubernetes' own rules, so build_namespace_diagram doesn't need to prefix them -
only the app node itself, since two different workload kinds can share a name.
build_cluster_diagram prefixes everything with the namespace, since names can
collide across namespaces.
"""

from __future__ import annotations

import re

from autodoc_core.models import App, ClusterInventory, NamespaceInventory


def _node_id(prefix: str, name: str) -> str:
    return f"{prefix}_{re.sub(r'[^a-zA-Z0-9_]', '_', name)}"


def _app_nodes_and_edges(app: App, app_id: str, node_prefix: str = "") -> list[str]:
    lines = [f'  {app_id}[["{app.name} ({app.kind})"]]']

    service_ids: dict[str, str] = {}
    for service in sorted(app.services, key=lambda s: s.name):
        svc_id = _node_id(f"{node_prefix}svc", service.name)
        service_ids[service.name] = svc_id
        lines.append(f'  {svc_id}("{service.name}")')
        lines.append(f"  {app_id} --> {svc_id}")

    for ingress in sorted(app.ingresses, key=lambda i: i.name):
        ing_id = _node_id(f"{node_prefix}ing", ingress.name)
        lines.append(f'  {ing_id}{{{{"{ingress.name}"}}}}')
        for service_name in sorted({rule.service_name for rule in ingress.rules}):
            svc_id = service_ids.get(service_name)
            if svc_id:
                lines.append(f"  {svc_id} --> {ing_id}")

    for volume in sorted(app.volumes, key=lambda v: v.claim_name):
        vol_id = _node_id(f"{node_prefix}vol", volume.claim_name)
        lines.append(f'  {vol_id}[("{volume.claim_name}")]')
        lines.append(f"  {app_id} --> {vol_id}")

    for ref in sorted(app.config_refs, key=lambda r: (r.kind, r.name)):
        cfg_id = _node_id(f"{node_prefix}cfg", f"{ref.kind}_{ref.name}")
        lines.append(f'  {cfg_id}[/"{ref.kind}: {ref.name}"/]')
        lines.append(f"  {app_id} --> {cfg_id}")

    return lines


def build_app_diagram(app: App) -> str:
    return "\n".join(["flowchart LR", *_app_nodes_and_edges(app, "app")])


def build_namespace_diagram(namespace: NamespaceInventory) -> str:
    lines = ["flowchart LR"]
    for app in sorted(namespace.apps, key=lambda a: a.name):
        app_id = _node_id("app", f"{app.kind}_{app.name}")
        lines.extend(_app_nodes_and_edges(app, app_id))
    return "\n".join(lines)


def build_cluster_diagram(inventory: ClusterInventory) -> str:
    lines = ["flowchart LR"]
    for namespace in sorted(inventory.namespaces, key=lambda n: n.name):
        ns_id = _node_id("ns", namespace.name)
        lines.append(f'  subgraph {ns_id} ["{namespace.name}"]')
        for app in sorted(namespace.apps, key=lambda a: a.name):
            app_id = _node_id(f"{ns_id}_app", f"{app.kind}_{app.name}")
            lines.extend(_app_nodes_and_edges(app, app_id, node_prefix=f"{ns_id}_"))
        lines.append("  end")
    return "\n".join(lines)

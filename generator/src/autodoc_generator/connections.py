"""Deterministic application-connection diagrams: who is CONFIGURED to use
whom. The third lens after topology (what exists) and network (what MAY talk):
every edge here is a service endpoint found in the app's own plain-text
configuration (App.service_references, extracted by the collector from env
values and referenced ConfigMap contents), resolved to the app that owns the
target Service.

Honest limits, stated on the pages that render this: connection strings that
live only in Secrets are invisible (the collector never reads Secrets), so an
absent edge never proves absence of a connection - but every drawn edge is a
real, declared one.
"""

from __future__ import annotations

import re

from autodoc_core.models import ClusterInventory, NamespaceInventory


def _node_id(prefix: str, name: str) -> str:
    return f"{prefix}_{re.sub(r'[^a-zA-Z0-9_]', '_', name)}"


def _service_owner(
    inventory: ClusterInventory | None,
    namespace: NamespaceInventory,
    target_namespace: str | None,
    service: str,
) -> tuple[str, str] | None:
    """(namespace, app) owning the Service, or None if it can't be resolved
    from the inventory (unknown namespace, or a Service no collected workload
    backs).
    """
    if target_namespace is None or target_namespace == namespace.name:
        candidates = [namespace]
    elif inventory is not None:
        candidates = [ns for ns in inventory.namespaces if ns.name == target_namespace]
    else:
        candidates = []
    for ns in candidates:
        for app in ns.apps:
            if any(svc.name == service for svc in app.services):
                return ns.name, app.name
    return None


def _edge_label(port: int | None) -> str:
    return str(port) if port is not None else ""


def build_namespace_connections_diagram(
    namespace: NamespaceInventory, inventory: ClusterInventory | None = None
) -> str:
    """Apps of one namespace with every declared outgoing connection. Targets
    outside the namespace (or unresolvable ones) render as external nodes;
    self-references (an app configured with its own public URL) are noise and
    skipped.
    """
    lines = ["flowchart LR"]
    app_ids = {}
    for app in sorted(namespace.apps, key=lambda a: a.name):
        app_id = _node_id("app", app.name)
        app_ids[app.name] = app_id
        lines.append(f'  {app_id}[["{app.name}"]]')

    external_ids: dict[str, str] = {}
    edges: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for app in namespace.apps:
        for ref in app.service_references:
            owner = _service_owner(inventory, namespace, ref.namespace, ref.service)
            if owner == (namespace.name, app.name):
                continue
            if owner is not None and owner[0] == namespace.name:
                target_id = app_ids[owner[1]]
            else:
                if owner is not None:
                    label = f"{owner[0]}/{owner[1]}"
                else:
                    scope = ref.namespace or namespace.name
                    label = f"service {ref.service} ({scope})"
                if label not in external_ids:
                    external_ids[label] = _node_id("ext", label)
                    lines.append(f'  {external_ids[label]}(["{label}"])')
                target_id = external_ids[label]
            key = (app_ids[app.name], target_id, _edge_label(ref.port))
            if key in seen:
                continue
            seen.add(key)
            ports = _edge_label(ref.port)
            arrow = f'-->|"{ports}"|' if ports else "-->"
            edges.append(f"  {app_ids[app.name]} {arrow} {target_id}")
    return "\n".join(lines + edges)


def build_cluster_connections_diagram(inventory: ClusterInventory) -> str:
    """The FULL who-uses-whom graph: every declared connection cluster-wide,
    app-level, grouped into one subgraph per involved namespace - INCLUDING
    the connections within a namespace, so the cluster view is the complete
    picture rather than only the cross-namespace edges. It stays readable
    because only apps with at least one edge appear at all; apps that declare
    nothing (most of a cluster) never clutter it.
    """
    # (src_ns, src_app, dst_ns|None, dst_app_or_label, ports) - dst_ns None
    # marks an unresolvable target rendered as a generic node.
    edges: list[tuple[str, str, str | None, str, str]] = []
    for namespace in inventory.namespaces:
        for app in namespace.apps:
            for ref in app.service_references:
                owner = _service_owner(inventory, namespace, ref.namespace, ref.service)
                if owner == (namespace.name, app.name):
                    continue  # its own public URL - noise
                if owner is None:
                    scope = ref.namespace or namespace.name
                    label = f"service {ref.service} ({scope})"
                    edges.append((namespace.name, app.name, None, label, _edge_label(ref.port)))
                else:
                    edges.append(
                        (namespace.name, app.name, owner[0], owner[1], _edge_label(ref.port))
                    )
    if not edges:
        return ""

    involved: dict[str, set[str]] = {}
    for src_ns, src_app, dst_ns, dst_app, _ in edges:
        involved.setdefault(src_ns, set()).add(src_app)
        if dst_ns is not None:
            involved.setdefault(dst_ns, set()).add(dst_app)

    lines = ["flowchart LR"]
    for ns_name in sorted(involved):
        lines.append(f"  subgraph {_node_id('ns', ns_name)}[{ns_name}]")
        for app_name in sorted(involved[ns_name]):
            lines.append(f'    {_node_id("app", f"{ns_name}/{app_name}")}[["{app_name}"]]')
        lines.append("  end")
    external_ids: dict[str, str] = {}
    rendered: list[str] = []
    seen: set[tuple] = set()
    for src_ns, src_app, dst_ns, dst_app, ports in sorted(edges):
        key = (src_ns, src_app, dst_ns, dst_app, ports)
        if key in seen:
            continue
        seen.add(key)
        src = _node_id("app", f"{src_ns}/{src_app}")
        if dst_ns is None:
            if dst_app not in external_ids:
                external_ids[dst_app] = _node_id("ext", dst_app)
                lines.append(f'  {external_ids[dst_app]}(["{dst_app}"])')
            dst = external_ids[dst_app]
        else:
            dst = _node_id("app", f"{dst_ns}/{dst_app}")
        arrow = f'-->|"{ports}"|' if ports else "-->"
        rendered.append(f"  {src} {arrow} {dst}")
    return "\n".join(lines + rendered)

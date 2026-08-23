"""Deterministic Markdown fact tables, built only from the inventory."""

from __future__ import annotations

from autodoc_core.models import App, NodeInfo

from .formatting import format_timestamp


def containers_table(app: App) -> str:
    if not app.containers:
        return ""
    rows = [
        f"| {c.name} | {'Yes' if c.is_init else '-'} | `{c.image}` | "
        f"{', '.join(map(str, c.ports)) or '-'} |"
        # Init containers first, in the order they actually run in.
        for c in sorted(app.containers, key=lambda c: (not c.is_init, c.name))
    ]
    return "\n".join(["| Container | Init | Image | Ports |", "|---|---|---|---|", *rows])


def probes_table(app: App) -> str:
    if not any(c.probes for c in app.containers):
        return ""
    rows = []
    for c in sorted(app.containers, key=lambda c: c.name):
        for p in sorted(c.probes, key=lambda p: p.kind):
            period = f"{p.period_seconds}s" if p.period_seconds is not None else "-"
            rows.append(f"| {c.name} | {p.kind} | {p.check} | {period} |")
    header = "| Container | Type | Check | Period |"
    return "\n".join([header, "|---|---|---|---|", *rows])


def services_table(app: App) -> str:
    if not app.services:
        return ""
    rows = []
    for service in sorted(app.services, key=lambda s: s.name):
        ports = ", ".join(f"{p.port}->{p.target_port}/{p.protocol}" for p in service.ports)
        rows.append(f"| {service.name} | {service.type} | {ports or '-'} |")
    return "\n".join(["| Service | Type | Ports |", "|---|---|---|", *rows])


def ingresses_table(app: App) -> str:
    if not app.ingresses:
        return ""
    rows = []
    for ingress in sorted(app.ingresses, key=lambda i: i.name):
        for rule in ingress.rules:
            host = rule.host or "*"
            rows.append(f"| {ingress.name} | {host} | {rule.path} | {rule.service_name} |")
    return "\n".join(["| Ingress | Host | Path | Service |", "|---|---|---|---|", *rows])


def volumes_table(app: App) -> str:
    if not app.volumes:
        return ""
    rows = [
        f"| {v.claim_name} | {v.storage_class or '-'} | {v.capacity or '-'} | "
        f"{', '.join(v.access_modes) or '-'} |"
        for v in sorted(app.volumes, key=lambda v: v.claim_name)
    ]
    return "\n".join(
        ["| Claim | Storage Class | Capacity | Access Modes |", "|---|---|---|---|", *rows]
    )


def resources_table(app: App) -> str:
    if not any(c.resource_requests or c.resource_limits for c in app.containers):
        return ""
    rows = []
    for c in sorted(app.containers, key=lambda c: c.name):
        cpu_request = c.resource_requests.get("cpu", "-")
        cpu_limit = c.resource_limits.get("cpu", "-")
        memory_request = c.resource_requests.get("memory", "-")
        memory_limit = c.resource_limits.get("memory", "-")
        rows.append(
            f"| {c.name} | {cpu_request} | {cpu_limit} | {memory_request} | {memory_limit} |"
        )
    header = "| Container | CPU Request | CPU Limit | Memory Request | Memory Limit |"
    return "\n".join([header, "|---|---|---|---|---|", *rows])


def autoscaler_table(app: App) -> str:
    if app.autoscaler is None:
        return ""
    a = app.autoscaler
    cpu_target = f"{a.target_cpu_percent}%" if a.target_cpu_percent is not None else "-"
    memory_target = f"{a.target_memory_percent}%" if a.target_memory_percent is not None else "-"
    rows = [
        "| Field | Value |",
        "|---|---|",
        f"| Min Replicas | {a.min_replicas} |",
        f"| Max Replicas | {a.max_replicas} |",
        f"| Target CPU | {cpu_target} |",
        f"| Target Memory | {memory_target} |",
    ]
    return "\n".join(rows)


def nodes_table(app: App) -> str:
    if not app.nodes:
        return ""
    rows = [f"| {node} |" for node in sorted(app.nodes)]
    return "\n".join(["| Node |", "|---|", *rows])


def _describe_traffic(rules: list, policy_types: list[str], direction: str) -> str:
    """Mirrors real NetworkPolicy semantics: a direction not listed in
    policyTypes is unrestricted by this policy; listed but with no rules
    means deny all; a rule with no peers means allow from/to everything
    (ports aside) - the union of all the policy's rules is permissive, so
    that overrides any other, more specific rule in the same direction.
    """
    if direction not in policy_types:
        return "not restricted"
    if not rules:
        return "deny all"
    peers: list[str] = []
    for rule in rules:
        if not rule.peers:
            return "all sources" if direction == "Ingress" else "all destinations"
        peers.extend(rule.peers)
    return ", ".join(sorted(set(peers)))


def network_policies_table(app: App) -> str:
    if not app.network_policies:
        return ""
    rows = []
    for policy in sorted(app.network_policies, key=lambda p: p.name):
        ingress = _describe_traffic(policy.ingress, policy.policy_types, "Ingress")
        egress = _describe_traffic(policy.egress, policy.policy_types, "Egress")
        types = ", ".join(policy.policy_types) or "-"
        rows.append(f"| {policy.name} | {types} | {ingress} | {egress} |")
    header = "| Policy | Types | Ingress From | Egress To |"
    return "\n".join([header, "|---|---|---|---|", *rows])


def env_table(app: App) -> str:
    """Never shows a literal env var's actual value - only its name and, for a
    valueFrom reference, which ConfigMap/Secret key it points at. The docs site
    is public; a value entered directly in a homelab Deployment spec might not be.
    """
    if not any(c.env for c in app.containers):
        return ""
    rows = []
    for c in sorted(app.containers, key=lambda c: c.name):
        for e in sorted(c.env, key=lambda e: e.name):
            source = e.value_from or "literal"
            rows.append(f"| {c.name} | {e.name} | {source} |")
    return "\n".join(["| Container | Env Var | Source |", "|---|---|---|", *rows])


def dependencies_table(app: App) -> str:
    if not app.config_refs:
        return ""
    rows = [
        f"| {ref.kind} | {ref.name} | {ref.via} |"
        for ref in sorted(app.config_refs, key=lambda r: (r.kind, r.name, r.via))
    ]
    return "\n".join(["| Kind | Name | Via |", "|---|---|---|", *rows])


# kubectl stores the entire last-applied manifest under this key - always huge, never
# useful on a docs page (every other fact table already shows what it contains).
_NOISY_ANNOTATIONS = frozenset({"kubectl.kubernetes.io/last-applied-configuration"})
_MAX_ANNOTATION_VALUE_LENGTH = 200


def metadata_table(app: App) -> str:
    annotations = {k: v for k, v in app.annotations.items() if k not in _NOISY_ANNOTATIONS}
    if not (app.created_at or app.owners or annotations):
        return ""
    rows = ["| Field | Value |", "|---|---|"]
    if app.created_at:
        rows.append(f"| Created | {format_timestamp(app.created_at)} |")
    if app.owners:
        rows.append(f"| Owners | {', '.join(sorted(app.owners))} |")
    for key, value in sorted(annotations.items()):
        if len(value) > _MAX_ANNOTATION_VALUE_LENGTH:
            value = value[:_MAX_ANNOTATION_VALUE_LENGTH] + "…"
        rows.append(f"| `{key}` | {value} |")
    return "\n".join(rows)


def node_specs_table(nodes: list[NodeInfo]) -> str:
    """Cluster-wide, unlike every other table in this module - nodes aren't
    scoped to an app.
    """
    if not nodes:
        return ""
    rows = []
    for node in sorted(nodes, key=lambda n: n.name):
        status = "Ready" if node.ready else "NotReady"
        rows.append(
            f"| {node.name} | {status} | {node.architecture} | {node.os_image} | "
            f"{node.kubelet_version} | {node.capacity_cpu} | {node.allocatable_cpu} | "
            f"{node.capacity_memory} | {node.allocatable_memory} |"
        )
    header = (
        "| Node | Status | Arch | OS | Kubelet | CPU (Capacity) | CPU (Allocatable) | "
        "Memory (Capacity) | Memory (Allocatable) |"
    )
    return "\n".join([header, "|---|---|---|---|---|---|---|---|---|", *rows])

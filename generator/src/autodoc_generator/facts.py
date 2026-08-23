"""Deterministic Markdown fact tables, built only from the inventory."""

from __future__ import annotations

from autodoc_core.models import App, NamespaceInventory, NodeInfo, StorageClassInfo

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


def _describe_tristate(value: bool | None) -> str:
    if value is None:
        return "-"
    return "yes" if value else "no"


def security_table(app: App) -> str:
    if not any(c.security for c in app.containers):
        return ""
    rows = []
    for c in sorted(app.containers, key=lambda c: c.name):
        s = c.security
        if s is None:
            rows.append(f"| {c.name} | - | - | - | - | - |")
            continue
        capabilities = (
            ", ".join(
                [f"+{cap}" for cap in s.added_capabilities]
                + [f"-{cap}" for cap in s.dropped_capabilities]
            )
            or "-"
        )
        rows.append(
            f"| {c.name} | {_describe_tristate(s.run_as_non_root)} | "
            f"{_describe_tristate(s.read_only_root_filesystem)} | "
            f"{_describe_tristate(s.allow_privilege_escalation)} | {capabilities} | "
            f"{s.seccomp_profile or '-'} |"
        )
    header = (
        "| Container | Run as Non-Root | Read-Only Root FS | Priv. Escalation | "
        "Capabilities | Seccomp |"
    )
    return "\n".join([header, "|---|---|---|---|---|---|", *rows])


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


def rollout_strategy_table(app: App) -> str:
    if app.rollout_strategy is None:
        return ""
    s = app.rollout_strategy
    rows = [
        "| Field | Value |",
        "|---|---|",
        f"| Strategy | {s.strategy_type} |",
        f"| Max Surge | {s.max_surge or '-'} |",
        f"| Max Unavailable | {s.max_unavailable or '-'} |",
        f"| Partition | {s.partition if s.partition is not None else '-'} |",
    ]
    return "\n".join(rows)


def _parse_registry(image: str) -> str:
    """Docker's own reference-parsing rule: no slash at all means Docker Hub
    ("nginx:1.25.3"); with a slash, the first path segment is the registry
    only if it looks like a host (contains "." or ":", or is "localhost") -
    otherwise it's a Docker Hub namespace ("library/nginx", "bitnami/redis").
    """
    ref = image.split("@", 1)[0]  # strip a digest, e.g. "...@sha256:..." - irrelevant here
    if "/" not in ref:
        return "docker.io"
    first_segment = ref.split("/", 1)[0]
    if "." in first_segment or ":" in first_segment or first_segment == "localhost":
        return first_segment
    return "docker.io"


def registries_table(app: App) -> str:
    if not app.containers:
        return ""
    rows = [
        f"| {c.name} | `{c.image}` | {_parse_registry(c.image)} |"
        for c in sorted(app.containers, key=lambda c: c.name)
    ]
    return "\n".join(["| Container | Image | Registry |", "|---|---|---|", *rows])


def image_pull_secrets_table(app: App) -> str:
    if not app.image_pull_secrets:
        return ""
    rows = [f"| {name} |" for name in sorted(app.image_pull_secrets)]
    return "\n".join(["| Pull Secret |", "|---|", *rows])


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


def pod_disruption_budgets_table(app: App) -> str:
    if not app.pod_disruption_budgets:
        return ""
    rows = []
    for pdb in sorted(app.pod_disruption_budgets, key=lambda p: p.name):
        min_available = pdb.min_available if pdb.min_available is not None else "-"
        max_unavailable = pdb.max_unavailable if pdb.max_unavailable is not None else "-"
        rows.append(f"| {pdb.name} | {min_available} | {max_unavailable} |")
    header = "| PDB | Min Available | Max Unavailable |"
    return "\n".join([header, "|---|---|---|", *rows])


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


def service_account_table(app: App) -> str:
    if app.service_account is None:
        return ""
    rows = ["| Field | Value |", "|---|---|", f"| ServiceAccount | {app.service_account.name} |"]
    if app.service_account.role_bindings:
        roles = ", ".join(
            f"{rb.role_kind}/{rb.role_name}"
            for rb in sorted(
                app.service_account.role_bindings, key=lambda rb: (rb.role_kind, rb.role_name)
            )
        )
        rows.append(f"| Roles | {roles} |")
    return "\n".join(rows)


def scheduling_table(app: App) -> str:
    if not (app.node_selector or app.node_affinity or app.tolerations):
        return ""
    rows = ["| Field | Value |", "|---|---|"]
    if app.node_selector:
        selector = ", ".join(f"{k}={v}" for k, v in sorted(app.node_selector.items()))
        rows.append(f"| Node Selector | {selector} |")
    for term in app.node_affinity:
        rows.append(f"| Node Affinity | {term} |")
    for toleration in sorted(app.tolerations):
        rows.append(f"| Toleration | {toleration} |")
    return "\n".join(rows)


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


def dependency_usage_table(namespace: NamespaceInventory) -> str:
    """Reverse of the per-app Dependencies table: for each ConfigMap/Secret in
    this namespace, which apps reference it and how - instead of, per app,
    which ConfigMaps/Secrets it references. Namespace-scoped like
    ConfigMaps/Secrets themselves are, not cluster-wide.
    """
    usage: dict[tuple[str, str], list[str]] = {}
    for app in namespace.apps:
        for ref in app.config_refs:
            usage.setdefault((ref.kind, ref.name), []).append(f"{app.name} ({ref.via})")
    if not usage:
        return ""
    rows = [
        f"| {kind} | {name} | {', '.join(sorted(users))} |"
        for (kind, name), users in sorted(usage.items())
    ]
    return "\n".join(["| Kind | Name | Used By |", "|---|---|---|", *rows])


def resource_quotas_table(namespace: NamespaceInventory) -> str:
    if not namespace.resource_quotas:
        return ""
    rows = []
    for rq in sorted(namespace.resource_quotas, key=lambda rq: rq.name):
        for resource in sorted(rq.hard):
            hard = rq.hard.get(resource, "-")
            used = rq.used.get(resource, "-")
            rows.append(f"| {rq.name} | {resource} | {hard} | {used} |")
    header = "| Quota | Resource | Hard | Used |"
    return "\n".join([header, "|---|---|---|---|", *rows])


def limit_ranges_table(namespace: NamespaceInventory) -> str:
    if not namespace.limit_ranges:
        return ""
    rows = []
    for lr in sorted(namespace.limit_ranges, key=lambda lr: lr.name):
        for item in lr.limits:
            resources = sorted(
                set(item.min) | set(item.max) | set(item.default) | set(item.default_request)
            )
            for resource in resources:
                rows.append(
                    f"| {lr.name} | {item.kind} | {resource} | "
                    f"{item.min.get(resource, '-')} | {item.max.get(resource, '-')} | "
                    f"{item.default.get(resource, '-')} | "
                    f"{item.default_request.get(resource, '-')} |"
                )
    header = "| LimitRange | Applies To | Resource | Min | Max | Default Limit | Default Request |"
    return "\n".join([header, "|---|---|---|---|---|---|---|", *rows])


def storage_classes_table(storage_classes: list[StorageClassInfo]) -> str:
    """Cluster-wide, unlike every other table in this module - StorageClasses
    aren't scoped to an app.
    """
    if not storage_classes:
        return ""
    rows = []
    for sc in sorted(storage_classes, key=lambda s: s.name):
        expansion = "-" if sc.allow_volume_expansion is None else str(sc.allow_volume_expansion)
        rows.append(
            f"| {sc.name} | {sc.provisioner} | {sc.reclaim_policy or '-'} | "
            f"{sc.volume_binding_mode or '-'} | {expansion} |"
        )
    header = "| StorageClass | Provisioner | Reclaim Policy | Binding Mode | Volume Expansion |"
    return "\n".join([header, "|---|---|---|---|---|", *rows])


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

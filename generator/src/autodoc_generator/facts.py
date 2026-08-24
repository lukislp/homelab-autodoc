"""Deterministic Markdown fact tables, built only from the inventory."""

from __future__ import annotations

from autodoc_core.models import (
    App,
    ClusterInventory,
    NamespaceInventory,
    NodeInfo,
    StorageClassInfo,
)

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
            rows.append(f"| {c.name} | - | - | - | - | - | - |")
            continue
        capabilities = (
            ", ".join(
                [f"+{cap}" for cap in s.added_capabilities]
                + [f"-{cap}" for cap in s.dropped_capabilities]
            )
            or "-"
        )
        rows.append(
            f"| {c.name} | {_describe_tristate(s.privileged)} | "
            f"{_describe_tristate(s.run_as_non_root)} | "
            f"{_describe_tristate(s.read_only_root_filesystem)} | "
            f"{_describe_tristate(s.allow_privilege_escalation)} | {capabilities} | "
            f"{s.seccomp_profile or '-'} |"
        )
    header = (
        "| Container | Privileged | Run as Non-Root | Read-Only Root FS | Priv. Escalation | "
        "Capabilities | Seccomp |"
    )
    return "\n".join([header, "|---|---|---|---|---|---|---|", *rows])


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


_MAX_EVENT_MESSAGE_LENGTH = 160


def warning_events_table(namespace: NamespaceInventory) -> str:
    """Recent Warning-type events, newest first (the collector already caps
    and orders them). Empty for both "collected, none present" and "not
    collected" - a namespace hub has no room for an unknown-vs-clean
    distinction, and rendering nothing is the honest default for both.
    """
    if not namespace.warning_events:
        return ""
    rows = []
    for event in namespace.warning_events:
        last_seen = format_timestamp(event.last_seen) if event.last_seen else "-"
        message = event.message
        if len(message) > _MAX_EVENT_MESSAGE_LENGTH:
            message = message[:_MAX_EVENT_MESSAGE_LENGTH] + "…"
        rows.append(
            f"| {last_seen} | {event.object_ref} | {event.reason} | {event.count} | {message} |"
        )
    header = "| Last Seen | Object | Reason | Count | Message |"
    return "\n".join([header, "|---|---|---|---|---|", *rows])


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


def app_is_fully_ready(app: App) -> bool:
    return app.ready_replicas == app.replicas


def collection_freshness(collected_at: str) -> str:
    """A "collected ..." stamp with the raw ISO timestamp attached as a data
    attribute for overrides/javascripts/freshness.js, which upgrades the text
    to a live relative age ("collected 3 h ago") and flags it stale once the
    last collector run is older than its threshold. Staleness has to be
    client-side: the static site only rebuilds on a push, so a build-time
    stale flag could never appear exactly when the collector stops pushing.
    The server-rendered absolute time is the no-JS fallback, not a
    placeholder.
    """
    return (
        f'<span class="freshness" data-collected-at="{collected_at}">'
        f"collected {format_timestamp(collected_at)}</span>"
    )


def _stat_row_html(chips: list[tuple[str, str, bool]]) -> str:
    """`chips` is (value, label, warn) triples - warn highlights the value in
    the warning color (used for a non-zero drift count).
    """
    cells = []
    for value, label, warn in chips:
        num_class = "stat-num stat-num--warn" if warn else "stat-num"
        cells.append(
            f'<div class="stat-chip"><span class="{num_class}">{value}</span>'
            f'<span class="stat-label">{label}</span></div>'
        )
    return '<div class="stat-row">' + "".join(cells) + "</div>"


def cluster_stat_chips(inventory: ClusterInventory, drift_count: int, findings_count: int) -> str:
    return _stat_row_html(
        [
            (str(len(inventory.namespaces)), "Namespaces", False),
            (str(len(inventory.nodes)), "Nodes", False),
            (str(len(inventory.storage_classes)), "Storage Classes", False),
            (str(findings_count), "Findings", findings_count > 0),
            (str(drift_count), "Drift, Last Run", drift_count > 0),
        ]
    )


def namespace_stat_chips(namespace: NamespaceInventory, drift_count: int) -> str:
    """Pods and CPU figures are the raw hard/used quantity strings from the
    namespace's first ResourceQuota, shown side by side rather than computed
    into a percentage - resource quantities are never parsed in this codebase
    (mixed units like "900m" vs "2" would need real unit-aware math to
    compare correctly).
    """
    quota = namespace.resource_quotas[0] if namespace.resource_quotas else None
    pods = f"{quota.used.get('pods', '-')}/{quota.hard.get('pods', '-')}" if quota else "-"
    cpu = (
        f"{quota.used.get('requests.cpu', '-')} / {quota.hard.get('requests.cpu', '-')}"
        if quota
        else "-"
    )
    return _stat_row_html(
        [
            (str(len(namespace.apps)), "Applications", False),
            (pods, "Pods (Quota)", False),
            (cpu, "CPU (Requests)", False),
            (str(drift_count), "Drift, Last Run", drift_count > 0),
        ]
    )


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


def cluster_images_table(inventory: ClusterInventory) -> str:
    """Cluster-wide, deduplicated: every image running anywhere in the
    cluster, and which workloads run it - version sprawl (two apps on
    different Postgres tags) becomes visible at a glance. Init containers
    count too: their images are pulled and run just the same.
    """
    used_by: dict[str, set[str]] = {}
    for namespace in inventory.namespaces:
        for app in namespace.apps:
            for container in app.containers:
                used_by.setdefault(container.image, set()).add(f"{namespace.name}/{app.name}")
    if not used_by:
        return ""
    rows = [
        f"| `{image}` | {_parse_registry(image)} | {', '.join(sorted(users))} |"
        for image, users in sorted(used_by.items())
    ]
    return "\n".join(["| Image | Registry | Used By |", "|---|---|---|", *rows])


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def cluster_card_facts(inventory: ClusterInventory, drift_count: int, findings_count: int) -> str:
    """The root-index card's two compact fact lines - scale on the first
    (namespaces/apps/nodes plus the kubelet version, or versions when the
    nodes disagree, which is itself worth noticing), health signals on the
    second. Drift gets the warn tint when non-zero, matching the stat chips;
    findings stay neutral - a homelab almost always has some, and a
    permanently red number on every card would train the eye to ignore it.
    """
    app_count = sum(len(namespace.apps) for namespace in inventory.namespaces)
    scale = [
        _plural(len(inventory.namespaces), "namespace"),
        _plural(app_count, "app"),
        _plural(len(inventory.nodes), "node"),
    ]
    versions = sorted({node.kubelet_version for node in inventory.nodes})
    if versions:
        scale.append(" / ".join(versions))
    drift_class = "card-facts card-facts--warn" if drift_count > 0 else "card-facts"
    return (
        f'<span class="card-facts">{" · ".join(scale)}</span><br>'
        f'<span class="{drift_class}">{_plural(findings_count, "finding")} · '
        f"{drift_count} drift last run</span>"
    )


# Flux's kustomize/helm controllers label everything they apply; plain Helm
# marks its releases via managed-by plus release annotations. All read from
# labels/annotations the collector already gathers - no new inventory field.
_FLUX_KUSTOMIZATION_NAME = "kustomize.toolkit.fluxcd.io/name"
_FLUX_KUSTOMIZATION_NAMESPACE = "kustomize.toolkit.fluxcd.io/namespace"
_FLUX_HELMRELEASE_NAME = "helm.toolkit.fluxcd.io/name"
_FLUX_HELMRELEASE_NAMESPACE = "helm.toolkit.fluxcd.io/namespace"
_HELM_MANAGED_BY = "app.kubernetes.io/managed-by"
_HELM_RELEASE_ANNOTATION = "meta.helm.sh/release-name"


def managed_by(app: App) -> str | None:
    """Who owns this workload's manifest: a Flux Kustomization, a Flux
    HelmRelease, a plain Helm release - or None when none of their markers
    are present, which the caller renders as nothing rather than guessing
    "manual" (an unmarked workload might still be applied by tooling this
    heuristic doesn't know).
    """

    def flux_ref(name_label: str, namespace_label: str) -> str | None:
        name = app.labels.get(name_label)
        if not name:
            return None
        namespace = app.labels.get(namespace_label)
        return f"{namespace}/{name}" if namespace else name

    kustomization = flux_ref(_FLUX_KUSTOMIZATION_NAME, _FLUX_KUSTOMIZATION_NAMESPACE)
    if kustomization:
        return f"Flux Kustomization {kustomization}"
    helm_release = flux_ref(_FLUX_HELMRELEASE_NAME, _FLUX_HELMRELEASE_NAMESPACE)
    if helm_release:
        return f"Flux HelmRelease {helm_release}"
    if app.labels.get(_HELM_MANAGED_BY) == "Helm":
        release = app.annotations.get(_HELM_RELEASE_ANNOTATION)
        return f"Helm release {release}" if release else "Helm"
    return None

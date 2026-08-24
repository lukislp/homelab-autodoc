"""Deterministic network-flow diagrams from collected NetworkPolicies.

Same hallucination boundary as diagrams.py: pure functions over the inventory,
no LLM. The topology diagrams show what EXISTS (apps, services, volumes); these
show what may TALK to what - every edge is an ingress rule some NetworkPolicy
actually allows, resolved back to the concrete source workloads where the
selectors permit it.

Peers come structured from the inventory (NetworkPolicyRule.peer_selectors);
for inventories collected before that field existed, the human-readable peer
strings ("pods:<sel>", "namespaces:<sel>+pods:<sel>", "ipBlock:<cidr>") are
parsed as a legacy fallback. Selector matching mirrors the collector's:
matchLabels subset semantics against the pod TEMPLATE labels
(App.pod_labels). Anything unresolvable stays visible as a generic node
instead of being dropped - an edge that cannot be attributed is still an
allowed flow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from autodoc_core.models import (
    App,
    ClusterInventory,
    NamespaceInventory,
    NetworkPolicyPeerInfo,
    NetworkPolicyRule,
)

# Namespaces are matched via the well-known label Kubernetes stamps on every
# namespace since 1.21 - the only namespace-selector shape this cluster's
# policies (and most real ones) use. Other keys stay unresolved-but-visible.
_NS_NAME_LABEL = "kubernetes.io/metadata.name"


def _parse_selector(text: str) -> dict[str, str]:
    if text == "all":
        return {}
    return dict(part.split("=", 1) for part in text.split(",") if "=" in part)


def _parse_peer(text: str) -> NetworkPolicyPeerInfo:
    """LEGACY fallback: inventories from collectors older than
    NetworkPolicyRule.peer_selectors only carry the display strings - parse
    them back into the structured shape. New inventories never hit this.
    """
    if text.startswith("ipBlock:"):
        return NetworkPolicyPeerInfo(ip_block=text.removeprefix("ipBlock:"))
    namespace_selector = None
    pod_selector = None
    for part in text.split("+"):
        if part.startswith("namespaces:"):
            namespace_selector = _parse_selector(part.removeprefix("namespaces:"))
        elif part.startswith("pods:"):
            pod_selector = _parse_selector(part.removeprefix("pods:"))
    return NetworkPolicyPeerInfo(namespace_selector=namespace_selector, pod_selector=pod_selector)


def _rule_peers(rule: NetworkPolicyRule) -> list[NetworkPolicyPeerInfo]:
    if rule.peer_selectors:
        return rule.peer_selectors
    return [_parse_peer(text) for text in rule.peers]


def _matches(selector: dict[str, str], labels: dict[str, str]) -> bool:
    return all(labels.get(key) == value for key, value in selector.items())


def _peer_namespaces(
    peer: NetworkPolicyPeerInfo,
    own_namespace: NamespaceInventory,
    inventory: ClusterInventory | None,
) -> list[NamespaceInventory] | None:
    """The namespaces a peer's sources may live in, or None when the selector
    can't be resolved to concrete namespaces (labels beyond the well-known
    name label - the inventory doesn't collect namespace labels).
    """
    if peer.namespace_selector is None:
        return [own_namespace]
    if peer.namespace_selector == {}:
        return list(inventory.namespaces) if inventory else None
    if set(peer.namespace_selector) == {_NS_NAME_LABEL}:
        wanted = peer.namespace_selector[_NS_NAME_LABEL]
        if wanted == own_namespace.name:
            return [own_namespace]
        if inventory:
            return [ns for ns in inventory.namespaces if ns.name == wanted]
    return None


@dataclass(frozen=True, slots=True)
class _Source:
    """A resolved flow source: a concrete app, a whole namespace, or a generic
    actor ("any source", an ipBlock, an unresolvable selector).
    """

    kind: str  # "app" | "namespace" | "generic"
    namespace: str | None
    name: str  # app name, namespace name, or the generic label


def _resolve_peer(
    peer: NetworkPolicyPeerInfo,
    own_namespace: NamespaceInventory,
    inventory: ClusterInventory | None,
) -> list[_Source]:
    if peer.ip_block is not None:
        return [_Source("generic", None, f"ipBlock {peer.ip_block}")]
    namespaces = _peer_namespaces(peer, own_namespace, inventory)
    if namespaces is None:
        ns_sel = ",".join(f"{k}={v}" for k, v in sorted((peer.namespace_selector or {}).items()))
        pod_sel = ",".join(f"{k}={v}" for k, v in sorted((peer.pod_selector or {}).items()))
        label = f"namespaces {ns_sel or 'all'}" + (f", pods {pod_sel}" if pod_sel else "")
        return [_Source("generic", None, label)]
    if peer.pod_selector is None or peer.pod_selector == {}:
        return [_Source("namespace", ns.name, ns.name) for ns in namespaces]
    sources = [
        _Source("app", ns.name, app.name)
        for ns in namespaces
        for app in ns.apps
        if _matches(peer.pod_selector, app.pod_labels)
    ]
    if sources:
        return sources
    # A selector matching no collected workload still allows traffic from
    # whatever it describes (a Job, an operator-created pod) - keep it visible.
    pod_sel = ",".join(f"{k}={v}" for k, v in sorted(peer.pod_selector.items()))
    scope = "/".join(sorted(ns.name for ns in namespaces))
    return [_Source("generic", None, f"pods {pod_sel} ({scope})")]


@dataclass(frozen=True, slots=True)
class Flow:
    """One allowed ingress flow: source -> target app, with the rule's ports
    ("" = all ports). The building block both diagrams aggregate from.
    """

    source: _Source
    target_namespace: str
    target_app: str
    ports: str


_ANY_SOURCE = _Source("generic", None, "any source")


def _app_flows(
    app: App, namespace: NamespaceInventory, inventory: ClusterInventory | None
) -> list[Flow]:
    """Every allowed ingress flow into one app. No NetworkPolicy at all means
    Kubernetes' default: everything may connect - rendered as an explicit
    "any source" flow rather than silently omitted, because that openness IS
    the fact worth seeing on a network page.
    """
    if not app.network_policies:
        return [Flow(_ANY_SOURCE, namespace.name, app.name, "")]
    flows: list[Flow] = []
    for policy in app.network_policies:
        if "Ingress" not in policy.policy_types:
            continue
        for rule in policy.ingress:
            ports = ", ".join(rule.ports)
            if not rule.peers:
                flows.append(Flow(_ANY_SOURCE, namespace.name, app.name, ports))
                continue
            for peer in _rule_peers(rule):
                for source in _resolve_peer(peer, namespace, inventory):
                    flows.append(Flow(source, namespace.name, app.name, ports))
    return flows


def namespace_flows(
    namespace: NamespaceInventory, inventory: ClusterInventory | None = None
) -> list[Flow]:
    return [flow for app in namespace.apps for flow in _app_flows(app, namespace, inventory)]


def _node_id(prefix: str, name: str) -> str:
    return f"{prefix}_{re.sub(r'[^a-zA-Z0-9_]', '_', name)}"


def _edge(source_id: str, target_id: str, ports: str, dashed: bool) -> str:
    arrow = "-.->" if dashed else "-->"
    if ports:
        return f'  {source_id} {arrow}|"{ports}"| {target_id}'
    return f"  {source_id} {arrow} {target_id}"


def build_namespace_network_diagram(
    namespace: NamespaceInventory, inventory: ClusterInventory | None = None
) -> str:
    """Apps of one namespace with every allowed ingress flow into them. Solid
    edges are explicit NetworkPolicy allowances; dashed edges mark apps no
    policy selects (unrestricted by Kubernetes default). Cross-namespace and
    generic sources render as their own nodes outside the app set.
    """
    lines = ["flowchart LR"]
    app_ids = {}
    for app in sorted(namespace.apps, key=lambda a: a.name):
        app_id = _node_id("app", app.name)
        app_ids[app.name] = app_id
        lines.append(f'  {app_id}[["{app.name}"]]')

    external_ids: dict[str, str] = {}
    edges: list[str] = []
    seen: set[tuple[str, str, str, bool]] = set()
    for flow in namespace_flows(namespace, inventory):
        source = flow.source
        dashed = source == _ANY_SOURCE and not _has_policies(namespace, flow.target_app)
        if source.kind == "app" and source.namespace == namespace.name:
            source_id = app_ids.get(source.name) or _node_id("app", source.name)
        else:
            label = source.name if source.kind == "generic" else f"{source.namespace}/{source.name}"
            if source.kind == "namespace":
                label = f"namespace {source.name}"
            if label not in external_ids:
                external_ids[label] = _node_id("ext", label)
                lines.append(f'  {external_ids[label]}(["{label}"])')
            source_id = external_ids[label]
        key = (source_id, app_ids[flow.target_app], flow.ports, dashed)
        if key in seen:
            continue
        seen.add(key)
        edges.append(_edge(source_id, app_ids[flow.target_app], flow.ports, dashed))
    return "\n".join(lines + edges)


def _has_policies(namespace: NamespaceInventory, app_name: str) -> bool:
    for app in namespace.apps:
        if app.name == app_name:
            return bool(app.network_policies)
    return False


def build_cluster_network_diagram(inventory: ClusterInventory) -> str:
    """Namespace-level aggregation of every allowed ingress flow - which
    namespaces (and generic actors) may reach into which. Edge labels carry
    the number of distinct app-level flows they summarize; the per-namespace
    network pages hold the detail. Flows within one namespace are that page's
    business and stay out of the cluster view.
    """
    lines = ["flowchart LR"]
    ns_ids = {}
    for ns in sorted(inventory.namespaces, key=lambda n: n.name):
        ns_id = _node_id("ns", ns.name)
        ns_ids[ns.name] = ns_id
        lines.append(f'  {ns_id}[["{ns.name}"]]')

    external_ids: dict[str, str] = {}
    counts: dict[tuple[str, str], int] = {}
    for ns in inventory.namespaces:
        for flow in namespace_flows(ns, inventory):
            source = flow.source
            if source.kind in ("app", "namespace"):
                if source.namespace == ns.name:
                    continue  # intra-namespace detail lives on the namespace page
                source_id = ns_ids.get(source.namespace or "")
                if source_id is None:
                    continue
            else:
                if source.name not in external_ids:
                    external_ids[source.name] = _node_id("ext", source.name)
                    lines.append(f'  {external_ids[source.name]}(["{source.name}"])')
                source_id = external_ids[source.name]
            key = (source_id, ns_ids[ns.name])
            counts[key] = counts.get(key, 0) + 1

    edges = [
        _edge(source_id, target_id, f"{count} flow{'s' if count != 1 else ''}", False)
        for (source_id, target_id), count in sorted(counts.items())
    ]
    return "\n".join(lines + edges)

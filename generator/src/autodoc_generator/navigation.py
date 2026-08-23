"""Navigation chrome for content pages: a breadcrumb back to the parent hub,
and a namespace-scoped sidebar (siblings apps + the namespace's own utility
pages) that replaces Material's global nav tree there. Deterministic
Markdown/HTML snippets, built only from names already in the inventory - same
hallucination boundary as facts.py, just navigational rather than factual.
"""

from __future__ import annotations

from autodoc_core.models import NamespaceInventory

# id (used as both the file stem and the `current` marker) -> display label.
NAMESPACE_PAGES = (
    ("topology", "Topology"),
    ("dependencies", "Dependencies"),
    ("resource-governance", "Resource Governance"),
)

CLUSTER_PAGES = (
    ("topology", "Topology"),
    ("findings", "Findings"),
    ("storage-classes", "Storage Classes"),
    ("nodes", "Nodes"),
    ("changelog", "Changelog"),
)


def breadcrumb(
    cluster_name: str, namespace_name: str | None = None, current: str | None = None
) -> str:
    """`current` is the deepest page's id/name - an app name, or one of
    CLUSTER_PAGES'/NAMESPACE_PAGES' ids - and is looked up to a display label
    and appended in bold. Omitted (None) on a hub page, where the
    cluster/namespace itself is the deepest/current page and gets the bold
    treatment instead.
    """
    if namespace_name is None:
        if current is None:
            return f"[homelab-autodoc](../index.md) · **{cluster_name}**"
        label = dict(CLUSTER_PAGES).get(current, current)
        return f"[homelab-autodoc](../index.md) · [{cluster_name}](index.md) · **{label}**"
    if current is None:
        return (
            f"[homelab-autodoc](../../index.md) · [{cluster_name}](../index.md) · "
            f"**{namespace_name}**"
        )
    label = dict(NAMESPACE_PAGES).get(current, current)
    return (
        f"[homelab-autodoc](../../index.md) · [{cluster_name}](../index.md) · "
        f"[{namespace_name}](index.md) · **{label}**"
    )


def _list_dot(ok: bool) -> str:
    return f'<span class="ns-list-dot {"ns-list-dot--ok" if ok else "ns-list-dot--warn"}"></span>'


def namespace_sidenav(namespace: NamespaceInventory, current: str) -> str:
    """`current` is an app name or one of NAMESPACE_PAGES' ids - whichever one
    matches renders as inert active text instead of a link to itself. Each app
    also gets a ready/not-ready dot, same as its card on the namespace hub.
    """
    lines = [f"[{namespace.name} →](index.md)", "", "**Applications**", ""]
    for app in sorted(namespace.apps, key=lambda a: a.name):
        dot = _list_dot(app.ready_replicas == app.replicas)
        if app.name == current:
            lines.append(f'- <span class="ns-active">{dot}{app.name}</span>')
        else:
            lines.append(f"- [{dot}{app.name}]({app.name}.md)")
    lines += ["", "**Namespace Pages**", ""]
    for page_id, label in NAMESPACE_PAGES:
        if page_id == current:
            lines.append(f'- <span class="ns-active">{label}</span>')
        else:
            lines.append(f"- [{label}]({page_id}.md)")
    return "\n".join(lines)


def cluster_page_links(current: str | None = None) -> str:
    """Chip-style links between the four cluster-scoped utility pages
    (topology/storage-classes/nodes/changelog) - the current page renders as
    an inert chip instead of a link to itself. `current=None` on the cluster
    hub page itself, where none of the four is "active".
    """
    parts = []
    for page_id, label in CLUSTER_PAGES:
        if page_id == current:
            parts.append(f'<span class="chip-link chip-link--active">{label}</span>')
        else:
            parts.append(f"[{label}]({page_id}.md){{: .chip-link }}")
    return " ".join(parts)

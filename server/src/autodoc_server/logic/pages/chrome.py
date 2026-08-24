"""Shared page chrome: front matter, breadcrumb + chip/sidebar layout
shells, and the responsive dual-variant diagram wrapper."""

from __future__ import annotations

from autodoc_core.models import NamespaceInventory
from autodoc_generator import navigation

HIDE_NAV_FRONTMATTER = "---\nhide:\n  - navigation\n---"


def cluster_content_page(
    cluster_name: str, current: str, heading: str, body: str, show_heading: bool = True
) -> str:
    """Shared shape for cluster-scoped content pages (topology, findings,
    images, storage classes, nodes): front matter + breadcrumb + the same
    chip row the cluster hub shows, marking `current` inert. The chips sit
    ABOVE the content: they are navigation, and below a long table (or the
    viewport-sized topology box) they were effectively invisible - on the
    topology page they were also the one element still forcing a scroll.

    show_heading=False drops the visible H1 (the topology page: breadcrumb
    and active chip already say where you are, and the heading's height came
    straight out of the diagram's viewport budget); the heading then goes
    into the front matter as `title:` so the browser tab and search keep it.
    """
    crumb = navigation.breadcrumb(cluster_name, current=current)
    front_matter = (
        HIDE_NAV_FRONTMATTER
        if show_heading
        else f'---\ntitle: "{heading}"\nhide:\n  - navigation\n---'
    )
    lines = [
        front_matter,
        "",
        f'<p class="ns-breadcrumb" markdown>{crumb}</p>',
        "",
        navigation.cluster_page_links(current),
        "",
    ]
    if show_heading:
        lines += [f"# {heading}", ""]
    lines.append(body)
    return "\n".join(lines)


def namespace_content_page(
    cluster_name: str, namespace: NamespaceInventory, current: str, heading: str, body: str
) -> str:
    """Shared shape for namespace-scoped content pages (topology, dependencies,
    resource governance): front matter + breadcrumb + the same compact,
    namespace-scoped sidebar app pages use (see navigation.py).
    """
    crumb = navigation.breadcrumb(cluster_name, namespace.name, current=current)
    lines = [
        HIDE_NAV_FRONTMATTER,
        "",
        f'<p class="ns-breadcrumb" markdown>{crumb}</p>',
        "",
        '<div class="ns-layout" markdown>',
        '<div class="ns-sidenav" markdown>',
        "",
        navigation.namespace_sidenav(namespace, current),
        "",
        "</div>",
        '<div class="ns-content" markdown>',
        "",
        f"# {heading}",
        "",
        body,
        "",
        "</div>",
        "</div>",
    ]
    return "\n".join(lines)


def responsive_diagram(wide: str, stacked: str) -> str:
    """Two pre-rendered variants of the same diagram, toggled purely by CSS
    breakpoint (mermaid-pan-zoom.css): desktops get the sideways-spread
    layout, phones keep the classic vertical stack. Both are in the DOM -
    Material renders Mermaid string-based, so the hidden one renders fine,
    and the pan-zoom script already skips hosts without layout.
    """
    return (
        '<div class="topology-variant topology-variant--wide" markdown>\n\n'
        f"```mermaid\n{wide}\n```\n\n"
        "</div>\n"
        '<div class="topology-variant topology-variant--stacked" markdown>\n\n'
        f"```mermaid\n{stacked}\n```\n\n"
        "</div>"
    )

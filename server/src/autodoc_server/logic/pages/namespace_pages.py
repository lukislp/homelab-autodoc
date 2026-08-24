"""Namespace-scoped content pages: topology, network, connections,
dependencies, resource governance."""

from __future__ import annotations

from autodoc_core.models import ClusterInventory, NamespaceInventory
from autodoc_generator import connections, diagrams, facts, network

from ..storage import Storage
from .chrome import namespace_content_page, responsive_diagram


def write_namespace_diagram(
    storage: Storage, cluster_name: str, namespace: NamespaceInventory
) -> None:
    body = responsive_diagram(
        wide=diagrams.build_namespace_diagram(namespace, spread=True),
        stacked=diagrams.build_namespace_diagram(namespace, spread=False),
    )
    page = namespace_content_page(
        cluster_name,
        namespace,
        "topology",
        f"{namespace.name} - Topology",
        body,
    )
    (storage.docs_dir / cluster_name / namespace.name / "topology.md").write_text(
        page, encoding="utf-8"
    )


def write_namespace_dependencies_page(
    storage: Storage, cluster_name: str, namespace: NamespaceInventory
) -> None:
    table = facts.dependency_usage_table(namespace)
    body = table if table else "No workload in this namespace references a ConfigMap or Secret."
    page = namespace_content_page(
        cluster_name, namespace, "dependencies", f"{namespace.name} - Dependencies", body
    )
    (storage.docs_dir / cluster_name / namespace.name / "dependencies.md").write_text(
        page, encoding="utf-8"
    )


def write_namespace_resource_governance_page(
    storage: Storage, cluster_name: str, namespace: NamespaceInventory
) -> None:
    quotas_table = facts.resource_quotas_table(namespace)
    limits_table = facts.limit_ranges_table(namespace)
    body = "\n\n".join(
        [
            "## Resource Quotas",
            quotas_table if quotas_table else "No ResourceQuotas exist in this namespace.",
            "## Limit Ranges",
            limits_table if limits_table else "No LimitRanges exist in this namespace.",
        ]
    )
    page = namespace_content_page(
        cluster_name,
        namespace,
        "resource-governance",
        f"{namespace.name} - Resource Governance",
        body,
    )
    (storage.docs_dir / cluster_name / namespace.name / "resource-governance.md").write_text(
        page, encoding="utf-8"
    )


def write_namespace_network_page(
    storage: Storage, cluster_name: str, namespace: NamespaceInventory, inventory: ClusterInventory
) -> None:
    """The namespace's allowed-traffic view - deliberately its own page next
    to (not inside) Topology: topology shows what exists, this shows what may
    talk to what, resolved from the collected NetworkPolicies.
    """
    diagram = network.build_namespace_network_diagram(namespace, inventory)
    body = "\n\n".join(
        [
            "Every allowed ingress flow into this namespace's apps, resolved from the "
            "collected NetworkPolicies. Solid edges are explicit policy allowances "
            "(labeled with their ports, unlabeled = all ports); dashed edges mark apps "
            "no policy selects - unrestricted by Kubernetes default.",
            f"```mermaid\n{diagram}\n```",
        ]
    )
    page = namespace_content_page(
        cluster_name, namespace, "network", f"{namespace.name} - Network", body
    )
    (storage.docs_dir / cluster_name / namespace.name / "network.md").write_text(
        page, encoding="utf-8"
    )


def write_namespace_connections_page(
    storage: Storage, cluster_name: str, namespace: NamespaceInventory, inventory: ClusterInventory
) -> None:
    """The third lens after Topology (what exists) and Network (what MAY
    talk): what each app is CONFIGURED to use, from its own plain-text
    config.
    """
    diagram = connections.build_namespace_connections_diagram(namespace, inventory)
    body = "\n\n".join(
        [
            "What each app is CONFIGURED to use - every edge is a service endpoint found in "
            "the app's own plain-text configuration (env values and referenced ConfigMap "
            "contents), resolved to the app owning that Service. Edge labels are the "
            "configured ports. Connection strings living only in Secrets are invisible here "
            "(the collector never reads Secrets), so an absent edge never proves absence - "
            "but every drawn edge is real and declared.",
            f"```mermaid\n{diagram}\n```",
        ]
    )
    page = namespace_content_page(
        cluster_name, namespace, "connections", f"{namespace.name} - Connections", body
    )
    (storage.docs_dir / cluster_name / namespace.name / "connections.md").write_text(
        page, encoding="utf-8"
    )

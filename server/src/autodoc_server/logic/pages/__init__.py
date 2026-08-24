"""One module per page family - site_builder stays the thin orchestrator."""

from .cluster_pages import (
    write_backups_page,
    write_changelog_page,
    write_cluster_connections_page,
    write_cluster_diagram,
    write_cluster_index,
    write_cluster_network_page,
    write_findings_page,
    write_images_page,
    write_nodes_page,
    write_storage_classes_page,
)
from .namespace_pages import (
    write_namespace_connections_page,
    write_namespace_dependencies_page,
    write_namespace_diagram,
    write_namespace_network_page,
    write_namespace_resource_governance_page,
)
from .root_page import write_root_index

__all__ = [
    "write_backups_page",
    "write_changelog_page",
    "write_cluster_connections_page",
    "write_cluster_diagram",
    "write_cluster_index",
    "write_cluster_network_page",
    "write_findings_page",
    "write_images_page",
    "write_namespace_connections_page",
    "write_namespace_dependencies_page",
    "write_namespace_diagram",
    "write_namespace_network_page",
    "write_namespace_resource_governance_page",
    "write_nodes_page",
    "write_root_index",
    "write_storage_classes_page",
]

from __future__ import annotations

import pytest
from autodoc_core.models import (
    App,
    ClusterInventory,
    Container,
    NamespaceInventory,
    StorageClassInfo,
)


@pytest.fixture
def sample_inventory() -> ClusterInventory:
    return ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-22T00:00:00+00:00",
        namespaces=[
            NamespaceInventory(
                name="demo",
                apps=[
                    App(
                        name="web",
                        kind="Deployment",
                        replicas=2,
                        ready_replicas=2,
                        containers=[Container(name="web", image="nginx:1.25.3", ports=[8080])],
                    )
                ],
            )
        ],
        storage_classes=[StorageClassInfo(name="local-path", provisioner="rancher.io/local-path")],
    )

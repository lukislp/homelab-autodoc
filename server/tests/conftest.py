from __future__ import annotations

import pytest
from autodoc_core.models import (
    App,
    ClusterInventory,
    ConfigReference,
    Container,
    NamespaceInventory,
    NodeInfo,
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
                        config_refs=[ConfigReference(kind="Secret", name="web-secrets", via="env")],
                    )
                ],
            )
        ],
        nodes=[
            NodeInfo(
                name="pi-node-1",
                architecture="arm64",
                kubelet_version="v1.31.2+k3s1",
                os_image="Debian GNU/Linux 12 (bookworm)",
                capacity_cpu="4",
                capacity_memory="8065700Ki",
                allocatable_cpu="3900m",
                allocatable_memory="7500000Ki",
                ready=True,
            )
        ],
    )

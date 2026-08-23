from __future__ import annotations

import pytest
from autodoc_core.models import (
    App,
    ClusterInventory,
    ConfigReference,
    Container,
    LimitRangeInfo,
    LimitRangeItemInfo,
    NamespaceInventory,
    NodeInfo,
    ResourceQuotaInfo,
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
                        config_refs=[ConfigReference(kind="Secret", name="web-secrets", via="env")],
                    )
                ],
                resource_quotas=[
                    ResourceQuotaInfo(
                        name="demo-quota",
                        hard={"requests.cpu": "4", "pods": "20"},
                        used={"requests.cpu": "1500m", "pods": "6"},
                    )
                ],
                limit_ranges=[
                    LimitRangeInfo(
                        name="demo-limits",
                        limits=[
                            LimitRangeItemInfo(
                                kind="Container",
                                default={"cpu": "500m", "memory": "256Mi"},
                                default_request={"cpu": "100m", "memory": "128Mi"},
                            )
                        ],
                    )
                ],
            )
        ],
        storage_classes=[StorageClassInfo(name="local-path", provisioner="rancher.io/local-path")],
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

from __future__ import annotations

from dataclasses import replace

import pytest

from autodoc_core.diff import diff_inventories
from autodoc_core.models import (
    App,
    ClusterInventory,
    Container,
    NamespaceInventory,
    ServiceInfo,
    Volume,
)


@pytest.fixture
def base_inventory() -> ClusterInventory:
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
                        volumes=[
                            Volume(
                                claim_name="web-data", storage_class="local-path", capacity="1Gi"
                            )
                        ],
                        services=[ServiceInfo(name="web", type="ClusterIP", cluster_ip="10.0.0.1")],
                    )
                ],
            )
        ],
    )


def test_diff_against_none_is_empty(base_inventory):
    assert diff_inventories(None, base_inventory) == []


def test_diff_no_changes_is_empty(base_inventory):
    assert diff_inventories(base_inventory, base_inventory) == []


def test_diff_ignores_ready_replicas_fluctuation(base_inventory):
    app = base_inventory.namespaces[0].apps[0]
    new_app = replace(app, ready_replicas=1)
    new_inventory = replace(
        base_inventory, namespaces=[replace(base_inventory.namespaces[0], apps=[new_app])]
    )

    assert diff_inventories(base_inventory, new_inventory) == []


def test_diff_detects_app_added(base_inventory):
    new_app = App(name="api", kind="Deployment", replicas=1, ready_replicas=1)
    apps = [*base_inventory.namespaces[0].apps, new_app]
    new_inventory = replace(
        base_inventory, namespaces=[replace(base_inventory.namespaces[0], apps=apps)]
    )

    changes = diff_inventories(base_inventory, new_inventory)

    assert len(changes) == 1
    assert changes[0].kind == "app_added"
    assert changes[0].app_name == "api"


def test_diff_detects_app_removed(base_inventory):
    empty_namespace = replace(base_inventory.namespaces[0], apps=[])
    new_inventory = replace(base_inventory, namespaces=[empty_namespace])

    changes = diff_inventories(base_inventory, new_inventory)

    assert len(changes) == 1
    assert changes[0].kind == "app_removed"
    assert changes[0].app_name == "web"


def test_diff_detects_image_change(base_inventory):
    app = base_inventory.namespaces[0].apps[0]
    new_app = replace(app, containers=[Container(name="web", image="nginx:1.26.0", ports=[8080])])
    new_inventory = replace(
        base_inventory, namespaces=[replace(base_inventory.namespaces[0], apps=[new_app])]
    )

    changes = diff_inventories(base_inventory, new_inventory)

    assert len(changes) == 1
    assert changes[0].kind == "app_changed"
    assert "container web image: nginx:1.25.3 -> nginx:1.26.0" in changes[0].details


def test_diff_detects_replicas_and_volume_change(base_inventory):
    app = base_inventory.namespaces[0].apps[0]
    new_app = replace(app, replicas=3, volumes=[])
    new_inventory = replace(
        base_inventory, namespaces=[replace(base_inventory.namespaces[0], apps=[new_app])]
    )

    changes = diff_inventories(base_inventory, new_inventory)

    assert changes[0].details == ["replicas: 2 -> 3", "volume web-data removed"]

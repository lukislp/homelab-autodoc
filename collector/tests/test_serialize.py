from __future__ import annotations

import json

import yaml

from autodoc_collector.models import App, ClusterInventory, Container, NamespaceInventory
from autodoc_collector.serialize import to_text


def _sample_inventory() -> ClusterInventory:
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
    )


def test_to_text_json_round_trips():
    text = to_text(_sample_inventory(), fmt="json")
    data = json.loads(text)

    assert data["cluster_name"] == "homelab"
    assert data["namespaces"][0]["apps"][0]["containers"][0]["image"] == "nginx:1.25.3"


def test_to_text_json_compact_has_no_indentation():
    text = to_text(_sample_inventory(), fmt="json", pretty=False)

    assert "\n" not in text
    assert json.loads(text)["cluster_name"] == "homelab"


def test_to_text_yaml_round_trips():
    text = to_text(_sample_inventory(), fmt="yaml")
    data = yaml.safe_load(text)

    assert data["cluster_name"] == "homelab"
    assert data["namespaces"][0]["name"] == "demo"

from __future__ import annotations

import json

from autodoc_core.models import (
    App,
    ClusterInventory,
    Container,
    IngressInfo,
    IngressRule,
    NamespaceInventory,
    ServiceInfo,
    ServicePort,
    Volume,
)
from autodoc_core.serialize import from_text, to_text


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
                        volumes=[
                            Volume(
                                claim_name="web-data",
                                storage_class="local-path",
                                capacity="1Gi",
                                access_modes=["ReadWriteOnce"],
                            )
                        ],
                        services=[
                            ServiceInfo(
                                name="web-svc",
                                type="ClusterIP",
                                cluster_ip="10.0.0.1",
                                ports=[ServicePort(port=80, target_port="8080", protocol="TCP")],
                            )
                        ],
                        ingresses=[
                            IngressInfo(
                                name="web-ingress",
                                rules=[
                                    IngressRule(path="/", service_name="web-svc", service_port="80")
                                ],
                                tls_hosts=["app.example.com"],
                            )
                        ],
                        labels={"tier": "frontend"},
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
    data = from_text(text, fmt="yaml")

    assert data == _sample_inventory()


def test_from_text_json_reconstructs_full_dataclass_tree():
    original = _sample_inventory()

    reconstructed = from_text(to_text(original, fmt="json"), fmt="json")

    assert reconstructed == original

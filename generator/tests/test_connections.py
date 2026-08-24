from __future__ import annotations

from autodoc_core.models import (
    App,
    ClusterInventory,
    NamespaceInventory,
    ServiceInfo,
    ServiceReference,
)

from autodoc_generator.connections import (
    build_cluster_connections_diagram,
    build_namespace_connections_diagram,
)


def _app(
    name: str,
    services: list[str] | None = None,
    references: list[ServiceReference] | None = None,
) -> App:
    return App(
        name=name,
        kind="Deployment",
        replicas=1,
        ready_replicas=1,
        services=[
            ServiceInfo(name=s, type="ClusterIP", cluster_ip="10.0.0.1") for s in services or []
        ],
        service_references=references or [],
    )


def test_same_namespace_reference_resolves_to_the_owning_app():
    # The motivating case: studylife-web's redis connection string.
    ns = NamespaceInventory(
        name="studylife-scale",
        apps=[
            _app(
                "studylife-web",
                references=[
                    ServiceReference(service="redis-cluster", port=6380, via="ConfigMap x/y")
                ],
            ),
            _app("redis", services=["redis-cluster"]),
        ],
    )

    diagram = build_namespace_connections_diagram(ns)

    assert '  app_studylife_web -->|"6380"| app_redis' in diagram


def test_cross_namespace_reference_renders_as_external_node():
    scale = NamespaceInventory(
        name="studylife-scale",
        apps=[
            _app(
                "studylife-web",
                references=[
                    ServiceReference(service="studylife-ai", namespace="studylife-ai", port=8000)
                ],
            )
        ],
    )
    ai = NamespaceInventory(
        name="studylife-ai", apps=[_app("studylife-ai", services=["studylife-ai"])]
    )
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-25T00:00:00+00:00",
        namespaces=[scale, ai],
    )

    diagram = build_namespace_connections_diagram(scale, inventory)

    assert '(["studylife-ai/studylife-ai"])' in diagram
    assert '-->|"8000"|' in diagram


def test_self_reference_is_skipped_and_unresolvable_stays_visible():
    ns = NamespaceInventory(
        name="demo",
        apps=[
            _app(
                "web",
                services=["web"],
                references=[
                    ServiceReference(service="web", port=443),  # its own public URL - noise
                    ServiceReference(service="ghost-db", port=5432),  # no owning app collected
                ],
            )
        ],
    )

    diagram = build_namespace_connections_diagram(ns)

    assert "app_web -->" in diagram  # only the ghost edge...
    assert diagram.count("-->") == 1
    assert '(["service ghost-db (demo)"])' in diagram


def test_cluster_diagram_shows_the_full_graph_in_subgraphs():
    scale = NamespaceInventory(
        name="studylife-scale",
        apps=[
            _app(
                "studylife-web",
                references=[
                    ServiceReference(service="redis-cluster", port=6380),
                    ServiceReference(service="studylife-ai", namespace="studylife-ai", port=8000),
                ],
            ),
            _app("redis", services=["redis-cluster"]),
        ],
    )
    ai = NamespaceInventory(
        name="studylife-ai", apps=[_app("studylife-ai", services=["studylife-ai"])]
    )
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-25T00:00:00+00:00",
        namespaces=[scale, ai],
    )

    diagram = build_cluster_connections_diagram(inventory)

    assert "subgraph ns_studylife_scale[studylife-scale]" in diagram
    assert "subgraph ns_studylife_ai[studylife-ai]" in diagram
    # Intra-namespace detail is part of the cluster picture too...
    assert '  app_studylife_scale_studylife_web -->|"6380"| app_studylife_scale_redis' in diagram
    # ...alongside the cross-namespace edge.
    assert '-->|"8000"|' in diagram


def test_empty_cluster_diagram_when_nothing_crosses_namespaces():
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-25T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=[_app("web")])],
    )

    assert build_cluster_connections_diagram(inventory) == ""


def test_cluster_diagram_survives_mixed_resolvable_and_unresolvable_targets():
    # Regression: one app with BOTH a resolvable and an unresolvable target
    # made sorted() compare None against str and crash the production rebuild.
    ns = NamespaceInventory(
        name="demo",
        apps=[
            _app(
                "web",
                references=[
                    ServiceReference(service="api", port=8080),
                    ServiceReference(service="ghost", port=1234),
                ],
            ),
            _app("api", services=["api"]),
        ],
    )
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-25T00:00:00+00:00",
        namespaces=[ns],
    )

    diagram = build_cluster_connections_diagram(inventory)

    assert '  app_demo_web -->|"8080"| app_demo_api' in diagram
    assert '(["service ghost (demo)"])' in diagram

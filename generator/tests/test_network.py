from __future__ import annotations

from autodoc_core.models import (
    App,
    ClusterInventory,
    NamespaceInventory,
    NetworkPolicyInfo,
    NetworkPolicyRule,
)

from autodoc_generator.network import (
    build_cluster_network_diagram,
    build_namespace_network_diagram,
)


def _app(name: str, pod_labels: dict | None = None, policies: list | None = None) -> App:
    return App(
        name=name,
        kind="Deployment",
        replicas=1,
        ready_replicas=1,
        pod_labels=pod_labels or {"app": name},
        network_policies=policies or [],
    )


def _allow(peers: list[str], ports: list[str] | None = None) -> NetworkPolicyInfo:
    return NetworkPolicyInfo(
        name="allow",
        policy_types=["Ingress"],
        ingress=[NetworkPolicyRule(peers=peers, ports=ports or [])],
    )


_DENY_ALL = NetworkPolicyInfo(name="default-deny-ingress", policy_types=["Ingress"], ingress=[])


def test_pod_selector_peer_resolves_to_the_source_app_with_ports():
    # The studylife-scale case that motivated the page: redis allows exactly
    # the web app - the diagram must show web -> redis, not just "a policy".
    ns = NamespaceInventory(
        name="studylife-scale",
        apps=[
            _app("studylife-web"),
            _app("redis", policies=[_DENY_ALL, _allow(["pods:app=studylife-web"], ["TCP/6379"])]),
        ],
    )

    diagram = build_namespace_network_diagram(ns)

    assert '  app_studylife_web -->|"TCP/6379"| app_redis' in diagram
    # The web app itself has no policy - unrestricted, shown dashed from "any source".
    assert '  ext_any_source(["any source"])' in diagram
    assert "  ext_any_source -.-> app_studylife_web" in diagram


def test_empty_peer_list_means_any_source_solid_edge():
    # Webhook pattern: the rule exists but restricts no sources.
    ns = NamespaceInventory(
        name="cert-manager",
        apps=[_app("webhook", policies=[_DENY_ALL, _allow([], ["TCP/10250"])])],
    )

    diagram = build_namespace_network_diagram(ns)

    assert '  ext_any_source -->|"TCP/10250"| app_webhook' in diagram
    assert "-.->" not in diagram  # explicit allowance, not an unrestricted app


def test_deny_all_only_app_gets_no_edges():
    ns = NamespaceInventory(name="demo", apps=[_app("locked", policies=[_DENY_ALL])])

    diagram = build_namespace_network_diagram(ns)

    assert '  app_locked[["locked"]]' in diagram
    assert "-->" not in diagram and "-.->" not in diagram


def test_cross_namespace_peer_resolves_to_the_concrete_app():
    monitoring = NamespaceInventory(name="monitoring", apps=[_app("prometheus")])
    target = NamespaceInventory(
        name="metallb-system",
        apps=[
            _app(
                "speaker",
                policies=[
                    _DENY_ALL,
                    _allow(
                        ["namespaces:kubernetes.io/metadata.name=monitoring+pods:app=prometheus"],
                        ["TCP/7472"],
                    ),
                ],
            )
        ],
    )
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-25T00:00:00+00:00",
        namespaces=[monitoring, target],
    )

    diagram = build_namespace_network_diagram(target, inventory)

    assert '  ext_monitoring_prometheus(["monitoring/prometheus"])' in diagram
    assert '  ext_monitoring_prometheus -->|"TCP/7472"| app_speaker' in diagram


def test_unresolvable_selectors_stay_visible_as_generic_nodes():
    ns = NamespaceInventory(
        name="demo",
        apps=[_app("web", policies=[_DENY_ALL, _allow(["namespaces:team=frontend"])])],
    )

    diagram = build_namespace_network_diagram(ns)

    assert "namespaces team=frontend" in diagram
    assert "--> app_web" in diagram


def test_cluster_diagram_aggregates_cross_namespace_flows_only():
    monitoring = NamespaceInventory(name="monitoring", apps=[_app("prometheus")])
    scale = NamespaceInventory(
        name="studylife-scale",
        apps=[
            _app("studylife-web"),
            _app(
                "redis",
                policies=[
                    _DENY_ALL,
                    _allow(["pods:app=studylife-web"], ["TCP/6379"]),
                    _allow(
                        ["namespaces:kubernetes.io/metadata.name=monitoring+pods:app=prometheus"],
                        ["TCP/9121"],
                    ),
                ],
            ),
        ],
    )
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-25T00:00:00+00:00",
        namespaces=[monitoring, scale],
    )

    diagram = build_cluster_network_diagram(inventory)

    # Cross-namespace: monitoring -> studylife-scale, exactly one flow.
    assert '  ns_monitoring -->|"1 flow"| ns_studylife_scale' in diagram
    # Intra-namespace web->redis stays on the namespace page, not here...
    assert "ns_studylife_scale -->" not in diagram
    # ...but the unrestricted web app still surfaces as an any-source flow.
    assert '  ext_any_source(["any source"])' in diagram

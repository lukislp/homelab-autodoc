from __future__ import annotations

from autodoc_core.models import (
    App,
    ClusterInventory,
    Container,
    ContainerSecurityInfo,
    NamespaceInventory,
    NetworkPolicyInfo,
    PodDisruptionBudgetInfo,
    ProbeInfo,
)

from autodoc_generator.findings import (
    cluster_findings_table,
    evaluate_app,
    evaluate_cluster,
    findings_table,
)


def _container(
    name: str = "web",
    image: str = "nginx:1.25.3",
    is_init: bool = False,
    probes: list[ProbeInfo] | None = None,
    limits: dict[str, str] | None = None,
    requests: dict[str, str] | None = None,
    security: ContainerSecurityInfo | None = None,
) -> Container:
    return Container(
        name=name,
        image=image,
        is_init=is_init,
        probes=probes or [],
        resource_limits=limits or {},
        resource_requests=requests or {},
        security=security,
    )


_HARDENED = ContainerSecurityInfo(run_as_non_root=True, allow_privilege_escalation=False)
_BOTH_PROBES = [
    ProbeInfo(kind="liveness", check="HTTP :8080/healthz"),
    ProbeInfo(kind="readiness", check="HTTP :8080/ready"),
]
_FULL_RESOURCES = {"cpu": "100m", "memory": "128Mi"}


def _clean_app(**overrides) -> App:
    """An app no rule fires on - each test then breaks exactly one fact."""
    defaults = dict(
        name="web",
        kind="Deployment",
        replicas=2,
        ready_replicas=2,
        containers=[
            _container(
                probes=_BOTH_PROBES,
                limits=dict(_FULL_RESOURCES),
                requests=dict(_FULL_RESOURCES),
                security=_HARDENED,
            )
        ],
        network_policies=[NetworkPolicyInfo(name="allow-web")],
        pod_disruption_budgets=[PodDisruptionBudgetInfo(name="web-pdb", min_available="1")],
    )
    defaults.update(overrides)
    return App(**defaults)


def _rules(app: App) -> set[str]:
    return {f.rule for f in evaluate_app(app)}


def test_clean_app_produces_no_findings():
    assert evaluate_app(_clean_app()) == []


def test_untagged_image_flags_latest_image_tag():
    app = _clean_app(
        containers=[
            _container(
                image="nginx",
                probes=_BOTH_PROBES,
                limits=dict(_FULL_RESOURCES),
                requests=dict(_FULL_RESOURCES),
                security=_HARDENED,
            )
        ]
    )

    findings = [f for f in evaluate_app(app) if f.rule == "latest-image-tag"]

    assert len(findings) == 1
    assert findings[0].subject == "container web"
    assert "has no tag" in findings[0].message


def test_latest_tag_flags_latest_image_tag():
    app = _clean_app(
        containers=[
            _container(
                image="ghcr.io/acme/web:latest",
                probes=_BOTH_PROBES,
                limits=dict(_FULL_RESOURCES),
                requests=dict(_FULL_RESOURCES),
                security=_HARDENED,
            )
        ]
    )

    assert "latest-image-tag" in _rules(app)


def test_registry_port_is_not_mistaken_for_a_tag():
    app = _clean_app(
        containers=[
            _container(
                image="registry.local:5000/web",
                probes=_BOTH_PROBES,
                limits=dict(_FULL_RESOURCES),
                requests=dict(_FULL_RESOURCES),
                security=_HARDENED,
            )
        ]
    )

    findings = [f for f in evaluate_app(app) if f.rule == "latest-image-tag"]

    assert len(findings) == 1
    assert "has no tag" in findings[0].message


def test_digest_pinned_image_is_not_flagged():
    app = _clean_app(
        containers=[
            _container(
                image="ghcr.io/acme/web@sha256:abc123",
                probes=_BOTH_PROBES,
                limits=dict(_FULL_RESOURCES),
                requests=dict(_FULL_RESOURCES),
                security=_HARDENED,
            )
        ]
    )

    assert "latest-image-tag" not in _rules(app)


def test_missing_both_probes_names_both():
    app = _clean_app(
        containers=[
            _container(
                limits=dict(_FULL_RESOURCES),
                requests=dict(_FULL_RESOURCES),
                security=_HARDENED,
            )
        ]
    )

    findings = [f for f in evaluate_app(app) if f.rule == "missing-probes"]

    assert len(findings) == 1
    assert "liveness or readiness" in findings[0].message


def test_missing_only_readiness_probe_names_just_that():
    app = _clean_app(
        containers=[
            _container(
                probes=[ProbeInfo(kind="liveness", check="HTTP :8080/healthz")],
                limits=dict(_FULL_RESOURCES),
                requests=dict(_FULL_RESOURCES),
                security=_HARDENED,
            )
        ]
    )

    findings = [f for f in evaluate_app(app) if f.rule == "missing-probes"]

    assert len(findings) == 1
    assert findings[0].message == "no readiness probe configured"


def test_partial_limits_name_the_missing_resource():
    app = _clean_app(
        containers=[
            _container(
                probes=_BOTH_PROBES,
                limits={"cpu": "500m"},
                requests=dict(_FULL_RESOURCES),
                security=_HARDENED,
            )
        ]
    )

    findings = [f for f in evaluate_app(app) if f.rule == "missing-resource-limits"]

    assert len(findings) == 1
    assert findings[0].message == "no memory limit set"


def test_missing_requests_flag_separately_from_limits():
    app = _clean_app(
        containers=[
            _container(probes=_BOTH_PROBES, limits=dict(_FULL_RESOURCES), security=_HARDENED)
        ]
    )

    rules = _rules(app)

    assert "missing-resource-requests" in rules
    assert "missing-resource-limits" not in rules


def test_absent_security_context_fires_both_security_rules():
    app = _clean_app(
        containers=[
            _container(
                probes=_BOTH_PROBES,
                limits=dict(_FULL_RESOURCES),
                requests=dict(_FULL_RESOURCES),
            )
        ]
    )

    rules = _rules(app)

    assert "run-as-root-allowed" in rules
    assert "privilege-escalation-allowed" in rules


def test_explicit_run_as_root_is_flagged():
    app = _clean_app(
        containers=[
            _container(
                probes=_BOTH_PROBES,
                limits=dict(_FULL_RESOURCES),
                requests=dict(_FULL_RESOURCES),
                security=ContainerSecurityInfo(
                    run_as_non_root=False, allow_privilege_escalation=False
                ),
            )
        ]
    )

    rules = _rules(app)

    assert "run-as-root-allowed" in rules
    assert "privilege-escalation-allowed" not in rules


def test_init_containers_are_exempt_from_probe_resource_and_security_rules():
    app = _clean_app(
        containers=[
            _container(name="init-migrate", image="migrate:1.0", is_init=True),
            _container(
                probes=_BOTH_PROBES,
                limits=dict(_FULL_RESOURCES),
                requests=dict(_FULL_RESOURCES),
                security=_HARDENED,
            ),
        ]
    )

    assert evaluate_app(app) == []


def test_init_containers_still_get_the_image_tag_rule():
    app = _clean_app(
        containers=[
            _container(name="init-migrate", image="migrate:latest", is_init=True),
            _container(
                probes=_BOTH_PROBES,
                limits=dict(_FULL_RESOURCES),
                requests=dict(_FULL_RESOURCES),
                security=_HARDENED,
            ),
        ]
    )

    findings = [f for f in evaluate_app(app) if f.rule == "latest-image-tag"]

    assert [f.subject for f in findings] == ["container init-migrate"]


def test_app_without_network_policy_is_flagged():
    app = _clean_app(network_policies=[])

    findings = [f for f in evaluate_app(app) if f.rule == "no-network-policy"]

    assert len(findings) == 1
    assert findings[0].subject == "workload"


def test_multi_replica_app_without_pdb_is_flagged():
    app = _clean_app(pod_disruption_budgets=[])

    findings = [f for f in evaluate_app(app) if f.rule == "missing-pdb"]

    assert len(findings) == 1
    assert "2 replicas" in findings[0].message


def test_single_replica_app_without_pdb_is_not_flagged():
    app = _clean_app(replicas=1, ready_replicas=1, pod_disruption_budgets=[])

    assert "missing-pdb" not in _rules(app)


def test_evaluate_cluster_attributes_findings_to_namespace_and_app():
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-23T00:00:00+00:00",
        namespaces=[
            NamespaceInventory(name="demo", apps=[_clean_app(network_policies=[])]),
            NamespaceInventory(name="clean", apps=[_clean_app(name="ok")]),
        ],
    )

    cluster_findings = evaluate_cluster(inventory)

    assert [(cf.namespace, cf.app, cf.finding.rule) for cf in cluster_findings] == [
        ("demo", "web", "no-network-policy")
    ]


def test_findings_table_renders_rule_subject_and_message():
    app = _clean_app(network_policies=[], pod_disruption_budgets=[])

    table = findings_table(evaluate_app(app))

    assert table.splitlines()[0] == "| Rule | Subject | Finding |"
    assert "| `missing-pdb` | workload |" in table
    assert "| `no-network-policy` | workload |" in table


def test_findings_table_empty_for_no_findings():
    assert findings_table([]) == ""


def test_cluster_findings_table_links_namespace_and_app():
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-23T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=[_clean_app(network_policies=[])])],
    )

    table = cluster_findings_table(inventory)

    assert "| [demo](demo/index.md) | [web](demo/web.md) | `no-network-policy` |" in table


def test_cluster_findings_table_empty_when_clean():
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-23T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=[_clean_app()])],
    )

    assert cluster_findings_table(inventory) == ""

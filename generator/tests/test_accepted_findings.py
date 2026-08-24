from __future__ import annotations

from autodoc_core.models import (
    App,
    ClusterInventory,
    Container,
    NamespaceInventory,
    NetworkPolicyInfo,
)

from autodoc_generator.findings import (
    accepted_findings_table,
    accepted_rules,
    cluster_accepted_findings_table,
    evaluate_app,
    evaluate_app_accepted,
    evaluate_cluster,
    evaluate_cluster_accepted,
)

_NS = NamespaceInventory(name="demo")


def _root_app(annotations: dict[str, str] | None = None) -> App:
    """Fires exactly run-as-root-allowed + privilege-escalation-allowed on its
    one container (no securityContext), everything else clean or silent.
    """
    return App(
        name="agent",
        kind="DaemonSet",
        replicas=1,
        ready_replicas=1,
        containers=[
            Container(
                name="agent",
                image="ghcr.io/example/agent:1.0.0",
                probes=[],
                resource_limits={"cpu": "100m", "memory": "64Mi"},
                resource_requests={"cpu": "100m", "memory": "64Mi"},
            )
        ],
        network_policies=[NetworkPolicyInfo(name="allow-agent")],
        annotations=annotations or {},
    )


def test_accepted_rules_reads_only_accept_annotations_with_a_reason():
    app = _root_app(
        annotations={
            "autodoc.homelab/accept-run-as-root-allowed": "reads root-owned host logs",
            "autodoc.homelab/accept-missing-probes": "   ",
            "autodoc.homelab/accept-": "prefix without a rule",
            "kubernetes.io/change-cause": "unrelated",
        }
    )

    assert accepted_rules(app) == {"run-as-root-allowed": "reads root-owned host logs"}


def test_accepted_rule_moves_the_finding_out_of_the_open_list():
    app = _root_app(
        annotations={"autodoc.homelab/accept-run-as-root-allowed": "reads root-owned host logs"}
    )

    open_rules = {f.rule for f in evaluate_app(app, _NS)}
    accepted = evaluate_app_accepted(app, _NS)

    assert "run-as-root-allowed" not in open_rules
    assert "privilege-escalation-allowed" in open_rules  # only the accepted rule moves
    assert [(af.finding.rule, af.reason) for af in accepted] == [
        ("run-as-root-allowed", "reads root-owned host logs")
    ]


def test_probe_findings_missing_probes_can_be_accepted_too():
    app = _root_app(annotations={"autodoc.homelab/accept-missing-probes": "no probe endpoint"})

    assert "missing-probes" not in {f.rule for f in evaluate_app(app, _NS)}
    assert {af.finding.rule for af in evaluate_app_accepted(app, _NS)} == {"missing-probes"}


def test_stale_acceptance_for_a_rule_that_no_longer_fires_is_inert():
    app = _root_app(annotations={"autodoc.homelab/accept-latest-image-tag": "was pinned since"})

    assert evaluate_app_accepted(app, _NS) == []
    # ...and the open findings are exactly what an unannotated app produces.
    unannotated = {f.rule for f in evaluate_app(_root_app(), _NS)}
    assert {f.rule for f in evaluate_app(app, _NS)} == unannotated


def test_evaluate_cluster_counts_only_open_findings():
    app = _root_app(
        annotations={
            "autodoc.homelab/accept-run-as-root-allowed": "reads root-owned host logs",
            "autodoc.homelab/accept-privilege-escalation-allowed": "needs setuid helpers",
            "autodoc.homelab/accept-missing-probes": "no probe endpoint",
        }
    )
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-24T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=[app])],
    )

    assert evaluate_cluster(inventory) == []
    accepted = evaluate_cluster_accepted(inventory)
    assert {(caf.namespace, caf.app, caf.finding.rule) for caf in accepted} == {
        ("demo", "agent", "run-as-root-allowed"),
        ("demo", "agent", "privilege-escalation-allowed"),
        ("demo", "agent", "missing-probes"),
    }


def test_accepted_findings_table_renders_rule_and_reason():
    app = _root_app(
        annotations={"autodoc.homelab/accept-run-as-root-allowed": "reads root-owned host logs"}
    )

    table = accepted_findings_table(evaluate_app_accepted(app, _NS))

    assert "| Rule | Subject | Finding | Accepted because |" in table
    assert "| `run-as-root-allowed` | container agent |" in table
    assert "| reads root-owned host logs |" in table


def test_cluster_accepted_findings_table_links_namespace_and_app():
    app = _root_app(
        annotations={"autodoc.homelab/accept-run-as-root-allowed": "reads root-owned host logs"}
    )
    inventory = ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-24T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=[app])],
    )

    table = cluster_accepted_findings_table(inventory)

    assert "| [demo](demo/index.md) | [agent](demo/agent.md) | `run-as-root-allowed` |" in table
    assert "| reads root-owned host logs |" in table
    assert (
        cluster_accepted_findings_table(
            ClusterInventory(cluster_name="empty", collected_at="2026-08-24T00:00:00+00:00")
        )
        == ""
    )

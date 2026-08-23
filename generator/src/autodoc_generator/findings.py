"""Deterministic best-practice findings, computed from the inventory alone.

Same hallucination boundary as facts.py: every rule is a pure predicate over
collected facts - no LLM, no scoring, no guesswork. A finding is a pointer to
a fact worth a second look ("this container pins no version"), not a verdict;
the site renders findings as review hints, never as pass/fail gates.

Rules only fire on facts the inventory positively shows. Anything the
collector didn't gather stays silent rather than being guessed at.
"""

from __future__ import annotations

from dataclasses import dataclass

from autodoc_core.models import App, ClusterInventory, Container


@dataclass(frozen=True, slots=True)
class Finding:
    rule: str  # stable kebab-case identifier, e.g. "latest-image-tag"
    subject: str  # what the rule fired on, e.g. "container web" or "workload"
    message: str


@dataclass(frozen=True, slots=True)
class ClusterFinding:
    """A Finding plus where in the cluster it lives - the aggregated
    per-cluster Findings page's row shape. `app` is empty for findings scoped
    to a namespace rather than a single workload.
    """

    namespace: str
    app: str
    finding: Finding


_WORKLOAD_SUBJECT = "workload"


def _image_tag(image: str) -> str | None:
    """The tag of an image reference, or None if there is none. Registry
    ports don't confuse this: a tag's ":" always comes after the last "/".
    """
    ref = image.split("@", 1)[0]
    last_segment = ref.rsplit("/", 1)[-1]
    if ":" not in last_segment:
        return None
    return last_segment.rsplit(":", 1)[-1]


def _image_tag_findings(app: App) -> list[Finding]:
    findings = []
    for c in app.containers:
        if "@" in c.image:
            continue  # digest-pinned - immutable, nothing floats
        tag = _image_tag(c.image)
        if tag is None:
            message = f"image `{c.image}` has no tag and floats on latest"
        elif tag == "latest":
            message = f"image `{c.image}` floats on the latest tag"
        else:
            continue
        findings.append(
            Finding(rule="latest-image-tag", subject=f"container {c.name}", message=message)
        )
    return findings


def _run_containers(app: App) -> list[Container]:
    """Init containers are exempt from the probe/resource/security rules
    below: they run to completion before the app serves, so liveness or
    limits guidance aimed at long-running containers doesn't apply.
    """
    return [c for c in app.containers if not c.is_init]


def _probe_findings(app: App) -> list[Finding]:
    findings = []
    for c in _run_containers(app):
        kinds = {p.kind for p in c.probes}
        missing = [kind for kind in ("liveness", "readiness") if kind not in kinds]
        if not missing:
            continue
        findings.append(
            Finding(
                rule="missing-probes",
                subject=f"container {c.name}",
                message=f"no {' or '.join(missing)} probe configured",
            )
        )
    return findings


def _resource_findings(app: App) -> list[Finding]:
    findings = []
    for c in _run_containers(app):
        missing_limits = [r for r in ("cpu", "memory") if r not in c.resource_limits]
        if missing_limits:
            findings.append(
                Finding(
                    rule="missing-resource-limits",
                    subject=f"container {c.name}",
                    message=f"no {'/'.join(missing_limits)} limit set",
                )
            )
        missing_requests = [r for r in ("cpu", "memory") if r not in c.resource_requests]
        if missing_requests:
            findings.append(
                Finding(
                    rule="missing-resource-requests",
                    subject=f"container {c.name}",
                    message=f"no {'/'.join(missing_requests)} request set",
                )
            )
    return findings


def _security_findings(app: App) -> list[Finding]:
    # `security is None` (no securityContext at all) fires both rules: the
    # Kubernetes defaults are exactly the permissive case each rule flags.
    findings = []
    for c in _run_containers(app):
        if c.security is None or c.security.run_as_non_root is not True:
            findings.append(
                Finding(
                    rule="run-as-root-allowed",
                    subject=f"container {c.name}",
                    message="runAsNonRoot is not enforced - the container may run as root",
                )
            )
        if c.security is None or c.security.allow_privilege_escalation is not False:
            findings.append(
                Finding(
                    rule="privilege-escalation-allowed",
                    subject=f"container {c.name}",
                    message="allowPrivilegeEscalation is not disabled",
                )
            )
    return findings


def _network_policy_findings(app: App) -> list[Finding]:
    if app.network_policies:
        return []
    return [
        Finding(
            rule="no-network-policy",
            subject=_WORKLOAD_SUBJECT,
            message="no NetworkPolicy selects this workload's pods - traffic is unrestricted",
        )
    ]


def _pdb_findings(app: App) -> list[Finding]:
    # A PDB on a single replica is pointless (any disruption takes the one
    # pod either way), so only multi-replica workloads are held to this.
    if app.replicas < 2 or app.pod_disruption_budgets:
        return []
    return [
        Finding(
            rule="missing-pdb",
            subject=_WORKLOAD_SUBJECT,
            message=(
                f"{app.replicas} replicas but no PodDisruptionBudget - "
                "a node drain may take all of them down at once"
            ),
        )
    ]


def evaluate_app(app: App) -> list[Finding]:
    return [
        *_image_tag_findings(app),
        *_probe_findings(app),
        *_resource_findings(app),
        *_security_findings(app),
        *_network_policy_findings(app),
        *_pdb_findings(app),
    ]


def evaluate_cluster(inventory: ClusterInventory) -> list[ClusterFinding]:
    return [
        ClusterFinding(namespace=namespace.name, app=app.name, finding=finding)
        for namespace in inventory.namespaces
        for app in namespace.apps
        for finding in evaluate_app(app)
    ]


def findings_table(findings: list[Finding]) -> str:
    if not findings:
        return ""
    rows = [
        f"| `{f.rule}` | {f.subject} | {f.message} |"
        for f in sorted(findings, key=lambda f: (f.subject, f.rule))
    ]
    return "\n".join(["| Rule | Subject | Finding |", "|---|---|---|", *rows])


def cluster_findings_table(inventory: ClusterInventory) -> str:
    cluster_findings = evaluate_cluster(inventory)
    if not cluster_findings:
        return ""
    rows = [
        f"| [{cf.namespace}]({cf.namespace}/index.md) | "
        f"[{cf.app}]({cf.namespace}/{cf.app}.md) | "
        f"`{cf.finding.rule}` | {cf.finding.subject} | {cf.finding.message} |"
        for cf in sorted(
            cluster_findings,
            key=lambda cf: (cf.namespace, cf.app, cf.finding.subject, cf.finding.rule),
        )
    ]
    header = "| Namespace | App | Rule | Subject | Finding |"
    return "\n".join([header, "|---|---|---|---|---|", *rows])

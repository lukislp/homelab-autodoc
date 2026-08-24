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

from autodoc_core.models import App, ClusterInventory, Container, NamespaceInventory


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


@dataclass(frozen=True, slots=True)
class AcceptedFinding:
    """A finding the workload's own manifest acknowledges as a deliberate
    decision, plus the mandatory human reason from the annotation value.
    """

    finding: Finding
    reason: str


@dataclass(frozen=True, slots=True)
class ClusterAcceptedFinding:
    namespace: str
    app: str
    finding: Finding
    reason: str


# One workload-object annotation acknowledges one rule:
#   autodoc.homelab/accept-<rule>: "<why this is deliberate>"
# The value is the mandatory reason - an empty one is ignored rather than
# silently accepting. Acceptance lives in the workload's own manifest, so it
# is reviewed and versioned next to the decision it excuses and disappears
# with the workload, instead of surviving it in a central list. Only
# app-scoped rules can be accepted this way: namespace-scoped findings have
# no workload object to carry the annotation.
_ACCEPT_ANNOTATION_PREFIX = "autodoc.homelab/accept-"


def accepted_rules(app: App) -> dict[str, str]:
    """Rule name -> reason, from the workload's accept annotations."""
    accepted = {}
    for key, value in app.annotations.items():
        if not key.startswith(_ACCEPT_ANNOTATION_PREFIX):
            continue
        rule = key.removeprefix(_ACCEPT_ANNOTATION_PREFIX)
        reason = value.strip()
        if rule and reason:
            accepted[rule] = reason
    return accepted


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
    # A CronJob's pods run to completion - readiness has nothing to gate and
    # liveness guidance aimed at long-running servers doesn't apply, so the
    # rule would only ever produce noise there (it flagged the project's own
    # collector CronJob in production).
    if app.kind == "CronJob":
        return []
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
        if c.security is not None and c.security.privileged:
            # privileged: true IS the explicit maximal grant - a privileged
            # container is always root-capable (the API even rejects
            # allowPrivilegeEscalation: false next to it), so the two
            # sub-rules below would only echo this finding twice.
            findings.append(
                Finding(
                    rule="privileged-container",
                    subject=f"container {c.name}",
                    message="privileged: true - full access to the host's devices and kernel",
                )
            )
            continue
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
    # DaemonSets are exempt too: their "replicas" are just the node count,
    # and a drain skips them entirely (kubectl drain --ignore-daemonsets),
    # so a PDB protects nothing there - in production this rule's only hits
    # were DaemonSets.
    if app.kind == "DaemonSet" or app.replicas < 2 or app.pod_disruption_budgets:
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


def _config_reference_findings(app: App, namespace: NamespaceInventory) -> list[Finding]:
    """Fires only when the collector actually gathered the namespace's
    ConfigMap names (configmap_names is not None) - an older collector or
    denied RBAC means "unknown", and unknown never becomes a finding. Secret
    references are never checked: the collector deliberately has no secrets
    access (see its RBAC manifest), so their existence is unknowable here.
    """
    if namespace.configmap_names is None:
        return []
    existing = set(namespace.configmap_names)
    return [
        Finding(
            rule="missing-configmap",
            subject=f"ConfigMap {ref.name}",
            message=f"referenced via {ref.via} but no such ConfigMap exists in the namespace",
        )
        for ref in app.config_refs
        if ref.kind == "ConfigMap" and ref.name not in existing
    ]


# ConfigMaps that exist by platform design without any workload referencing
# them - never orphans. kube-root-ca.crt: in every namespace since
# Kubernetes 1.21, mounted implicitly for API-server trust.
# cnpg-default-monitoring: CloudNativePG's operator places it in its own and
# every Cluster's namespace and consumes it through the Cluster CRD's
# monitoring spec - a resource kind this inventory doesn't collect.
_WELL_KNOWN_CONFIGMAPS = frozenset({"kube-root-ca.crt", "cnpg-default-monitoring"})


def evaluate_namespace(namespace: NamespaceInventory) -> list[Finding]:
    """Namespace-scoped rules (not attributable to a single workload):
    currently just orphaned ConfigMaps. Worded as "no collected workload
    references it" deliberately - a ConfigMap may serve something outside
    the collected workload kinds (a Job, an operator reading it directly),
    which this inventory can't see.
    """
    if namespace.configmap_names is None:
        return []
    referenced = {
        ref.name for app in namespace.apps for ref in app.config_refs if ref.kind == "ConfigMap"
    }
    return [
        Finding(
            rule="orphaned-configmap",
            subject=f"ConfigMap {name}",
            message="exists but no collected workload references it",
        )
        for name in namespace.configmap_names
        if name not in referenced and name not in _WELL_KNOWN_CONFIGMAPS
    ]


def _all_app_findings(app: App, namespace: NamespaceInventory) -> list[Finding]:
    return [
        *_image_tag_findings(app),
        *_probe_findings(app),
        *_resource_findings(app),
        *_security_findings(app),
        *_network_policy_findings(app),
        *_pdb_findings(app),
        *_config_reference_findings(app, namespace),
    ]


def evaluate_app(app: App, namespace: NamespaceInventory) -> list[Finding]:
    """Open findings only. Rules the workload's accept annotations
    acknowledge are excluded here and surface via evaluate_app_accepted
    instead - so every existing table and count stays an honest "needs a
    look" without each caller having to know about acceptance.
    """
    accepted = accepted_rules(app)
    return [f for f in _all_app_findings(app, namespace) if f.rule not in accepted]


def evaluate_app_accepted(app: App, namespace: NamespaceInventory) -> list[AcceptedFinding]:
    """The findings evaluate_app suppressed, each with its annotation's
    reason. An accepted rule that no longer fires produces nothing - a stale
    annotation is inert, not an error.
    """
    accepted = accepted_rules(app)
    return [
        AcceptedFinding(finding=f, reason=accepted[f.rule])
        for f in _all_app_findings(app, namespace)
        if f.rule in accepted
    ]


def evaluate_cluster(inventory: ClusterInventory) -> list[ClusterFinding]:
    per_app = [
        ClusterFinding(namespace=namespace.name, app=app.name, finding=finding)
        for namespace in inventory.namespaces
        for app in namespace.apps
        for finding in evaluate_app(app, namespace)
    ]
    per_namespace = [
        ClusterFinding(namespace=namespace.name, app="", finding=finding)
        for namespace in inventory.namespaces
        for finding in evaluate_namespace(namespace)
    ]
    return per_app + per_namespace + _backup_findings(inventory)[0]


def evaluate_cluster_accepted(inventory: ClusterInventory) -> list[ClusterAcceptedFinding]:
    per_app = [
        ClusterAcceptedFinding(
            namespace=namespace.name, app=app.name, finding=af.finding, reason=af.reason
        )
        for namespace in inventory.namespaces
        for app in namespace.apps
        for af in evaluate_app_accepted(app, namespace)
    ]
    return per_app + _backup_findings(inventory)[1]


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
        + (f"[{cf.app}]({cf.namespace}/{cf.app}.md) | " if cf.app else "- | ")
        + f"`{cf.finding.rule}` | {cf.finding.subject} | {cf.finding.message} |"
        for cf in sorted(
            cluster_findings,
            key=lambda cf: (cf.namespace, cf.app, cf.finding.subject, cf.finding.rule),
        )
    ]
    header = "| Namespace | App | Rule | Subject | Finding |"
    return "\n".join([header, "|---|---|---|---|---|", *rows])


def accepted_findings_table(accepted: list[AcceptedFinding]) -> str:
    if not accepted:
        return ""
    rows = [
        f"| `{af.finding.rule}` | {af.finding.subject} | {af.finding.message} | {af.reason} |"
        for af in sorted(accepted, key=lambda af: (af.finding.subject, af.finding.rule))
    ]
    header = "| Rule | Subject | Finding | Accepted because |"
    return "\n".join([header, "|---|---|---|---|", *rows])


def cluster_accepted_findings_table(inventory: ClusterInventory) -> str:
    accepted = evaluate_cluster_accepted(inventory)
    if not accepted:
        return ""
    rows = [
        f"| [{caf.namespace}]({caf.namespace}/index.md) | "
        f"[{caf.app}]({caf.namespace}/{caf.app}.md) | "
        f"`{caf.finding.rule}` | {caf.finding.subject} | {caf.finding.message} | {caf.reason} |"
        for caf in sorted(
            accepted,
            key=lambda caf: (caf.namespace, caf.app, caf.finding.subject, caf.finding.rule),
        )
    ]
    header = "| Namespace | App | Rule | Subject | Finding | Accepted because |"
    return "\n".join([header, "|---|---|---|---|---|---|", *rows])


def _backup_findings(
    inventory: ClusterInventory,
) -> tuple[list[ClusterFinding], list[ClusterAcceptedFinding]]:
    """Cluster-scoped backup-coverage rules. They need the Velero schedules,
    which only exist at inventory level, so they live here instead of
    evaluate_app - and stay silent when backup posture wasn't collected
    (None): unknown never becomes a finding.

    no-backup: a PVC-backed workload without the file-system-backup opt-in.
    backup-not-scheduled: the opt-in annotation is present but NO Velero
    Schedule includes the workload's namespace - the exact silent failure
    mode found in production: the annotation does nothing, with no error
    anywhere.
    """
    if inventory.backups is None:
        return [], []
    covered = {
        ns for schedule in inventory.backups.velero_schedules for ns in schedule.included_namespaces
    }
    open_findings: list[ClusterFinding] = []
    accepted: list[ClusterAcceptedFinding] = []
    for namespace in inventory.namespaces:
        for app in namespace.apps:
            finding = None
            if app.volumes and not app.backup_volumes:
                finding = Finding(
                    rule="no-backup",
                    subject=_WORKLOAD_SUBJECT,
                    message=(
                        f"{len(app.volumes)} persistent volume(s) but no "
                        "backup.velero.io/backup-volumes opt-in - not part of any "
                        "file-system backup"
                    ),
                )
            elif app.backup_volumes and namespace.name not in covered:
                finding = Finding(
                    rule="backup-not-scheduled",
                    subject=_WORKLOAD_SUBJECT,
                    message=(
                        "volumes are opted into Velero but no Schedule includes this "
                        "namespace - the annotation silently does nothing"
                    ),
                )
            if finding is None:
                continue
            reasons = accepted_rules(app)
            if finding.rule in reasons:
                accepted.append(
                    ClusterAcceptedFinding(
                        namespace=namespace.name,
                        app=app.name,
                        finding=finding,
                        reason=reasons[finding.rule],
                    )
                )
            else:
                open_findings.append(
                    ClusterFinding(namespace=namespace.name, app=app.name, finding=finding)
                )
    return open_findings, accepted

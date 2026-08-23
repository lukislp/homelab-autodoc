"""One adapter per Kubernetes workload kind, normalized to a common shape.

To add a kind (DaemonSet, CronJob, ...): implement `kind` + `list()`/`normalize()`
and add an instance to DEFAULT_WORKLOAD_COLLECTORS. collect.py never changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from autodoc_core.models import ConfigReference, Container, EnvVar, ProbeInfo, RolloutStrategyInfo
from kubernetes import client

from .k8s_apis import K8sApis


@dataclass(frozen=True, slots=True)
class NormalizedWorkload:
    kind: str
    name: str
    replicas: int
    ready_replicas: int
    pod_labels: dict[str, str]
    containers: list[Container] = field(default_factory=list)
    claim_names: frozenset[str] = frozenset()
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    created_at: str | None = None
    owners: list[str] = field(default_factory=list)
    config_refs: frozenset[ConfigReference] = frozenset()
    service_account_name: str | None = None
    node_selector: dict[str, str] = field(default_factory=dict)
    node_affinity: list[str] = field(default_factory=list)
    tolerations: list[str] = field(default_factory=list)
    rollout_strategy: RolloutStrategyInfo | None = None
    image_pull_secrets: frozenset[str] = frozenset()


class WorkloadCollector(Protocol):
    kind: str

    def list(self, apis: K8sApis, namespace: str) -> list[NormalizedWorkload]: ...


def _env_vars_from_container(c: client.V1Container) -> list[EnvVar]:
    result: list[EnvVar] = []
    for e in c.env or []:
        value_from = e.value_from
        if value_from is None:
            result.append(EnvVar(name=e.name, value=e.value))
        elif value_from.config_map_key_ref:
            ref = value_from.config_map_key_ref
            result.append(EnvVar(name=e.name, value_from=f"ConfigMap:{ref.name}/{ref.key}"))
        elif value_from.secret_key_ref:
            ref = value_from.secret_key_ref
            result.append(EnvVar(name=e.name, value_from=f"Secret:{ref.name}/{ref.key}"))
        else:
            # field_ref/resource_field_ref (e.g. pod IP, resource limits) - not a
            # ConfigMap/Secret dependency, no value worth surfacing either.
            result.append(EnvVar(name=e.name))
    return result


def _describe_probe_check(probe: client.V1Probe) -> str:
    if probe.http_get:
        g = probe.http_get
        return f"{g.scheme or 'HTTP'} :{g.port}{g.path or '/'}"
    if probe.tcp_socket:
        return f"TCP :{probe.tcp_socket.port}"
    if probe.grpc:
        return f"gRPC :{probe.grpc.port}"
    if probe.exec:
        return f"exec: {' '.join(probe.exec.command or [])}"
    return "unknown"


def _probes_from_container(c: client.V1Container) -> list[ProbeInfo]:
    probes = []
    for kind, probe in (
        ("liveness", c.liveness_probe),
        ("readiness", c.readiness_probe),
        ("startup", c.startup_probe),
    ):
        if probe is None:
            continue
        probes.append(
            ProbeInfo(
                kind=kind, check=_describe_probe_check(probe), period_seconds=probe.period_seconds
            )
        )
    return probes


def _build_container(c: client.V1Container, is_init: bool) -> Container:
    return Container(
        name=c.name,
        image=c.image,
        ports=[p.container_port for p in (c.ports or [])],
        resource_requests=dict((c.resources.requests or {}) if c.resources else {}),
        resource_limits=dict((c.resources.limits or {}) if c.resources else {}),
        env=_env_vars_from_container(c),
        is_init=is_init,
        probes=_probes_from_container(c),
    )


def _containers_from_pod_spec(pod_spec: client.V1PodSpec) -> list[Container]:
    return [_build_container(c, is_init=True) for c in (pod_spec.init_containers or [])] + [
        _build_container(c, is_init=False) for c in pod_spec.containers
    ]


def _claim_names_from_pod_spec(pod_spec: client.V1PodSpec) -> frozenset[str]:
    return frozenset(
        volume.persistent_volume_claim.claim_name
        for volume in (pod_spec.volumes or [])
        if volume.persistent_volume_claim
    )


def _config_refs_from_pod_spec(pod_spec: client.V1PodSpec) -> frozenset[ConfigReference]:
    refs: set[ConfigReference] = set()
    for c in [*(pod_spec.init_containers or []), *pod_spec.containers]:
        for e in c.env or []:
            value_from = e.value_from
            if value_from and value_from.config_map_key_ref:
                refs.add(
                    ConfigReference(
                        kind="ConfigMap", name=value_from.config_map_key_ref.name, via="env"
                    )
                )
            elif value_from and value_from.secret_key_ref:
                refs.add(
                    ConfigReference(kind="Secret", name=value_from.secret_key_ref.name, via="env")
                )
        for env_from in c.env_from or []:
            if env_from.config_map_ref:
                refs.add(
                    ConfigReference(
                        kind="ConfigMap", name=env_from.config_map_ref.name, via="envFrom"
                    )
                )
            elif env_from.secret_ref:
                refs.add(
                    ConfigReference(kind="Secret", name=env_from.secret_ref.name, via="envFrom")
                )
    for volume in pod_spec.volumes or []:
        if volume.config_map:
            refs.add(ConfigReference(kind="ConfigMap", name=volume.config_map.name, via="volume"))
        elif volume.secret:
            refs.add(ConfigReference(kind="Secret", name=volume.secret.secret_name, via="volume"))
    return frozenset(refs)


def _describe_node_selector_requirement(req: client.V1NodeSelectorRequirement) -> str:
    if req.operator in ("Exists", "DoesNotExist"):
        return f"{req.key} {req.operator}"
    return f"{req.key} {req.operator} ({','.join(req.values or [])})"


def _describe_node_selector_term(term: client.V1NodeSelectorTerm) -> str:
    parts = [_describe_node_selector_requirement(r) for r in (term.match_expressions or [])]
    parts += [_describe_node_selector_requirement(r) for r in (term.match_fields or [])]
    return " AND ".join(parts) if parts else "any node"


def _node_affinity_from_pod_spec(pod_spec: client.V1PodSpec) -> list[str]:
    affinity = pod_spec.affinity.node_affinity if pod_spec.affinity else None
    if not affinity:
        return []
    result = []
    required = affinity.required_during_scheduling_ignored_during_execution
    for term in (required.node_selector_terms if required else None) or []:
        result.append(f"required: {_describe_node_selector_term(term)}")
    for preferred in affinity.preferred_during_scheduling_ignored_during_execution or []:
        description = _describe_node_selector_term(preferred.preference)
        result.append(f"preferred (weight {preferred.weight}): {description}")
    return result


def _describe_toleration(t: client.V1Toleration) -> str:
    if t.operator == "Exists" and not t.key:
        base = "all taints"
    elif t.operator == "Exists":
        base = f"{t.key} Exists"
    else:
        base = f"{t.key}={t.value}" if t.value else (t.key or "")
    effect = f":{t.effect}" if t.effect else ""
    seconds = f" ({t.toleration_seconds}s)" if t.toleration_seconds is not None else ""
    return f"{base}{effect}{seconds}"


def _tolerations_from_pod_spec(pod_spec: client.V1PodSpec) -> list[str]:
    return [_describe_toleration(t) for t in (pod_spec.tolerations or [])]


def _owners_from_metadata(meta: client.V1ObjectMeta) -> list[str]:
    return [f"{o.kind}/{o.name}" for o in (meta.owner_references or [])]


def _image_pull_secrets_from_pod_spec(pod_spec: client.V1PodSpec) -> frozenset[str]:
    return frozenset(
        ref.name for ref in (pod_spec.image_pull_secrets or []) if ref.name is not None
    )


def _rollout_strategy_from_deployment(
    strategy: client.V1DeploymentStrategy | None,
) -> RolloutStrategyInfo | None:
    if strategy is None or not strategy.type:
        return None
    rolling_update = strategy.rolling_update
    return RolloutStrategyInfo(
        strategy_type=strategy.type,
        max_surge=str(rolling_update.max_surge)
        if rolling_update and rolling_update.max_surge is not None
        else None,
        max_unavailable=str(rolling_update.max_unavailable)
        if rolling_update and rolling_update.max_unavailable is not None
        else None,
    )


def _rollout_strategy_from_daemon_set(
    strategy: client.V1DaemonSetUpdateStrategy | None,
) -> RolloutStrategyInfo | None:
    if strategy is None or not strategy.type:
        return None
    rolling_update = strategy.rolling_update
    return RolloutStrategyInfo(
        strategy_type=strategy.type,
        max_surge=str(rolling_update.max_surge)
        if rolling_update and rolling_update.max_surge is not None
        else None,
        max_unavailable=str(rolling_update.max_unavailable)
        if rolling_update and rolling_update.max_unavailable is not None
        else None,
    )


def _rollout_strategy_from_stateful_set(
    strategy: client.V1StatefulSetUpdateStrategy | None,
) -> RolloutStrategyInfo | None:
    if strategy is None or not strategy.type:
        return None
    rolling_update = strategy.rolling_update
    return RolloutStrategyInfo(
        strategy_type=strategy.type,
        max_unavailable=str(rolling_update.max_unavailable)
        if rolling_update and rolling_update.max_unavailable is not None
        else None,
        partition=rolling_update.partition if rolling_update else None,
    )


class DeploymentCollector:
    kind = "Deployment"

    def list(self, apis: K8sApis, namespace: str) -> list[NormalizedWorkload]:
        items = apis.apps_v1.list_namespaced_deployment(namespace).items
        return [self.normalize(item) for item in items]

    def normalize(self, deployment: client.V1Deployment) -> NormalizedWorkload:
        pod_spec = deployment.spec.template.spec
        meta = deployment.metadata
        return NormalizedWorkload(
            kind=self.kind,
            name=meta.name,
            replicas=deployment.spec.replicas or 0,
            ready_replicas=((deployment.status.ready_replicas or 0) if deployment.status else 0),
            pod_labels=deployment.spec.template.metadata.labels or {},
            containers=_containers_from_pod_spec(pod_spec),
            claim_names=_claim_names_from_pod_spec(pod_spec),
            labels=dict(meta.labels or {}),
            annotations=dict(meta.annotations or {}),
            created_at=meta.creation_timestamp.isoformat() if meta.creation_timestamp else None,
            owners=_owners_from_metadata(meta),
            config_refs=_config_refs_from_pod_spec(pod_spec),
            service_account_name=pod_spec.service_account_name,
            node_selector=dict(pod_spec.node_selector or {}),
            node_affinity=_node_affinity_from_pod_spec(pod_spec),
            tolerations=_tolerations_from_pod_spec(pod_spec),
            rollout_strategy=_rollout_strategy_from_deployment(deployment.spec.strategy),
            image_pull_secrets=_image_pull_secrets_from_pod_spec(pod_spec),
        )


class StatefulSetCollector:
    kind = "StatefulSet"

    def list(self, apis: K8sApis, namespace: str) -> list[NormalizedWorkload]:
        items = apis.apps_v1.list_namespaced_stateful_set(namespace).items
        return [self.normalize(item) for item in items]

    def normalize(self, stateful_set: client.V1StatefulSet) -> NormalizedWorkload:
        pod_spec = stateful_set.spec.template.spec
        meta = stateful_set.metadata
        return NormalizedWorkload(
            kind=self.kind,
            name=meta.name,
            replicas=stateful_set.spec.replicas or 0,
            ready_replicas=(
                (stateful_set.status.ready_replicas or 0) if stateful_set.status else 0
            ),
            pod_labels=stateful_set.spec.template.metadata.labels or {},
            containers=_containers_from_pod_spec(pod_spec),
            claim_names=_claim_names_from_pod_spec(pod_spec),
            labels=dict(meta.labels or {}),
            annotations=dict(meta.annotations or {}),
            created_at=meta.creation_timestamp.isoformat() if meta.creation_timestamp else None,
            owners=_owners_from_metadata(meta),
            config_refs=_config_refs_from_pod_spec(pod_spec),
            service_account_name=pod_spec.service_account_name,
            node_selector=dict(pod_spec.node_selector or {}),
            node_affinity=_node_affinity_from_pod_spec(pod_spec),
            tolerations=_tolerations_from_pod_spec(pod_spec),
            rollout_strategy=_rollout_strategy_from_stateful_set(stateful_set.spec.update_strategy),
            image_pull_secrets=_image_pull_secrets_from_pod_spec(pod_spec),
        )


class DaemonSetCollector:
    kind = "DaemonSet"

    def list(self, apis: K8sApis, namespace: str) -> list[NormalizedWorkload]:
        items = apis.apps_v1.list_namespaced_daemon_set(namespace).items
        return [self.normalize(item) for item in items]

    def normalize(self, daemon_set: client.V1DaemonSet) -> NormalizedWorkload:
        pod_spec = daemon_set.spec.template.spec
        meta = daemon_set.metadata
        status = daemon_set.status
        return NormalizedWorkload(
            kind=self.kind,
            name=meta.name,
            # DaemonSet has no .spec.replicas - one pod per matching node instead.
            replicas=(status.desired_number_scheduled or 0) if status else 0,
            ready_replicas=(status.number_ready or 0) if status else 0,
            pod_labels=daemon_set.spec.template.metadata.labels or {},
            containers=_containers_from_pod_spec(pod_spec),
            claim_names=_claim_names_from_pod_spec(pod_spec),
            labels=dict(meta.labels or {}),
            annotations=dict(meta.annotations or {}),
            created_at=meta.creation_timestamp.isoformat() if meta.creation_timestamp else None,
            owners=_owners_from_metadata(meta),
            config_refs=_config_refs_from_pod_spec(pod_spec),
            service_account_name=pod_spec.service_account_name,
            node_selector=dict(pod_spec.node_selector or {}),
            node_affinity=_node_affinity_from_pod_spec(pod_spec),
            tolerations=_tolerations_from_pod_spec(pod_spec),
            rollout_strategy=_rollout_strategy_from_daemon_set(daemon_set.spec.update_strategy),
            image_pull_secrets=_image_pull_secrets_from_pod_spec(pod_spec),
        )


class CronJobCollector:
    kind = "CronJob"

    def list(self, apis: K8sApis, namespace: str) -> list[NormalizedWorkload]:
        items = apis.batch_v1.list_namespaced_cron_job(namespace).items
        return [self.normalize(item) for item in items]

    def normalize(self, cron_job: client.V1CronJob) -> NormalizedWorkload:
        pod_spec = cron_job.spec.job_template.spec.template.spec
        meta = cron_job.metadata
        status = cron_job.status
        return NormalizedWorkload(
            kind=self.kind,
            name=meta.name,
            # A CronJob isn't a long-running workload - "replicas" doesn't apply the
            # way it does for Deployment/StatefulSet/DaemonSet. Modeled as a single
            # job template that's either currently running (an active Job exists)
            # or not, so it still renders sensibly as an "N/1 ready" fact.
            replicas=1,
            ready_replicas=1 if status and status.active else 0,
            pod_labels=cron_job.spec.job_template.spec.template.metadata.labels or {},
            containers=_containers_from_pod_spec(pod_spec),
            claim_names=_claim_names_from_pod_spec(pod_spec),
            labels=dict(meta.labels or {}),
            annotations=dict(meta.annotations or {}),
            created_at=meta.creation_timestamp.isoformat() if meta.creation_timestamp else None,
            owners=_owners_from_metadata(meta),
            config_refs=_config_refs_from_pod_spec(pod_spec),
            service_account_name=pod_spec.service_account_name,
            node_selector=dict(pod_spec.node_selector or {}),
            node_affinity=_node_affinity_from_pod_spec(pod_spec),
            tolerations=_tolerations_from_pod_spec(pod_spec),
            image_pull_secrets=_image_pull_secrets_from_pod_spec(pod_spec),
        )


DEFAULT_WORKLOAD_COLLECTORS: tuple[WorkloadCollector, ...] = (
    DeploymentCollector(),
    StatefulSetCollector(),
    DaemonSetCollector(),
    CronJobCollector(),
)

"""One adapter per Kubernetes workload kind, normalized to a common shape.

To add a kind (DaemonSet, CronJob, ...): implement `kind` + `list()`/`normalize()`
and add an instance to DEFAULT_WORKLOAD_COLLECTORS. collect.py never changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from autodoc_core.models import Container
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


class WorkloadCollector(Protocol):
    kind: str

    def list(self, apis: K8sApis, namespace: str) -> list[NormalizedWorkload]: ...


def _containers_from_pod_spec(pod_spec: client.V1PodSpec) -> list[Container]:
    return [
        Container(name=c.name, image=c.image, ports=[p.container_port for p in (c.ports or [])])
        for c in pod_spec.containers
    ]


def _claim_names_from_pod_spec(pod_spec: client.V1PodSpec) -> frozenset[str]:
    return frozenset(
        volume.persistent_volume_claim.claim_name
        for volume in (pod_spec.volumes or [])
        if volume.persistent_volume_claim
    )


class DeploymentCollector:
    kind = "Deployment"

    def list(self, apis: K8sApis, namespace: str) -> list[NormalizedWorkload]:
        items = apis.apps_v1.list_namespaced_deployment(namespace).items
        return [self.normalize(item) for item in items]

    def normalize(self, deployment: client.V1Deployment) -> NormalizedWorkload:
        pod_spec = deployment.spec.template.spec
        return NormalizedWorkload(
            kind=self.kind,
            name=deployment.metadata.name,
            replicas=deployment.spec.replicas or 0,
            ready_replicas=((deployment.status.ready_replicas or 0) if deployment.status else 0),
            pod_labels=deployment.spec.template.metadata.labels or {},
            containers=_containers_from_pod_spec(pod_spec),
            claim_names=_claim_names_from_pod_spec(pod_spec),
            labels=dict(deployment.metadata.labels or {}),
        )


class StatefulSetCollector:
    kind = "StatefulSet"

    def list(self, apis: K8sApis, namespace: str) -> list[NormalizedWorkload]:
        items = apis.apps_v1.list_namespaced_stateful_set(namespace).items
        return [self.normalize(item) for item in items]

    def normalize(self, stateful_set: client.V1StatefulSet) -> NormalizedWorkload:
        pod_spec = stateful_set.spec.template.spec
        return NormalizedWorkload(
            kind=self.kind,
            name=stateful_set.metadata.name,
            replicas=stateful_set.spec.replicas or 0,
            ready_replicas=(
                (stateful_set.status.ready_replicas or 0) if stateful_set.status else 0
            ),
            pod_labels=stateful_set.spec.template.metadata.labels or {},
            containers=_containers_from_pod_spec(pod_spec),
            claim_names=_claim_names_from_pod_spec(pod_spec),
            labels=dict(stateful_set.metadata.labels or {}),
        )


DEFAULT_WORKLOAD_COLLECTORS: tuple[WorkloadCollector, ...] = (
    DeploymentCollector(),
    StatefulSetCollector(),
)

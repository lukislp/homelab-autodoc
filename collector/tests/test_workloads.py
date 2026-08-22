"""normalize() against hand-built kubernetes.client objects; list() is a thin
I/O wrapper not worth testing without a live/mocked API.
"""

from __future__ import annotations

from autodoc_core.models import Container
from kubernetes import client

from autodoc_collector.workloads import DeploymentCollector, StatefulSetCollector


def test_deployment_collector_normalizes_pod_template():
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name="web", labels={"tier": "frontend"}),
        spec=client.V1DeploymentSpec(
            replicas=3,
            selector=client.V1LabelSelector(match_labels={"app": "web"}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "web"}),
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name="web",
                            image="nginx:1.25.3",
                            ports=[client.V1ContainerPort(container_port=8080)],
                        )
                    ],
                    volumes=[
                        client.V1Volume(
                            name="data",
                            persistent_volume_claim=(
                                client.V1PersistentVolumeClaimVolumeSource(claim_name="web-data")
                            ),
                        )
                    ],
                ),
            ),
        ),
        status=client.V1DeploymentStatus(ready_replicas=2),
    )

    workload = DeploymentCollector().normalize(deployment)

    assert workload.kind == "Deployment"
    assert workload.name == "web"
    assert workload.replicas == 3
    assert workload.ready_replicas == 2
    assert workload.pod_labels == {"app": "web"}
    assert workload.containers == [Container(name="web", image="nginx:1.25.3", ports=[8080])]
    assert workload.claim_names == frozenset({"web-data"})
    assert workload.labels == {"tier": "frontend"}


def test_statefulset_collector_normalizes_pod_template():
    stateful_set = client.V1StatefulSet(
        metadata=client.V1ObjectMeta(name="postgres", labels={}),
        spec=client.V1StatefulSetSpec(
            replicas=1,
            service_name="postgres",
            selector=client.V1LabelSelector(match_labels={"app": "postgres"}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "postgres"}),
                spec=client.V1PodSpec(
                    containers=[client.V1Container(name="postgres", image="postgres:16")]
                ),
            ),
        ),
        status=client.V1StatefulSetStatus(replicas=1, ready_replicas=1),
    )

    workload = StatefulSetCollector().normalize(stateful_set)

    assert workload.kind == "StatefulSet"
    assert workload.name == "postgres"
    assert workload.replicas == 1
    assert workload.ready_replicas == 1
    assert workload.pod_labels == {"app": "postgres"}


def test_normalize_without_status_defaults_ready_replicas_to_zero():
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name="web", labels={}),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels={"app": "web"}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "web"}),
                spec=client.V1PodSpec(
                    containers=[client.V1Container(name="web", image="nginx:1.25.3")]
                ),
            ),
        ),
        status=None,
    )

    workload = DeploymentCollector().normalize(deployment)

    assert workload.ready_replicas == 0

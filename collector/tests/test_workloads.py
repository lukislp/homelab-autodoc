"""normalize() against hand-built kubernetes.client objects; list() is a thin
I/O wrapper not worth testing without a live/mocked API.
"""

from __future__ import annotations

from datetime import UTC, datetime

from autodoc_core.models import ConfigReference, Container, EnvVar
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


def test_deployment_collector_normalizes_resources_env_and_config_refs():
    created_at = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(
            name="web",
            labels={"tier": "frontend"},
            annotations={"kustomize.toolkit.fluxcd.io/name": "web-deploy"},
            creation_timestamp=created_at,
            owner_references=[
                client.V1OwnerReference(
                    kind="ReplicaSet", name="web-abc", api_version="apps/v1", uid="x"
                )
            ],
        ),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels={"app": "web"}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "web"}),
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name="web",
                            image="nginx:1.25.3",
                            resources=client.V1ResourceRequirements(
                                requests={"cpu": "100m", "memory": "128Mi"},
                                limits={"cpu": "500m", "memory": "256Mi"},
                            ),
                            env=[
                                client.V1EnvVar(name="LOG_LEVEL", value="info"),
                                client.V1EnvVar(
                                    name="API_KEY",
                                    value_from=client.V1EnvVarSource(
                                        secret_key_ref=client.V1SecretKeySelector(
                                            name="web-secrets", key="API_KEY"
                                        )
                                    ),
                                ),
                            ],
                            env_from=[
                                client.V1EnvFromSource(
                                    config_map_ref=client.V1ConfigMapEnvSource(name="web-config")
                                )
                            ],
                        )
                    ],
                    volumes=[
                        client.V1Volume(
                            name="tls",
                            secret=client.V1SecretVolumeSource(secret_name="web-tls"),
                        )
                    ],
                ),
            ),
        ),
        status=client.V1DeploymentStatus(ready_replicas=1),
    )

    workload = DeploymentCollector().normalize(deployment)

    assert workload.containers == [
        Container(
            name="web",
            image="nginx:1.25.3",
            resource_requests={"cpu": "100m", "memory": "128Mi"},
            resource_limits={"cpu": "500m", "memory": "256Mi"},
            env=[
                EnvVar(name="LOG_LEVEL", value="info"),
                EnvVar(name="API_KEY", value_from="Secret:web-secrets/API_KEY"),
            ],
        )
    ]
    assert workload.annotations == {"kustomize.toolkit.fluxcd.io/name": "web-deploy"}
    assert workload.created_at == created_at.isoformat()
    assert workload.owners == ["ReplicaSet/web-abc"]
    assert workload.config_refs == frozenset(
        {
            ConfigReference(kind="Secret", name="web-secrets", via="env"),
            ConfigReference(kind="ConfigMap", name="web-config", via="envFrom"),
            ConfigReference(kind="Secret", name="web-tls", via="volume"),
        }
    )


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

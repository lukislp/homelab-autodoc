"""normalize() against hand-built kubernetes.client objects; list() is a thin
I/O wrapper not worth testing without a live/mocked API.
"""

from __future__ import annotations

from datetime import UTC, datetime

from autodoc_core.models import (
    ConfigReference,
    Container,
    ContainerSecurityInfo,
    EnvVar,
    RolloutStrategyInfo,
)
from kubernetes import client

from autodoc_collector.workloads import (
    CronJobCollector,
    DaemonSetCollector,
    DeploymentCollector,
    StatefulSetCollector,
)


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


def test_statefulset_collector_normalizes_partitioned_rolling_update():
    stateful_set = client.V1StatefulSet(
        metadata=client.V1ObjectMeta(name="postgres", labels={}),
        spec=client.V1StatefulSetSpec(
            replicas=3,
            service_name="postgres",
            selector=client.V1LabelSelector(match_labels={"app": "postgres"}),
            update_strategy=client.V1StatefulSetUpdateStrategy(
                type="RollingUpdate",
                rolling_update=client.V1RollingUpdateStatefulSetStrategy(
                    max_unavailable="1", partition=2
                ),
            ),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "postgres"}),
                spec=client.V1PodSpec(
                    containers=[client.V1Container(name="postgres", image="postgres:16")]
                ),
            ),
        ),
        status=client.V1StatefulSetStatus(replicas=3, ready_replicas=3),
    )

    workload = StatefulSetCollector().normalize(stateful_set)

    assert workload.rollout_strategy == RolloutStrategyInfo(
        strategy_type="RollingUpdate", max_unavailable="1", partition=2
    )


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


def test_deployment_collector_normalizes_container_level_security_context():
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name="web", labels={}),
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
                            security_context=client.V1SecurityContext(
                                run_as_non_root=True,
                                read_only_root_filesystem=True,
                                allow_privilege_escalation=False,
                                capabilities=client.V1Capabilities(
                                    add=["NET_BIND_SERVICE"], drop=["ALL"]
                                ),
                                seccomp_profile=client.V1SeccompProfile(type="RuntimeDefault"),
                            ),
                        )
                    ],
                ),
            ),
        ),
        status=client.V1DeploymentStatus(ready_replicas=1),
    )

    workload = DeploymentCollector().normalize(deployment)

    assert workload.containers[0].security == ContainerSecurityInfo(
        run_as_non_root=True,
        read_only_root_filesystem=True,
        allow_privilege_escalation=False,
        added_capabilities=["NET_BIND_SERVICE"],
        dropped_capabilities=["ALL"],
        seccomp_profile="RuntimeDefault",
    )


def test_deployment_collector_falls_back_to_pod_level_security_context():
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name="web", labels={}),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels={"app": "web"}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "web"}),
                spec=client.V1PodSpec(
                    security_context=client.V1PodSecurityContext(
                        run_as_non_root=True,
                        seccomp_profile=client.V1SeccompProfile(
                            type="Localhost", localhost_profile="profiles/web.json"
                        ),
                    ),
                    containers=[client.V1Container(name="web", image="nginx:1.25.3")],
                ),
            ),
        ),
        status=client.V1DeploymentStatus(ready_replicas=1),
    )

    workload = DeploymentCollector().normalize(deployment)

    assert workload.containers[0].security == ContainerSecurityInfo(
        run_as_non_root=True, seccomp_profile="Localhost:profiles/web.json"
    )


def test_deployment_collector_container_level_security_overrides_pod_level():
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name="web", labels={}),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels={"app": "web"}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "web"}),
                spec=client.V1PodSpec(
                    security_context=client.V1PodSecurityContext(run_as_non_root=True),
                    containers=[
                        client.V1Container(
                            name="web",
                            image="nginx:1.25.3",
                            security_context=client.V1SecurityContext(run_as_non_root=False),
                        )
                    ],
                ),
            ),
        ),
        status=client.V1DeploymentStatus(ready_replicas=1),
    )

    workload = DeploymentCollector().normalize(deployment)

    assert workload.containers[0].security == ContainerSecurityInfo(run_as_non_root=False)


def test_deployment_collector_without_security_context_leaves_security_none():
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
        status=client.V1DeploymentStatus(ready_replicas=1),
    )

    workload = DeploymentCollector().normalize(deployment)

    assert workload.containers[0].security is None


def test_deployment_collector_normalizes_image_pull_secrets():
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name="web", labels={}),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels={"app": "web"}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "web"}),
                spec=client.V1PodSpec(
                    containers=[client.V1Container(name="web", image="ghcr.io/lukislp/web:1.0")],
                    image_pull_secrets=[
                        client.V1LocalObjectReference(name="ghcr-pull-secret"),
                        client.V1LocalObjectReference(name="ghcr-pull-secret"),
                    ],
                ),
            ),
        ),
        status=client.V1DeploymentStatus(ready_replicas=1),
    )

    workload = DeploymentCollector().normalize(deployment)

    assert workload.image_pull_secrets == frozenset({"ghcr-pull-secret"})


def test_deployment_collector_without_image_pull_secrets_is_empty():
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
        status=client.V1DeploymentStatus(ready_replicas=1),
    )

    workload = DeploymentCollector().normalize(deployment)

    assert workload.image_pull_secrets == frozenset()


def test_deployment_collector_normalizes_rolling_update_strategy():
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name="web", labels={}),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels={"app": "web"}),
            strategy=client.V1DeploymentStrategy(
                type="RollingUpdate",
                rolling_update=client.V1RollingUpdateDeployment(
                    max_surge="25%", max_unavailable="0"
                ),
            ),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "web"}),
                spec=client.V1PodSpec(
                    containers=[client.V1Container(name="web", image="nginx:1.25.3")]
                ),
            ),
        ),
        status=client.V1DeploymentStatus(ready_replicas=1),
    )

    workload = DeploymentCollector().normalize(deployment)

    assert workload.rollout_strategy == RolloutStrategyInfo(
        strategy_type="RollingUpdate", max_surge="25%", max_unavailable="0"
    )


def test_deployment_collector_without_strategy_has_no_rollout_strategy():
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
        status=client.V1DeploymentStatus(ready_replicas=1),
    )

    workload = DeploymentCollector().normalize(deployment)

    assert workload.rollout_strategy is None


def test_deployment_collector_normalizes_node_selector():
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name="web", labels={}),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels={"app": "web"}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "web"}),
                spec=client.V1PodSpec(
                    node_selector={"kubernetes.io/arch": "arm64"},
                    containers=[client.V1Container(name="web", image="nginx:1.25.3")],
                ),
            ),
        ),
        status=client.V1DeploymentStatus(ready_replicas=1),
    )

    workload = DeploymentCollector().normalize(deployment)

    assert workload.node_selector == {"kubernetes.io/arch": "arm64"}


def test_deployment_collector_normalizes_required_and_preferred_node_affinity():
    required_term = client.V1NodeSelectorTerm(
        match_expressions=[
            client.V1NodeSelectorRequirement(
                key="kubernetes.io/arch", operator="In", values=["arm64"]
            )
        ]
    )
    preferred_term = client.V1NodeSelectorTerm(
        match_expressions=[client.V1NodeSelectorRequirement(key="disktype", operator="Exists")]
    )
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name="web", labels={}),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels={"app": "web"}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "web"}),
                spec=client.V1PodSpec(
                    affinity=client.V1Affinity(
                        node_affinity=client.V1NodeAffinity(
                            required_during_scheduling_ignored_during_execution=(
                                client.V1NodeSelector(node_selector_terms=[required_term])
                            ),
                            preferred_during_scheduling_ignored_during_execution=[
                                client.V1PreferredSchedulingTerm(
                                    weight=10, preference=preferred_term
                                )
                            ],
                        )
                    ),
                    containers=[client.V1Container(name="web", image="nginx:1.25.3")],
                ),
            ),
        ),
        status=client.V1DeploymentStatus(ready_replicas=1),
    )

    workload = DeploymentCollector().normalize(deployment)

    assert workload.node_affinity == [
        "required: kubernetes.io/arch In (arm64)",
        "preferred (weight 10): disktype Exists",
    ]


def test_deployment_collector_normalizes_tolerations():
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name="web", labels={}),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels={"app": "web"}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "web"}),
                spec=client.V1PodSpec(
                    tolerations=[
                        client.V1Toleration(
                            key="node-role.kubernetes.io/master",
                            operator="Exists",
                            effect="NoSchedule",
                        ),
                        client.V1Toleration(
                            key="node.kubernetes.io/not-ready",
                            operator="Exists",
                            effect="NoExecute",
                            toleration_seconds=300,
                        ),
                        client.V1Toleration(operator="Exists"),
                    ],
                    containers=[client.V1Container(name="web", image="nginx:1.25.3")],
                ),
            ),
        ),
        status=client.V1DeploymentStatus(ready_replicas=1),
    )

    workload = DeploymentCollector().normalize(deployment)

    assert workload.tolerations == [
        "node-role.kubernetes.io/master Exists:NoSchedule",
        "node.kubernetes.io/not-ready Exists:NoExecute (300s)",
        "all taints",
    ]


def test_deployment_collector_normalizes_init_containers_before_regular_ones():
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name="web", labels={}),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels={"app": "web"}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "web"}),
                spec=client.V1PodSpec(
                    init_containers=[
                        client.V1Container(name="migrate", image="migrate:1.0"),
                    ],
                    containers=[
                        client.V1Container(name="web", image="nginx:1.25.3"),
                    ],
                ),
            ),
        ),
        status=client.V1DeploymentStatus(ready_replicas=1),
    )

    workload = DeploymentCollector().normalize(deployment)

    assert [(c.name, c.is_init) for c in workload.containers] == [
        ("migrate", True),
        ("web", False),
    ]


def test_deployment_collector_normalizes_probes():
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name="web", labels={}),
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
                            liveness_probe=client.V1Probe(
                                http_get=client.V1HTTPGetAction(path="/healthz", port=8080),
                                period_seconds=10,
                            ),
                            readiness_probe=client.V1Probe(
                                tcp_socket=client.V1TCPSocketAction(port=8080)
                            ),
                            startup_probe=client.V1Probe(
                                _exec=client.V1ExecAction(command=["pg_isready"])
                            ),
                        ),
                    ],
                ),
            ),
        ),
        status=client.V1DeploymentStatus(ready_replicas=1),
    )

    workload = DeploymentCollector().normalize(deployment)

    probes = workload.containers[0].probes
    assert {(p.kind, p.check, p.period_seconds) for p in probes} == {
        ("liveness", "HTTP :8080/healthz", 10),
        ("readiness", "TCP :8080", None),
        ("startup", "exec: pg_isready", None),
    }


def test_deployment_collector_normalizes_service_account_name():
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name="web", labels={}),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels={"app": "web"}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "web"}),
                spec=client.V1PodSpec(
                    service_account_name="web-sa",
                    containers=[client.V1Container(name="web", image="nginx:1.25.3")],
                ),
            ),
        ),
        status=client.V1DeploymentStatus(ready_replicas=1),
    )

    workload = DeploymentCollector().normalize(deployment)

    assert workload.service_account_name == "web-sa"


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


def test_daemonset_collector_normalizes_pod_template():
    daemon_set = client.V1DaemonSet(
        metadata=client.V1ObjectMeta(name="node-exporter", labels={}),
        spec=client.V1DaemonSetSpec(
            selector=client.V1LabelSelector(match_labels={"app": "node-exporter"}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "node-exporter"}),
                spec=client.V1PodSpec(
                    containers=[client.V1Container(name="node-exporter", image="node-exporter:1.0")]
                ),
            ),
        ),
        status=client.V1DaemonSetStatus(
            current_number_scheduled=2,
            desired_number_scheduled=2,
            number_misscheduled=0,
            number_ready=2,
        ),
    )

    workload = DaemonSetCollector().normalize(daemon_set)

    assert workload.kind == "DaemonSet"
    assert workload.name == "node-exporter"
    assert workload.replicas == 2
    assert workload.ready_replicas == 2
    assert workload.pod_labels == {"app": "node-exporter"}


def test_daemonset_collector_normalizes_rolling_update_strategy():
    daemon_set = client.V1DaemonSet(
        metadata=client.V1ObjectMeta(name="node-exporter", labels={}),
        spec=client.V1DaemonSetSpec(
            selector=client.V1LabelSelector(match_labels={"app": "node-exporter"}),
            update_strategy=client.V1DaemonSetUpdateStrategy(
                type="RollingUpdate",
                rolling_update=client.V1RollingUpdateDaemonSet(max_surge="0", max_unavailable="1"),
            ),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "node-exporter"}),
                spec=client.V1PodSpec(
                    containers=[client.V1Container(name="node-exporter", image="node-exporter:1.0")]
                ),
            ),
        ),
        status=client.V1DaemonSetStatus(
            current_number_scheduled=2,
            desired_number_scheduled=2,
            number_misscheduled=0,
            number_ready=2,
        ),
    )

    workload = DaemonSetCollector().normalize(daemon_set)

    assert workload.rollout_strategy == RolloutStrategyInfo(
        strategy_type="RollingUpdate", max_surge="0", max_unavailable="1"
    )


def test_daemonset_collector_without_status_defaults_to_zero():
    daemon_set = client.V1DaemonSet(
        metadata=client.V1ObjectMeta(name="node-exporter", labels={}),
        spec=client.V1DaemonSetSpec(
            selector=client.V1LabelSelector(match_labels={"app": "node-exporter"}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": "node-exporter"}),
                spec=client.V1PodSpec(
                    containers=[client.V1Container(name="node-exporter", image="node-exporter:1.0")]
                ),
            ),
        ),
        status=None,
    )

    workload = DaemonSetCollector().normalize(daemon_set)

    assert workload.replicas == 0
    assert workload.ready_replicas == 0


def test_cronjob_collector_normalizes_job_template():
    cron_job = client.V1CronJob(
        metadata=client.V1ObjectMeta(name="autodoc-collector", labels={}),
        spec=client.V1CronJobSpec(
            schedule="0 2 * * *",
            job_template=client.V1JobTemplateSpec(
                spec=client.V1JobSpec(
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(labels={}),
                        spec=client.V1PodSpec(
                            containers=[client.V1Container(name="collector", image="collector:1.0")]
                        ),
                    )
                )
            ),
        ),
        status=client.V1CronJobStatus(
            active=[client.V1ObjectReference(name="autodoc-collector-123")]
        ),
    )

    workload = CronJobCollector().normalize(cron_job)

    assert workload.kind == "CronJob"
    assert workload.name == "autodoc-collector"
    assert workload.replicas == 1
    assert workload.ready_replicas == 1
    assert workload.containers[0].image == "collector:1.0"


def test_cronjob_collector_not_currently_running():
    cron_job = client.V1CronJob(
        metadata=client.V1ObjectMeta(name="autodoc-collector", labels={}),
        spec=client.V1CronJobSpec(
            schedule="0 2 * * *",
            job_template=client.V1JobTemplateSpec(
                spec=client.V1JobSpec(
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(labels={}),
                        spec=client.V1PodSpec(
                            containers=[client.V1Container(name="collector", image="collector:1.0")]
                        ),
                    )
                )
            ),
        ),
        status=client.V1CronJobStatus(active=None),
    )

    workload = CronJobCollector().normalize(cron_job)

    assert workload.ready_replicas == 0

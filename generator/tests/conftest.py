from __future__ import annotations

import pytest
from autodoc_core.models import (
    App,
    ConfigReference,
    Container,
    EnvVar,
    IngressInfo,
    IngressRule,
    ServiceInfo,
    ServicePort,
    Volume,
)


@pytest.fixture
def sample_app() -> App:
    return App(
        name="web",
        kind="Deployment",
        replicas=2,
        ready_replicas=2,
        containers=[
            Container(
                name="web",
                image="nginx:1.25.3",
                ports=[8080],
                resource_requests={"cpu": "100m", "memory": "128Mi"},
                resource_limits={"cpu": "500m", "memory": "256Mi"},
                env=[
                    EnvVar(name="LOG_LEVEL", value="info"),
                    EnvVar(name="API_KEY", value_from="Secret:web-secrets/API_KEY"),
                ],
            )
        ],
        volumes=[
            Volume(
                claim_name="web-data",
                storage_class="local-path",
                capacity="1Gi",
                access_modes=["ReadWriteOnce"],
            )
        ],
        services=[
            ServiceInfo(
                name="web-svc",
                type="ClusterIP",
                cluster_ip="10.0.0.1",
                ports=[ServicePort(port=80, target_port="8080", protocol="TCP")],
            )
        ],
        ingresses=[
            IngressInfo(
                name="web-ingress",
                rules=[
                    IngressRule(
                        host="web.example.com", path="/", service_name="web-svc", service_port="80"
                    )
                ],
                tls_hosts=["web.example.com"],
            )
        ],
        labels={"tier": "frontend"},
        annotations={"kustomize.toolkit.fluxcd.io/name": "web-deploy"},
        created_at="2026-08-01T12:00:00+00:00",
        owners=["ReplicaSet/web-abc123"],
        config_refs=[
            ConfigReference(kind="Secret", name="web-secrets", via="env"),
            ConfigReference(kind="ConfigMap", name="web-config", via="volume"),
        ],
    )


@pytest.fixture
def bare_app() -> App:
    return App(name="worker", kind="Deployment", replicas=1, ready_replicas=1)

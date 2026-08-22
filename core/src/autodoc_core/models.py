"""The deterministic cluster inventory. Every field comes straight from the
Kubernetes API - this is the hallucination boundary the generator writes on
top of, never into.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Container:
    name: str
    image: str
    ports: list[int] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Volume:
    claim_name: str
    storage_class: str | None
    capacity: str | None
    access_modes: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ServicePort:
    port: int
    target_port: str
    protocol: str
    name: str | None = None


@dataclass(frozen=True, slots=True)
class ServiceInfo:
    name: str
    type: str
    cluster_ip: str | None
    ports: list[ServicePort] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class IngressRule:
    path: str
    service_name: str
    service_port: str
    host: str | None = None


@dataclass(frozen=True, slots=True)
class IngressInfo:
    name: str
    rules: list[IngressRule] = field(default_factory=list)
    tls_hosts: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class App:
    name: str
    kind: str
    replicas: int
    ready_replicas: int
    containers: list[Container] = field(default_factory=list)
    volumes: list[Volume] = field(default_factory=list)
    services: list[ServiceInfo] = field(default_factory=list)
    ingresses: list[IngressInfo] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NamespaceInventory:
    name: str
    apps: list[App] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ClusterInventory:
    cluster_name: str
    collected_at: str
    namespaces: list[NamespaceInventory] = field(default_factory=list)

"""The deterministic cluster inventory. Every field comes straight from the
Kubernetes API - this is the hallucination boundary the generator writes on
top of, never into.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class EnvVar:
    name: str
    # Exactly one of these is set. `value` is a literal from the pod spec (never a
    # ConfigMap/Secret value - those are never read). `value_from` describes a
    # valueFrom reference, e.g. "ConfigMap:app-config/KEY" or "Secret:app-secrets/KEY".
    value: str | None = None
    value_from: str | None = None


@dataclass(frozen=True, slots=True)
class Container:
    name: str
    image: str
    ports: list[int] = field(default_factory=list)
    resource_requests: dict[str, str] = field(default_factory=dict)
    resource_limits: dict[str, str] = field(default_factory=dict)
    env: list[EnvVar] = field(default_factory=list)


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
class ConfigReference:
    kind: str  # "ConfigMap" | "Secret"
    name: str
    via: str  # "env" | "envFrom" | "volume"


@dataclass(frozen=True, slots=True)
class Autoscaler:
    min_replicas: int
    max_replicas: int
    # Resource-metric utilization targets only (the vast majority of real HPA
    # usage) - custom/external/object metrics aren't modeled, there's no
    # generic deterministic way to describe an arbitrary metric's meaning.
    target_cpu_percent: int | None = None
    target_memory_percent: int | None = None


@dataclass(frozen=True, slots=True)
class NetworkPolicyRule:
    # Human-readable peer descriptions, e.g. "pods:app=foo", "namespaces:all",
    # "ipBlock:10.0.0.0/8". An empty list means "all sources/destinations" -
    # the rule is present but has no peer restriction.
    peers: list[str] = field(default_factory=list)
    ports: list[str] = field(default_factory=list)  # e.g. "TCP/8080"; empty means all ports


@dataclass(frozen=True, slots=True)
class NetworkPolicyInfo:
    name: str
    policy_types: list[str] = field(default_factory=list)  # "Ingress" | "Egress"
    ingress: list[NetworkPolicyRule] = field(default_factory=list)
    egress: list[NetworkPolicyRule] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RoleBindingInfo:
    name: str
    role_kind: str  # "Role" | "ClusterRole" - what the binding grants
    role_name: str


@dataclass(frozen=True, slots=True)
class ServiceAccountInfo:
    name: str
    role_bindings: list[RoleBindingInfo] = field(default_factory=list)


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
    annotations: dict[str, str] = field(default_factory=dict)
    created_at: str | None = None
    owners: list[str] = field(default_factory=list)  # ["Kind/Name", ...]
    config_refs: list[ConfigReference] = field(default_factory=list)
    autoscaler: Autoscaler | None = None
    nodes: list[str] = field(default_factory=list)  # names of nodes running this app's pods
    network_policies: list[NetworkPolicyInfo] = field(default_factory=list)
    service_account: ServiceAccountInfo | None = None


@dataclass(frozen=True, slots=True)
class NamespaceInventory:
    name: str
    apps: list[App] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ClusterInventory:
    cluster_name: str
    collected_at: str
    namespaces: list[NamespaceInventory] = field(default_factory=list)

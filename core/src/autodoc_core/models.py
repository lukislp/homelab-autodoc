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
class ProbeInfo:
    kind: str  # "liveness" | "readiness" | "startup"
    # Human-readable description of what the probe checks, e.g.
    # "HTTP :8080/healthz", "TCP :5432", "exec: pg_isready", "gRPC :9090".
    check: str
    period_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class ContainerSecurityInfo:
    # Each flag is the *effective* value - a container-level securityContext
    # setting if present, else the pod-level podSecurityContext's setting for
    # the fields that support one (run_as_non_root, seccomp_profile). Capability
    # add/drop, read_only_root_filesystem, allow_privilege_escalation, and
    # privileged have no pod-level equivalent, so those are container-only.
    run_as_non_root: bool | None = None
    read_only_root_filesystem: bool | None = None
    allow_privilege_escalation: bool | None = None
    privileged: bool | None = None
    added_capabilities: list[str] = field(default_factory=list)
    dropped_capabilities: list[str] = field(default_factory=list)
    seccomp_profile: str | None = None  # e.g. "RuntimeDefault", "Localhost:profiles/foo.json"


@dataclass(frozen=True, slots=True)
class Container:
    name: str
    image: str
    ports: list[int] = field(default_factory=list)
    resource_requests: dict[str, str] = field(default_factory=dict)
    resource_limits: dict[str, str] = field(default_factory=dict)
    env: list[EnvVar] = field(default_factory=list)
    is_init: bool = False
    probes: list[ProbeInfo] = field(default_factory=list)
    security: ContainerSecurityInfo | None = None


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
class ServiceReference:
    """A concrete service endpoint an app is CONFIGURED to talk to - parsed
    at collection time from plain-text env values and the contents of
    ConfigMaps the app references. The raw values are scanned in memory and
    never persisted; Secrets are never read at all, so a connection string
    that lives only in a Secret stays invisible (documented limitation, the
    price of the no-secret-access guarantee).
    """

    service: str
    namespace: str | None = None  # None = the app's own namespace
    port: int | None = None
    via: str = ""  # e.g. "env CACHE_URL" or "ConfigMap studylife-config/Cache__ConnectionString"


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
class NetworkPolicyPeerInfo:
    """One structured NetworkPolicy peer. Exactly one shape per peer:
    ip_block set, or any combination of the two selectors. Selector
    semantics mirror the Kubernetes API: None = that selector is absent
    (namespace_selector None means "the policy's own namespace"), {} = the
    selector is present but empty ("all"). matchExpressions are not modeled
    - the collector marks such peers unresolvable rather than guessing.
    """

    ip_block: str | None = None
    namespace_selector: dict[str, str] | None = None
    pod_selector: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class NetworkPolicyRule:
    # Human-readable peer descriptions, e.g. "pods:app=foo", "namespaces:all",
    # "ipBlock:10.0.0.0/8" - DERIVED from peer_selectors for display; the
    # structured list below is what the network-flow resolution consumes.
    # An empty list means "all sources/destinations" - the rule is present
    # but has no peer restriction.
    peers: list[str] = field(default_factory=list)
    ports: list[str] = field(default_factory=list)  # e.g. "TCP/8080"; empty means all ports
    # Structured peers, same order as `peers`. Empty on inventories from
    # collectors older than this field - consumers fall back to parsing the
    # display strings there.
    peer_selectors: list[NetworkPolicyPeerInfo] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class NetworkPolicyInfo:
    name: str
    policy_types: list[str] = field(default_factory=list)  # "Ingress" | "Egress"
    ingress: list[NetworkPolicyRule] = field(default_factory=list)
    egress: list[NetworkPolicyRule] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RolloutStrategyInfo:
    strategy_type: str  # "RollingUpdate" | "Recreate" | "OnDelete"
    # Raw IntOrString strings (e.g. "25%", "1"), never parsed here. Deployment/
    # DaemonSet use max_surge+max_unavailable; StatefulSet uses max_unavailable
    # (only on newer clusters) and partition instead - a workload kind only
    # ever populates the fields its own update strategy actually has.
    max_surge: str | None = None
    max_unavailable: str | None = None
    partition: int | None = None


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
class PodDisruptionBudgetInfo:
    name: str
    # Exactly one of these is normally set (Kubernetes defaults maxUnavailable
    # to 1 only when neither is specified) - kept as raw IntOrString strings
    # (e.g. "1", "50%"), never parsed here.
    min_available: str | None = None
    max_unavailable: str | None = None


@dataclass(frozen=True, slots=True)
class App:
    name: str
    kind: str
    replicas: int
    ready_replicas: int
    containers: list[Container] = field(default_factory=list)
    volumes: list[Volume] = field(default_factory=list)
    # Volume names the pod template's backup.velero.io/backup-volumes annotation
    # opts into Velero's file-system backup - the raw opt-in fact, empty when
    # the annotation is absent. Names are pod-spec VOLUME names, not PVC claim
    # names.
    backup_volumes: list[str] = field(default_factory=list)
    services: list[ServiceInfo] = field(default_factory=list)
    ingresses: list[IngressInfo] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    # The pod TEMPLATE's labels - what NetworkPolicy/Service selectors actually
    # match against (workload-object labels can differ). Feeds the network-flow
    # diagrams' peer resolution.
    pod_labels: dict[str, str] = field(default_factory=dict)
    created_at: str | None = None
    owners: list[str] = field(default_factory=list)  # ["Kind/Name", ...]
    config_refs: list[ConfigReference] = field(default_factory=list)
    service_references: list[ServiceReference] = field(default_factory=list)
    autoscaler: Autoscaler | None = None
    nodes: list[str] = field(default_factory=list)  # names of nodes running this app's pods
    network_policies: list[NetworkPolicyInfo] = field(default_factory=list)
    service_account: ServiceAccountInfo | None = None
    pod_disruption_budgets: list[PodDisruptionBudgetInfo] = field(default_factory=list)
    node_selector: dict[str, str] = field(default_factory=dict)
    # Human-readable node affinity terms, e.g. "required: kubernetes.io/arch In (arm64)".
    node_affinity: list[str] = field(default_factory=list)
    # Human-readable toleration summaries, e.g. "node-role.kubernetes.io/master:NoSchedule".
    tolerations: list[str] = field(default_factory=list)
    rollout_strategy: RolloutStrategyInfo | None = None
    # Names only, e.g. ["ghcr-pull-secret"] - never the referenced Secret's contents.
    image_pull_secrets: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ResourceQuotaInfo:
    name: str
    # Raw Kubernetes quantity strings (e.g. "4", "8Gi"), keyed by resource name
    # (e.g. "requests.cpu", "limits.memory", "pods") - never parsed here.
    hard: dict[str, str] = field(default_factory=dict)
    used: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LimitRangeItemInfo:
    kind: str  # "Container" | "Pod" | "PersistentVolumeClaim"
    # Raw Kubernetes quantity strings, keyed by resource name (e.g. "cpu", "memory").
    min: dict[str, str] = field(default_factory=dict)
    max: dict[str, str] = field(default_factory=dict)
    default: dict[str, str] = field(default_factory=dict)
    default_request: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LimitRangeInfo:
    name: str
    limits: list[LimitRangeItemInfo] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class WarningEventInfo:
    reason: str  # e.g. "BackOff", "FailedScheduling"
    object_ref: str  # "Kind/name" the event is about
    message: str
    count: int
    last_seen: str | None = None  # ISO 8601; None if the API reported no timestamp


@dataclass(frozen=True, slots=True)
class NamespaceInventory:
    name: str
    apps: list[App] = field(default_factory=list)
    resource_quotas: list[ResourceQuotaInfo] = field(default_factory=list)
    limit_ranges: list[LimitRangeInfo] = field(default_factory=list)
    # Names of the ConfigMaps that exist in this namespace - existence only,
    # never contents. None (as opposed to []) means this run didn't gather
    # them (an older collector, or RBAC denied) - consumers must treat None
    # as "unknown", never as "there are none". Secret names are deliberately
    # NOT collected: listing secrets returns their full values at the API
    # level, and the collector's no-secret-access guarantee outweighs being
    # able to flag a dangling Secret reference.
    configmap_names: list[str] | None = None
    # Recent Warning-type events, newest first, capped by the collector.
    # Same None-vs-empty semantics as configmap_names.
    warning_events: list[WarningEventInfo] | None = None
    # Rule name -> reason from autodoc.homelab/accept-<rule> annotations on
    # the Namespace OBJECT itself, accepting that rule for every workload in
    # the namespace (workload-level annotations win on the same rule). Meant
    # for hand-installed system stacks (storage/CSI drivers and the like)
    # whose upstream manifests can't practically carry per-workload
    # annotations. Only the accept-prefixed annotations are collected -
    # never the namespace's full annotation set. Same None-vs-empty
    # semantics as configmap_names.
    accepted_rules: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class StorageClassInfo:
    name: str
    provisioner: str
    reclaim_policy: str | None = None
    volume_binding_mode: str | None = None
    allow_volume_expansion: bool | None = None


@dataclass(frozen=True, slots=True)
class NodeInfo:
    name: str
    architecture: str
    kubelet_version: str
    os_image: str
    # Raw Kubernetes quantity strings (e.g. "4", "8065700Ki") - shown as-is,
    # never parsed/summed here. Capacity is the node's total; allocatable is
    # what's actually schedulable after the node's own system reservations.
    capacity_cpu: str
    capacity_memory: str
    allocatable_cpu: str
    allocatable_memory: str
    ready: bool


@dataclass(frozen=True, slots=True)
class VeleroScheduleInfo:
    name: str
    schedule: str  # cron expression
    ttl: str | None = None
    included_namespaces: list[str] = field(default_factory=list)
    # ISO 8601 of the schedule's last started backup (status.lastBackup);
    # None if it never ran or the field was absent.
    last_backup: str | None = None


@dataclass(frozen=True, slots=True)
class VeleroBackupInfo:
    name: str
    phase: str  # "Completed" | "PartiallyFailed" | "Failed" | "InProgress" | ...
    schedule: str | None = None  # owning Schedule's name, None for manual backups
    started: str | None = None
    expiration: str | None = None
    errors: int = 0


@dataclass(frozen=True, slots=True)
class CNPGScheduledBackupInfo:
    namespace: str
    name: str
    schedule: str
    cluster: str  # the CNPG Cluster it backs up
    last_schedule_time: str | None = None


@dataclass(frozen=True, slots=True)
class CNPGBackupInfo:
    namespace: str
    name: str
    phase: str
    stopped_at: str | None = None


@dataclass(frozen=True, slots=True)
class ClusterBackupInfo:
    """Backup posture as collected from the Velero and CNPG CRs. The whole
    struct is None on ClusterInventory when this run couldn't gather it (older
    collector, RBAC denied, CRDs absent) - unknown never renders as "no
    backups".
    """

    velero_schedules: list[VeleroScheduleInfo] = field(default_factory=list)
    velero_backups: list[VeleroBackupInfo] = field(default_factory=list)  # newest first, capped
    cnpg_scheduled_backups: list[CNPGScheduledBackupInfo] = field(default_factory=list)
    cnpg_backups: list[CNPGBackupInfo] = field(default_factory=list)  # newest first, capped


@dataclass(frozen=True, slots=True)
class ClusterInventory:
    cluster_name: str
    collected_at: str
    namespaces: list[NamespaceInventory] = field(default_factory=list)
    storage_classes: list[StorageClassInfo] = field(default_factory=list)
    nodes: list[NodeInfo] = field(default_factory=list)
    backups: ClusterBackupInfo | None = None

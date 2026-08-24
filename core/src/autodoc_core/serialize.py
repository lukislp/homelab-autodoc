"""ClusterInventory <-> JSON/YAML text."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Literal

import yaml

from .models import (
    App,
    Autoscaler,
    ClusterInventory,
    ConfigReference,
    Container,
    ContainerSecurityInfo,
    EnvVar,
    IngressInfo,
    IngressRule,
    LimitRangeInfo,
    LimitRangeItemInfo,
    NamespaceInventory,
    NetworkPolicyInfo,
    NetworkPolicyRule,
    NodeInfo,
    PodDisruptionBudgetInfo,
    ProbeInfo,
    ResourceQuotaInfo,
    RoleBindingInfo,
    RolloutStrategyInfo,
    ServiceAccountInfo,
    ServiceInfo,
    ServicePort,
    StorageClassInfo,
    Volume,
    WarningEventInfo,
)

Format = Literal["json", "yaml"]


def to_dict(inventory: ClusterInventory) -> dict:
    return asdict(inventory)


def to_text(inventory: ClusterInventory, fmt: Format, pretty: bool = True) -> str:
    data = to_dict(inventory)
    if fmt == "json":
        return json.dumps(data, indent=2 if pretty else None, sort_keys=False)
    if fmt == "yaml":
        return yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    raise ValueError(f"unsupported format: {fmt}")


def _env_var_from_dict(d: dict) -> EnvVar:
    return EnvVar(name=d["name"], value=d.get("value"), value_from=d.get("value_from"))


def _config_reference_from_dict(d: dict) -> ConfigReference:
    return ConfigReference(kind=d["kind"], name=d["name"], via=d["via"])


def _probe_from_dict(d: dict) -> ProbeInfo:
    return ProbeInfo(kind=d["kind"], check=d["check"], period_seconds=d.get("period_seconds"))


def _container_security_from_dict(d: dict) -> ContainerSecurityInfo:
    return ContainerSecurityInfo(
        run_as_non_root=d.get("run_as_non_root"),
        read_only_root_filesystem=d.get("read_only_root_filesystem"),
        allow_privilege_escalation=d.get("allow_privilege_escalation"),
        privileged=d.get("privileged"),
        added_capabilities=list(d.get("added_capabilities", [])),
        dropped_capabilities=list(d.get("dropped_capabilities", [])),
        seccomp_profile=d.get("seccomp_profile"),
    )


def _container_from_dict(d: dict) -> Container:
    security = d.get("security")
    return Container(
        name=d["name"],
        image=d["image"],
        ports=list(d.get("ports", [])),
        resource_requests=dict(d.get("resource_requests", {})),
        resource_limits=dict(d.get("resource_limits", {})),
        env=[_env_var_from_dict(e) for e in d.get("env", [])],
        is_init=d.get("is_init", False),
        probes=[_probe_from_dict(p) for p in d.get("probes", [])],
        security=_container_security_from_dict(security) if security else None,
    )


def _volume_from_dict(d: dict) -> Volume:
    return Volume(
        claim_name=d["claim_name"],
        storage_class=d.get("storage_class"),
        capacity=d.get("capacity"),
        access_modes=list(d.get("access_modes", [])),
    )


def _service_port_from_dict(d: dict) -> ServicePort:
    return ServicePort(
        port=d["port"], target_port=d["target_port"], protocol=d["protocol"], name=d.get("name")
    )


def _service_from_dict(d: dict) -> ServiceInfo:
    return ServiceInfo(
        name=d["name"],
        type=d["type"],
        cluster_ip=d.get("cluster_ip"),
        ports=[_service_port_from_dict(p) for p in d.get("ports", [])],
    )


def _ingress_rule_from_dict(d: dict) -> IngressRule:
    return IngressRule(
        path=d["path"],
        service_name=d["service_name"],
        service_port=d["service_port"],
        host=d.get("host"),
    )


def _ingress_from_dict(d: dict) -> IngressInfo:
    return IngressInfo(
        name=d["name"],
        rules=[_ingress_rule_from_dict(r) for r in d.get("rules", [])],
        tls_hosts=list(d.get("tls_hosts", [])),
    )


def _autoscaler_from_dict(d: dict) -> Autoscaler:
    return Autoscaler(
        min_replicas=d["min_replicas"],
        max_replicas=d["max_replicas"],
        target_cpu_percent=d.get("target_cpu_percent"),
        target_memory_percent=d.get("target_memory_percent"),
    )


def _network_policy_rule_from_dict(d: dict) -> NetworkPolicyRule:
    return NetworkPolicyRule(peers=list(d.get("peers", [])), ports=list(d.get("ports", [])))


def _network_policy_from_dict(d: dict) -> NetworkPolicyInfo:
    return NetworkPolicyInfo(
        name=d["name"],
        policy_types=list(d.get("policy_types", [])),
        ingress=[_network_policy_rule_from_dict(r) for r in d.get("ingress", [])],
        egress=[_network_policy_rule_from_dict(r) for r in d.get("egress", [])],
    )


def _role_binding_from_dict(d: dict) -> RoleBindingInfo:
    return RoleBindingInfo(name=d["name"], role_kind=d["role_kind"], role_name=d["role_name"])


def _service_account_from_dict(d: dict) -> ServiceAccountInfo:
    return ServiceAccountInfo(
        name=d["name"],
        role_bindings=[_role_binding_from_dict(rb) for rb in d.get("role_bindings", [])],
    )


def _pdb_from_dict(d: dict) -> PodDisruptionBudgetInfo:
    return PodDisruptionBudgetInfo(
        name=d["name"],
        min_available=d.get("min_available"),
        max_unavailable=d.get("max_unavailable"),
    )


def _rollout_strategy_from_dict(d: dict) -> RolloutStrategyInfo:
    return RolloutStrategyInfo(
        strategy_type=d["strategy_type"],
        max_surge=d.get("max_surge"),
        max_unavailable=d.get("max_unavailable"),
        partition=d.get("partition"),
    )


def _app_from_dict(d: dict) -> App:
    autoscaler = d.get("autoscaler")
    service_account = d.get("service_account")
    rollout_strategy = d.get("rollout_strategy")
    return App(
        name=d["name"],
        kind=d["kind"],
        replicas=d["replicas"],
        ready_replicas=d["ready_replicas"],
        containers=[_container_from_dict(c) for c in d.get("containers", [])],
        volumes=[_volume_from_dict(v) for v in d.get("volumes", [])],
        services=[_service_from_dict(s) for s in d.get("services", [])],
        ingresses=[_ingress_from_dict(i) for i in d.get("ingresses", [])],
        labels=dict(d.get("labels", {})),
        annotations=dict(d.get("annotations", {})),
        created_at=d.get("created_at"),
        owners=list(d.get("owners", [])),
        config_refs=[_config_reference_from_dict(c) for c in d.get("config_refs", [])],
        autoscaler=_autoscaler_from_dict(autoscaler) if autoscaler else None,
        nodes=list(d.get("nodes", [])),
        network_policies=[_network_policy_from_dict(np) for np in d.get("network_policies", [])],
        service_account=_service_account_from_dict(service_account) if service_account else None,
        pod_disruption_budgets=[_pdb_from_dict(p) for p in d.get("pod_disruption_budgets", [])],
        node_selector=dict(d.get("node_selector", {})),
        node_affinity=list(d.get("node_affinity", [])),
        tolerations=list(d.get("tolerations", [])),
        rollout_strategy=_rollout_strategy_from_dict(rollout_strategy)
        if rollout_strategy
        else None,
        image_pull_secrets=list(d.get("image_pull_secrets", [])),
    )


def _resource_quota_from_dict(d: dict) -> ResourceQuotaInfo:
    return ResourceQuotaInfo(
        name=d["name"], hard=dict(d.get("hard", {})), used=dict(d.get("used", {}))
    )


def _limit_range_item_from_dict(d: dict) -> LimitRangeItemInfo:
    return LimitRangeItemInfo(
        kind=d["kind"],
        min=dict(d.get("min", {})),
        max=dict(d.get("max", {})),
        default=dict(d.get("default", {})),
        default_request=dict(d.get("default_request", {})),
    )


def _limit_range_from_dict(d: dict) -> LimitRangeInfo:
    return LimitRangeInfo(
        name=d["name"],
        limits=[_limit_range_item_from_dict(item) for item in d.get("limits", [])],
    )


def _warning_event_from_dict(d: dict) -> WarningEventInfo:
    return WarningEventInfo(
        reason=d["reason"],
        object_ref=d["object_ref"],
        message=d["message"],
        count=d["count"],
        last_seen=d.get("last_seen"),
    )


def _namespace_from_dict(d: dict) -> NamespaceInventory:
    # configmap_names/warning_events distinguish None ("not collected") from [] ("collected,
    # none exist") - see the model's own comment - so unlike every other list
    # field it must NOT be defaulted to [] here.
    configmap_names = d.get("configmap_names")
    warning_events = d.get("warning_events")
    return NamespaceInventory(
        name=d["name"],
        apps=[_app_from_dict(a) for a in d.get("apps", [])],
        resource_quotas=[_resource_quota_from_dict(rq) for rq in d.get("resource_quotas", [])],
        limit_ranges=[_limit_range_from_dict(lr) for lr in d.get("limit_ranges", [])],
        configmap_names=list(configmap_names) if configmap_names is not None else None,
        warning_events=[_warning_event_from_dict(e) for e in warning_events]
        if warning_events is not None
        else None,
    )


def _storage_class_from_dict(d: dict) -> StorageClassInfo:
    return StorageClassInfo(
        name=d["name"],
        provisioner=d["provisioner"],
        reclaim_policy=d.get("reclaim_policy"),
        volume_binding_mode=d.get("volume_binding_mode"),
        allow_volume_expansion=d.get("allow_volume_expansion"),
    )


def _node_info_from_dict(d: dict) -> NodeInfo:
    return NodeInfo(
        name=d["name"],
        architecture=d["architecture"],
        kubelet_version=d["kubelet_version"],
        os_image=d["os_image"],
        capacity_cpu=d["capacity_cpu"],
        capacity_memory=d["capacity_memory"],
        allocatable_cpu=d["allocatable_cpu"],
        allocatable_memory=d["allocatable_memory"],
        ready=d["ready"],
    )


def from_dict(data: dict) -> ClusterInventory:
    return ClusterInventory(
        cluster_name=data["cluster_name"],
        collected_at=data["collected_at"],
        namespaces=[_namespace_from_dict(ns) for ns in data.get("namespaces", [])],
        storage_classes=[_storage_class_from_dict(sc) for sc in data.get("storage_classes", [])],
        nodes=[_node_info_from_dict(n) for n in data.get("nodes", [])],
    )


def from_text(text: str, fmt: Format) -> ClusterInventory:
    if fmt == "json":
        return from_dict(json.loads(text))
    if fmt == "yaml":
        return from_dict(yaml.safe_load(text))
    raise ValueError(f"unsupported format: {fmt}")

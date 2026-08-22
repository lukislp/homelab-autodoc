"""ClusterInventory <-> JSON/YAML text."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Literal

import yaml

from .models import (
    App,
    ClusterInventory,
    Container,
    IngressInfo,
    IngressRule,
    NamespaceInventory,
    ServiceInfo,
    ServicePort,
    Volume,
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


def _container_from_dict(d: dict) -> Container:
    return Container(name=d["name"], image=d["image"], ports=list(d.get("ports", [])))


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


def _app_from_dict(d: dict) -> App:
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
    )


def _namespace_from_dict(d: dict) -> NamespaceInventory:
    return NamespaceInventory(name=d["name"], apps=[_app_from_dict(a) for a in d.get("apps", [])])


def from_dict(data: dict) -> ClusterInventory:
    return ClusterInventory(
        cluster_name=data["cluster_name"],
        collected_at=data["collected_at"],
        namespaces=[_namespace_from_dict(ns) for ns in data.get("namespaces", [])],
    )


def from_text(text: str, fmt: Format) -> ClusterInventory:
    if fmt == "json":
        return from_dict(json.loads(text))
    if fmt == "yaml":
        return from_dict(yaml.safe_load(text))
    raise ValueError(f"unsupported format: {fmt}")

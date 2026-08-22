"""Deterministic diff between two cluster inventory snapshots - the S4 drift
signal. Field-level, no LLM involved.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import App, ClusterInventory


@dataclass(frozen=True, slots=True)
class Change:
    kind: str  # "app_added" | "app_removed" | "app_changed"
    namespace: str
    app_name: str
    details: list[str] = field(default_factory=list)


def diff_inventories(old: ClusterInventory | None, new: ClusterInventory) -> list[Change]:
    if old is None:
        return []

    old_apps = _apps_by_key(old)
    new_apps = _apps_by_key(new)
    changes: list[Change] = []

    for namespace, app_name in sorted(new_apps.keys() - old_apps.keys()):
        changes.append(Change(kind="app_added", namespace=namespace, app_name=app_name))
    for namespace, app_name in sorted(old_apps.keys() - new_apps.keys()):
        changes.append(Change(kind="app_removed", namespace=namespace, app_name=app_name))
    for key in sorted(old_apps.keys() & new_apps.keys()):
        namespace, app_name = key
        details = _diff_app(old_apps[key], new_apps[key])
        if details:
            changes.append(
                Change(kind="app_changed", namespace=namespace, app_name=app_name, details=details)
            )

    return changes


def _apps_by_key(inventory: ClusterInventory) -> dict[tuple[str, str], App]:
    return {
        (namespace.name, app.name): app
        for namespace in inventory.namespaces
        for app in namespace.apps
    }


def _diff_app(old: App, new: App) -> list[str]:
    # ready_replicas is deliberately not compared - it fluctuates during every
    # normal rollout/restart and would turn drift detection into noise.
    details: list[str] = []

    if old.replicas != new.replicas:
        details.append(f"replicas: {old.replicas} -> {new.replicas}")

    old_containers = {c.name: c for c in old.containers}
    new_containers = {c.name: c for c in new.containers}
    for name in sorted(old_containers.keys() | new_containers.keys()):
        old_c, new_c = old_containers.get(name), new_containers.get(name)
        if old_c is None:
            details.append(f"container {name} added: {new_c.image}")
        elif new_c is None:
            details.append(f"container {name} removed (was {old_c.image})")
        else:
            if old_c.image != new_c.image:
                details.append(f"container {name} image: {old_c.image} -> {new_c.image}")
            if old_c.ports != new_c.ports:
                details.append(f"container {name} ports: {old_c.ports} -> {new_c.ports}")

    old_volumes = {v.claim_name: v for v in old.volumes}
    new_volumes = {v.claim_name: v for v in new.volumes}
    old_services = {s.name: s for s in old.services}
    new_services = {s.name: s for s in new.services}
    old_ingresses = {i.name: i for i in old.ingresses}
    new_ingresses = {i.name: i for i in new.ingresses}

    details.extend(_diff_by_name("volume", old_volumes, new_volumes))
    details.extend(_diff_by_name("service", old_services, new_services))
    details.extend(_diff_by_name("ingress", old_ingresses, new_ingresses))

    return details


def _diff_by_name(label: str, old_by_name: dict, new_by_name: dict) -> list[str]:
    details: list[str] = []
    for name in sorted(new_by_name.keys() - old_by_name.keys()):
        details.append(f"{label} {name} added")
    for name in sorted(old_by_name.keys() - new_by_name.keys()):
        details.append(f"{label} {name} removed")
    for name in sorted(old_by_name.keys() & new_by_name.keys()):
        if old_by_name[name] != new_by_name[name]:
            details.append(f"{label} {name} changed")
    return details

"""Deterministic Markdown fact tables, built only from the inventory."""

from __future__ import annotations

from autodoc_core.models import App


def containers_table(app: App) -> str:
    if not app.containers:
        return ""
    rows = [
        f"| {c.name} | `{c.image}` | {', '.join(map(str, c.ports)) or '-'} |"
        for c in sorted(app.containers, key=lambda c: c.name)
    ]
    return "\n".join(["| Container | Image | Ports |", "|---|---|---|", *rows])


def services_table(app: App) -> str:
    if not app.services:
        return ""
    rows = []
    for service in sorted(app.services, key=lambda s: s.name):
        ports = ", ".join(f"{p.port}->{p.target_port}/{p.protocol}" for p in service.ports)
        rows.append(f"| {service.name} | {service.type} | {ports or '-'} |")
    return "\n".join(["| Service | Type | Ports |", "|---|---|---|", *rows])


def ingresses_table(app: App) -> str:
    if not app.ingresses:
        return ""
    rows = []
    for ingress in sorted(app.ingresses, key=lambda i: i.name):
        for rule in ingress.rules:
            host = rule.host or "*"
            rows.append(f"| {ingress.name} | {host} | {rule.path} | {rule.service_name} |")
    return "\n".join(["| Ingress | Host | Path | Service |", "|---|---|---|---|", *rows])


def volumes_table(app: App) -> str:
    if not app.volumes:
        return ""
    rows = [
        f"| {v.claim_name} | {v.storage_class or '-'} | {v.capacity or '-'} | "
        f"{', '.join(v.access_modes) or '-'} |"
        for v in sorted(app.volumes, key=lambda v: v.claim_name)
    ]
    return "\n".join(
        ["| Claim | Storage Class | Capacity | Access Modes |", "|---|---|---|---|", *rows]
    )

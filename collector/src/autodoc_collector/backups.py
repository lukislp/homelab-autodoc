"""Backup posture from the Velero and CNPG custom resources.

Read via CustomObjectsApi like HTTPRoutes - untyped dicts, only ever reduced
to the few status/spec facts the models carry. Degradation contract:

- 404 (CRD not installed) -> empty list: a cluster without Velero truthfully
  HAS no Velero schedules.
- 403 (RBAC denies it) -> the WHOLE ClusterBackupInfo becomes None: partial
  permission would render as "these backups don't exist", and unknown must
  never look like absence.
"""

from __future__ import annotations

from autodoc_core.models import (
    ClusterBackupInfo,
    CNPGBackupInfo,
    CNPGScheduledBackupInfo,
    VeleroBackupInfo,
    VeleroScheduleInfo,
)
from kubernetes.client.exceptions import ApiException

from .k8s_apis import K8sApis

_VELERO_GROUP = "velero.io"
_CNPG_GROUP = "postgresql.cnpg.io"
_VERSION = "v1"
# Velero's CRs live in its install namespace - "velero" is the tool's own
# default and this cluster's convention. A different install namespace would
# read as "no schedules", which the Backups page then shows honestly.
_VELERO_NAMESPACE = "velero"
# Recent-run lists are trend context, not an archive - the page shows the
# newest handful, the full history lives in the CRs themselves.
_RECENT_RUNS_CAP = 10


def _list_velero(apis: K8sApis, plural: str) -> list[dict] | None:
    try:
        result = apis.custom_objects.list_namespaced_custom_object(
            group=_VELERO_GROUP, version=_VERSION, namespace=_VELERO_NAMESPACE, plural=plural
        )
    except ApiException as e:
        if e.status == 404:
            return []
        if e.status == 403:
            return None
        raise
    return result.get("items", [])


def _list_cnpg(apis: K8sApis, plural: str) -> list[dict] | None:
    try:
        result = apis.custom_objects.list_cluster_custom_object(
            group=_CNPG_GROUP, version=_VERSION, plural=plural
        )
    except ApiException as e:
        if e.status == 404:
            return []
        if e.status == 403:
            return None
        raise
    return result.get("items", [])


def collect_backup_info(apis: K8sApis) -> ClusterBackupInfo | None:
    velero_schedules = _list_velero(apis, "schedules")
    velero_backups = _list_velero(apis, "backups")
    cnpg_scheduled = _list_cnpg(apis, "scheduledbackups")
    cnpg_backups = _list_cnpg(apis, "backups")
    if None in (velero_schedules, velero_backups, cnpg_scheduled, cnpg_backups):
        return None

    schedules = [
        VeleroScheduleInfo(
            name=item["metadata"]["name"],
            schedule=item.get("spec", {}).get("schedule", ""),
            ttl=item.get("spec", {}).get("template", {}).get("ttl"),
            included_namespaces=list(
                item.get("spec", {}).get("template", {}).get("includedNamespaces") or []
            ),
            last_backup=(item.get("status") or {}).get("lastBackup"),
        )
        for item in sorted(velero_schedules, key=lambda i: i["metadata"]["name"])
    ]

    runs = [
        VeleroBackupInfo(
            name=item["metadata"]["name"],
            phase=(item.get("status") or {}).get("phase", "Unknown"),
            schedule=(item["metadata"].get("labels") or {}).get("velero.io/schedule-name"),
            started=(item.get("status") or {}).get("startTimestamp"),
            expiration=(item.get("status") or {}).get("expiration"),
            errors=(item.get("status") or {}).get("errors", 0),
        )
        for item in sorted(
            velero_backups,
            key=lambda i: i["metadata"].get("creationTimestamp", ""),
            reverse=True,
        )[:_RECENT_RUNS_CAP]
    ]

    scheduled = [
        CNPGScheduledBackupInfo(
            namespace=item["metadata"]["namespace"],
            name=item["metadata"]["name"],
            schedule=item.get("spec", {}).get("schedule", ""),
            cluster=item.get("spec", {}).get("cluster", {}).get("name", ""),
            last_schedule_time=(item.get("status") or {}).get("lastScheduleTime"),
        )
        for item in sorted(
            cnpg_scheduled, key=lambda i: (i["metadata"]["namespace"], i["metadata"]["name"])
        )
    ]

    pg_runs = [
        CNPGBackupInfo(
            namespace=item["metadata"]["namespace"],
            name=item["metadata"]["name"],
            phase=(item.get("status") or {}).get("phase", "Unknown"),
            stopped_at=(item.get("status") or {}).get("stoppedAt"),
        )
        for item in sorted(
            cnpg_backups,
            key=lambda i: i["metadata"].get("creationTimestamp", ""),
            reverse=True,
        )[:_RECENT_RUNS_CAP]
    ]

    return ClusterBackupInfo(
        velero_schedules=schedules,
        velero_backups=runs,
        cnpg_scheduled_backups=scheduled,
        cnpg_backups=pg_runs,
    )

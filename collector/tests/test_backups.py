from __future__ import annotations

from types import SimpleNamespace

import pytest
from kubernetes.client.exceptions import ApiException

from autodoc_collector.backups import collect_backup_info


def _apis(namespaced=None, cluster=None):
    def list_namespaced_custom_object(group, version, namespace, plural):
        return namespaced(group, plural)

    def list_cluster_custom_object(group, version, plural):
        return cluster(group, plural)

    return SimpleNamespace(
        custom_objects=SimpleNamespace(
            list_namespaced_custom_object=list_namespaced_custom_object,
            list_cluster_custom_object=list_cluster_custom_object,
        )
    )


_VELERO_ITEMS = {
    "schedules": [
        {
            "metadata": {"name": "nightly"},
            "spec": {
                "schedule": "0 3 * * *",
                "template": {"ttl": "168h0m0s", "includedNamespaces": ["demo"]},
            },
            "status": {"lastBackup": "2026-08-25T03:00:00Z"},
        }
    ],
    "backups": [
        {
            "metadata": {
                "name": "nightly-20260825",
                "creationTimestamp": "2026-08-25T03:00:00Z",
                "labels": {"velero.io/schedule-name": "nightly"},
            },
            "status": {
                "phase": "Completed",
                "startTimestamp": "2026-08-25T03:00:01Z",
                "expiration": "2026-09-01T03:00:00Z",
            },
        }
    ],
}

_CNPG_ITEMS = {
    "scheduledbackups": [
        {
            "metadata": {"namespace": "db", "name": "pg-daily"},
            "spec": {"schedule": "0 0 3 * * *", "cluster": {"name": "pg"}},
            "status": {"lastScheduleTime": "2026-08-25T03:00:00Z"},
        }
    ],
    "backups": [
        {
            "metadata": {"namespace": "db", "name": "pg-daily-1", "creationTimestamp": "x"},
            "status": {"phase": "completed", "stoppedAt": "2026-08-25T03:05:00Z"},
        }
    ],
}


def test_collects_velero_and_cnpg_facts():
    apis = _apis(
        namespaced=lambda group, plural: {"items": _VELERO_ITEMS[plural]},
        cluster=lambda group, plural: {"items": _CNPG_ITEMS[plural]},
    )

    info = collect_backup_info(apis)

    schedule = info.velero_schedules[0]
    assert (schedule.name, schedule.schedule, schedule.ttl) == ("nightly", "0 3 * * *", "168h0m0s")
    assert schedule.included_namespaces == ["demo"]
    assert schedule.last_backup == "2026-08-25T03:00:00Z"
    run = info.velero_backups[0]
    assert (run.name, run.phase, run.schedule) == ("nightly-20260825", "Completed", "nightly")
    assert info.cnpg_scheduled_backups[0].cluster == "pg"
    assert info.cnpg_backups[0].phase == "completed"


def test_missing_crds_mean_truly_empty_not_unknown():
    def not_found(*_):
        raise ApiException(status=404)

    apis = _apis(namespaced=not_found, cluster=not_found)

    info = collect_backup_info(apis)

    assert info is not None
    assert info.velero_schedules == [] and info.cnpg_backups == []


def test_denied_rbac_means_unknown_not_empty():
    def forbidden(*_):
        raise ApiException(status=403)

    apis = _apis(
        namespaced=forbidden,
        cluster=lambda group, plural: {"items": _CNPG_ITEMS[plural]},
    )

    assert collect_backup_info(apis) is None


def test_unexpected_errors_still_raise():
    def boom(*_):
        raise ApiException(status=500)

    apis = _apis(namespaced=boom, cluster=boom)

    with pytest.raises(ApiException):
        collect_backup_info(apis)

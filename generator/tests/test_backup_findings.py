from __future__ import annotations

from autodoc_core.models import (
    App,
    ClusterBackupInfo,
    ClusterInventory,
    NamespaceInventory,
    VeleroScheduleInfo,
    Volume,
)

from autodoc_generator.facts import velero_schedules_table
from autodoc_generator.findings import evaluate_cluster, evaluate_cluster_accepted


def _app(
    name: str,
    volumes: bool = True,
    backup_volumes: list[str] | None = None,
    annotations: dict[str, str] | None = None,
) -> App:
    return App(
        name=name,
        kind="Deployment",
        replicas=1,
        ready_replicas=1,
        volumes=[Volume(claim_name=f"{name}-data", storage_class="local-path", capacity="1Gi")]
        if volumes
        else [],
        backup_volumes=backup_volumes or [],
        annotations=annotations or {},
    )


def _inventory(apps: list[App], backups: ClusterBackupInfo | None) -> ClusterInventory:
    return ClusterInventory(
        cluster_name="homelab",
        collected_at="2026-08-25T00:00:00+00:00",
        namespaces=[NamespaceInventory(name="demo", apps=apps)],
        backups=backups,
    )


_SCHEDULE = ClusterBackupInfo(
    velero_schedules=[
        VeleroScheduleInfo(name="nightly", schedule="0 3 * * *", included_namespaces=["demo"])
    ]
)


def _rules(inventory: ClusterInventory) -> set[str]:
    return {cf.finding.rule for cf in evaluate_cluster(inventory)}


def test_pvc_app_without_opt_in_gets_a_no_backup_finding():
    inventory = _inventory([_app("web")], _SCHEDULE)

    assert "no-backup" in _rules(inventory)


def test_opted_in_app_in_a_scheduled_namespace_is_clean():
    inventory = _inventory([_app("web", backup_volumes=["data"])], _SCHEDULE)

    assert "no-backup" not in _rules(inventory)
    assert "backup-not-scheduled" not in _rules(inventory)


def test_opt_in_outside_every_schedule_namespace_is_flagged():
    # The silent production failure mode: annotation present, namespace not in
    # any Schedule's includedNamespaces - Velero never even considers the pod.
    outside = ClusterBackupInfo(
        velero_schedules=[
            VeleroScheduleInfo(name="nightly", schedule="0 3 * * *", included_namespaces=["other"])
        ]
    )
    inventory = _inventory([_app("web", backup_volumes=["data"])], outside)

    assert "backup-not-scheduled" in _rules(inventory)


def test_uncollected_backup_posture_stays_silent():
    inventory = _inventory([_app("web")], None)

    assert "no-backup" not in _rules(inventory)


def test_volumeless_app_needs_no_backup():
    inventory = _inventory([_app("stateless", volumes=False)], _SCHEDULE)

    assert "no-backup" not in _rules(inventory)


def test_no_backup_can_be_accepted_with_a_reason():
    app = _app(
        "collector",
        annotations={"autodoc.homelab/accept-no-backup": "job pod lives a minute a night"},
    )
    inventory = _inventory([app], _SCHEDULE)

    assert "no-backup" not in _rules(inventory)
    accepted = evaluate_cluster_accepted(inventory)
    assert [(caf.finding.rule, caf.reason) for caf in accepted] == [
        ("no-backup", "job pod lives a minute a night")
    ]


def test_velero_schedules_table_renders_cron_namespaces_and_last_backup():
    table = velero_schedules_table(
        ClusterBackupInfo(
            velero_schedules=[
                VeleroScheduleInfo(
                    name="nightly",
                    schedule="0 3 * * *",
                    ttl="168h0m0s",
                    included_namespaces=["demo", "other"],
                    last_backup="2026-08-25T03:00:00Z",
                )
            ]
        )
    )

    assert "| nightly | `0 3 * * *` | 168h0m0s | demo, other |" in table
    assert "never" not in table

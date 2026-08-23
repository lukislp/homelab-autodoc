"""Admin-only management of already-registered clusters: list and delete.
Registering a new cluster happens through the device-grant flow
(routes_device.py) instead - there's no "create" here.
"""

from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, HTTPException

from ..logic import site_builder
from ..logic.storage import Storage
from .deps import get_mkdocs_config_path, get_storage
from .session import require_admin_session

router = APIRouter()


@router.get("/api/admin/clusters", dependencies=[Depends(require_admin_session)])
def list_clusters(storage: Storage = Depends(get_storage)) -> list[str]:
    return storage.list_clusters()


@router.delete("/api/admin/clusters/{cluster_name}", dependencies=[Depends(require_admin_session)])
def delete_cluster(
    cluster_name: str,
    storage: Storage = Depends(get_storage),
) -> dict:
    if not storage.delete_cluster(cluster_name):
        raise HTTPException(status_code=404, detail="unknown cluster")

    # The generated pages have to go explicitly: nothing ever removes a
    # now-orphaned docs_dir tree for a cluster that no longer exists
    # (docs_dir/site_dir are otherwise ephemeral: wiped on every pod restart,
    # not on a cluster's deletion in between restarts). Every other cluster's
    # pages stay untouched, so the rebuild only needs the root index plus one
    # static build - see rebuild_site_after_cluster_delete's docstring for why
    # not a full rebuild_all_sites.
    shutil.rmtree(storage.docs_dir / cluster_name, ignore_errors=True)
    site_builder.rebuild_site_after_cluster_delete(storage, get_mkdocs_config_path())

    return {"status": "deleted", "cluster": cluster_name}

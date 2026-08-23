"""Admin-only management of already-registered clusters: list and delete.
Registering a new cluster happens through the device-grant flow
(routes_device.py) instead - there's no "create" here.
"""

from __future__ import annotations

import shutil

from autodoc_generator.llm import LLMClient
from fastapi import APIRouter, Depends, HTTPException

from ..logic import site_builder
from ..logic.storage import Storage
from .deps import get_llm, get_mkdocs_config_path, get_storage
from .session import require_admin_session

router = APIRouter()


@router.get("/api/admin/clusters", dependencies=[Depends(require_admin_session)])
def list_clusters(storage: Storage = Depends(get_storage)) -> list[str]:
    return storage.list_clusters()


@router.delete("/api/admin/clusters/{cluster_name}", dependencies=[Depends(require_admin_session)])
def delete_cluster(
    cluster_name: str,
    storage: Storage = Depends(get_storage),
    llm: LLMClient | None = Depends(get_llm),
) -> dict:
    if not storage.delete_cluster(cluster_name):
        raise HTTPException(status_code=404, detail="unknown cluster")

    # regenerate_cluster_docs only ever writes pages for clusters that still
    # exist - it never removes a now-orphaned directory for one that doesn't,
    # so that has to happen explicitly before the rebuild picks the site back
    # up (docs_dir/site_dir are otherwise ephemeral: wiped on every pod
    # restart, not on a cluster's deletion in between restarts).
    shutil.rmtree(storage.docs_dir / cluster_name, ignore_errors=True)
    mkdocs_config_path = get_mkdocs_config_path()
    site_builder.rebuild_all_sites(storage, llm, mkdocs_config_path)
    # rebuild_all_sites skips the actual static build when zero clusters
    # remain (it also runs at server startup, where that would be unsafe -
    # see its own docstring) - a request handler has no such constraint, and
    # deleting the last cluster still needs the built site to drop it.
    site_builder.build_static_site(mkdocs_config_path)

    return {"status": "deleted", "cluster": cluster_name}

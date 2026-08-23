from __future__ import annotations

from autodoc_core.serialize import from_text
from autodoc_generator.llm import LLMClient
from fastapi import APIRouter, Depends

from ..logic import drift, site_builder
from ..logic.storage import Storage
from .auth import require_cluster_push_token
from .deps import get_llm, get_mkdocs_config_path, get_storage
from .schemas import InventoryPushRequest

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@router.get("/api/site/version")
def site_version(storage: Storage = Depends(get_storage)) -> dict:
    """Build stamp of the served static site. The auto-refresh script every
    doc page loads (overrides/javascripts/auto-refresh.js) polls this and
    reloads the page when a new build lands, so open pages never go stale
    after a collector push or a cluster delete. Every mkdocs build rewrites
    the root index, so its mtime doubles as the stamp; 0 means no build yet
    (a fresh install with nothing registered).
    """
    index = storage.docs_dir.parent / "site" / "index.html"
    version = index.stat().st_mtime_ns if index.exists() else 0
    return {"version": str(version)}


@router.post(
    "/api/clusters/{cluster_name}/inventory",
    dependencies=[Depends(require_cluster_push_token)],
)
def push_inventory(
    cluster_name: str,
    payload: InventoryPushRequest,
    storage: Storage = Depends(get_storage),
    llm: LLMClient | None = Depends(get_llm),
) -> dict:
    inventory = from_text(payload.text, fmt=payload.format)
    changes = drift.record_drift(storage, cluster_name, inventory)
    storage.save_inventory(cluster_name, inventory)

    site_builder.regenerate_cluster_docs(storage, cluster_name, llm)
    site_builder.build_static_site(get_mkdocs_config_path())

    return {
        "status": "ok",
        "cluster": cluster_name,
        "namespaces": len(inventory.namespaces),
        "drift_changes": len(changes),
    }

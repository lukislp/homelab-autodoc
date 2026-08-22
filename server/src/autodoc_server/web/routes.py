from __future__ import annotations

from autodoc_core.serialize import from_text
from autodoc_generator.llm import LLMClient
from fastapi import APIRouter, Depends

from ..logic import site_builder
from ..logic.storage import Storage
from .auth import require_push_token
from .deps import get_llm, get_mkdocs_config_path, get_storage
from .schemas import InventoryPushRequest

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@router.post(
    "/api/clusters/{cluster_name}/inventory",
    dependencies=[Depends(require_push_token)],
)
def push_inventory(
    cluster_name: str,
    payload: InventoryPushRequest,
    storage: Storage = Depends(get_storage),
    llm: LLMClient | None = Depends(get_llm),
) -> dict:
    inventory = from_text(payload.text, fmt=payload.format)
    storage.save_inventory(cluster_name, inventory)

    site_builder.regenerate_cluster_docs(storage, cluster_name, llm)
    site_builder.build_static_site(get_mkdocs_config_path())

    return {"status": "ok", "cluster": cluster_name, "namespaces": len(inventory.namespaces)}

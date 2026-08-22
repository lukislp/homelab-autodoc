"""Per-cluster push-token verification. Each cluster's token is minted once,
at device-grant approval time (see device_grant.py + routes_device.py), and
persisted via Storage - this replaces the earlier single shared
AUTODOC_PUSH_TOKEN that every cluster used to authenticate with.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Path

from ..logic.storage import Storage
from .deps import get_storage


def require_cluster_push_token(
    cluster_name: str = Path(...),
    x_push_token: str = Header(...),
    storage: Storage = Depends(get_storage),
) -> None:
    if not storage.verify_push_token(cluster_name, x_push_token):
        raise HTTPException(status_code=401, detail="invalid or missing push token")

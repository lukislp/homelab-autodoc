"""OAuth 2.0 Device Authorization Grant (RFC 8628) endpoints.

A new cluster calls POST /device/code without any pre-shared secret, shows
the returned user_code, and polls POST /device/token until an admin approves
or denies it at GET/POST /admin/devices/*. Error `detail` values follow the
RFC's vocabulary (authorization_pending, access_denied, expired_token) so a
standard device-flow client library recognizes them.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..logic.device_grant import DeviceGrantStore, approve_registration
from ..logic.storage import Storage
from .admin_auth import require_admin_token
from .deps import get_device_grant_store, get_storage

router = APIRouter()


class DeviceCodeRequest(BaseModel):
    cluster_name: str


class DeviceCodeResponse(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int = 5


@router.post("/device/code", response_model=DeviceCodeResponse)
def request_device_code(
    payload: DeviceCodeRequest,
    request: Request,
    store: DeviceGrantStore = Depends(get_device_grant_store),
) -> DeviceCodeResponse:
    registration = store.create(payload.cluster_name)
    verification_uri = str(request.base_url) + "admin/devices"
    return DeviceCodeResponse(
        device_code=registration.device_code,
        user_code=registration.user_code,
        verification_uri=verification_uri,
        verification_uri_complete=f"{verification_uri}?user_code={registration.user_code}",
        expires_in=int(registration.expires_at - registration.created_at),
    )


class DeviceTokenRequest(BaseModel):
    device_code: str


@router.post("/device/token")
def poll_device_token(
    payload: DeviceTokenRequest, store: DeviceGrantStore = Depends(get_device_grant_store)
) -> dict:
    registration = store.get_by_device_code(payload.device_code)
    if registration is None or store.is_expired(registration):
        raise HTTPException(status_code=400, detail="expired_token")
    if registration.status == "pending":
        raise HTTPException(status_code=400, detail="authorization_pending")
    if registration.status == "denied":
        raise HTTPException(status_code=400, detail="access_denied")

    return {
        "status": "approved",
        "cluster_name": registration.cluster_name,
        "push_token": registration.push_token,
    }


@router.get("/admin/devices", dependencies=[Depends(require_admin_token)])
def list_pending_devices(store: DeviceGrantStore = Depends(get_device_grant_store)) -> list[dict]:
    return [
        {"user_code": r.user_code, "cluster_name": r.cluster_name}
        for r in sorted(store.list_pending(), key=lambda r: r.created_at)
    ]


@router.post("/admin/devices/{user_code}/approve", dependencies=[Depends(require_admin_token)])
def approve_device(
    user_code: str,
    store: DeviceGrantStore = Depends(get_device_grant_store),
    storage: Storage = Depends(get_storage),
) -> dict:
    updated = approve_registration(store, storage, user_code)
    if updated is None:
        raise HTTPException(status_code=404, detail="unknown user_code")

    return {"status": "approved", "cluster_name": updated.cluster_name}


@router.post("/admin/devices/{user_code}/deny", dependencies=[Depends(require_admin_token)])
def deny_device(user_code: str, store: DeviceGrantStore = Depends(get_device_grant_store)) -> dict:
    updated = store.deny(user_code)
    if updated is None:
        raise HTTPException(status_code=404, detail="unknown user_code")

    return {"status": "denied"}

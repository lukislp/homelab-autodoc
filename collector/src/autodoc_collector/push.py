"""Client-side half of the OAuth 2.0 Device Authorization Grant (RFC 8628):
register this cluster with a server, wait for an admin to approve it, then
push an inventory using the resulting per-cluster token.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx


class RegistrationDenied(Exception):
    pass


class RegistrationExpired(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DeviceCode:
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


def request_device_code(server_url: str, cluster_name: str, timeout: float = 10.0) -> DeviceCode:
    response = httpx.post(
        f"{server_url.rstrip('/')}/device/code",
        json={"cluster_name": cluster_name},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    return DeviceCode(
        device_code=data["device_code"],
        user_code=data["user_code"],
        verification_uri=data["verification_uri"],
        verification_uri_complete=data["verification_uri_complete"],
        expires_in=data["expires_in"],
        interval=data["interval"],
    )


def poll_for_push_token(
    server_url: str,
    device_code: str,
    interval: int,
    expires_in: int,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> str:
    deadline = clock() + expires_in
    url = f"{server_url.rstrip('/')}/device/token"

    while clock() < deadline:
        response = httpx.post(url, json={"device_code": device_code}, timeout=10.0)
        if response.status_code == 200:
            return response.json()["push_token"]

        detail = response.json().get("detail")
        if detail == "authorization_pending":
            sleep(interval)
            continue
        if detail == "access_denied":
            raise RegistrationDenied("the admin denied this cluster's registration")
        if detail == "expired_token":
            raise RegistrationExpired("the registration request expired before it was approved")
        response.raise_for_status()

    raise RegistrationExpired("timed out waiting for admin approval")


def push_inventory(
    server_url: str,
    cluster_name: str,
    push_token: str,
    text: str,
    fmt: str,
    # The server regenerates every page (facts, diagrams, a full mkdocs build) and,
    # if an LLM is configured, calls it once per app - synchronously, in this same
    # request - before responding. On a many-app cluster and modest hardware
    # (Raspberry Pi) that's minutes, not seconds; this runs from an unattended
    # nightly CronJob, so there's no UX reason to time out aggressively.
    timeout: float = 300.0,
) -> dict:
    response = httpx.post(
        f"{server_url.rstrip('/')}/api/clusters/{cluster_name}/inventory",
        json={"format": fmt, "text": text},
        headers={"X-Push-Token": push_token},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()

"""OAuth 2.0 Device Authorization Grant (RFC 8628) state.

In-memory, single-process - fine at homelab scale. A pending (not yet
approved) registration lost on restart just means the cluster asks again,
which is cheap and expected; approved push tokens are persisted separately
(see Storage.save_push_token), so an approved cluster survives a restart.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal

from .storage import Storage

Status = Literal["pending", "approved", "denied"]

_USER_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity


@dataclass(frozen=True, slots=True)
class DeviceRegistration:
    device_code: str
    user_code: str
    cluster_name: str
    status: Status
    created_at: float
    expires_at: float
    push_token: str | None = None


def _generate_user_code() -> str:
    chars = [secrets.choice(_USER_CODE_ALPHABET) for _ in range(8)]
    return f"{''.join(chars[:4])}-{''.join(chars[4:])}"


class DeviceGrantStore:
    def __init__(self, ttl_seconds: int = 600, clock: Callable[[], float] = time.time) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._by_device_code: dict[str, DeviceRegistration] = {}
        self._device_code_by_user_code: dict[str, str] = {}

    def create(self, cluster_name: str) -> DeviceRegistration:
        now = self._clock()
        registration = DeviceRegistration(
            device_code=secrets.token_urlsafe(32),
            user_code=self._unique_user_code(),
            cluster_name=cluster_name,
            status="pending",
            created_at=now,
            expires_at=now + self._ttl_seconds,
        )
        self._by_device_code[registration.device_code] = registration
        self._device_code_by_user_code[registration.user_code] = registration.device_code
        return registration

    def _unique_user_code(self) -> str:
        while True:
            code = _generate_user_code()
            if code not in self._device_code_by_user_code:
                return code

    def get_by_device_code(self, device_code: str) -> DeviceRegistration | None:
        return self._by_device_code.get(device_code)

    def get_by_user_code(self, user_code: str) -> DeviceRegistration | None:
        device_code = self._device_code_by_user_code.get(user_code)
        return self._by_device_code.get(device_code) if device_code else None

    def is_expired(self, registration: DeviceRegistration) -> bool:
        return self._clock() >= registration.expires_at

    def list_pending(self) -> list[DeviceRegistration]:
        return [
            r
            for r in self._by_device_code.values()
            if r.status == "pending" and not self.is_expired(r)
        ]

    def approve(self, user_code: str, push_token: str) -> DeviceRegistration | None:
        return self._set_status(user_code, "approved", push_token=push_token)

    def deny(self, user_code: str) -> DeviceRegistration | None:
        return self._set_status(user_code, "denied")

    def _set_status(
        self, user_code: str, status: Status, push_token: str | None = None
    ) -> DeviceRegistration | None:
        registration = self.get_by_user_code(user_code)
        if registration is None:
            return None
        updated = replace(registration, status=status, push_token=push_token)
        self._by_device_code[updated.device_code] = updated
        return updated


def approve_registration(
    store: DeviceGrantStore, storage: Storage, user_code: str
) -> DeviceRegistration | None:
    """Mint a push token for the registration's cluster, persist it, and approve.

    Kept out of the web layer - minting a credential on approval is a device-
    grant decision, not an HTTP concern.
    """
    registration = store.get_by_user_code(user_code)
    if registration is None:
        return None

    token = secrets.token_urlsafe(32)
    storage.save_push_token(registration.cluster_name, token)
    return store.approve(user_code, token)

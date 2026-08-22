"""Temporary shared-token guard for the device-approval admin endpoints -
replaced by real session-based admin login (GitHub/OIDC) in a follow-up PR.
Deliberately a separate credential from the per-cluster push token.
"""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


def require_admin_token(x_admin_token: str = Header(...)) -> None:
    expected = os.environ.get("AUTODOC_ADMIN_TOKEN")
    if not expected or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="invalid or missing admin token")

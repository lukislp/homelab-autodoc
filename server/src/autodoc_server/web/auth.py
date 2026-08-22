"""Temporary shared-token guard for the inventory push endpoint - replaced by
the OAuth 2.0 Device Authorization Grant in S3.5. Not the final security model.
"""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


def require_push_token(x_push_token: str = Header(...)) -> None:
    expected = os.environ.get("AUTODOC_PUSH_TOKEN")
    if not expected or not hmac.compare_digest(x_push_token, expected):
        raise HTTPException(status_code=401, detail="invalid or missing push token")

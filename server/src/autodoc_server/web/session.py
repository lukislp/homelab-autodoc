"""Admin session guard, backed by Starlette's signed-cookie SessionMiddleware."""

from __future__ import annotations

from fastapi import HTTPException, Request


def require_admin_session(request: Request) -> str:
    identity = request.session.get("identity")
    if not identity:
        raise HTTPException(status_code=401, detail="not logged in")
    return identity

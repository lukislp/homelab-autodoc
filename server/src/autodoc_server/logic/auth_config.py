"""Persisted admin-auth provider configuration. No web framework import here."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

Provider = Literal["github", "oidc"]


@dataclass(frozen=True, slots=True)
class AuthProviderConfig:
    provider: Provider
    client_id: str
    client_secret: str
    allowed_identity: str
    issuer_url: str | None = None  # required when provider == "oidc"


class AuthConfigStore:
    def __init__(self, config_dir: Path) -> None:
        self._path = config_dir / "auth.json"

    def load(self) -> AuthProviderConfig | None:
        if not self._path.exists():
            return None
        data = json.loads(self._path.read_text(encoding="utf-8"))
        return AuthProviderConfig(**data)

    def save(self, config: AuthProviderConfig) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")

    def is_configured(self) -> bool:
        return self._path.exists()

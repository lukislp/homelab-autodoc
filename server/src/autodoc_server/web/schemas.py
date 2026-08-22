from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class InventoryPushRequest(BaseModel):
    format: Literal["json", "yaml"] = "json"
    text: str

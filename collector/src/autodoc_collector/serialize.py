"""Turns a ClusterInventory into JSON or YAML text."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Literal

import yaml

from .models import ClusterInventory

Format = Literal["json", "yaml"]


def to_dict(inventory: ClusterInventory) -> dict:
    return asdict(inventory)


def to_text(inventory: ClusterInventory, fmt: Format, pretty: bool = True) -> str:
    data = to_dict(inventory)
    if fmt == "json":
        return json.dumps(data, indent=2 if pretty else None, sort_keys=False)
    if fmt == "yaml":
        return yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    raise ValueError(f"unsupported format: {fmt}")

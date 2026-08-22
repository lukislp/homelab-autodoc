#!/usr/bin/env python3
"""Bump the `version = "..."` line in one or more pyproject.toml files in place.

A regex substitution on just that line, not a full TOML load/dump round-trip -
the latter reformats the whole file and produces noisy unrelated diffs on
every release. All packages in this monorepo release under one shared
version, so every pyproject.toml is passed in on each run.
"""

import re
import sys
from pathlib import Path


def sync_one(path: Path, new_version: str) -> bool:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(?m)^version = "[^"]+"$', f'version = "{new_version}"', text, count=1
    )
    if count != 1:
        print(f"::error::no version line found in {path}", file=sys.stderr)
        return False

    path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    new_version = sys.argv[1]
    paths = [Path(p) for p in sys.argv[2:]]

    results = [sync_one(path, new_version) for path in paths]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())

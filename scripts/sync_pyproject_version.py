#!/usr/bin/env python3
"""Bump the `version = "..."` line in a pyproject.toml in place.

A regex substitution on just that line, not a full TOML load/dump round-trip -
the latter reformats the whole file and produces noisy unrelated diffs on
every release.
"""

import re
import sys
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1])
    new_version = sys.argv[2]

    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(?m)^version = "[^"]+"$', f'version = "{new_version}"', text, count=1
    )
    if count != 1:
        print(f"::error::no version line found in {path}", file=sys.stderr)
        return 1

    path.write_text(updated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

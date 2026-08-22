#!/usr/bin/env python3
"""Turn a coverage.py JSON report into a shields.io endpoint badge JSON."""

import json
import sys


def color_for(percent: float) -> str:
    if percent >= 80:
        return "brightgreen"
    if percent >= 60:
        return "green"
    if percent >= 40:
        return "yellow"
    if percent >= 20:
        return "orange"
    return "red"


def main() -> int:
    coverage_path, out_path = sys.argv[1], sys.argv[2]
    label = sys.argv[3] if len(sys.argv) > 3 else "coverage"

    with open(coverage_path, encoding="utf-8") as f:
        report = json.load(f)

    percent = report["totals"]["percent_covered"]
    badge = {
        "schemaVersion": 1,
        "label": label,
        "message": f"{percent:.1f}%",
        "color": color_for(percent),
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(badge, f)

    return 0


if __name__ == "__main__":
    sys.exit(main())

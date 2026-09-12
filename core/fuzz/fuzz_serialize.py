"""Atheris fuzz harness for the inventory (de)serialization and diff in autodoc_core.

Contract under test: from_text() either returns a ClusterInventory or raises one of the
documented parse/shape errors - never anything else - and every inventory it does accept
survives the JSON and YAML round trips unchanged and diffs against itself as "no change".

Run locally (Linux, needs the atheris wheel):
    pip install --require-hashes -r requirements/core.txt -r requirements/core-fuzz.txt
    pip install --no-deps -e core
    python core/fuzz/fuzz_serialize.py -max_total_time=60
CI runs the same harness for a short, fixed time budget (see .github/workflows/ci-cd.yml).
"""

from __future__ import annotations

import sys

import atheris
import yaml

from autodoc_core.diff import diff_inventories
from autodoc_core.serialize import from_dict, from_text, to_dict, to_text

# What a malformed or mis-shaped document is allowed to raise: JSON/YAML syntax errors,
# missing keys, wrong value types. RecursionError covers a YAML document nested deeper than
# the interpreter stack - the parser's limit, not a defect in this code.
EXPECTED = (ValueError, KeyError, TypeError, AttributeError, yaml.YAMLError, RecursionError)


def test_one_input(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    fmt = "yaml" if fdp.ConsumeBool() else "json"
    text = fdp.ConsumeUnicodeNoSurrogates(2048)
    try:
        inventory = from_text(text, fmt)
    except EXPECTED:
        return

    if from_dict(to_dict(inventory)) != inventory:
        raise AssertionError("to_dict/from_dict round trip changed the inventory")
    for round_trip_fmt in ("json", "yaml"):
        if from_text(to_text(inventory, round_trip_fmt), round_trip_fmt) != inventory:
            raise AssertionError(f"{round_trip_fmt} text round trip changed the inventory")
    if diff_inventories(inventory, inventory):
        raise AssertionError("an inventory must not differ from itself")
    diff_inventories(None, inventory)


if __name__ == "__main__":
    atheris.instrument_all()
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()

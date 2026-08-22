from __future__ import annotations

from autodoc_generator.formatting import format_timestamp


def test_format_timestamp_drops_microseconds_and_labels_utc():
    assert format_timestamp("2026-08-22T22:54:12.396265+00:00") == "2026-08-22 22:54 UTC"


def test_format_timestamp_handles_second_precision():
    assert format_timestamp("2026-08-01T12:00:00+00:00") == "2026-08-01 12:00 UTC"


def test_format_timestamp_falls_back_to_raw_string_on_unparseable_input():
    assert format_timestamp("not-a-timestamp") == "not-a-timestamp"

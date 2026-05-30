"""Unit tests for cache build streaming helpers."""

from __future__ import annotations

import dataclasses

import pytest

pytestmark = pytest.mark.unit


@dataclasses.dataclass
class _SamplePayload:
    patient_id: str
    value: int


def test_json_ready_converts_dataclasses_recursively() -> None:
    from src.bilun.cache.build_streaming import json_ready

    payload = {
        "rows": [_SamplePayload(patient_id="P-1", value=3)],
        "nested": {"items": [1, {"a": 2}]},
    }
    assert json_ready(payload) == {
        "rows": [{"patient_id": "P-1", "value": 3}],
        "nested": {"items": [1, {"a": 2}]},
    }


def test_dump_json_compact_uses_compact_separators() -> None:
    from src.bilun.cache.build_streaming import dump_json_compact

    assert dump_json_compact({"a": 1, "b": "two"}) == '{"a":1,"b":"two"}'

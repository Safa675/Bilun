"""L1.4 material Gate B — generic path (Track F facade + export CLIs removed)."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from scripts.sut.prose.gate_b_generic import export_candidates
from scripts.sut.prose.gate_b_sections import SECTION_MATERIAL_31_32

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[3]
CLAUSES = ROOT / "data/gazette/sut_clauses.parquet"
PROSE_JSON = ROOT / "data/gazette/prose_rules/material_bundling_prose.json"
SCHEMA = ROOT / "data/gazette/prose_rules/material_bundling_prose.schema.json"


@pytest.fixture(scope="module")
def gate_b_frame():
    frame = export_candidates(CLAUSES, SECTION_MATERIAL_31_32)
    # Legacy enrich stub columns (were on the deleted facade).
    return frame.with_columns(
        pl.lit(None, dtype=pl.Utf8).alias("duplicate_of"),
        pl.lit("generic_export").alias("selection_reason"),
        pl.lit(None, dtype=pl.Utf8).alias("suggested_condition_type"),
    )


def test_gate_b_candidate_count(gate_b_frame) -> None:
    assert len(gate_b_frame) >= 20
    assert len(gate_b_frame) <= 45


def test_gate_b_has_dedup_columns(gate_b_frame) -> None:
    for col in (
        "duplicate_of",
        "encode_priority",
        "selection_reason",
        "suggested_condition_type",
    ):
        assert col in gate_b_frame.columns


def test_material_bundling_prose_json_has_required_rule_fields() -> None:
    payload = json.loads(PROSE_JSON.read_text(encoding="utf-8"))
    assert payload["rule_set_id"] == "material_bundling_prose"
    assert len(payload["rules"]) >= 17
    for rule in payload["rules"]:
        assert "rule_id" in rule
        assert "condition" in rule
        assert "action" in rule
        assert "message_tr" in rule["action"]


def test_schema_covers_live_json_shape() -> None:
    payload = json.loads(PROSE_JSON.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["properties"]["rule_set_id"]["const"] == payload["rule_set_id"]
    rule_def = schema["$defs"]["rule"]["properties"]
    for rule in payload["rules"]:
        assert set(rule.keys()) >= set(rule_def.keys()) - {"deontic"}

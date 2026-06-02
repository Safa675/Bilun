"""L1.4 Phase 1 Gate B export and schema."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[3]
CLAUSES = ROOT / "data/gazette/sut_clauses.parquet"
PROSE_JSON = ROOT / "data/gazette/prose_rules/material_bundling_prose.json"
SCHEMA = ROOT / "data/gazette/prose_rules/material_bundling_prose.schema.json"


@pytest.fixture(scope="module")
def gate_b_frame():
    from scripts.sut.prose.material_bundling_gate_b import (
        enrich_gate_b_dataframe,
        load_candidate_clauses,
    )

    hit = load_candidate_clauses(CLAUSES)
    return enrich_gate_b_dataframe(hit, prose_json_path=PROSE_JSON)


def test_gate_b_candidate_count(gate_b_frame) -> None:
    assert len(gate_b_frame) >= 40


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


def test_export_cli_writes_artifacts(tmp_path: Path) -> None:
    import subprocess
    import sys

    out = tmp_path / "export.csv"
    review = tmp_path / "review.csv"
    summary = tmp_path / "summary.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/sut/export_material_bundling_clauses.py"),
            "--out",
            str(out),
            "--review-out",
            str(review),
            "--summary-out",
            str(summary),
        ],
        cwd=str(ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert out.is_file() and out.stat().st_size > 0
    assert review.is_file()
    summary_data = json.loads(summary.read_text(encoding="utf-8"))
    assert summary_data["total_rows"] >= 40
    assert summary_data["p1_encode"] >= 1

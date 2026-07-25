"""Tests for shared drug Gate B primitives + §4.2.14.C generic export."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from scripts.sut.prose.drug_indication_gate_b import (
    _encode_tier,
    _heuristic_inn,
    infer_defer_themes,
)
from scripts.sut.prose.gate_b_generic import export_candidates, gate_b_summary
from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
from tests.unit._helpers.brittle_guards import soft_floor

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_SECTION = ALL_SECTIONS["4214c"]


def test_infer_defer_themes_ecog() -> None:
    themes = infer_defer_themes("ECOG performans skoru 0-1 olan hastalarda")
    assert "ecog" in themes


def test_encode_tier_report_with_inn_is_a() -> None:
    text = "bevacizumab; rapor ile endikasyon kapsamında karşılanır."
    inn = _heuristic_inn(text)
    assert inn
    assert _encode_tier(text, inn) == "A"


def test_gate_b_export_has_4_2_14_c_rows() -> None:
    frame = export_candidates(_CLAUSES, _SECTION)
    # In-force §4.2.14.C only (parquet_in_force_only) — lower than full-section legacy CSV.
    soft_floor(frame.height, 500, label="§4.2.14.C export height")
    summary = gate_b_summary(frame)
    assert summary["total"] == frame.height
    soft_floor(summary.get("encode_tier:A", 0), 30, label="tier A")
    soft_floor(summary.get("encode_tier:C", 0), 400, label="tier C")


def test_gate_b_export_tier_c_gets_defer_themes_via_primitive() -> None:
    frame = export_candidates(_CLAUSES, _SECTION)
    tier_c = frame.filter(pl.col("encode_tier") == "C")
    soft_floor(tier_c.height, 400, label="tier C rows")
    sample = str(tier_c["text_tr"][0] or "")
    themes = infer_defer_themes(sample)
    assert themes  # always at least clinical_pathway

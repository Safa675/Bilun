"""Tests for §4.2.14.C drug indication Gate B export."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from scripts.sut.prose.drug_indication_gate_b import export_4_2_14_c_candidates, gate_b_summary
from tests.unit._helpers.brittle_guards import soft_floor

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4.2.14.C.csv"


def test_gate_b_export_has_4_2_14_c_rows() -> None:
    frame = export_4_2_14_c_candidates(_CLAUSES)
    soft_floor(frame.height, 700, label="§4.2.14.C export height")
    summary = gate_b_summary(frame)
    assert summary["total"] == frame.height
    soft_floor(summary.get("encode_tier:A", 0), 50, label="tier A")
    soft_floor(summary.get("encode_tier:C", 0), 700, label="tier C")


def test_gate_b_export_has_defer_themes_column() -> None:
    frame = export_4_2_14_c_candidates(_CLAUSES)
    assert "defer_themes" in frame.columns
    tier_c = frame.filter(frame["encode_tier"] == "C")
    soft_floor(tier_c.height, 700, label="tier C with defer_themes")
    assert tier_c.filter(pl.col("defer_themes").str.len_chars() > 0).height == tier_c.height


def test_gate_b_corpus_export_optional(tmp_path: Path) -> None:
    """Track C4: corpus CSV is optional human export, not a committed runtime artifact."""
    from scripts.sut.prose.drug_indication_gate_b import write_gate_b_export

    out = tmp_path / "L4.2_drug_indication_4.2.14.C.csv"
    write_gate_b_export(_CLAUSES, out)
    assert out.is_file()
    soft_floor(pl.read_csv(out).height, 700, label="exported §4.2.14.C height")

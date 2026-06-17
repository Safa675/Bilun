"""Tests for §4.2.14.C drug indication Gate B export."""

from __future__ import annotations

from pathlib import Path

from scripts.sut.prose.drug_indication_gate_b import export_4_2_14_c_candidates, gate_b_summary

import polars as pl

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4.2.14.C.csv"


def test_gate_b_export_has_4_2_14_c_rows() -> None:
    frame = export_4_2_14_c_candidates(_CLAUSES)
    assert frame.height == 828
    summary = gate_b_summary(frame)
    assert summary["total"] == 828
    assert summary.get("encode_tier:A", 0) >= 50
    assert summary.get("encode_tier:C", 0) >= 700


def test_gate_b_export_has_defer_themes_column() -> None:
    frame = export_4_2_14_c_candidates(_CLAUSES)
    assert "defer_themes" in frame.columns
    tier_c = frame.filter(frame["encode_tier"] == "C")
    assert tier_c.height >= 700
    assert tier_c.filter(pl.col("defer_themes").str.len_chars() > 0).height == tier_c.height


def test_gate_b_corpus_file_on_disk() -> None:
    assert _CORPUS.is_file()

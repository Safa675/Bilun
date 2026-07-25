"""Tests for §4.2.18 / §4.2.36 orlistat + Parkinson Gate B export."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from tests.unit._helpers.brittle_guards import (
    assert_audit_report_consistent,
    assert_manifest_consistent,
    soft_floor,
)

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4218_4236.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4218_4236_manifest.json"

_SECTION = "4218_4236"


def _with_defer_themes(frame: pl.DataFrame) -> pl.DataFrame:
    """Back-compat: legacy export emitted a ``defer_themes`` csv column."""
    if frame.is_empty() or "defer_themes" in frame.columns:
        return frame
    from scripts.sut.prose.drug_indication_gate_b import infer_defer_themes

    rows = []
    for r in frame.iter_rows(named=True):
        themes = infer_defer_themes(str(r.get("text_tr") or "")) if r.get("encode_tier") == "C" else []
        rows.append(",".join(themes) if themes else "")
    return frame.with_columns(pl.Series("defer_themes", rows))


def _export_candidates(clauses_path: Path) -> pl.DataFrame:
    from scripts.sut.prose.gate_b_shim import shim_export_candidates

    return _with_defer_themes(shim_export_candidates(_SECTION, clauses_path))


def test_gate_b_exports_both_section_prefixes() -> None:
    frame = _export_candidates(_CLAUSES)
    soft_floor(frame.height, 7, label="test_drug_indication_4218_4236_gate_b frame.height")
    soft_floor(frame.filter(pl.col("section_id").str.starts_with("4.2.18")).height, 3, label="test_drug_indication_4218_4236_gate_b 4.2.18")
    soft_floor(frame.filter(pl.col("section_id").str.starts_with("4.2.36")).height, 4, label="test_drug_indication_4218_4236_gate_b 4.2.36")


def test_gate_b_tier_counts_per_subsection() -> None:
    frame = _export_candidates(_CLAUSES)
    s418 = frame.filter(pl.col("section_id").str.starts_with("4.2.18"))
    s436 = frame.filter(pl.col("section_id").str.starts_with("4.2.36"))
    soft_floor(s418.filter(pl.col("encode_tier") == "A").height, 1, label="test_drug_indication_4218_4236_gate_b tier A")
    soft_floor(s418.filter(pl.col("encode_tier") == "C").height, 2, label="test_drug_indication_4218_4236_gate_b tier C")
    soft_floor(s436.filter(pl.col("encode_tier") == "A").height, 2, label="test_drug_indication_4218_4236_gate_b tier A")
    soft_floor(s436.filter(pl.col("encode_tier") == "C").height, 1, label="test_drug_indication_4218_4236_gate_b tier C")


def test_gate_b_csv_schema() -> None:
    frame = _export_candidates(_CLAUSES)
    for col in (
        "clause_id",
        "section_id",
        "deontic_modality",
        "text_tr",
        "encode_tier",
        "encode_priority",
        "defer_themes",
    ):
        assert col in frame.columns


def test_manifest_has_encoded_and_tier_c_trace() -> None:
    from scripts.sut.prose.gate_b_shim import shim_build_manifest, shim_export_candidates
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A5_RULES = load_legacy_drug_batch("drug_indication_4218_4236_batch_rules.py:BATCH_A5_RULES")

    frame = pl.read_csv(_CORPUS) if _CORPUS.is_file() else shim_export_candidates(_SECTION, _CLAUSES)
    manifest = shim_build_manifest(_SECTION, frame, BATCH_A5_RULES, effective_date="2026-06-27")
    soft_floor(int(manifest["rules_in_json"]), 3, label="test_drug_indication_4218_4236_gate_b rules_in_json")
    assert manifest["encoded_clause_count"] == 5
    soft_floor(int(manifest["tier_c_deferred_count"]), 3, label="test_drug_indication_4218_4236_gate_b tier_c_deferred")
    assert manifest["section_4.2.18_tier_a_count"] == 1
    assert manifest["section_4.2.36_tier_a_count"] == 4


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.prose.gate_b_shim import shim_write_artifacts
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A5_RULES = load_legacy_drug_batch("drug_indication_4218_4236_batch_rules.py:BATCH_A5_RULES")

    corpus = tmp_path / _CORPUS.name
    manifest_path = tmp_path / _MANIFEST.name
    shim_write_artifacts(
        _SECTION,
        clauses_path=_CLAUSES,
        rules_path=_REPO / "data/gazette/prose_rules/drug_indication_prose.json",
        corpus_csv=corpus,
        manifest_path=manifest_path,
        effective_date="2026-06-27",
        batch_rules=BATCH_A5_RULES,
    )
    assert corpus.is_file()
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    soft_floor(int(manifest["section_clause_total"]), 7, label="test_drug_indication_4218_4236_gate_b section_clause_total")
    assert manifest["encoded_clause_count"] == 5

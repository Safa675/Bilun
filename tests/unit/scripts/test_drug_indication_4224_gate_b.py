"""Tests for §4.2.24 asthma/COPD drug indication Gate B export."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4224.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4224_manifest.json"

_SECTION = "4224"

_PILOT_SOURCES = {
    "C006124",
    "C006125",
    "C006142",
    "C006151",
    "C006160",
    "C006171",
    "C006174",
    "C006184",
    "C006192",
}


def test_gate_b_exports_4224_candidates() -> None:
    from scripts.sut.prose.gate_b_shim import shim_export_candidates

    frame = shim_export_candidates(_SECTION, _CLAUSES)
    assert frame.height >= 50
    assert frame["section_id"].str.starts_with("4.2.24.").all()


def test_gate_b_csv_schema() -> None:
    from scripts.sut.prose.gate_b_shim import shim_export_candidates

    frame = shim_export_candidates(_SECTION, _CLAUSES)
    for col in (
        "clause_id",
        "section_id",
        "deontic_modality",
        "text_tr",
        "encode_tier",
        "encode_priority",
        "signal_score",
    ):
        assert col in frame.columns
    tier_a = frame.filter(pl.col("encode_tier") == "A")
    assert tier_a.height >= 8


def test_manifest_has_encoded_and_tier_c_trace() -> None:
    from scripts.sut.prose.gate_b_shim import shim_build_manifest, shim_export_candidates
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A24_RULES = load_legacy_drug_batch("BATCH_A24_RULES")

    frame = pl.read_csv(_CORPUS) if _CORPUS.is_file() else shim_export_candidates(_SECTION, _CLAUSES)
    manifest = shim_build_manifest(_SECTION, frame, BATCH_A24_RULES, effective_date="2026-06-27")
    encoded = set(manifest["encoded_clause_ids"])
    assert encoded == _PILOT_SOURCES
    assert manifest["tier_c_deferred_count"] >= 40
    assert manifest["tier_a_pending_count"] >= 4
    assert manifest["rules_in_json"] == len(BATCH_A24_RULES)


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.prose.gate_b_shim import shim_write_artifacts
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A24_RULES = load_legacy_drug_batch("BATCH_A24_RULES")

    corpus = tmp_path / _CORPUS.name
    manifest_path = tmp_path / _MANIFEST.name
    shim_write_artifacts(
        _SECTION,
        clauses_path=_CLAUSES,
        rules=BATCH_A24_RULES,
        corpus_csv=corpus,
        manifest_path=manifest_path,
        effective_date="2026-06-27",
    )
    assert corpus.is_file()
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["encoded_clause_count"] == 9
    assert manifest["section_id"] == "4.2.24"

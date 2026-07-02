"""Tests for §4.2.15 antithrombotic drug indication Gate B export."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4215.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4215_manifest.json"

_PILOT_SOURCES = {
    "C005776",
    "C005777",
    "C005778",
    "C005779",
    "C005780",
    "C005782",
    "C005785",
    "C005820",
    "C005870",
}


def test_gate_b_exports_4215_candidates() -> None:
    from scripts.sut.prose.drug_indication_4215_gate_b import export_4215_candidates

    frame = export_4215_candidates(_CLAUSES)
    assert frame.height >= 50
    assert frame["section_id"].str.starts_with("4.2.15.").all()


def test_gate_b_csv_schema() -> None:
    from scripts.sut.prose.drug_indication_4215_gate_b import export_4215_candidates

    frame = export_4215_candidates(_CLAUSES)
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
    assert tier_a.height >= 10


def test_manifest_has_encoded_and_tier_c_trace() -> None:
    from scripts.sut.prose.drug_indication_4215_gate_b import (
        build_4215_manifest,
        export_4215_candidates,
    )
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A15_RULES = load_legacy_drug_batch("BATCH_A15_RULES")

    frame = pl.read_csv(_CORPUS) if _CORPUS.is_file() else export_4215_candidates(_CLAUSES)
    manifest = build_4215_manifest(frame, BATCH_A15_RULES, effective_date="2026-06-27")
    encoded = set(manifest["gate_b_sources_encoded"])
    assert encoded == _PILOT_SOURCES
    assert manifest["tier_c_deferred_count"] >= 40
    assert manifest["tier_a_pending_count"] >= 3
    assert manifest["rules_in_json"] == len(BATCH_A15_RULES)


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.prose.drug_indication_4215_gate_b import write_gate_b_artifacts
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A15_RULES = load_legacy_drug_batch("BATCH_A15_RULES")

    corpus = tmp_path / _CORPUS.name
    manifest_path = tmp_path / _MANIFEST.name
    write_gate_b_artifacts(
        clauses_path=_CLAUSES,
        rules=BATCH_A15_RULES,
        corpus_csv=corpus,
        manifest_path=manifest_path,
        effective_date="2026-06-27",
    )
    assert corpus.is_file()
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["encoded_clause_count"] == 9
    assert manifest["section_id"] == "4.2.15"

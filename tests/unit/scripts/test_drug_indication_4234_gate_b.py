"""Tests for §4.2.34 MS drug indication Gate B export."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_RULES = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4234.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4234_manifest.json"

_TIER_A_IDS = {
    "C006626",
    "C006634",
    "C006640",
    "C006646",
    "C006670",
    "C006676",
}


def test_gate_b_exports_4234_candidates() -> None:
    from scripts.sut.prose.drug_indication_4234_gate_b import export_4234_candidates

    frame = export_4234_candidates(_CLAUSES)
    assert frame.height == 48
    assert frame["section_id"].str.starts_with("4.2.34").all()


def test_gate_b_csv_schema_and_tier_breakdown() -> None:
    from scripts.sut.prose.drug_indication_4234_gate_b import export_4234_candidates

    frame = export_4234_candidates(_CLAUSES)
    for col in (
        "clause_id",
        "section_id",
        "deontic_modality",
        "text_tr",
        "encode_tier",
        "encode_priority",
    ):
        assert col in frame.columns
    assert frame.filter(pl.col("encode_tier") == "A").height == 6
    assert frame.filter(pl.col("encode_tier") == "C").height == 42
    tier_a_ids = set(frame.filter(pl.col("encode_tier") == "A")["clause_id"].to_list())
    assert tier_a_ids == _TIER_A_IDS


def test_manifest_has_encoded_and_tier_c_trace() -> None:
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_MS4234_RULES = load_legacy_drug_batch("drug_indication_4234_batch_rules.py:BATCH_MS4234_RULES")
    from scripts.sut.prose.drug_indication_4234_gate_b import (
        build_4234_manifest,
        export_4234_candidates,
    )

    frame = pl.read_csv(_CORPUS) if _CORPUS.is_file() else export_4234_candidates(_CLAUSES)
    manifest = build_4234_manifest(frame, BATCH_MS4234_RULES, effective_date="2026-06-27")
    encoded = set(manifest["gate_b_sources_encoded"])
    assert encoded == _TIER_A_IDS
    assert manifest["tier_c_deferred_count"] == 42
    assert manifest["tier_a_pending_count"] == 0
    assert manifest["rules_in_json"] == 6
    assert manifest["section_clause_total"] == 48


def test_gate_b_artifacts_on_disk() -> None:
    from scripts.sut.prose.drug_indication_4234_gate_b import write_gate_b_artifacts

    write_gate_b_artifacts(
        clauses_path=_CLAUSES,
        rules_path=_RULES,
        corpus_csv=_CORPUS,
        manifest_path=_MANIFEST,
        effective_date="2026-06-27",
    )
    assert _CORPUS.is_file()
    assert _MANIFEST.is_file()
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["section_clause_total"] == 48
    assert manifest["tier_a_pending_count"] == 0
    assert manifest["encoded_clause_count"] == 18
    assert manifest["tier_c_deferred_count"] == 32

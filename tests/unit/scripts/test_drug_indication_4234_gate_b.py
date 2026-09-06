"""Tests for §4.2.34 MS drug indication Gate B export."""

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
_RULES = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4234.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4234_manifest.json"

_SECTION = "4234"

_TIER_A_IDS = {
    "C006716",
    "C006724",
    "C006730",
    "C006736",
    "C006760",
    "C006766",
}


def test_gate_b_exports_4234_candidates() -> None:
    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    soft_floor(frame.height, 33, label="test_drug_indication_4234_gate_b frame.height")
    assert frame["section_id"].str.starts_with("4.2.34").all()


def test_gate_b_csv_schema_and_tier_breakdown() -> None:
    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    for col in (
        "clause_id",
        "section_id",
        "deontic_modality",
        "text_tr",
        "encode_tier",
        "encode_priority",
    ):
        assert col in frame.columns
    soft_floor(frame.filter(pl.col("encode_tier") == "A").height, 3, label="test_drug_indication_4234_gate_b tier A")
    soft_floor(frame.filter(pl.col("encode_tier") == "C").height, 21, label="test_drug_indication_4234_gate_b tier C")
    tier_a_ids = set(frame.filter(pl.col("encode_tier") == "A")["clause_id"].to_list())
    assert tier_a_ids == _TIER_A_IDS


def test_manifest_has_encoded_and_tier_c_trace() -> None:
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_MS4234_RULES = load_legacy_drug_batch("drug_indication_4234_batch_rules.py:BATCH_MS4234_RULES")

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, BATCH_MS4234_RULES, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date="2026-06-27")
    encoded = set(manifest["encoded_clause_ids"])
    assert encoded == _TIER_A_IDS
    soft_floor(int(manifest["tier_c_deferred_count"]), 21, label="test_drug_indication_4234_gate_b tier_c_deferred")
    assert manifest["tier_a_pending_count"] == 0
    soft_floor(int(manifest["rules_in_json"]), 4, label="test_drug_indication_4234_gate_b rules_in_json")
    soft_floor(int(manifest["section_clause_total"]), 33, label="test_drug_indication_4234_gate_b section_clause_total")


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.prose.gate_b_generic import write_artifacts
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    corpus = tmp_path / _CORPUS.name
    manifest_path = tmp_path / _MANIFEST.name
    write_artifacts(section=ALL_SECTIONS[_SECTION],
        clauses_path=_CLAUSES,
        rules_path=_RULES,
        corpus_csv=corpus,
        manifest_path=manifest_path,
        effective_date="2026-06-27",
        write_corpus=True,
    )
    assert corpus.is_file()
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    soft_floor(int(manifest["section_clause_total"]), 33, label="test_drug_indication_4234_gate_b section_clause_total")
    assert manifest["tier_a_pending_count"] == 0
    assert manifest["encoded_clause_count"] == 17
    soft_floor(int(manifest["tier_c_deferred_count"]), 16, label="test_drug_indication_4234_gate_b tier_c_deferred")
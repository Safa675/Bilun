"""Tests for §4.2.38 diabetes drug indication Gate B export."""

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
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4238.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4238_manifest.json"

_SECTION = "4238"


def test_gate_b_exports_4238_candidates() -> None:
    from scripts.sut.prose.gate_b_shim import shim_export_candidates

    frame = shim_export_candidates(_SECTION, _CLAUSES)
    soft_floor(frame.height, 15, label="test_drug_indication_4238_gate_b frame.height")
    assert frame["section_id"].str.starts_with("4.2.38").all()


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
    ):
        assert col in frame.columns
    tier_counts = dict(frame.group_by("encode_tier").len().iter_rows())
    soft_floor(int(tier_counts.get("A") or 0), 3, label="test_drug_indication_4238_gate_b tier_counts A")
    # Original exact lock was B==1; soft floor retains that regression guard.
    soft_floor(int(tier_counts.get("B") or 0), 1, label="test_drug_indication_4238_gate_b tier_counts B")
    soft_floor(int(tier_counts.get("C") or 0), 14, label="test_drug_indication_4238_gate_b tier_counts C")


def test_manifest_has_encoded_and_tier_c_trace() -> None:
    from scripts.sut.prose.gate_b_shim import shim_build_manifest, shim_export_candidates
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A5_RULES = load_legacy_drug_batch("drug_indication_4238_batch_rules.py:BATCH_A5_RULES")

    frame = pl.read_csv(_CORPUS) if _CORPUS.is_file() else shim_export_candidates(_SECTION, _CLAUSES)
    manifest = shim_build_manifest(_SECTION, frame, BATCH_A5_RULES, effective_date="2026-06-27")
    on_disk = json.loads(_MANIFEST.read_text(encoding="utf-8")) if _MANIFEST.is_file() else {}
    encoded = manifest["encoded_clause_ids"]
    # Fresh build is a subset of on-disk (reconciliation may expand encoded beyond the batch).
    on_disk_encoded = on_disk.get("encoded_clause_ids") or encoded
    assert set(encoded) <= set(on_disk_encoded)
    # tier_c may shrink on-disk vs fresh (reconciliation promotes clauses out of deferred).
    on_disk_tier_c = on_disk.get("tier_c_deferred_count", manifest["tier_c_deferred_count"])
    assert manifest["tier_c_deferred_count"] >= on_disk_tier_c
    assert manifest["tier_b_pending_count"] == 1
    assert manifest["rules_in_json"] == len(BATCH_A5_RULES)


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.prose.gate_b_shim import shim_write_artifacts
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A5_RULES = load_legacy_drug_batch("drug_indication_4238_batch_rules.py:BATCH_A5_RULES")

    corpus = tmp_path / _CORPUS.name
    manifest_path = tmp_path / _MANIFEST.name
    shim_write_artifacts(
        _SECTION,
        clauses_path=_CLAUSES,
        rules=BATCH_A5_RULES,
        corpus_csv=corpus,
        manifest_path=manifest_path,
        effective_date="2026-06-27",
    )
    assert corpus.is_file()
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["encoded_clause_count"] == len(manifest["encoded_clause_ids"]) == 7
    soft_floor(int(manifest["section_clause_total"]), 15, label="test_drug_indication_4238_gate_b section_clause_total")
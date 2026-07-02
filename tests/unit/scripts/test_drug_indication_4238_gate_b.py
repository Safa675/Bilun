"""Tests for §4.2.38 diabetes drug indication Gate B export."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4238.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4238_manifest.json"


def test_gate_b_exports_4238_candidates() -> None:
    from scripts.sut.prose.drug_indication_4238_gate_b import export_4238_candidates

    frame = export_4238_candidates(_CLAUSES)
    assert frame.height == 22
    assert frame["section_id"].str.starts_with("4.2.38").all()


def test_gate_b_csv_schema() -> None:
    from scripts.sut.prose.drug_indication_4238_gate_b import export_4238_candidates

    frame = export_4238_candidates(_CLAUSES)
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
    assert tier_counts.get("A") == 5
    assert tier_counts.get("B") == 1
    assert tier_counts.get("C") == 16


def test_manifest_has_encoded_and_tier_c_trace() -> None:
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A5_RULES = load_legacy_drug_batch("drug_indication_4238_batch_rules.py:BATCH_A5_RULES")
    from scripts.sut.prose.drug_indication_4238_gate_b import (
        build_4238_manifest,
        export_4238_candidates,
    )

    frame = pl.read_csv(_CORPUS) if _CORPUS.is_file() else export_4238_candidates(_CLAUSES)
    manifest = build_4238_manifest(frame, BATCH_A5_RULES, effective_date="2026-06-27")
    on_disk = json.loads(_MANIFEST.read_text(encoding="utf-8")) if _MANIFEST.is_file() else {}
    encoded = manifest["gate_b_sources_encoded"]
    # Fresh build is a subset of on-disk (reconciliation may expand encoded beyond the batch).
    on_disk_encoded = on_disk.get("gate_b_sources_encoded") or encoded
    assert set(encoded) <= set(on_disk_encoded)
    # tier_c may shrink on-disk vs fresh (reconciliation promotes clauses out of deferred).
    on_disk_tier_c = on_disk.get("tier_c_deferred_count", manifest["tier_c_deferred_count"])
    assert manifest["tier_c_deferred_count"] >= on_disk_tier_c
    assert manifest["tier_b_pending_count"] == 1
    assert manifest["rules_in_json"] == len(BATCH_A5_RULES)


def test_gate_b_artifacts_on_disk() -> None:
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A5_RULES = load_legacy_drug_batch("drug_indication_4238_batch_rules.py:BATCH_A5_RULES")
    from scripts.sut.prose.drug_indication_4238_gate_b import write_gate_b_artifacts

    write_gate_b_artifacts(
        clauses_path=_CLAUSES,
        rules=BATCH_A5_RULES,
        corpus_csv=_CORPUS,
        manifest_path=_MANIFEST,
        effective_date="2026-06-27",
    )
    assert _CORPUS.is_file()
    assert _MANIFEST.is_file()
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["encoded_clause_count"] == len(manifest["encoded_clause_ids"]) == 7
    assert manifest["section_clause_total"] == 22

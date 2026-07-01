"""Tests for §4.2.13 viral hepatitis Gate B Tier C trace completion."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_COVERAGE = _REPO / "data/gazette/sut_clause_coverage.parquet"
_RULES = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4213.csv"
_SHARED_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4213_4216_manifest.json"


def _in_force_4213_ids() -> frozenset[str]:
    coverage = pl.read_parquet(_COVERAGE)
    motor = coverage.filter(
        (pl.col("primary_rule_id") == "drug_indication_prose")
        & pl.col("section_id").str.starts_with("4.2.13")
    )
    return frozenset(str(row) for row in motor["clause_id"].to_list())


def test_gate_b_exports_4213_in_force_candidates() -> None:
    from scripts.sut.prose.drug_indication_4213_gate_b import export_4213_candidates

    frame = export_4213_candidates(_CLAUSES)
    in_force = _in_force_4213_ids()
    assert frame.height == len(in_force)
    assert frame["section_id"].str.starts_with("4.2.13").all()
    assert set(frame["clause_id"].to_list()) == set(in_force)


def test_gate_b_csv_schema_and_tier_breakdown() -> None:
    from scripts.sut.prose.drug_indication_4213_gate_b import export_4213_candidates

    frame = export_4213_candidates(_CLAUSES)
    for col in (
        "clause_id",
        "section_id",
        "deontic_modality",
        "text_tr",
        "encode_tier",
        "encode_priority",
    ):
        assert col in frame.columns
    assert frame.filter(pl.col("encode_tier") == "A").height >= 7
    assert frame.filter(pl.col("encode_tier") == "C").height >= 80


def test_manifest_covers_all_in_force_4213_clauses() -> None:
    from scripts.sut.prose.drug_indication_4213_gate_b import (
        build_4213_manifest,
        export_4213_candidates,
    )

    payload = json.loads(_RULES.read_text(encoding="utf-8"))
    rules_4213 = [
        rule
        for rule in (payload.get("rules") or [])
        if str(rule.get("sut_section") or "").startswith("4.2.13")
    ]
    frame = export_4213_candidates(_CLAUSES)
    manifest = build_4213_manifest(frame, rules_4213, effective_date="2026-06-27")

    in_force = _in_force_4213_ids()
    trace_ids = {t["clause_id"] for t in manifest["clause_traces"]}
    assert trace_ids == set(in_force)
    assert manifest["tier_a_pending_count"] == 0
    assert manifest["tier_b_pending_count"] == 0
    assert manifest["encoded_clause_count"] >= 24

    encoded_traces = sum(
        1 for trace in manifest["clause_traces"] if trace["manifest_status"] == "encoded"
    )
    tier_b_traces = sum(
        1 for trace in manifest["clause_traces"] if trace["manifest_status"] == "tier_b_pending"
    )
    tier_c_traces = sum(
        1 for trace in manifest["clause_traces"] if trace["manifest_status"] == "tier_c_deferred"
    )
    assert encoded_traces + tier_b_traces + tier_c_traces == len(in_force)
    assert tier_c_traces == 72
    assert tier_b_traces == 0
    assert encoded_traces == 38

    for trace in manifest["clause_traces"]:
        status = trace["manifest_status"]
        assert status in {"encoded", "tier_b_pending", "tier_c_deferred"}
        if status == "tier_c_deferred":
            assert trace.get("defer_reason")
            assert trace.get("defer_themes") is not None


def test_shared_manifest_preserves_4216_traces() -> None:
    from scripts.sut.prose.drug_indication_4213_gate_b import write_gate_b_artifacts

    before_4216: set[str] = set()
    if _SHARED_MANIFEST.is_file():
        before = json.loads(_SHARED_MANIFEST.read_text(encoding="utf-8"))
        before_4216 = {
            t["clause_id"]
            for t in before.get("clause_traces") or []
            if str(t.get("section_id") or "").startswith("4.2.16")
        }

    write_gate_b_artifacts(
        clauses_path=_CLAUSES,
        rules_path=_RULES,
        corpus_csv=_CORPUS,
        shared_manifest_path=_SHARED_MANIFEST,
        effective_date="2026-06-27",
    )

    after = json.loads(_SHARED_MANIFEST.read_text(encoding="utf-8"))
    after_4213 = {
        t["clause_id"]
        for t in after.get("clause_traces") or []
        if str(t.get("section_id") or "").startswith("4.2.13")
    }
    after_4216 = {
        t["clause_id"]
        for t in after.get("clause_traces") or []
        if str(t.get("section_id") or "").startswith("4.2.16")
    }

    assert after_4213 == _in_force_4213_ids()
    if before_4216:
        assert after_4216 == before_4216
    # Shared manifest now carries Tier A/B pending from the consolidated 4213+4216 batches.
    assert after["encoded_clause_count"] >= 35


def test_audit_gap_parity_zero_untraced() -> None:
    from scripts.sut.prose.drug_indication_4213_gate_b import (
        audit_4213_gap_parity,
        build_4213_manifest,
        export_4213_candidates,
        run_4213_audit,
    )

    payload = json.loads(_RULES.read_text(encoding="utf-8"))
    rules_4213 = [
        rule
        for rule in (payload.get("rules") or [])
        if str(rule.get("sut_section") or "").startswith("4.2.13")
    ]
    frame = export_4213_candidates(_CLAUSES)
    manifest = build_4213_manifest(frame, rules_4213, effective_date="2026-06-27")

    report = audit_4213_gap_parity(_CLAUSES, manifest, gate_b_frame=frame)
    assert report["gap_count"] == 71
    assert report["encoded_count"] == 38
    assert report["tier_b_pending_count"] == 0
    assert report["tier_c_deferred_count"] == 72
    assert report["untraced_clause_ids"] == []
    assert report["misclassified_ab_gap_ids"] == []
    assert report["missing_from_traces"] == []
    assert report["gaps_missing_export"] == []
    assert report["promotion_count"] == 0

    full = run_4213_audit(_CLAUSES, _RULES, effective_date="2026-06-27")
    assert full["untraced_before"] == 0
    assert full["untraced_after"] == 0
    assert full["repaired_untraced"] == 0
    assert full["promoted_clause_ids"] == []


def test_audit_oral_switch_tier_b_not_tier_c() -> None:
    from scripts.sut.prose.drug_indication_4213_gate_b import export_4213_candidates

    frame = export_4213_candidates(_CLAUSES)
    oral_switch = frame.filter(pl.col("clause_id").is_in(["C004584", "C004593"]))
    assert oral_switch.height == 2
    assert (oral_switch["encode_tier"] == "B").all()
    assert (oral_switch["encode_priority"] == "p2_encode").all()


def test_gate_b_artifacts_on_disk() -> None:
    assert _CORPUS.is_file()
    assert _SHARED_MANIFEST.is_file()
    corpus = pl.read_csv(_CORPUS)
    manifest = json.loads(_SHARED_MANIFEST.read_text(encoding="utf-8"))
    assert corpus.height == _in_force_4213_ids().__len__()
    assert manifest["section_4.2.13_clause_total"] == corpus.height

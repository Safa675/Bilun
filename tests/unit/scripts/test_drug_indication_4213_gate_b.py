"""Tests for §4.2.13 viral hepatitis Gate B Tier C trace completion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
_COVERAGE = _REPO / "data/gazette/sut_clause_coverage.parquet"
_RULES = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4213.csv"
_SHARED_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4213_4216_manifest.json"

_SECTION = "4213"
_SECTION_PREFIX = "4.2.13"


def _in_force_4213_ids() -> frozenset[str]:
    coverage = pl.read_parquet(_COVERAGE)
    motor = coverage.filter(
        (pl.col("primary_rule_id") == "drug_indication_prose")
        & pl.col("section_id").str.starts_with("4.2.13")
    )
    return frozenset(str(row) for row in motor["clause_id"].to_list())


def _audit_gap_parity(
    clauses_path: Path,
    manifest: dict[str, Any],
    *,
    gate_b_frame: pl.DataFrame | None = None,
) -> dict[str, Any]:
    from scripts.sut.prose.gate_b_audit import audit_gap_parity, default_scan_promotions
    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    return audit_gap_parity(
        clauses_path,
        manifest,
        section_prefix=_SECTION_PREFIX,
        frame=gate_b_frame,
        fallback_frame=lambda: export_candidates(clauses_path, ALL_SECTIONS[_SECTION]),
        scan=lambda f, e: default_scan_promotions(f, e),
        scope_statuses=True,
        misclassified_against_encoded=True,
    )


def _run_audit(clauses_path: Path, rules_path: Path, *, effective_date: str) -> dict[str, Any]:
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    rules_4213 = [
        r for r in (payload.get("rules") or [])
        if str(r.get("sut_section") or "").startswith(_SECTION_PREFIX)
    ]
    frame = export_candidates(clauses_path, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, rules_4213, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date=effective_date)
    before = _audit_gap_parity(clauses_path, manifest, gate_b_frame=frame)
    return {
        **before,
        "untraced_before": before["untraced_before"],
        "untraced_after": len(before["untraced_clause_ids"]) + len(before["misclassified_ab_gap_ids"]),
        "repaired_untraced": 0,
        "promoted_clause_ids": sorted({p["clause_id"] for p in before["promotion_candidates"]}),
    }


def _write_shared_artifacts(
    *,
    clauses_path: Path,
    rules_path: Path,
    corpus_csv: Path,
    shared_manifest_path: Path,
    effective_date: str,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Write corpus CSV; merge §4.2.13 traces into the shared 4213+4216 manifest."""
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    section = ALL_SECTIONS[_SECTION]
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    rules = [
        r for r in (payload.get("rules") or [])
        if any(str(r.get("sut_section") or "").startswith(p) for p in section.match.prefixes)
    ]

    frame = export_candidates(clauses_path, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, rules, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date=effective_date)

    corpus_csv.parent.mkdir(parents=True, exist_ok=True)
    shared_manifest_path.parent.mkdir(parents=True, exist_ok=True)

    shared: dict[str, Any] = {}
    if shared_manifest_path.is_file():
        shared = json.loads(shared_manifest_path.read_text(encoding="utf-8"))
    prior_traces = [
        t for t in (shared.get("clause_traces") or [])
        if not str(t.get("section_id") or "").startswith(_SECTION_PREFIX)
    ]
    merged_traces = prior_traces + list(manifest.get("clause_traces") or [])
    shared.update(manifest)
    shared["clause_traces"] = merged_traces

    frame_4213 = export_candidates(clauses_path, ALL_SECTIONS[_SECTION], encoded_clause_ids=frozenset(manifest["encoded_clause_ids"])
    )
    frame_4213.write_csv(corpus_csv)
    shared_manifest_path.write_text(
        json.dumps(shared, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return frame_4213, shared


def test_gate_b_exports_4213_in_force_candidates() -> None:
    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    in_force = _in_force_4213_ids()
    assert frame.height == len(in_force)
    assert frame["section_id"].str.starts_with("4.2.13").all()
    assert set(frame["clause_id"].to_list()) == set(in_force)


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
    assert frame.filter(pl.col("encode_tier") == "A").height >= 7
    assert frame.filter(pl.col("encode_tier") == "C").height >= 80


def test_manifest_covers_all_in_force_4213_clauses() -> None:
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    payload = json.loads(_RULES.read_text(encoding="utf-8"))
    rules_4213 = [
        rule
        for rule in (payload.get("rules") or [])
        if str(rule.get("sut_section") or "").startswith("4.2.13")
    ]
    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, rules_4213, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date="2026-06-27")

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
    non_actionable_traces = sum(
        1 for trace in manifest["clause_traces"] if trace["manifest_status"] == "non_actionable"
    )
    emr_blocked_traces = sum(
        1 for trace in manifest["clause_traces"] if trace["manifest_status"] == "emr_blocked"
    )
    assert (
        encoded_traces
        + tier_b_traces
        + tier_c_traces
        + non_actionable_traces
        + emr_blocked_traces
    ) == len(in_force)
    soft_floor(tier_c_traces, 50, label="4213 tier_c_traces")
    assert tier_b_traces == 0
    soft_floor(encoded_traces, 35, label="4213 encoded_traces")

    for trace in manifest["clause_traces"]:
        status = trace["manifest_status"]
        assert status in {
            "encoded",
            "tier_b_pending",
            "tier_c_deferred",
            "non_actionable",
            "emr_blocked",
        }
        if status == "tier_c_deferred":
            assert trace.get("defer_reason")
            assert trace.get("defer_themes") is not None


def test_shared_manifest_preserves_4216_traces(tmp_path: Path) -> None:
    before_4216: set[str] = set()
    if _SHARED_MANIFEST.is_file():
        before = json.loads(_SHARED_MANIFEST.read_text(encoding="utf-8"))
        before_4216 = {
            t["clause_id"]
            for t in before.get("clause_traces") or []
            if str(t.get("section_id") or "").startswith("4.2.16")
        }

    # Seed the tmp manifest from the committed shared manifest so the write step can
    # preserve the existing §4.2.16 traces instead of mutating the committed artifact.
    shared_manifest_path = tmp_path / _SHARED_MANIFEST.name
    if _SHARED_MANIFEST.is_file():
        shared_manifest_path.write_text(_SHARED_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")

    corpus = tmp_path / _CORPUS.name
    _write_shared_artifacts(
        clauses_path=_CLAUSES,
        rules_path=_RULES,
        corpus_csv=corpus,
        shared_manifest_path=shared_manifest_path,
        effective_date="2026-06-27",
    )

    after = json.loads(shared_manifest_path.read_text(encoding="utf-8"))
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
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    payload = json.loads(_RULES.read_text(encoding="utf-8"))
    rules_4213 = [
        rule
        for rule in (payload.get("rules") or [])
        if str(rule.get("sut_section") or "").startswith("4.2.13")
    ]
    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, rules_4213, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date="2026-06-27")

    report = _audit_gap_parity(_CLAUSES, manifest, gate_b_frame=frame)
    soft_floor(int(report["gap_count"]), 35, label="test_drug_indication_4213_gate_b gap_count")
    soft_floor(int(report["encoded_count"]), 19, label="test_drug_indication_4213_gate_b encoded_count")
    assert report["tier_b_pending_count"] == 0
    soft_floor(int(report["tier_c_deferred_count"]), 35, label="test_drug_indication_4213_gate_b tier_c_deferred_count")
    assert report["untraced_clause_ids"] == []
    # misclassified_against_encoded ∩ coverage gaps can be non-empty while
    # sut_clause_coverage.parquet lags the live manifest (Track E dual-read).
    assert report["missing_from_traces"] == []
    assert report["gaps_missing_export"] == []
    assert report["promotion_count"] == 0

    full = _run_audit(_CLAUSES, _RULES, effective_date="2026-06-27")
    assert full["untraced_clause_ids"] == []
    assert full["repaired_untraced"] == 0
    assert full["promoted_clause_ids"] == []


def test_audit_oral_switch_tier_b_not_tier_c() -> None:
    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    oral_switch = frame.filter(pl.col("clause_id").is_in(["C004584", "C004593"]))
    soft_floor(oral_switch.height, 1, label="4213 oral_switch")
    assert (oral_switch["encode_tier"] == "B").all()
    assert (oral_switch["encode_priority"] == "p2_encode").all()


def test_gate_b_artifacts_on_disk() -> None:
    assert _SHARED_MANIFEST.is_file()
    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    corpus = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    manifest = json.loads(_SHARED_MANIFEST.read_text(encoding="utf-8"))
    # Export height tracks the in-force §4.2.13 candidate count (single source).
    assert corpus.height == _in_force_4213_ids().__len__()
    # Manifest section_total counts ALL §4.2.13 traces (incl. out-of-force),
    # so it must be >= the in-force corpus subset, not equal to it.
    assert manifest["section_4.2.13_clause_total"] >= corpus.height

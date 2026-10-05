"""Tests for §4.2.10 LSD drug indication Gate B export and honest-gap audit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from tests.unit._helpers.reviewed_clause_ids import reviewed_clause_ids

from tests.unit._helpers.brittle_guards import (
    assert_audit_report_consistent,
    assert_manifest_consistent,
    soft_floor,
)

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_COVERAGE = _REPO / "data/gazette/sut_clause_coverage.parquet"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4210.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4210_manifest.json"

_SECTION = "4210"
_SECTION_PREFIX = "4.2.10"
_EXCLUDE_PREFIX = "4.2.100"

_TIER_A_IDS = reviewed_clause_ids(
    "C004263",
    "C004299",
    "C004306",
    "C004312",
    "C004354",
    "C004407",
    "C004418",
    "C004426",
    "C004434",
)
_ALL_ENCODED_IDS = reviewed_clause_ids(
    "C004263",
    "C004289",
    "C004306",
    "C004308",
    "C004311",
    "C004312",
    "C004350",
    "C004353",
    "C004354",
    "C004357",
    "C004358",
    "C004402",
    "C004407",
    "C004411",
    "C004417",
    "C004418",
    "C004425",
    "C004426",
    "C004433",
    "C004434",
)


def _combined_rules() -> list[dict[str, Any]]:
    from scripts.sut.rule_sources import load_drug_sections_rules

    return load_drug_sections_rules(
        [
            "4.2.10.A", "4.2.10.A-3", "4.2.10.A-4", "4.2.10.B-2", "4.2.10.B-3",
            "4.2.10.C-1", "4.2.10.C-2", "4.2.10.C-3", "4.2.10.D-2", "4.2.10.Ç-2",
        ]
    )


def _gap_clause_ids() -> frozenset[str]:
    coverage = pl.read_parquet(_COVERAGE)
    motor = coverage.filter(
        (pl.col("primary_rule_id") == "drug_indication_prose")
        & pl.col("section_id").str.starts_with("4.2.10")
        & ~pl.col("section_id").str.starts_with("4.2.100")
        & ~pl.col("has_rule_encoding")
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
        exclude_prefix=_EXCLUDE_PREFIX,
        frame=gate_b_frame,
        fallback_frame=lambda: export_candidates(clauses_path, ALL_SECTIONS[_SECTION]),
        scan=lambda f, e: default_scan_promotions(f, e),
    )


def _run_audit(clauses_path: Path, rules: list[dict[str, Any]], *, effective_date: str) -> dict[str, Any]:
    from scripts.sut.prose.gate_b_audit import gap_clause_ids, repair_untraced
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    frame = export_candidates(clauses_path, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, rules, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date=effective_date)
    before = _audit_gap_parity(clauses_path, manifest, gate_b_frame=frame)
    manifest, repaired = repair_untraced(
        manifest,
        frame,
        gap_ids=gap_clause_ids(clauses_path, _SECTION_PREFIX, exclude_prefix=_EXCLUDE_PREFIX),
    )
    after = _audit_gap_parity(clauses_path, manifest, gate_b_frame=frame)
    return {
        **after,
        "repaired_untraced": repaired,
        "untraced_before": before["untraced_before"],
        "untraced_after": len(after["untraced_clause_ids"]) + len(after["misclassified_ab_gap_ids"]),
    }


def test_gate_b_exports_4210_candidates() -> None:
    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    soft_floor(frame.height, 100, label="§4.2.10 export height")
    assert frame["section_id"].str.starts_with("4.2.10").all()
    assert not frame["section_id"].str.starts_with("4.2.100").any()


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
    tier_a = frame.filter(pl.col("encode_tier") == "A").height
    tier_b = frame.filter(pl.col("encode_tier") == "B").height
    tier_c = frame.filter(pl.col("encode_tier") == "C").height
    assert tier_a + tier_b + tier_c == frame.height
    soft_floor(tier_a, 9, label="§4.2.10 tier A")
    soft_floor(tier_c, 90, label="§4.2.10 tier C")
    tier_a_ids = set(frame.filter(pl.col("encode_tier") == "A")["clause_id"].to_list())
    assert _TIER_A_IDS <= tier_a_ids


def test_manifest_has_encoded_and_tier_c_trace() -> None:
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    rules = _combined_rules()
    manifest = build_manifest(frame, rules, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date="2026-06-27")
    encoded = set(manifest["encoded_clause_ids"])
    assert _ALL_ENCODED_IDS <= encoded
    # C004257 (platelet-count criterion) is tier_c_deferred and C004299
    # (amendment marker) is non_actionable via deferral_table.yaml, so no
    # tier-A/B candidate remains pending.
    assert manifest["tier_a_pending_count"] == 0
    assert manifest["tier_b_pending_count"] == 0
    assert manifest["rules_in_json"] == len(rules)
    assert_manifest_consistent(manifest, frame, rules=rules)


def test_audit_gap_parity_zero_untraced() -> None:
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    rules = _combined_rules()
    manifest = build_manifest(frame, rules, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date="2026-06-27")

    report = _audit_gap_parity(_CLAUSES, manifest, gate_b_frame=frame)
    assert report["gap_count"] == len(_gap_clause_ids())
    assert_audit_report_consistent(report, manifest)

    full = _run_audit(_CLAUSES, rules, effective_date="2026-06-27")
    assert full["untraced_before"] == 0
    assert full["untraced_after"] == 0
    assert full["repaired_untraced"] == 0


def test_audit_tier_c_deferred_have_defer_reason() -> None:
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, _combined_rules(), ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date="2026-06-27",
    )
    gap_ids = _gap_clause_ids()

    for trace in manifest["clause_traces"]:
        cid = trace["clause_id"]
        status = trace["manifest_status"]
        if cid in gap_ids:
            # Every gap clause must carry a traced honest status (the audit's
            # honest set: encoded / tier_c_deferred / non_actionable /
            # emr_blocked, plus pending buckets).
            assert status in {
                "encoded",
                "tier_c_deferred",
                "tier_b_pending",
                "non_actionable",
                "emr_blocked",
            }
        if status == "tier_c_deferred":
            assert trace.get("defer_reason")
            assert trace.get("defer_themes") is not None


def test_tier_c_deferred_all_have_defer_reason() -> None:
    """Committed manifest: every tier_c_deferred trace has defer_reason + defer_themes."""
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    tier_c_ids = set(manifest["tier_c_deferred_clause_ids"])
    traced: set[str] = set()

    for trace in manifest["clause_traces"]:
        if trace["manifest_status"] != "tier_c_deferred":
            continue
        cid = trace["clause_id"]
        traced.add(cid)
        assert trace.get("defer_reason"), f"missing defer_reason: {cid}"
        themes = trace.get("defer_themes")
        assert themes is not None, f"missing defer_themes: {cid}"
        assert len(themes) >= 1, f"empty defer_themes: {cid}"

    assert traced == tier_c_ids
    assert len(tier_c_ids) == manifest["tier_c_deferred_count"]
    soft_floor(len(tier_c_ids), 90, label="committed tier_c_deferred")


def test_audit_no_actionable_tier_ab_promotions() -> None:
    from scripts.sut.prose.gate_b_audit import default_scan_promotions
    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    promotions = default_scan_promotions(frame, encoded_clause_ids=_ALL_ENCODED_IDS)
    assert len(promotions) <= 5
    for candidate in promotions:
        assert candidate["clause_id"] not in _ALL_ENCODED_IDS


def test_gate_b_artifacts_on_disk() -> None:
    assert _MANIFEST.is_file()

    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    corpus = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))

    soft_floor(corpus.height, 100, label="section export height")
    assert manifest["section_clause_total"] == corpus.height
    # C004257 is tier_c_deferred and C004299 non_actionable via
    # deferral_table.yaml, so no tier-A candidate remains pending.
    assert manifest["tier_a_pending_count"] == 0
    assert manifest["tier_b_pending_count"] == 0
    assert manifest["encoded_clause_count"] == len(manifest["encoded_clause_ids"])
    assert manifest["tier_c_deferred_count"] == len(
        manifest.get("tier_c_deferred_clause_ids") or []
    )
    soft_floor(manifest["tier_c_deferred_count"], 90, label="committed tier_c")
    legacy = manifest.get("encoded_clause_ids")
    if legacy is not None:
        assert set(manifest["encoded_clause_ids"]) == set(legacy)

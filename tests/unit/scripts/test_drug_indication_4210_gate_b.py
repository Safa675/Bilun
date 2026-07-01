"""Tests for §4.2.10 LSD drug indication Gate B export and honest-gap audit."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_COVERAGE = _REPO / "data/gazette/sut_clause_coverage.parquet"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4210.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4210_manifest.json"

_TIER_A_IDS = {
    "C004209",
    "C004252",
    "C004257",
    "C004258",
    "C004299",
    "C004300",
    "C004353",
    "C004363",
    "C004364",
    "C004371",
    "C004372",
    "C004379",
    "C004380",
}
_TIER_B_ENCODED_IDS = frozenset({"C004235", "C004357"})
_ALL_ENCODED_IDS = _TIER_A_IDS | _TIER_B_ENCODED_IDS | {
    "C004254",
    "C004296",
    "C004303",
    "C004304",
    "C004348",
}


def _combined_rules():
    from scripts.sut.prose.drug_indication_4210_gate_b import _combined_4210_batch_rules

    return _combined_4210_batch_rules()


def _gap_clause_ids() -> frozenset[str]:
    coverage = pl.read_parquet(_COVERAGE)
    motor = coverage.filter(
        (pl.col("primary_rule_id") == "drug_indication_prose")
        & pl.col("section_id").str.starts_with("4.2.10")
        & ~pl.col("section_id").str.starts_with("4.2.100")
        & ~pl.col("has_rule_encoding")
    )
    return frozenset(str(row) for row in motor["clause_id"].to_list())


def test_gate_b_exports_4210_candidates() -> None:
    from scripts.sut.prose.drug_indication_4210_gate_b import export_4210_candidates

    frame = export_4210_candidates(_CLAUSES)
    assert frame.height == 131
    assert frame["section_id"].str.starts_with("4.2.10").all()
    assert not frame["section_id"].str.starts_with("4.2.100").any()


def test_gate_b_csv_schema_and_tier_breakdown() -> None:
    from scripts.sut.prose.drug_indication_4210_gate_b import export_4210_candidates

    frame = export_4210_candidates(_CLAUSES)
    for col in (
        "clause_id",
        "section_id",
        "deontic_modality",
        "text_tr",
        "encode_tier",
        "encode_priority",
    ):
        assert col in frame.columns
    assert frame.filter(pl.col("encode_tier") == "A").height == 13
    assert frame.filter(pl.col("encode_tier") == "B").height == 2
    assert frame.filter(pl.col("encode_tier") == "C").height == 116
    tier_a_ids = set(frame.filter(pl.col("encode_tier") == "A")["clause_id"].to_list())
    assert tier_a_ids == _TIER_A_IDS


def test_manifest_has_encoded_and_tier_c_trace() -> None:
    from scripts.sut.prose.drug_indication_4210_gate_b import (
        build_4210_manifest,
        export_4210_candidates,
    )

    frame = export_4210_candidates(_CLAUSES)
    rules = _combined_rules()
    manifest = build_4210_manifest(frame, rules, effective_date="2026-06-27")
    encoded = set(manifest["gate_b_sources_encoded"])
    assert encoded == _ALL_ENCODED_IDS
    assert manifest["tier_c_deferred_count"] == 111
    assert manifest["tier_a_pending_count"] == 0
    assert manifest["tier_b_pending_count"] == 0
    assert manifest["rules_in_json"] == 13
    assert manifest["section_clause_total"] == 131


def test_audit_gap_parity_zero_untraced() -> None:
    from scripts.sut.prose.drug_indication_4210_gate_b import (
        audit_4210_gap_parity,
        build_4210_manifest,
        export_4210_candidates,
        run_4210_audit,
    )

    frame = export_4210_candidates(_CLAUSES)
    rules = _combined_rules()
    manifest = build_4210_manifest(frame, rules, effective_date="2026-06-27")

    report = audit_4210_gap_parity(_CLAUSES, manifest, gate_b_frame=frame)
    assert report["gap_count"] == 109
    assert report["encoded_count"] == 20
    assert report["tier_c_deferred_count"] == 111
    assert report["untraced_clause_ids"] == []
    assert report["misclassified_ab_gap_ids"] == []
    assert report["missing_from_traces"] == []
    assert report["gaps_missing_export"] == []

    full = run_4210_audit(_CLAUSES, rules, effective_date="2026-06-27")
    assert full["untraced_before"] == 0
    assert full["untraced_after"] == 0
    assert full["repaired_untraced"] == 0


def test_audit_tier_c_deferred_have_defer_reason() -> None:
    from scripts.sut.prose.drug_indication_4210_gate_b import (
        build_4210_manifest,
        export_4210_candidates,
    )

    frame = export_4210_candidates(_CLAUSES)
    manifest = build_4210_manifest(frame, _combined_rules(), effective_date="2026-06-27")
    gap_ids = _gap_clause_ids()

    for trace in manifest["clause_traces"]:
        cid = trace["clause_id"]
        status = trace["manifest_status"]
        if cid in gap_ids:
            assert status in {"encoded", "tier_c_deferred", "tier_b_pending"}
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
    assert len(tier_c_ids) == manifest["tier_c_deferred_count"] == 109


def test_audit_no_actionable_tier_ab_promotions() -> None:
    from scripts.sut.prose.drug_indication_4210_gate_b import (
        export_4210_candidates,
        scan_4210_tier_ab_promotions,
    )

    frame = export_4210_candidates(_CLAUSES)
    promotions = scan_4210_tier_ab_promotions(frame, encoded_clause_ids=_ALL_ENCODED_IDS)
    assert len(promotions) <= 1
    for candidate in promotions:
        assert candidate["clause_id"] not in _ALL_ENCODED_IDS


def test_gate_b_artifacts_on_disk() -> None:
    assert _CORPUS.is_file()
    assert _MANIFEST.is_file()

    corpus = pl.read_csv(_CORPUS)
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))

    assert corpus.height == 131
    assert manifest["section_clause_total"] == 131
    assert manifest["tier_a_pending_count"] == 0
    assert manifest["tier_b_pending_count"] == 0
    assert manifest["encoded_clause_count"] == len(manifest["encoded_clause_ids"])
    assert manifest["tier_c_deferred_count"] == 109
    assert set(manifest["encoded_clause_ids"]) == set(manifest["gate_b_sources_encoded"])

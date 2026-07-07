"""Tests for §4.2.1 rheumatology/biologic drug indication Gate B export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl
import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4201.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4201_manifest.json"

_SECTION = "4201"
_SECTION_PREFIX = "4.2.1"


def is_421_proper(section_id: str) -> bool:
    """True for §4.2.1 proper — excludes 4.2.10–4.2.19 false prefix matches."""
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    return ALL_SECTIONS[_SECTION].match.matches(section_id)


def _in_force_clause_ids(clauses_path: Path) -> frozenset[str]:
    """In-force §4.2.1 proper clause IDs (regex boundary) from coverage parquet."""
    from scripts.sut.prose.gate_b_audit import in_force_clause_ids

    return in_force_clause_ids(clauses_path, _SECTION_PREFIX, matcher=is_421_proper)


def _audit_gap_parity(
    clauses_path: Path,
    manifest: dict[str, Any],
    *,
    gate_b_frame: pl.DataFrame | None = None,
) -> dict[str, Any]:
    from scripts.sut.prose.gate_b_audit import audit_gap_parity, default_scan_promotions
    from scripts.sut.prose.gate_b_shim import shim_export_candidates

    def _scan(frame: pl.DataFrame, encoded: Any) -> list[dict[str, Any]]:
        return default_scan_promotions(frame, encoded)

    return audit_gap_parity(
        clauses_path,
        manifest,
        section_prefix=_SECTION_PREFIX,
        matcher=is_421_proper,
        frame=gate_b_frame,
        fallback_frame=lambda: shim_export_candidates(_SECTION, clauses_path),
        scan=_scan,
    )


def _run_audit(clauses_path: Path, rules_path: Path, *, effective_date: str) -> dict[str, Any]:
    from scripts.sut.prose.gate_b_audit import (
        gap_clause_ids,
        normalize_defer_reasons as _normalize_defer,
        repair_untraced as _repair,
    )
    from scripts.sut.prose.gate_b_shim import shim_build_manifest, shim_export_candidates

    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    rules = [r for r in (payload.get("rules") or []) if is_421_proper(str(r.get("sut_section") or ""))]
    frame = shim_export_candidates(_SECTION, clauses_path)
    manifest = shim_build_manifest(_SECTION, frame, rules, effective_date=effective_date)
    before = _audit_gap_parity(clauses_path, manifest, gate_b_frame=frame)
    manifest, repaired = _repair(manifest, frame, gap_ids=gap_clause_ids(clauses_path, _SECTION_PREFIX, matcher=is_421_proper))
    manifest, defer_fixed = _normalize_defer(manifest, frame)
    after = _audit_gap_parity(clauses_path, manifest, gate_b_frame=frame)
    return {
        **after,
        "repaired_untraced": repaired,
        "defer_reason_fixed": defer_fixed,
        "untraced_before": before["untraced_before"],
        "untraced_after": len(after["untraced_clause_ids"]) + len(after["misclassified_ab_gap_ids"]),
        "promoted_clause_ids": sorted({p["clause_id"] for p in after["promotion_candidates"]}),
    }


def _load_4201_prose_rules() -> list[dict]:
    payload = json.loads(
        (_REPO / "data/gazette/prose_rules/drug_indication_prose.json").read_text(encoding="utf-8")
    )
    return [
        rule
        for rule in (payload.get("rules") or [])
        if is_421_proper(str(rule.get("sut_section") or ""))
    ]


def test_section_filter_excludes_4210_plus() -> None:
    assert is_421_proper("4.2.1")
    assert is_421_proper("4.2.1.A")
    assert is_421_proper("4.2.1.C-1")
    assert not is_421_proper("4.2.10")
    assert not is_421_proper("4.2.17")
    assert not is_421_proper("4.2.19")


def test_gate_b_exports_4201_candidates() -> None:
    from scripts.sut.prose.gate_b_shim import shim_export_candidates

    frame = shim_export_candidates(_SECTION, _CLAUSES)
    assert frame.height == 282
    assert frame.filter(pl.col("section_id").str.starts_with("4.2.17")).height == 0
    assert frame.filter(pl.col("section_id") == "4.2.1.A").height >= 1


def test_gate_b_csv_schema_and_tier_a_signal() -> None:
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
    tier_b = frame.filter(pl.col("encode_tier") == "B")
    assert tier_a.height >= 40
    if tier_b.height:
        assert tier_a["signal_score"].max() >= tier_b["signal_score"].max()


def test_manifest_pilot_encoded_and_pending_trace() -> None:
    from scripts.sut.prose.gate_b_shim import shim_build_manifest, shim_export_candidates
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A1_RULES = load_legacy_drug_batch("drug_indication_4201_pilot_batch_rules.py:BATCH_A1_RULES")

    frame = shim_export_candidates(_SECTION, _CLAUSES)
    manifest = shim_build_manifest(_SECTION, frame, BATCH_A1_RULES, effective_date="2026-06-27")
    encoded = manifest["encoded_clause_ids"]
    assert len(encoded) >= 14
    assert manifest["rules_in_json"] == 14
    assert manifest["tier_a_pending_count"] >= 25
    assert manifest["tier_c_deferred_count"] >= 5
    assert manifest["section_id"] == "4.2.1"


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.prose.gate_b_shim import shim_write_artifacts

    rules_path = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
    corpus = tmp_path / _CORPUS.name
    manifest_path = tmp_path / _MANIFEST.name
    shim_write_artifacts(
        _SECTION,
        clauses_path=_CLAUSES,
        rules_path=rules_path,
        corpus_csv=corpus,
        manifest_path=manifest_path,
        effective_date="2026-06-27",
    )
    assert corpus.is_file()
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["section_clause_total"] == 282
    assert manifest["encoded_clause_count"] >= 90
    assert manifest["tier_a_pending_count"] == 0
    assert manifest["tier_b_pending_count"] == 0


def test_a2_manifest_covers_pending_sources() -> None:
    from scripts.sut.prose.gate_b_shim import shim_build_manifest, shim_export_candidates
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A2_RULES = load_legacy_drug_batch("drug_indication_4201_a2_batch_rules.py:BATCH_A2_RULES")
    BATCH_A1_RULES = load_legacy_drug_batch("drug_indication_4201_pilot_batch_rules.py:BATCH_A1_RULES")

    combined = [
        {k: v for k, v in rule.items() if k != "encode_batch"}
        for rule in (*BATCH_A1_RULES, *BATCH_A2_RULES)
    ]
    frame = shim_export_candidates(_SECTION, _CLAUSES)
    manifest = shim_build_manifest(_SECTION, frame, combined, effective_date="2026-06-27")
    a2_sources = {
        str(clause_id)
        for rule in BATCH_A2_RULES
        for clause_id in (rule.get("gate_b_sources") or [])
    }
    encoded = set(manifest["encoded_clause_ids"])
    assert a2_sources <= encoded
    assert manifest["rules_in_json"] == len(combined)
    assert manifest["encoded_clause_count"] >= 25
    assert manifest["section_clause_total"] == 282


def test_a3_manifest_covers_batch_sources() -> None:
    from scripts.sut.prose.gate_b_shim import shim_build_manifest, shim_export_candidates
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A3_RULES = load_legacy_drug_batch("drug_indication_4201_a3_batch_rules.py:BATCH_A3_RULES")
    BATCH_A2_RULES = load_legacy_drug_batch("drug_indication_4201_a2_batch_rules.py:BATCH_A2_RULES")
    BATCH_A1_RULES = load_legacy_drug_batch("drug_indication_4201_pilot_batch_rules.py:BATCH_A1_RULES")

    combined = [
        {k: v for k, v in rule.items() if k != "encode_batch"}
        for rule in (*BATCH_A1_RULES, *BATCH_A2_RULES, *BATCH_A3_RULES)
    ]
    frame = shim_export_candidates(_SECTION, _CLAUSES)
    manifest = shim_build_manifest(_SECTION, frame, combined, effective_date="2026-06-27")
    a3_sources = {
        str(clause_id)
        for rule in BATCH_A3_RULES
        for clause_id in (rule.get("gate_b_sources") or [])
    }
    encoded = set(manifest["encoded_clause_ids"])
    assert a3_sources <= encoded
    assert manifest["rules_in_json"] == len(combined)
    assert manifest["encoded_clause_count"] >= 40
    assert manifest["section_clause_total"] == 282


def test_in_force_manifest_traces_all_clauses() -> None:
    from scripts.sut.prose.gate_b_shim import shim_export_candidates

    in_force = _in_force_clause_ids(_CLAUSES)
    assert len(in_force) == 282
    frame = shim_export_candidates(_SECTION, _CLAUSES)
    assert frame.height == len(in_force)
    if _MANIFEST.is_file():
        manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        traced_ids = {t["clause_id"] for t in manifest["clause_traces"]}
        assert in_force <= traced_ids
        assert manifest["section_clause_total"] == 282


def test_a4_manifest_covers_all_parallel_clusters() -> None:
    from scripts.sut.prose.gate_b_shim import shim_build_manifest, shim_export_candidates
    from scripts.sut.rule_sources import load_drug_sections_rules, load_legacy_drug_batch

    BATCH_A4_RULES = load_drug_sections_rules(
        ["4.2.1.C-1", "4.2.1.C-2", "4.2.1.C-5", "4.2.1.C-7"]
    )
    BATCH_A3_RULES = load_legacy_drug_batch("drug_indication_4201_a3_batch_rules.py:BATCH_A3_RULES")
    BATCH_A2_RULES = load_legacy_drug_batch("drug_indication_4201_a2_batch_rules.py:BATCH_A2_RULES")
    BATCH_A1_RULES = load_legacy_drug_batch("drug_indication_4201_pilot_batch_rules.py:BATCH_A1_RULES")

    combined = [
        {k: v for k, v in rule.items() if k != "encode_batch"}
        for rule in (*BATCH_A1_RULES, *BATCH_A2_RULES, *BATCH_A3_RULES, *BATCH_A4_RULES)
    ]
    frame = shim_export_candidates(_SECTION, _CLAUSES)
    manifest = shim_build_manifest(_SECTION, frame, combined, effective_date="2026-06-27")
    a4_sources = {
        str(clause_id)
        for rule in BATCH_A4_RULES
        for clause_id in (rule.get("gate_b_sources") or [])
    }
    encoded = set(manifest["encoded_clause_ids"])
    assert a4_sources <= encoded
    assert manifest["rules_in_json"] == len(combined)
    assert manifest["encoded_clause_count"] >= 55
    assert manifest["section_clause_total"] == 282


def _gap_clause_ids() -> frozenset[str]:
    coverage = pl.read_parquet(_REPO / "data/gazette/sut_clause_coverage.parquet")
    motor = coverage.filter(
        (pl.col("primary_rule_id") == "drug_indication_prose")
        & pl.col("section_id").map_elements(is_421_proper, return_dtype=pl.Boolean)
        & ~pl.col("has_rule_encoding")
    )
    return frozenset(str(row) for row in motor["clause_id"].to_list())


def test_audit_gap_parity_zero_untraced() -> None:
    from scripts.sut.prose.gate_b_shim import shim_build_manifest, shim_export_candidates

    rules = _load_4201_prose_rules()
    frame = shim_export_candidates(_SECTION, _CLAUSES)
    manifest = shim_build_manifest(_SECTION, frame, rules, effective_date="2026-06-27")

    report = _audit_gap_parity(_CLAUSES, manifest, gate_b_frame=frame)
    assert report["gap_count"] == 154
    assert report["encoded_count"] == 129
    assert report["tier_c_deferred_count"] == 154
    assert report["untraced_clause_ids"] == []
    assert report["misclassified_ab_gap_ids"] == []
    assert report["missing_from_traces"] == []
    assert report["gaps_missing_export"] == []
    assert report["defer_reason_gap_count"] == 0

    full = _run_audit(
        _CLAUSES,
        _REPO / "data/gazette/prose_rules/drug_indication_prose.json",
        effective_date="2026-06-27",
    )
    assert full["untraced_before"] == 0
    assert full["untraced_after"] == 0
    assert full["repaired_untraced"] == 0
    assert full["defer_reason_fixed"] == 0


def test_audit_tier_c_deferred_have_defer_reason() -> None:
    from scripts.sut.prose.gate_b_shim import shim_build_manifest, shim_export_candidates

    rules = _load_4201_prose_rules()
    frame = shim_export_candidates(_SECTION, _CLAUSES)
    manifest = shim_build_manifest(_SECTION, frame, rules, effective_date="2026-06-27")
    gap_ids = _gap_clause_ids()

    for trace in manifest["clause_traces"]:
        cid = trace["clause_id"]
        status = trace["manifest_status"]
        if cid in gap_ids:
            assert status in {"encoded", "tier_c_deferred"}
        if status == "tier_c_deferred":
            assert trace.get("defer_reason")
            assert trace.get("defer_themes") is not None


def test_audit_no_actionable_tier_ab_promotions() -> None:
    from scripts.sut.prose.gate_b_audit import default_scan_promotions
    from scripts.sut.prose.gate_b_shim import shim_export_candidates

    rules = _load_4201_prose_rules()
    encoded = {
        str(clause_id)
        for rule in rules
        for clause_id in (rule.get("gate_b_sources") or [])
    }
    frame = shim_export_candidates(_SECTION, _CLAUSES)
    promotions = default_scan_promotions(frame, encoded_clause_ids=encoded)
    assert promotions == []
    for candidate in promotions:
        assert candidate["clause_id"] not in encoded


def test_normalize_defer_reasons_fills_missing() -> None:
    from scripts.sut.prose.gate_b_audit import normalize_defer_reasons
    from scripts.sut.prose.gate_b_shim import shim_build_manifest, shim_export_candidates

    rules = _load_4201_prose_rules()
    frame = shim_export_candidates(_SECTION, _CLAUSES)
    manifest = shim_build_manifest(_SECTION, frame, rules, effective_date="2026-06-27")
    traces = manifest["clause_traces"]
    stripped = False
    for trace in traces:
        if trace.get("manifest_status") == "tier_c_deferred":
            trace.pop("defer_reason", None)
            trace["defer_themes"] = None
            stripped = True
            break
    assert stripped

    repaired, fixed = normalize_defer_reasons(manifest, frame)
    assert fixed >= 1
    for trace in repaired["clause_traces"]:
        if trace.get("manifest_status") == "tier_c_deferred":
            assert trace.get("defer_reason")
            assert trace.get("defer_themes") is not None

"""Tests for §4.2.1 rheumatology/biologic drug indication Gate B export."""

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
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4201.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4201_manifest.json"

_SECTION = "4201"
_SECTION_PREFIX = "4.2.1"


def _resolved_sources(rules: list[dict]) -> set[str]:
    """Resolve gate_b_sources cites to clause_ids (dual-read)."""
    from scripts.sut.prose.clause_identity import (
        AmbiguousClauseCiteError,
        UnknownClauseCiteError,
        is_clause_id,
        resolve_gate_b_sources_to_clause_ids,
    )

    clauses = pl.read_parquet(_CLAUSES)
    out: set[str] = set()
    for rule in rules:
        for raw in rule.get("gate_b_sources") or []:
            if raw is None or not str(raw).strip():
                continue
            try:
                out.update(
                    resolve_gate_b_sources_to_clause_ids(
                        [raw], clauses, in_force_only=True, allow_ambiguous=False
                    )
                )
            except (AmbiguousClauseCiteError, UnknownClauseCiteError):
                text = str(raw).strip()
                if is_clause_id(text):
                    out.add(text)
    return out


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
    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    def _scan(frame: pl.DataFrame, encoded: Any) -> list[dict[str, Any]]:
        return default_scan_promotions(frame, encoded)

    return audit_gap_parity(
        clauses_path,
        manifest,
        section_prefix=_SECTION_PREFIX,
        matcher=is_421_proper,
        frame=gate_b_frame,
        fallback_frame=lambda: export_candidates(clauses_path, ALL_SECTIONS[_SECTION]),
        scan=_scan,
    )


def _run_audit(clauses_path: Path, rules_path: Path, *, effective_date: str) -> dict[str, Any]:
    from scripts.sut.prose.gate_b_audit import (
        gap_clause_ids,
        normalize_defer_reasons as _normalize_defer,
        repair_untraced as _repair,
    )
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    rules = [r for r in (payload.get("rules") or []) if is_421_proper(str(r.get("sut_section") or ""))]
    frame = export_candidates(clauses_path, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, rules, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date=effective_date)
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
    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    expected = len(_in_force_clause_ids(_CLAUSES))
    assert frame.height == expected
    soft_floor(frame.height, 200, label="§4.2.1 export height")
    assert frame.filter(pl.col("section_id").str.starts_with("4.2.17")).height == 0
    assert frame.filter(pl.col("section_id") == "4.2.1.A").height >= 1


def test_gate_b_csv_schema_and_tier_a_signal() -> None:
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
        "signal_score",
    ):
        assert col in frame.columns
    tier_a = frame.filter(pl.col("encode_tier") == "A")
    tier_b = frame.filter(pl.col("encode_tier") == "B")
    assert tier_a.height >= 40
    if tier_b.height:
        assert tier_a["signal_score"].max() >= tier_b["signal_score"].max()


def test_manifest_pilot_encoded_and_pending_trace() -> None:
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A1_RULES = load_legacy_drug_batch("drug_indication_4201_pilot_batch_rules.py:BATCH_A1_RULES")

    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, BATCH_A1_RULES, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date="2026-06-27")
    encoded = manifest["encoded_clause_ids"]
    soft_floor(len(encoded), 14, label="pilot encoded")
    assert manifest["rules_in_json"] == len(BATCH_A1_RULES)
    soft_floor(manifest["tier_a_pending_count"], 25, label="tier_a_pending")
    soft_floor(manifest["tier_c_deferred_count"], 5, label="tier_c_deferred")
    assert manifest["section_id"] == "4.2.1"
    assert_manifest_consistent(manifest, frame, rules=BATCH_A1_RULES)


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.prose.gate_b_generic import write_artifacts
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    rules_path = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
    corpus = tmp_path / _CORPUS.name
    manifest_path = tmp_path / _MANIFEST.name
    write_artifacts(section=ALL_SECTIONS[_SECTION],
        clauses_path=_CLAUSES,
        rules_path=rules_path,
        corpus_csv=corpus,
        manifest_path=manifest_path,
        effective_date="2026-06-27",
        write_corpus=True,
    )
    assert corpus.is_file()
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    corpus_frame = pl.read_csv(corpus)
    assert manifest["section_clause_total"] == corpus_frame.height
    soft_floor(manifest["encoded_clause_count"], 90, label="encoded_clause_count")
    soft_floor(manifest["tier_a_pending_count"], 1, label="tier_a_pending_count")
    assert manifest["tier_b_pending_count"] == 2
    assert_manifest_consistent(manifest, corpus_frame)


def test_a2_manifest_covers_pending_sources() -> None:
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A2_RULES = load_legacy_drug_batch("drug_indication_4201_a2_batch_rules.py:BATCH_A2_RULES")
    BATCH_A1_RULES = load_legacy_drug_batch("drug_indication_4201_pilot_batch_rules.py:BATCH_A1_RULES")

    combined = [
        {k: v for k, v in rule.items() if k != "encode_batch"}
        for rule in (*BATCH_A1_RULES, *BATCH_A2_RULES)
    ]
    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, combined, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date="2026-06-27")
    a2_sources = _resolved_sources(BATCH_A2_RULES)
    encoded = set(manifest["encoded_clause_ids"])
    assert a2_sources <= encoded
    assert manifest["rules_in_json"] == len(combined)
    soft_floor(manifest["encoded_clause_count"], 25, label="a2 encoded")
    assert_manifest_consistent(manifest, frame, rules=combined)


def test_a3_manifest_covers_batch_sources() -> None:
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A3_RULES = load_legacy_drug_batch("drug_indication_4201_a3_batch_rules.py:BATCH_A3_RULES")
    BATCH_A2_RULES = load_legacy_drug_batch("drug_indication_4201_a2_batch_rules.py:BATCH_A2_RULES")
    BATCH_A1_RULES = load_legacy_drug_batch("drug_indication_4201_pilot_batch_rules.py:BATCH_A1_RULES")

    combined = [
        {k: v for k, v in rule.items() if k != "encode_batch"}
        for rule in (*BATCH_A1_RULES, *BATCH_A2_RULES, *BATCH_A3_RULES)
    ]
    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, combined, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date="2026-06-27")
    a3_sources = _resolved_sources(BATCH_A3_RULES)
    encoded = set(manifest["encoded_clause_ids"])
    assert a3_sources <= encoded
    assert manifest["rules_in_json"] == len(combined)
    soft_floor(manifest["encoded_clause_count"], 40, label="a3 encoded")
    assert_manifest_consistent(manifest, frame, rules=combined)


def test_in_force_manifest_traces_all_clauses() -> None:
    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    in_force = _in_force_clause_ids(_CLAUSES)
    soft_floor(len(in_force), 200, label="§4.2.1 in-force")
    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    assert frame.height == len(in_force)
    if _MANIFEST.is_file():
        manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        traced_ids = {t["clause_id"] for t in manifest["clause_traces"]}
        assert in_force <= traced_ids
        # Manifest may retain a few historical out-of-export traces; total >= live export.
        assert manifest["section_clause_total"] >= frame.height


def test_a4_manifest_covers_all_parallel_clusters() -> None:
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
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
    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, combined, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date="2026-06-27")
    a4_sources = _resolved_sources(BATCH_A4_RULES)
    encoded = set(manifest["encoded_clause_ids"])
    assert a4_sources <= encoded
    assert manifest["rules_in_json"] == len(combined)
    soft_floor(manifest["encoded_clause_count"], 55, label="a4 encoded")
    assert_manifest_consistent(manifest, frame, rules=combined)


def _gap_clause_ids() -> frozenset[str]:
    coverage = pl.read_parquet(_REPO / "data/gazette/sut_clause_coverage.parquet")
    motor = coverage.filter(
        (pl.col("primary_rule_id") == "drug_indication_prose")
        & pl.col("section_id").map_elements(is_421_proper, return_dtype=pl.Boolean)
        & ~pl.col("has_rule_encoding")
    )
    return frozenset(str(row) for row in motor["clause_id"].to_list())


def test_audit_gap_parity_zero_untraced() -> None:
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    rules = _load_4201_prose_rules()
    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, rules, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date="2026-06-27")

    report = _audit_gap_parity(_CLAUSES, manifest, gate_b_frame=frame)
    assert report["gap_count"] == len(_gap_clause_ids())
    assert_audit_report_consistent(report, manifest)
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
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    rules = _load_4201_prose_rules()
    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, rules, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date="2026-06-27")
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
    from scripts.sut.prose.gate_b_generic import export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    rules = _load_4201_prose_rules()
    encoded = {
        str(clause_id)
        for rule in rules
        for clause_id in (rule.get("gate_b_sources") or [])
    }
    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    promotions = default_scan_promotions(frame, encoded_clause_ids=encoded)
    assert promotions == []
    for candidate in promotions:
        assert candidate["clause_id"] not in encoded


def test_normalize_defer_reasons_fills_missing() -> None:
    from scripts.sut.prose.gate_b_audit import normalize_defer_reasons
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS

    rules = _load_4201_prose_rules()
    frame = export_candidates(_CLAUSES, ALL_SECTIONS[_SECTION])
    manifest = build_manifest(frame, rules, ALL_SECTIONS[_SECTION], resolve_clauses=pl.read_parquet(_CLAUSES),
        effective_date="2026-06-27")
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

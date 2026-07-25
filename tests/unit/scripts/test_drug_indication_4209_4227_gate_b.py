"""Tests for §4.2.9 ESA / §4.2.27 coagulation Gate B export."""

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
_CORPUS = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4209_4227.csv"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4209_4227_manifest.json"

_SECTION = "4209_4227"
_SECTION_4227 = "4.2.27"


def _gap_clause_ids_4227(clauses_path: Path) -> frozenset[str]:
    """Motor-bound §4.2.27 clause IDs with ``has_rule_encoding=false``."""
    from scripts.sut.prose.gate_b_audit import gap_clause_ids

    return gap_clause_ids(clauses_path, _SECTION_4227)


def _in_force_clause_ids_4227(clauses_path: Path) -> frozenset[str]:
    """In-force §4.2.27 clause IDs (no encoding filter)."""
    from scripts.sut.prose.gate_b_audit import in_force_clause_ids

    return in_force_clause_ids(clauses_path, _SECTION_4227)


def _with_defer_themes(frame: pl.DataFrame) -> pl.DataFrame:
    """Back-compat: legacy export emitted a ``defer_themes`` csv column."""
    if frame.is_empty() or "defer_themes" in frame.columns:
        return frame
    from scripts.sut.prose.drug_indication_gate_b import infer_defer_themes

    rows = []
    for r in frame.iter_rows(named=True):
        themes = infer_defer_themes(str(r.get("text_tr") or "")) if r.get("encode_tier") == "C" else []
        rows.append(",".join(themes) if themes else "")
    return frame.with_columns(pl.Series("defer_themes", rows))


def _export_candidates(clauses_path: Path) -> pl.DataFrame:
    from scripts.sut.prose.gate_b_shim import shim_export_candidates

    return _with_defer_themes(shim_export_candidates(_SECTION, clauses_path))


def _build_manifest(frame: pl.DataFrame, rules: list[dict[str, Any]], *, effective_date: str) -> dict[str, Any]:
    from scripts.sut.prose.gate_b_shim import shim_build_manifest

    return shim_build_manifest(_SECTION, frame, rules, effective_date=effective_date)


def audit_4227_gap_parity(
    clauses_path: Path,
    manifest: dict[str, Any],
    *,
    gate_b_frame: pl.DataFrame | None = None,
) -> dict[str, Any]:
    """Parity audit: every §4.2.27 coverage gap must be honestly traced."""
    gap_ids = _gap_clause_ids_4227(clauses_path)
    trace_ids = {
        str(t.get("clause_id") or "")
        for t in (manifest.get("clause_traces") or [])
        if str(t.get("section_id") or "").startswith(_SECTION_4227)
    }
    statuses = {
        s: frozenset(
            str(t["clause_id"])
            for t in (manifest.get("clause_traces") or [])
            if str(t.get("section_id") or "").startswith(_SECTION_4227)
            and t.get("manifest_status") == s
        )
        for s in ("encoded", "tier_c_deferred", "tier_a_pending", "tier_b_pending")
    }
    honest = statuses["encoded"] | statuses["tier_c_deferred"] | statuses["tier_a_pending"] | statuses["tier_b_pending"]
    untraced = sorted(gap_ids - honest)
    missing_from_traces = sorted(gap_ids - trace_ids)
    frame = gate_b_frame if gate_b_frame is not None else _export_candidates(clauses_path)
    export_ids_4227 = (
        set(frame.filter(pl.col("section_id").str.starts_with(_SECTION_4227))["clause_id"].to_list())
        if frame.height
        else set()
    )
    gaps_missing_export = sorted(gap_ids - export_ids_4227)
    return {
        "gap_count": len(gap_ids),
        "encoded_count": len(statuses["encoded"]),
        "tier_b_pending_count": len(statuses["tier_b_pending"]),
        "tier_c_deferred_count": len(statuses["tier_c_deferred"]),
        "untraced_before": len(untraced) + len(gaps_missing_export),
        "untraced_after": len(untraced) + len(gaps_missing_export),
        "untraced_clause_ids": untraced,
        "missing_from_traces": missing_from_traces,
        "gaps_missing_export": gaps_missing_export,
    }


def test_gate_b_exports_both_section_prefixes() -> None:
    frame = _export_candidates(_CLAUSES)
    assert frame.filter(pl.col("section_id").str.starts_with("4.2.9")).height >= 30
    soft_floor(frame.filter(pl.col("section_id").str.starts_with("4.2.27")).height, 48, label="test_drug_indication_4209_4227_gate_b 4.2.27")


def test_gate_b_4227_in_force_export() -> None:
    in_force = _in_force_clause_ids_4227(_CLAUSES)
    frame = _export_candidates(_CLAUSES)
    export_427 = set(
        frame.filter(pl.col("section_id").str.starts_with("4.2.27"))["clause_id"].to_list()
    )
    assert export_427 == set(in_force)
    gaps = _gap_clause_ids_4227(_CLAUSES)
    soft_floor(len(gaps), 20, label="4209/4227 gaps")
    assert gaps - export_427 == set()


def test_gate_b_tier_a_counts() -> None:
    frame = _export_candidates(_CLAUSES)
    s429 = frame.filter(pl.col("section_id").str.starts_with("4.2.9"))
    s427 = frame.filter(pl.col("section_id").str.starts_with("4.2.27"))
    assert s429.filter(pl.col("encode_tier") == "A").height >= 7
    assert s427.filter(pl.col("encode_tier") == "A").height >= 13


def test_gate_b_csv_schema() -> None:
    frame = _export_candidates(_CLAUSES)
    for col in (
        "clause_id",
        "section_id",
        "deontic_modality",
        "text_tr",
        "encode_tier",
        "encode_priority",
        "defer_themes",
    ):
        assert col in frame.columns


def test_manifest_has_encoded_and_tier_c_trace() -> None:
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A6_RULES = load_legacy_drug_batch("drug_indication_4209_4227_batch_rules.py:BATCH_A6_RULES")
    BATCH_A8_RULES = load_legacy_drug_batch("drug_indication_4227_a8_batch_rules.py:BATCH_A8_RULES")
    combined = BATCH_A6_RULES + BATCH_A8_RULES
    frame = _export_candidates(_CLAUSES)
    manifest = _build_manifest(frame, combined, effective_date="2026-06-27")
    audit = audit_4227_gap_parity(_CLAUSES, manifest, gate_b_frame=frame)
    assert manifest["rules_in_json"] == len(combined)
    assert manifest["section_4.2.27_clause_total"] == 69
    assert audit["untraced_after"] == 0
    assert manifest["tier_c_deferred_count"] >= 40
    assert manifest["section_4.2.9_tier_a_count"] >= 7
    assert manifest["section_4.2.27_tier_a_count"] >= 13


def test_gate_b_artifacts_on_disk(tmp_path: Path) -> None:
    from scripts.sut.prose.gate_b_shim import shim_write_artifacts
    from scripts.sut.rule_sources import load_legacy_drug_batch

    BATCH_A6_RULES = load_legacy_drug_batch("drug_indication_4209_4227_batch_rules.py:BATCH_A6_RULES")
    BATCH_A8_RULES = load_legacy_drug_batch("drug_indication_4227_a8_batch_rules.py:BATCH_A8_RULES")
    corpus = tmp_path / "corpus.csv"
    manifest = tmp_path / "manifest.json"
    combined = BATCH_A6_RULES + BATCH_A8_RULES
    shim_write_artifacts(
        _SECTION,
        clauses_path=_CLAUSES,
        rules_path=_REPO / "data/gazette/prose_rules/drug_indication_prose.json",
        corpus_csv=corpus,
        manifest_path=manifest,
        effective_date="2026-06-27",
        batch_rules=combined,
    )
    assert corpus.is_file()
    assert manifest.is_file()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["rules_in_json"] == len(combined)
    assert payload["section_4.2.27_clause_total"] == 69
    assert payload["section_id"] == "4.2.9,4.2.27"

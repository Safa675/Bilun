"""A1 — §4.2.14.C manifest trace coverage verification (R5 Epic A Phase 2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.sut.prose.drug_indication_a1_manifest_coverage import (
    gate_b_4214c_clause_ids,
    in_force_4214c_clause_ids,
    manifest_coverage_gap,
    manifest_traced_clause_ids,
    repair_4214c_manifest,
)

_REPO = Path(__file__).resolve().parents[3]
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4.2.14.C_manifest.json"
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"


@pytest.fixture(scope="module")
def manifest() -> dict:
    assert _MANIFEST.is_file()
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))


def test_a1_in_force_clauses_fully_traced(manifest: dict) -> None:
    gap = manifest_coverage_gap(manifest, clauses_path=_CLAUSES, in_force_only=True)
    assert gap["missing_clause_ids"] == [], (
        f"Untraced in-force §4.2.14.C clauses: {gap['missing_clause_ids'][:20]}"
    )
    assert gap["traced_count"] == gap["canonical_count"]


def test_a1_manifest_status_buckets_disjoint(manifest: dict) -> None:
    encoded = set(manifest.get("encoded_clause_ids") or [])
    tier_c = set(manifest.get("tier_c_deferred_clause_ids") or [])
    emr = set(manifest.get("emr_blocked_clause_ids") or [])
    non_actionable = set(manifest.get("non_actionable_clause_ids") or [])

    assert encoded.isdisjoint(tier_c)
    assert encoded.isdisjoint(emr)
    assert encoded.isdisjoint(non_actionable)
    assert emr.isdisjoint(non_actionable)
    assert tier_c.isdisjoint(non_actionable)


def test_a1_clause_traces_match_in_force_total(manifest: dict) -> None:
    in_force = in_force_4214c_clause_ids(_CLAUSES)
    traces = manifest.get("clause_traces") or []
    trace_ids = {str(row["clause_id"]) for row in traces}
    assert in_force <= trace_ids
    assert manifest["section_clause_total"] == len(trace_ids)
    assert manifest["clause_trace_complete"] is True


def test_a1_gate_b_corpus_count_documented(manifest: dict) -> None:
    gate_b_total = gate_b_4214c_clause_ids(_CLAUSES)
    summary = manifest.get("gate_b_summary") or {}
    assert summary.get("total") == len(gate_b_total)
    assert len(gate_b_total) >= 828


def test_a1_tier_c_deferred_entries_have_defer_reason(manifest: dict) -> None:
    tier_c_ids = set(manifest.get("tier_c_deferred_clause_ids") or [])
    for row in manifest.get("tier_c_manifest") or []:
        if str(row.get("clause_id")) in tier_c_ids:
            assert row.get("defer_reason")
            assert row.get("defer_themes")


def test_a1_repair_is_idempotent() -> None:
    repaired = repair_4214c_manifest(dry_run=True)
    after_traced = manifest_traced_clause_ids(repaired)
    in_force = in_force_4214c_clause_ids(_CLAUSES)
    assert in_force <= after_traced
    assert repaired["a1_coverage_gap"]["missing_clause_ids"] == []

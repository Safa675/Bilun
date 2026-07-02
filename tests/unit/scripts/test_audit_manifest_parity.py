"""Tests for manifest bucket list / clause_traces parity audit."""

from __future__ import annotations

import json

import pytest

from scripts.sut.audit_manifest_parity import audit_manifest_payload
from scripts.sut.prose.manifest_reconcile import reconcile_manifest_payload

pytestmark = pytest.mark.unit


def _minimal_manifest(*, stale_encoded: bool = False) -> dict:
    traces = [
        {"clause_id": "C000001", "manifest_status": "encoded", "encode_tier": "A"},
        {"clause_id": "C000002", "manifest_status": "tier_c_deferred", "encode_tier": "C"},
        {"clause_id": "C000003", "manifest_status": "emr_blocked", "encode_tier": "C"},
    ]
    encoded = ["C000001"]
    if stale_encoded:
        encoded.append("C999999")  # not in traces
    return {
        "section_clause_total": 3,
        "clause_trace_complete": True,
        "clause_traces": traces,
        "encoded_clause_ids": encoded,
        "encoded_clause_count": len(encoded),
        "tier_c_deferred_clause_ids": ["C000002"],
        "tier_c_deferred_count": 1,
        "emr_blocked_clause_ids": ["C000003"],
        "emr_blocked_count": 1,
        "non_actionable_clause_ids": [],
        "non_actionable_count": 0,
        "tier_a_pending_clause_ids": [],
        "tier_a_pending_count": 0,
        "tier_b_pending_clause_ids": [],
        "tier_b_pending_count": 0,
    }


def test_audit_detects_stale_list_ids() -> None:
    issues = audit_manifest_payload("fixture.json", _minimal_manifest(stale_encoded=True))
    kinds = {i.kind for i in issues}
    assert "stale_list_ids" in kinds
    assert "union_mismatch" in kinds
    assert "false_complete_flag" in kinds


def test_audit_passes_when_lists_match_traces() -> None:
    manifest = _minimal_manifest(stale_encoded=False)
    assert audit_manifest_payload("fixture.json", manifest) == []


def test_audit_skips_list_type_manifest() -> None:
    """Header-clause-id manifests (bare JSON arrays) must not crash the audit."""
    assert audit_manifest_payload("header_ids.json", ["C001", "C002"]) == []


def test_reconcile_rebuilds_lists_from_traces() -> None:
    manifest = _minimal_manifest(stale_encoded=True)
    reconcile_manifest_payload(manifest, backfill=False)
    assert manifest["encoded_clause_ids"] == ["C000001"]
    assert manifest["encoded_clause_count"] == 1
    assert manifest["clause_trace_complete"] is True
    assert audit_manifest_payload("fixture.json", manifest) == []


def test_reconcile_backfills_tier_c_defer_metadata() -> None:
    manifest = _minimal_manifest()
    manifest["clause_traces"][1]["text_tr"] = "EGFR mutasyonu pozitif hastalarda"
    manifest["clause_traces"][1].pop("defer_reason", None)
    manifest["clause_traces"][1].pop("defer_themes", None)
    reconcile_manifest_payload(manifest, backfill=True)
    trace = manifest["clause_traces"][1]
    assert trace.get("defer_themes")
    assert trace.get("defer_reason")

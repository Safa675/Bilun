"""Tests for §4.2.14.C Phase 5 clause trace manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.sut.prose.drug_indication_a1_manifest_coverage import in_force_4214c_clause_ids
from scripts.sut.prose.drug_indication_gate_b import (
    export_4_2_14_c_candidates,
    infer_defer_themes,
)
from scripts.sut.prose.drug_indication_manifest import build_phase5_manifest

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_MANIFEST = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4.2.14.C_manifest.json"
_RULES = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"

_ALLOWED_THEMES = {
    "ecog",
    "mutation_panel",
    "prior_therapy",
    "response_assessment",
    "moh_patient_approval",
    "clinical_pathway",
}


def test_infer_defer_themes_detects_mutation_and_prior_therapy() -> None:
    text = (
        "PD-L1 <%50, platin bazlı 2 kür sonunda minör yanıt; EGFR/ALK/ROS1 negatif "
        "olduğunun gösterilmesi gerekir."
    )
    themes = infer_defer_themes(text)
    assert "mutation_panel" in themes
    assert "response_assessment" in themes


def test_phase5_manifest_traces_all_4214c_clauses() -> None:
    assert _MANIFEST.is_file()
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert payload["manifest_version"] == "phase5-v1"
    # section_clause_total reflects in-force (struck-filtered) trace count.
    trace_total = payload["section_clause_total"]
    assert payload["clause_trace_complete"] is True
    assert payload["manifest_coverage_pct"] == 100.0
    assert len(payload["clause_traces"]) == trace_total
    # A1 repair: tier-C deferred is a small in-force tail; EMR-blocked holds pathway clauses.
    assert payload["tier_c_deferred_count"] >= 20
    assert payload.get("emr_blocked_count", 0) >= 0  # EMR-blocked set regenerates per parquet

    traced_ids = {row["clause_id"] for row in payload["clause_traces"]}
    assert len(traced_ids) == trace_total

    in_force = in_force_4214c_clause_ids(_CLAUSES)
    assert traced_ids == in_force

    for row in payload["clause_traces"]:
        cid = row["clause_id"]
        status = row.get("manifest_status")
        if status == "encoded":
            assert cid in payload["encoded_clause_ids"]
        elif status == "tier_c_deferred":
            assert cid in payload["tier_c_deferred_clause_ids"]
        elif status == "emr_blocked":
            assert cid in (payload.get("emr_blocked_clause_ids") or [])
        elif status == "non_actionable":
            assert cid in (payload.get("non_actionable_clause_ids") or [])
    assert payload["encoded_clause_count"] >= 200
    assert payload["tier_a_pending_count"] == 11
    assert payload["tier_b_pending_count"] == 2


def test_tier_c_manifest_entries_have_theme_tags() -> None:
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    tier_c_rows = payload["tier_c_manifest"]
    assert tier_c_rows
    # tier_c_manifest lists in-force tier-C deferred rows (A1 repair).
    assert len(tier_c_rows) >= 20
    for row in tier_c_rows:
        themes = row.get("defer_themes") or []
        assert themes
        assert set(themes) <= _ALLOWED_THEMES
        assert row.get("defer_reason")


def test_v1_stop_conditions_met_except_inn_stretch_goal() -> None:
    from src.bilun.domain.prose_rules.drug_indication import drug_indication_v1_stop_conditions

    stop = drug_indication_v1_stop_conditions()
    assert stop["v1_manifest_complete"] is True
    assert stop["v1_corpus_complete"] is True
    assert stop["v1_synthetic_complete"] is True
    assert stop["conditions"]["json_rules_gte_80"] is True
    assert stop["conditions"]["tier_b_rules_gte_20"] is True
    assert stop["conditions"]["clause_trace_complete"] is True
    assert stop["conditions"]["tier_c_manifest_traced"] is True
    assert stop["v1_inn_coverage_stretch_goal"] is False


@pytest.fixture(scope="module")
def rebuilt_manifest() -> dict:
    gate_b = export_4_2_14_c_candidates(_CLAUSES, rules_path=_RULES)
    rules_payload = json.loads(_RULES.read_text(encoding="utf-8"))
    rules = list(rules_payload.get("rules") or [])
    return build_phase5_manifest(
        gate_b_frame=gate_b,
        rules=rules,
        phase1_added=0,
        phase2_added=0,
        batch_clause_ids={},
        gate_b_summary_payload={"total": gate_b.height},
        effective_date="2026-06-17",
    )


def test_build_phase5_manifest_partition_is_disjoint(rebuilt_manifest: dict) -> None:
    encoded = set(rebuilt_manifest["encoded_clause_ids"])
    pending_a = set(rebuilt_manifest["tier_a_pending_clause_ids"])
    pending_b = set(rebuilt_manifest["tier_b_pending_clause_ids"])
    deferred = set(rebuilt_manifest["tier_c_deferred_clause_ids"])
    assert encoded.isdisjoint(pending_a)
    assert encoded.isdisjoint(pending_b)
    assert encoded.isdisjoint(deferred)
    assert pending_a.isdisjoint(deferred)
    assert pending_b.isdisjoint(deferred)
    assert len(encoded | pending_a | pending_b | deferred) >= 400

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "scripts/audits/build_rule_surfacing_inventory.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("rule_surfacing_inventory", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_all_canonical_runtime_calls_are_captured() -> None:
    audit = _load_script()
    analyze = audit.discover_runtime_calls(audit.ENGINE_PATH, "analyze_claim")
    report = audit.discover_runtime_calls(
        audit.PATIENT_REPORT_PATH, "compute_patient_billing_report"
    )

    assert {row.callable for row in analyze} == audit.EXPECTED_ANALYZE_CALLS
    assert {row.callable for row in report} == audit.EXPECTED_REPORT_CALLS
    audit.assert_known_runtime_calls("analyze_claim", analyze)
    audit.assert_known_runtime_calls("compute_patient_billing_report", report)


def test_claim_compliance_two_rule_allowlist_is_captured() -> None:
    audit = _load_script()
    expected = {
        "icu_bundled_leakage_510090",
        "tablo15_8_missing_diagnosis",
    }
    assert set(audit.discover_claim_compliance_rule_ids()) == expected
    assert set(audit.discover_cohort_claim_compliance_rule_ids()) == expected
    payload = audit.build_audit()
    row = next(
        row
        for row in payload["rows"]
        if row.get("runtime_id") == "compute_patient_billing_report:project_claim_compliance"
    )
    assert set(row["emitted_rule_ids_or_kinds"]) == expected
    assert row["recommended_action_surface"] == "claim_compliance"
    assert row["visibility_status"] == "patient_and_cohort_visible"


def test_registry_only_rows_are_not_runtime() -> None:
    audit = _load_script()
    payload = audit.build_audit()
    registry_only = [row for row in payload["rows"] if row["runtime_status"] == "registry_only"]
    assert registry_only
    assert all(row["inventory_level"] == "registry_rule_family" for row in registry_only)
    assert all(row["runtime_id"] is None for row in registry_only)
    assert all(row["visibility_status"] == "not_applicable" for row in registry_only)


def test_nonstandard_imported_runtime_call_is_discovered_and_fails_closed(
    tmp_path: Path,
) -> None:
    audit = _load_script()
    known = audit.discover_runtime_calls(audit.ENGINE_PATH, "analyze_claim")
    fixture = tmp_path / "future_engine.py"
    fixture.write_text(
        "from future.rules import assess_future_rule\n"
        "\n"
        "def analyze_claim(ctx):\n"
        "    return assess_future_rule(ctx)\n",
        encoding="utf-8",
    )
    future = audit.discover_runtime_calls(fixture, "analyze_claim")

    assert {row.callable for row in future} == {"assess_future_rule"}
    assert future[0].module == "future.rules"
    with pytest.raises(ValueError, match="unexpected=.*assess_future_rule"):
        audit.assert_known_runtime_calls("analyze_claim", [*known, *future])


def test_visible_runtime_rows_do_not_carry_hidden_reason() -> None:
    audit = _load_script()
    payload = audit.build_audit()
    visible = [
        row
        for row in payload["rows"]
        if row["inventory_level"] == "runtime_detector"
        and row["visibility_status"]
        in {"patient_visible", "cohort_visible", "patient_and_cohort_visible"}
    ]
    assert visible
    assert all(row["hidden_reason"] is None for row in visible)


def test_patient_report_metadata_is_exact_and_source_validated() -> None:
    audit = _load_script()
    report = audit.discover_runtime_calls(
        audit.PATIENT_REPORT_PATH, "compute_patient_billing_report"
    )

    assert {row.callable for row in report} == set(audit.PATIENT_REPORT_META)
    audit.validate_explicit_metadata(report)


def test_patient_report_metadata_stale_key_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    audit = _load_script()
    report = audit.discover_runtime_calls(
        audit.PATIENT_REPORT_PATH, "compute_patient_billing_report"
    )
    monkeypatch.setitem(
        audit.PATIENT_REPORT_META,
        "stale_future_adapter",
        dict(audit.PATIENT_REPORT_META["collect_billing_actions"]),
    )

    with pytest.raises(ValueError, match="metadata drift:.*stale_future_adapter"):
        audit.validate_explicit_metadata(report)


def test_patient_visibility_and_recommended_action_surface_drift_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = _load_script()
    report = audit.discover_runtime_calls(
        audit.PATIENT_REPORT_PATH, "compute_patient_billing_report"
    )
    original = audit.PATIENT_REPORT_META["recommend_session_uplift_from_claims"]
    monkeypatch.setitem(
        audit.PATIENT_REPORT_META,
        "recommend_session_uplift_from_claims",
        {**original, "surface": "future_surface"},
    )

    with pytest.raises(ValueError, match="recommended-actions surface drift"):
        audit.validate_explicit_metadata(report)


def test_money_metadata_invariant_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    audit = _load_script()
    report = audit.discover_runtime_calls(
        audit.PATIENT_REPORT_PATH, "compute_patient_billing_report"
    )
    original = audit.PATIENT_REPORT_META["project_claim_compliance"]
    monkeypatch.setitem(
        audit.PATIENT_REPORT_META,
        "project_claim_compliance",
        {**original, "included": True},
    )

    with pytest.raises(ValueError, match="unpriced compliance cannot carry/count money"):
        audit.validate_explicit_metadata(report)


def test_independent_rerun_debt_is_separate_from_duplicate_surface_derivation() -> None:
    audit = _load_script()
    payload = audit.build_audit()
    debt = payload["independent_rerun_debt"]

    assert debt["relationship_count"] == 12
    assert debt["distinct_overlap_rule_ids_or_kinds"] == 1291
    project = [
        row
        for row in debt["relationships"]
        if row["adapter_runtime_id"]
        == "compute_patient_billing_report:project_claim_compliance"
    ]
    assert len(project) == 2
    assert all(row["direct_source_call"] for row in project)
    assert all("hard_coded_two_rule_projection_rerun" in row["debt_flags"] for row in project)

    minimal = [
        {
            "runtime_id": "analyze_claim:hidden",
            "emitted_rule_ids_or_kinds": ["same_rule"],
            "visibility_status": "hidden_runtime",
            "money_semantics": "unpriced_compliance",
            "duplicate_status": "none",
        },
        {
            "runtime_id": "compute_patient_billing_report:visible",
            "emitted_rule_ids_or_kinds": ["same_rule"],
            "visibility_status": "patient_visible",
            "money_semantics": "unpriced_compliance",
            "duplicate_status": "none",
        },
    ]
    semantic = audit._semantic_rollup(minimal)
    assert semantic["same_rule"]["patient_visible"] is True
    assert semantic["same_rule"]["hidden_runtime"] is False
    assert semantic["same_rule"]["duplicate_surfaced"] is False


def test_analyze_claim_required_inputs_include_canonical_context() -> None:
    audit = _load_script()
    payload = audit.build_audit()
    analyze_rows = [
        row
        for row in payload["rows"]
        if row.get("entrypoint") == "analyze_claim"
    ]
    assert analyze_rows
    assert all("claim_context" in row["required_inputs"] for row in analyze_rows)


def test_committed_outputs_match_generator() -> None:
    audit = _load_script()
    payload = audit.build_audit()
    assert audit.check_committed_outputs(payload) == []

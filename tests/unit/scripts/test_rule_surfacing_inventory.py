from __future__ import annotations

import ast
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


def test_focused_materializer_keeps_all_detector_identities_and_current_emissions() -> None:
    audit = _load_script()
    calls = audit._focused_materializer_calls()
    specs, non_emitting = audit._focused_specs()
    analyze = audit.discover_runtime_calls(audit.ENGINE_PATH, "analyze_claim")
    by_name = {row.callable: row for row in analyze}
    assert len(calls) == len(specs) == 18
    assert sum(len(rows) for rows in specs.values()) == 32
    assert len(non_emitting) == 3
    assert set(calls) <= set(by_name)
    assert all(by_name[group].module == module for group, module in calls.items())
    assert all(by_name[group].lines for group in calls)
    assert audit.resolve_emissions(by_name["detect_admission_billing_window"], by_name) == []
    assert audit.resolve_emissions(by_name["detect_exam_admission_date_mismatch"], by_name) == []
    radiation = audit.resolve_emissions(by_name["detect_radiation_oncology_violations"], by_name)
    assert len(radiation) == 12
    assert "radiation_oncology.same_day_collapse.hyperthermia" not in radiation


def test_focused_materializer_wrong_detector_branch_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = _load_script()
    source = audit.FOCUSED_MATERIALIZER_PATH.read_text(encoding="utf-8")
    source = source.replace(
        "return detect_duplicate_tests(claims, procedures)",
        "return detect_duplicate_exam_10day(claims, procedures)",
    )
    fixture = tmp_path / "focused_legacy_materializer.py"
    fixture.write_text(source, encoding="utf-8")
    monkeypatch.setattr(audit, "FOCUSED_MATERIALIZER_PATH", fixture)
    with pytest.raises(ValueError, match="detector call drift"):
        audit._focused_materializer_calls()


def test_focused_report_visible_projection_dataflow_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = _load_script()
    audit._validate_focused_report_dataflow()
    source = audit.PATIENT_REPORT_PATH.read_text(encoding="utf-8")
    source = source.replace(
        "*focused_batch.findings,",
        "# omitted focused findings",
    )
    fixture = tmp_path / "patient_report.py"
    fixture.write_text(source, encoding="utf-8")
    monkeypatch.setattr(audit, "PATIENT_REPORT_PATH", fixture)
    monkeypatch.setattr(
        audit, "_module_for_path", lambda path: "src.bilun.domain.billing.patient_report"
    )
    with pytest.raises(ValueError, match="findings no longer reaches claim compliance"):
        audit._validate_focused_report_dataflow()


def test_focused_public_gate_rejects_missing_index_fail_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = _load_script()
    source = audit.COMPLIANCE_API_PATH.read_text(encoding="utf-8")
    source = source.replace(
        "if not complete_build_evidence_available(reader, wavea_index, active_build):",
        "if wavea_index is not None and not complete_build_evidence_available(reader, wavea_index, active_build):",
    )
    fixture = tmp_path / "compliance.py"
    fixture.write_text(source, encoding="utf-8")
    monkeypatch.setattr(audit, "COMPLIANCE_API_PATH", fixture)
    with pytest.raises(ValueError, match="cohort compliance draft API gate drift"):
        audit._validate_focused_report_dataflow()


def test_focused_public_gate_rejects_missing_index_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = _load_script()
    source = audit.WAVEA_GATE_API_PATH.read_text(encoding="utf-8")
    source = source.replace(
        "validate_full_wavea_evidence_index(index)",
        "pass",
    )
    fixture = tmp_path / "wavea_gate.py"
    fixture.write_text(source, encoding="utf-8")
    monkeypatch.setattr(audit, "WAVEA_GATE_API_PATH", fixture)
    with pytest.raises(ValueError, match="complete-build evidence gate drift"):
        audit._validate_focused_report_dataflow()


def test_focused_public_gate_rejects_missing_patient_cardinality_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = _load_script()
    source = audit.WAVEA_GATE_API_PATH.read_text(encoding="utf-8")
    source = source.replace(
        'counts.get("wavea_evidence_detail") == expected',
        'counts.get("wavea_evidence_detail") >= 0',
    )
    fixture = tmp_path / "wavea_gate.py"
    fixture.write_text(source, encoding="utf-8")
    monkeypatch.setattr(audit, "WAVEA_GATE_API_PATH", fixture)
    with pytest.raises(ValueError, match="complete-build evidence gate drift"):
        audit._validate_focused_report_dataflow()


def test_generic_claim_compliance_surface_is_rule_id_agnostic() -> None:
    audit = _load_script()
    expected = {
        "icu_bundled_leakage_510090",
        "tablo15_8_missing_diagnosis",
        "tablo15_10_unreported_lab_result",
        "tablo15_20_missing_drug_barcode",
        "tablo15_5_material_identity_error",
        "blood_component_isbt128_barcode",
        "tablo15_11_drug_quantity_error",
        "tablo15_16_material_type_missing",
        "tablo15_21_inpatient_on_outpatient",
        "tablo15_2_duplicate_exam_10day",
        "tablo15_3_vakabasi_wrong_method",
        "tablo15_4_normal_poliklinik_wrong_method",
    }
    payload = audit.build_audit()
    surface = payload["claim_compliance_surface"]
    assert surface["canonical_evaluator_runtime_ids"] == [
        "analyze_claim:evaluate_rule_findings",
        "compute_patient_billing_report:evaluate_rule_findings",
    ]
    assert surface["generic_projection_runtime_id"] == (
        "compute_patient_billing_report:project_claim_compliance"
    )
    assert "claim_compliance_rule_allowlist" not in payload
    assert "no rule-ID allowlist" in surface["projection_contract"]

    claim_source = audit.CLAIM_COMPLIANCE_PATH.read_text(encoding="utf-8")
    cohort_source = audit.COHORT_COMPLIANCE_PATH.read_text(encoding="utf-8")
    forbidden_symbols = ("_CLAIM_COMPLIANCE_RULES", "ICU_RULE_ID", "DIAGNOSIS_RULE_ID")
    for source in (claim_source, cohort_source):
        assert not any(symbol in source for symbol in forbidden_symbols)
    claim_tree = ast.parse(claim_source)
    project_fn = next(
        node
        for node in claim_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "project_claim_compliance"
    )
    assert not any(
        isinstance(node, ast.Name) and node.id.endswith("RULE_ID")
        for node in ast.walk(project_fn)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id.startswith("detect_")
        for node in ast.walk(project_fn)
    )

    row = next(
        row
        for row in payload["rows"]
        if row.get("runtime_id") == "compute_patient_billing_report:project_claim_compliance"
    )
    assert set(row["emitted_rule_ids_or_kinds"]) == expected
    public_expected = {
        "icu_bundled_leakage_510090",
        "tablo15_8_missing_diagnosis",
        "tablo15_10_unreported_lab_result",
        "tablo15_20_missing_drug_barcode",
        "tablo15_5_material_identity_error",
    }
    assert set(row["public_emitted_rule_ids_or_kinds"]) == public_expected
    assert len(row["draft_hidden_emitted_rule_ids_or_kinds"]) == 7
    assert row["public_visibility_gate"] == "complete-25-v1"
    assert row["recommended_action_surface"] == "claim_compliance"
    assert row["visibility_status"] == "patient_and_cohort_visible"
    assert row["money_semantics"] == "unpriced_compliance"
    assert row["money_fields"] == []
    assert row["included_in_totals"] is False

    for rule_id in public_expected:
        semantic = payload["semantic_findings"][rule_id]
        assert semantic["patient_visible"] is True
        assert semantic["cohort_visible"] is True
        assert semantic["hidden_runtime"] is False

    evaluator = audit.PATIENT_REPORT_META["evaluate_rule_findings"]
    assert evaluator["finding_type"] == "compliance"
    assert evaluator["surface"] == "claim_compliance"
    assert evaluator["patient_ui"] == "ComplianceViewSection#claim-compliance"
    assert evaluator["cohort_api"] == "/compliance-index?surface=claim_compliance"
    assert evaluator["cohort_ui"] == "SUTComplianceDashboard:claim_compliance"
    assert evaluator["money"] == "unpriced_compliance"
    assert evaluator["money_fields"] == []
    assert evaluator["included"] is False
    assert evaluator["visibility"] == "patient_and_cohort_visible"
    assert evaluator["duplicate_group"] == "claim_compliance:patient+cohort"
    assert evaluator["duplicate_status"] == "intentional_cross_view"

    rows_by_runtime_id = {row["runtime_id"]: row for row in payload["rows"] if row["runtime_id"]}
    assert rows_by_runtime_id["analyze_claim:evaluate_rule_findings"]["visibility_status"] == (
        "hidden_runtime"
    )
    assert rows_by_runtime_id[
        "compute_patient_billing_report:evaluate_rule_findings"
    ]["visibility_status"] == "patient_and_cohort_visible"


def test_focused_checkpoint_keeps_draft_review_and_money_hidden() -> None:
    audit = _load_script()
    payload = audit.build_audit()
    focused = payload["focused_wavea_checkpoint"]
    assert focused["detector_groups"] == 18
    assert focused["tracked_rule_ids"] == 32
    assert focused["currently_detector_emittable_rule_ids"] == 29
    assert len(focused["non_emitting_unavailable_rule_ids"]) == 3
    assert focused["review_and_financial_evidence_visibility"] == "draft_gate_hidden"
    assert focused["release_ready"] is False
    broad = payload["broad_wavea_checkpoint"]
    assert broad == {
        "detector_groups": 7,
        "authored_rule_ids": 496,
        "review_and_financial_evidence_visibility": "draft_gate_hidden",
        "release_ready": False,
    }
    # Report totals only. The anaesthesia and companion bed motors left this list when they got action rows
    # (tasks/todo.md, "Action rows for the three showcase faults"), the ICU motor when it did ("Finish the
    # wiring of the four puan motors"), the newborn bed motor when its amount was netted ("Newborn bed motor").
    assert payload["counts"]["aggregate_only_findings"] == 1
    aggregate_only = {
        row["runtime_id"]
        for row in payload["rows"]
        if row.get("runtime_id") and row.get("visibility_status") == "aggregate_only"
    }
    assert aggregate_only == {"compute_patient_billing_report:finalize_report_totals"}

    rows = {row["runtime_id"]: row for row in payload["rows"] if row.get("runtime_id")}
    evidence = rows["compute_patient_billing_report:project_full_wavea_evidence"]
    assert evidence["visibility_status"] == "hidden_runtime"
    assert evidence["money_semantics"] == "informational"
    assert evidence["money_fields"] == []
    assert evidence["included_in_totals"] is False
    focused_confirmed = payload["semantic_findings"]["blood_component_isbt128_barcode"]
    assert focused_confirmed["patient_visible"] is False
    assert focused_confirmed["cohort_visible"] is False
    assert focused_confirmed["hidden_runtime"] is True
    raw_radiation = rows["analyze_claim:detect_radiation_oncology_violations"]
    assert raw_radiation["legacy_monetary_hint_unconfirmed"] is True
    assert raw_radiation["money_semantics"] == "informational"
    assert raw_radiation["included_in_totals"] is False
    radiation = payload["semantic_findings"]["radiation_oncology.course_cap.external_rt_design"]
    assert radiation["patient_visible"] is False
    assert radiation["cohort_visible"] is False
    assert radiation["financial"] is False
    assert radiation["hidden_runtime"] is True


def test_canonical_evaluator_contract_matches_direct_sources_and_rule_order() -> None:
    audit = _load_script()

    assert audit._canonical_evaluator_emissions(
        "src.bilun.domain.billing.rule_findings", "evaluate_rule_findings"
    ) == {
        "icu_bundled_leakage_510090",
        "tablo15_8_missing_diagnosis",
        "tablo15_10_unreported_lab_result",
        "tablo15_20_missing_drug_barcode",
        "tablo15_5_material_identity_error",
    }


def test_drug_indication_canonical_evaluator_is_audited() -> None:
    audit = _load_script()
    payload = audit.build_audit()
    rows = {
        row["runtime_id"]: row
        for row in payload["rows"]
        if row.get("runtime_id")
    }

    analyzer = rows["analyze_claim:evaluate_drug_indication_findings"]
    evaluator = rows[
        "compute_patient_billing_report:evaluate_drug_indication_findings"
    ]
    projection = rows[
        "compute_patient_billing_report:validate_drug_indication_from_claims"
    ]
    assert analyzer["visibility_status"] == "hidden_runtime"
    assert evaluator["visibility_status"] == "patient_and_cohort_visible"
    assert projection["visibility_status"] == "patient_and_cohort_visible"
    assert evaluator["money_semantics"] == "unpriced_compliance"
    assert evaluator["included_in_totals"] is False
    assert evaluator["emitted_rule_ids_or_kinds"] == projection[
        "emitted_rule_ids_or_kinds"
    ]
    assert evaluator["emitted_rule_ids_or_kinds"]


def test_canonical_evaluator_unknown_qualified_detector_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = _load_script()
    fixture = tmp_path / "evaluator.py"
    fixture.write_text(
        "import future.detectors as detector_module\n"
        "\n"
        "_RULE_ORDER = (\"known_rule\",)\n"
        "_REQUIRED_INPUTS = {\"known_rule\": [\"claim_context\"]}\n"
        "_LINE_MAPPING = {\"known_rule\": (\"claim\", None)}\n"
        "_SOURCE_ENGINE = {\"known_rule\": \"detect_known\"}\n"
        "\n"
        "def evaluate_rule_findings(ctx):\n"
        "    return detector_module.detect_unknown(ctx)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "_module_path", lambda module: fixture)

    with pytest.raises(ValueError, match="canonical evaluator"):
        audit._canonical_evaluator_emissions("synthetic.evaluator", "evaluate_rule_findings")


def test_selected_tablo15_findings_are_generic_and_not_hidden() -> None:
    audit = _load_script()
    payload = audit.build_audit()
    selected = {
        "tablo15_10_unreported_lab_result",
        "tablo15_20_missing_drug_barcode",
        "tablo15_5_material_identity_error",
    }
    project = next(
        row
        for row in payload["rows"]
        if row.get("runtime_id") == "compute_patient_billing_report:project_claim_compliance"
    )
    assert selected <= set(project["emitted_rule_ids_or_kinds"])
    assert all(
        payload["semantic_findings"][rule_id]["hidden_runtime"] is False
        for rule_id in selected
    )


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


def test_module_qualified_runtime_call_is_discovered_and_fails_closed(
    tmp_path: Path,
) -> None:
    audit = _load_script()
    known = audit.discover_runtime_calls(audit.ENGINE_PATH, "analyze_claim")
    fixture = tmp_path / "future_engine.py"
    fixture.write_text(
        "import future.rules as rules\n"
        "\n"
        "def analyze_claim(ctx):\n"
        "    return rules.assess_future_rule(ctx)\n",
        encoding="utf-8",
    )
    future = audit.discover_runtime_calls(fixture, "analyze_claim")

    assert {row.callable for row in future} == {"assess_future_rule"}
    assert future[0].module == "future.rules"
    with pytest.raises(ValueError, match="unexpected=.*assess_future_rule"):
        audit.assert_known_runtime_calls("analyze_claim", [*known, *future])


def test_selected_tablo15_findings_are_intentional_cross_view_duplicates() -> None:
    audit = _load_script()
    payload = audit.build_audit()
    selected = {
        "tablo15_10_unreported_lab_result",
        "tablo15_20_missing_drug_barcode",
        "tablo15_5_material_identity_error",
    }
    intended_duplicate_runtime_ids = [
        "compute_patient_billing_report:evaluate_rule_findings",
        "compute_patient_billing_report:project_claim_compliance",
    ]

    for rule_id in selected:
        semantic = payload["semantic_findings"][rule_id]
        assert semantic["duplicate_surfaced"] is True
        assert semantic["duplicate_surface_runtime_ids"] == intended_duplicate_runtime_ids
        assert semantic["financial"] is False
        assert semantic["runtime_ids"] == [
            "analyze_claim:evaluate_rule_findings",
            "compute_patient_billing_report:evaluate_rule_findings",
            "compute_patient_billing_report:project_claim_compliance",
        ]


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

    assert debt["relationship_count"] == len(debt["relationships"])
    assert debt["distinct_overlap_rule_ids_or_kinds"] == len(
        {
            overlap
            for relationship in debt["relationships"]
            for overlap in relationship["overlap_rule_ids_or_kinds"]
        }
    )
    project = [
        row
        for row in debt["relationships"]
        if row["adapter_runtime_id"]
        == "compute_patient_billing_report:project_claim_compliance"
    ]
    assert project == []
    assert all(
        "hard_coded_two_rule_projection_rerun" not in row["debt_flags"]
        for row in debt["relationships"]
    )
    expected_adapters = {
        f"compute_patient_billing_report:{name}"
        for name in audit.EQUIVALENT_EMISSIONS
    }
    assert {
        row["adapter_runtime_id"] for row in debt["relationships"]
    } == expected_adapters
    assert all(row["overlap_count"] > 0 for row in debt["relationships"])

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

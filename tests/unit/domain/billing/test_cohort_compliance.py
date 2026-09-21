"""Unit tests for cache-time cohort compliance index."""

from __future__ import annotations

import pytest

from src.bilun.domain.billing.cohort_compliance import (
    build_cohort_compliance_index,
    empty_cohort_compliance_index,
    slice_compliance_index,
)
from src.bilun.domain.billing.rule_findings import LAB_RULE_ID, build_finding_id

pytestmark = pytest.mark.unit


def _action(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "action_id": "materials:pre_auth",
        "surface": "materials",
        "kind": "material_pre_auth",
        "finding_type": "compliance",
        "claim_id": "F-1",
        "billed_try": 100.0,
        "material_code": "M1",
        "sut_section_id": "3.1.2",
    }
    row.update(overrides)
    return row


def test_mixed_finding_types_keep_only_compliance() -> None:
    reports = {
        "P-A": {
            "recommended_actions": [
                _action(action_id="mat-a", billed_try=40.0),
                {
                    "action_id": "copay:exemption_review",
                    "surface": "copay",
                    "kind": "exemption_review",
                    "finding_type": "opportunity",
                    "billed_try": 999.0,
                },
                {
                    "action_id": "session:uplift",
                    "surface": "session_uplift",
                    "kind": "session_uplift",
                    "finding_type": "opportunity",
                    "billed_try": 50.0,
                },
            ]
        },
        "P-B": {
            "recommended_actions": [
                _action(
                    action_id="lab-b",
                    surface="lab",
                    kind="hemogram_bundling",
                    billed_try=12.5,
                    material_code=None,
                    procedure_code="L107020",
                )
            ]
        },
        "P-C": {"recommended_actions": []},
    }

    index = build_cohort_compliance_index(reports)

    assert index["artifacts_available"] is True
    assert index["n_patients"] == 3
    assert index["n_findings"] == 2
    assert index["n_patients_with_findings"] == 2
    assert index["billed_at_risk_try"] == 52.5
    surfaces = {row["surface"] for row in index["rows"]}
    assert surfaces == {"materials", "lab"}
    assert all(row["finding_type"] == "compliance" for row in index["rows"])
    kinds = {row["kind"] for row in index["rows"]}
    assert "material_pre_auth" in kinds
    assert "hemogram_bundling" in kinds


def test_drug_indication_action_keeps_canonical_identity_and_no_money() -> None:
    finding_id = "drug_indication:P-DRUG:C-1:D-1:indication_mismatch"
    index = build_cohort_compliance_index(
        {
            "P-DRUG": {
                "recommended_actions": [
                    _action(
                        action_id=finding_id,
                        surface="drug_indication",
                        kind="indication_mismatch",
                        claim_id="C-1",
                        billed_try=None,
                        material_code=None,
                        drug_code="A1",
                        drug_name="ORENCIA",
                        drug_claim_line_id="D-1",
                        finding_id=finding_id,
                        severity="error",
                        applicability_status="indication_mismatch",
                        evaluation_status="evaluated",
                        observed_icd10_codes=["E66.9"],
                        matched_icd10_codes=[],
                        unmatched_icd10_codes=["E66.9"],
                        eligible_routes=[{"rule_id": "r1", "icd10_codes": ["M06"]}],
                        recommended_action_tr="Tanı ve raporu kontrol edin.",
                    )
                ]
            }
        }
    )

    row = index["rows"][0]
    assert row["finding_id"] == row["action_id"] == finding_id
    assert row["drug_claim_line_id"] == "D-1"
    assert row["observed_icd10_codes"] == ["E66.9"]
    assert row["eligible_routes"] == [{"rule_id": "r1", "icd10_codes": ["M06"]}]
    assert row["severity"] == "error"
    assert row["recommended_action_tr"] == "Tanı ve raporu kontrol edin."
    assert row["billed_try"] is None
    assert index["billed_at_risk_try"] == 0.0
    assert index["by_surface"]["drug_indication"]["billed_try"] is None

    filtered = slice_compliance_index(index, surface="drug_indication")
    assert filtered["by_surface"]["drug_indication"]["billed_try"] is None
    assert filtered["billed_at_risk_try"] is None


def test_optional_override_excluded_mandatory_mapped_to_payment_methods() -> None:
    reports = {
        "P-PAY": {
            "recommended_actions": [
                {
                    "action_id": "strategy:optional",
                    "surface": "billing_strategy",
                    "kind": "optional_override",
                    "finding_type": "opportunity",
                    "billed_try": 80.0,
                },
                {
                    "action_id": "strategy:mandatory",
                    "surface": "billing_strategy",
                    "kind": "mandatory_compliance",
                    "finding_type": "compliance",
                    "billed_try": 25.0,
                    "procedure_code": "P99",
                },
            ]
        }
    }

    index = build_cohort_compliance_index(reports)
    assert index["n_findings"] == 1
    row = index["rows"][0]
    assert row["surface"] == "payment_methods"
    assert row["source_surface"] == "billing_strategy"
    assert row["kind"] == "mandatory_compliance"
    assert index["by_surface"]["payment_methods"]["n"] == 1
    assert index["by_surface"]["materials"]["n"] == 0


def test_late_legacy_money_after_more_than_100_null_findings() -> None:
    findings = []
    for i in range(101):
        claim_id = f"C-{i}"
        finding_id = build_finding_id(
            rule_id="tablo15_8_missing_diagnosis",
            patient_id="P-NEW",
            claim_id=claim_id,
            line_kind="claim",
            line_id=None,
        )
        findings.append({
            "finding_id": finding_id,
            "action_id": finding_id,
            "patient_id": "P-NEW",
            "claim_id": claim_id,
            "rule_id": "tablo15_8_missing_diagnosis",
            "line_kind": "claim",
            "line_id": None,
        })
    legacy = {"P-LEGACY": {"recommended_actions": [_action(billed_try=123.45)]}}
    baseline = build_cohort_compliance_index(legacy)
    reports = {"P-NEW": {"claim_compliance": {"findings": findings}}, **legacy}

    index = build_cohort_compliance_index(reports)
    for result in (index, slice_compliance_index(index)):
        assert result["n_findings"] == 102
        assert result["billed_at_risk_try"] == baseline["billed_at_risk_try"] == 123.45
        assert result["by_surface"]["materials"] == baseline["by_surface"]["materials"]
        assert result["by_surface"]["claim_compliance"]["billed_try"] is None
        assert result["rows"][-1] == baseline["rows"][0]
        assert all(
            row[field] is None
            for row in result["rows"][:101]
            for field in (
                "amount_try", "billed_try", "payable_try", "savings_try",
                "recoverable_uplift_try", "compliance_savings_try",
                "risk_amount_try", "audit_exposure_try",
            )
        )
    assert reports["P-LEGACY"] == legacy["P-LEGACY"]


def test_wave_a_lab_finding_projects_through_generic_cohort_surface() -> None:
    finding_id = build_finding_id(
        rule_id=LAB_RULE_ID,
        patient_id="P-LAB",
        claim_id="C-LAB",
        line_kind="procedure",
        line_id="PROC-LAB",
    )
    reports = {
        "P-LAB": {
            "claim_compliance": {
                "findings": [
                    {
                        "finding_id": finding_id,
                        "action_id": finding_id,
                        "patient_id": "P-LAB",
                        "claim_id": "C-LAB",
                        "rule_id": LAB_RULE_ID,
                        "line_kind": "procedure",
                        "line_id": "PROC-LAB",
                        "procedure_line_id": "PROC-LAB",
                        "detail": "Lab result was not reported.",
                    }
                ]
            }
        }
    }

    index = build_cohort_compliance_index(reports)

    assert index["by_surface"]["claim_compliance"]["n"] == 1
    assert index["rows"][0]["finding_id"] == finding_id


def test_future_rule_finding_projects_without_cohort_rule_registration() -> None:
    finding_id = "canonical-future-finding-id"
    reports = {
        "P-FUTURE": {
            "claim_compliance": {
                "findings": [
                    {
                        "finding_id": finding_id,
                        "action_id": finding_id,
                        "patient_id": "P-FUTURE",
                        "claim_id": "C-FUTURE",
                        "rule_id": "future_rule_added_after_cohort_code",
                        "line_kind": "procedure",
                        "line_id": "PROC-FUTURE",
                        "procedure_line_id": "PROC-FUTURE",
                        "procedure_code": "FUT-1",
                        "procedure_name": "Future procedure",
                        "severity": "warning",
                        "detail": "Future canonical finding.",
                        "source": "canonical-rule-engine",
                        "provenance": {"version": "future"},
                        "surface": "claim_compliance",
                        "finding_type": "compliance",
                    }
                ]
            }
        }
    }

    index = build_cohort_compliance_index(reports)
    row = index["rows"][0]

    assert row["finding_id"] == row["action_id"] == finding_id
    assert row["rule_id"] == "future_rule_added_after_cohort_code"
    assert row["procedure_line_id"] == "PROC-FUTURE"
    assert row["severity"] == "warning"
    assert row["detail"] == "Future canonical finding."
    assert row["source"] == "canonical-rule-engine"
    assert row["provenance"] == {"version": "future"}
    assert row["surface"] == "claim_compliance"
    assert row["finding_type"] == "compliance"
    assert all(row[field] is None for field in (
        "amount_try", "billed_try", "payable_try", "savings_try",
        "recoverable_uplift_try", "compliance_savings_try",
        "risk_amount_try", "audit_exposure_try",
    ))


def test_wave_a_findings_preserve_source_metadata_and_null_money() -> None:
    specs = (
        (
            "tablo15_10_unreported_lab_result", "procedure", "PROC-LAB",
            "procedure_line_id", {"procedure_code": "L-1", "procedure_name": "Lab"},
        ),
        (
            "tablo15_20_missing_drug_barcode", "drug", "DRUG-1",
            "drug_claim_line_id", {"drug_code": "D-1"},
        ),
        (
            "tablo15_5_material_identity_error", "material", "MAT-1",
            "material_line_id", {"material_code": "M-1", "material_name": "Material"},
        ),
    )
    findings = []
    for rule_id, line_kind, line_id, line_id_field, metadata in specs:
        finding_id = build_finding_id(
            rule_id=rule_id,
            patient_id="P-WAVE-A",
            claim_id="C-WAVE-A",
            line_kind=line_kind,
            line_id=line_id,
        )
        findings.append({
            "finding_id": finding_id,
            "action_id": finding_id,
            "patient_id": "P-WAVE-A",
            "claim_id": "C-WAVE-A",
            "rule_id": rule_id,
            "line_kind": line_kind,
            "line_id": line_id,
            line_id_field: line_id,
            "detail": rule_id,
            "sut_section_id": "SUT",
            **metadata,
        })
    reports = {
        "P-WAVE-A": {
            "recommended_actions": [_action(action_id="legacy", billed_try=77.25)],
            "claim_compliance": {"findings": findings},
        }
    }

    index = build_cohort_compliance_index(reports)
    claim_rows = [row for row in index["rows"] if row["surface"] == "claim_compliance"]

    assert len(claim_rows) == 3
    assert index["by_surface"]["claim_compliance"] == {
        "n": 3, "billed_try": None, "n_patients": 1,
    }
    assert index["billed_at_risk_try"] == 77.25
    assert index["by_surface"]["materials"]["billed_try"] == 77.25
    assert {(row["rule_id"], row["line_kind"], row["line_id"]) for row in claim_rows} == {
        (rule_id, line_kind, line_id) for rule_id, line_kind, line_id, _, _ in specs
    }
    by_rule = {row["rule_id"]: row for row in claim_rows}
    assert by_rule["tablo15_10_unreported_lab_result"]["procedure_line_id"] == "PROC-LAB"
    assert by_rule["tablo15_10_unreported_lab_result"]["procedure_code"] == "L-1"
    assert by_rule["tablo15_20_missing_drug_barcode"]["drug_claim_line_id"] == "DRUG-1"
    assert by_rule["tablo15_20_missing_drug_barcode"]["drug_code"] == "D-1"
    assert by_rule["tablo15_5_material_identity_error"]["material_line_id"] == "MAT-1"
    assert by_rule["tablo15_5_material_identity_error"]["material_code"] == "M-1"
    for row in claim_rows:
        assert all(
            row[field] is None
            for field in (
                "amount_try", "billed_try", "payable_try", "savings_try",
                "recoverable_uplift_try", "compliance_savings_try",
                "risk_amount_try", "audit_exposure_try",
            )
        )


def test_claim_compliance_dedupes_and_drops_noncanonical_rows() -> None:
    rule_id = "tablo15_20_missing_drug_barcode"
    finding_id = build_finding_id(
        rule_id=rule_id,
        patient_id="P-STRICT",
        claim_id="C-STRICT",
        line_kind="drug",
        line_id="DRUG-STRICT",
    )
    canonical = {
        "finding_id": finding_id,
        "action_id": finding_id,
        "patient_id": "P-STRICT",
        "claim_id": "C-STRICT",
        "rule_id": rule_id,
        "line_kind": "drug",
        "line_id": "DRUG-STRICT",
        "drug_claim_line_id": "DRUG-STRICT",
        "drug_code": "D-STRICT",
    }
    malformed = [
        dict(canonical, patient_id="P-OTHER"),
        dict(canonical, claim_id=""),
        dict(canonical, rule_id=""),
        dict(canonical, line_kind="unsupported"),
        dict(canonical, line_kind="procedure"),
        dict(canonical, line_id="DRUG-OTHER"),
        dict(canonical, procedure_line_id="PROC-OTHER"),
        dict(canonical, finding_id=""),
        dict(canonical, action_id="wrong-action-id"),
    ]
    reports = {
        "P-STRICT": {
            "claim_compliance": {
                "findings": [canonical, dict(canonical), *malformed],
            }
        }
    }

    index = build_cohort_compliance_index(reports)
    rows = [row for row in index["rows"] if row["surface"] == "claim_compliance"]

    assert len(rows) == 1
    assert rows[0]["finding_id"] == rows[0]["action_id"] == finding_id


def test_claim_compliance_evaluations_are_generic_validated_and_deduped_by_rule_and_claim() -> None:
    canonical = {
        "patient_id": "P-EVAL",
        "claim_id": "C-EVAL",
        "rule_id": "future_evaluation_rule",
        "status": "evaluated",
        "evaluation_status": "evaluated",
        "required_inputs": [],
        "missing_inputs": [],
    }
    reports = {
        "P-EVAL": {
            "claim_compliance": {
                "evaluations": [
                    canonical,
                    dict(canonical),
                    dict(canonical, patient_id="P-OTHER"),
                    dict(canonical, claim_id=""),
                    dict(canonical, rule_id=""),
                    dict(canonical, status="invalid"),
                    dict(canonical, evaluation_status="missing_inputs"),
                    dict(canonical, required_inputs="future_input"),
                    dict(canonical, missing_inputs=[1]),
                    {
                        "patient_id": "P-EVAL",
                        "claim_id": "C-MISSING",
                        "rule_id": "future_missing_rule",
                        "status": "missing_input",
                        "evaluation_status": "missing_inputs",
                        "required_inputs": ["future_input"],
                        "missing_inputs": ["future_input"],
                    },
                ]
            }
        }
    }

    summary = slice_compliance_index(
        build_cohort_compliance_index(reports),
        surface="claim_compliance",
    )["claim_compliance"]

    assert summary["counts"] == {
        "evaluated": 1,
        "missing_inputs": 1,
        "unavailable": 0,
    }
    assert summary["non_evaluated_total"] == 1
    assert summary["details"][0]["rule_id"] == "future_missing_rule"
    assert summary["details"][0]["status"] == "missing_inputs"


def test_claim_compliance_preserves_legitimate_null_claim_missing_input_evaluation() -> None:
    reports = {
        "P-MISSING-CONTEXT": {
            "claim_compliance": {
                "evaluations": [
                    {
                        "patient_id": "P-MISSING-CONTEXT",
                        "claim_id": None,
                        "rule_id": "future_context_rule",
                        "status": "missing_inputs",
                        "evaluation_status": "missing_inputs",
                        "required_inputs": ["claim_context"],
                        "missing_inputs": ["claim_context"],
                    },
                    {
                        "patient_id": "P-MISSING-CONTEXT",
                        "claim_id": "C-AVAILABLE",
                        "rule_id": "future_context_rule",
                        "status": "evaluated",
                        "evaluation_status": "evaluated",
                        "required_inputs": ["claim_context"],
                        "missing_inputs": [],
                    },
                ]
            }
        }
    }

    summary = slice_compliance_index(
        build_cohort_compliance_index(reports),
        surface="claim_compliance",
    )["claim_compliance"]

    assert summary["counts"] == {
        "evaluated": 1,
        "missing_inputs": 1,
        "unavailable": 0,
    }
    assert summary["non_evaluated_total"] == 1
    assert summary["details"] == [
        {
            "patient_id": "P-MISSING-CONTEXT",
            "claim_id": None,
            "rule_id": "future_context_rule",
            "status": "missing_inputs",
            "evaluation_status": "missing_inputs",
            "required_inputs": ["claim_context"],
            "missing_inputs": ["claim_context"],
            "surface": "claim_compliance",
        }
    ]


def test_claim_compliance_rejects_malformed_null_claim_evaluation() -> None:
    reports = {
        "P-MALFORMED": {
            "claim_compliance": {
                "evaluations": [
                    {
                        "patient_id": "P-MALFORMED",
                        "claim_id": None,
                        "rule_id": "future_context_rule",
                        "status": "evaluated",
                        "evaluation_status": "evaluated",
                        "required_inputs": ["claim_context"],
                        "missing_inputs": [],
                    },
                    {
                        "patient_id": "P-MALFORMED",
                        "claim_id": None,
                        "rule_id": "future_context_rule_without_metadata",
                        "status": "missing_inputs",
                        "evaluation_status": "missing_inputs",
                        "required_inputs": [],
                        "missing_inputs": [],
                    },
                ]
            }
        }
    }

    summary = slice_compliance_index(
        build_cohort_compliance_index(reports),
        surface="claim_compliance",
    )["claim_compliance"]

    assert summary["counts"] == {
        "evaluated": 0,
        "missing_inputs": 0,
        "unavailable": 0,
    }
    assert summary["details"] == []


def test_k21_k26_claim_contract_compatibility() -> None:
    specs = (
        ("icu_bundled_leakage_510090", "procedure", "PROC-K21", "procedure_line_id"),
        ("tablo15_8_missing_diagnosis", "claim", None, None),
    )
    findings = []
    for rule_id, line_kind, line_id, line_id_field in specs:
        finding_id = build_finding_id(
            rule_id=rule_id,
            patient_id="P-LEGACY-RULES",
            claim_id="C-LEGACY-RULES",
            line_kind=line_kind,
            line_id=line_id,
        )
        row = {
            "finding_id": finding_id,
            "action_id": finding_id,
            "patient_id": "P-LEGACY-RULES",
            "claim_id": "C-LEGACY-RULES",
            "rule_id": rule_id,
            "line_kind": line_kind,
            "line_id": line_id,
        }
        if line_id_field is not None:
            row[line_id_field] = line_id
        findings.append(row)

    index = build_cohort_compliance_index({
        "P-LEGACY-RULES": {"claim_compliance": {"findings": findings}}
    })
    rows = [row for row in index["rows"] if row["surface"] == "claim_compliance"]

    assert [(row["rule_id"], row["line_kind"], row["line_id"]) for row in rows] == [
        ("icu_bundled_leakage_510090", "procedure", "PROC-K21"),
        ("tablo15_8_missing_diagnosis", "claim", None),
    ]


def test_materials_kinds_preserved() -> None:
    reports = {
        "P-MAT": {
            "recommended_actions": [
                _action(kind="material_pre_auth", action_id="a"),
                _action(kind="material_miat", action_id="b", billed_try=10),
                _action(kind="material_bundling", action_id="c", billed_try=5),
            ]
        }
    }
    index = build_cohort_compliance_index(reports)
    assert [row["kind"] for row in index["rows"]] == [
        "material_pre_auth",
        "material_miat",
        "material_bundling",
    ]


def test_copay_compliance_rows_excluded() -> None:
    reports = {
        "P-COP": {
            "recommended_actions": [
                {
                    "action_id": "copay:exemption_review",
                    "surface": "copay",
                    "kind": "exemption_review",
                    "finding_type": "compliance",
                    "billed_try": 30.0,
                }
            ]
        }
    }
    index = build_cohort_compliance_index(reports)
    assert index["n_findings"] == 0
    assert index["rows"] == []


def test_unavailable_payload_has_null_counts_not_zeros() -> None:
    payload = empty_cohort_compliance_index(artifacts_available=False)
    assert payload["artifacts_available"] is False
    assert payload["n_findings"] is None
    assert payload["billed_at_risk_try"] is None
    assert payload["by_surface"] == {}
    assert payload["rows"] == []
    sliced = slice_compliance_index(payload, surface="claim_compliance")
    assert sliced["artifacts_available"] is False
    assert sliced["claim_compliance"] is None
    assert sliced["billed_at_risk_try"] is None
    assert sliced["by_surface"] == {}


def test_slice_filters_surface_and_patient() -> None:
    reports = {
        "P-A": {"recommended_actions": [_action(action_id="a", billed_try=10)]},
        "P-B": {
            "recommended_actions": [
                _action(
                    action_id="b",
                    surface="lab",
                    kind="hemogram_bundling",
                    billed_try=7,
                    material_code=None,
                )
            ]
        },
    }
    index = build_cohort_compliance_index(reports)
    sliced = slice_compliance_index(
        index, surface="materials", patient_ids=frozenset({"P-A"}), limit=10
    )
    assert sliced["n_findings"] == 1
    assert sliced["rows"][0]["patient_id"] == "P-A"
    assert sliced["pagination"]["total_matching"] == 1
    assert sliced["pagination"]["has_more"] is False


def test_claim_compliance_evaluation_summary_is_exact_bounded_and_filterable() -> None:
    reports = {}
    for patient_index in range(30):
        patient_id = f"P-{patient_index:02d}"
        evaluations = [
            {
                "patient_id": patient_id,
                "claim_id": f"CLEAN-{patient_index:02d}",
                "rule_id": "icu_bundled_leakage_510090",
                "status": "evaluated",
                "evaluation_status": "evaluated",
                "required_inputs": [],
                "missing_inputs": [],
            }
            for _ in range(10)
        ]
        evaluations.append({
            "patient_id": patient_id,
            "claim_id": f"MISSING-{patient_index:02d}",
            "rule_id": "tablo15_8_missing_diagnosis",
            "status": "missing_inputs",
            "evaluation_status": "missing_inputs",
            "required_inputs": ["primary_icd10"],
            "missing_inputs": ["primary_icd10"],
        })
        reports[patient_id] = {"claim_compliance": {"findings": [], "evaluations": evaluations}}

    index = build_cohort_compliance_index(reports)
    assert "evaluations" not in index["claim_compliance"]

    sliced = slice_compliance_index(index, surface="claim_compliance", limit=1)
    summary = sliced["claim_compliance"]
    assert summary["counts"] == {"evaluated": 30, "missing_inputs": 30, "unavailable": 0}
    assert summary["non_evaluated_total"] == 30
    assert len(summary["details"]) <= 20
    assert summary["details_truncated"] is True
    assert summary["evaluations"] == []
    assert not any("CLEAN-" in str(value) for value in summary.values())

    filtered = slice_compliance_index(
        index,
        surface="claim_compliance",
        patient_ids=frozenset({"P-29"}),
        limit=1,
    )["claim_compliance"]
    assert filtered["counts"] == {"evaluated": 1, "missing_inputs": 1, "unavailable": 0}
    assert filtered["non_evaluated_total"] == 1
    assert filtered["details_truncated"] is True
    assert filtered["evaluations"] == []

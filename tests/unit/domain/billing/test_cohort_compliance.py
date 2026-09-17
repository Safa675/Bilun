"""Unit tests for cache-time cohort compliance index."""

from __future__ import annotations

import pytest

from src.bilun.domain.billing.cohort_compliance import (
    build_cohort_compliance_index,
    empty_cohort_compliance_index,
    slice_compliance_index,
)

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
    findings = [
        {
            "patient_id": "P-NEW",
            "claim_id": f"C-{i}",
            "rule_id": "tablo15_8_missing_diagnosis",
        }
        for i in range(101)
    ]
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

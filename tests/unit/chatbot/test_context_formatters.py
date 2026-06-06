"""Snapshot-style tests for SUT context formatters."""

from __future__ import annotations

import pytest

from src.bilun.chatbot.context import (
    build_billing_context,
    build_cohort_context,
    build_full_billing_context,
    build_patient_context,
)

pytestmark = pytest.mark.unit


def _sample_cohort_data() -> dict:
    return {
        "optimization_summary": {
            "status": "ready",
            "summary": {
                "copay_exemptions": {
                    "n_exempt_patients": 2,
                    "n_total_patients": 10,
                    "exemption_rate": 0.2,
                    "top_diseases": [
                        {"disease": "Diabetes", "count": 2},
                    ],
                },
                "surcharge_exposure": {
                    "exactness_status": "missing_exact_inputs",
                    "unavailable_reason": "exact_claim_lines_missing",
                    "required_inputs_missing": ["procedure_claim_lines"],
                },
            },
        }
    }


def _sample_patient_data() -> dict:
    return {
        "patient_outcome": {
            "status": "ready",
            "summary": {
                "patient_id": "P-001",
                "drg_summary": {
                    "n_episodes": 1,
                    "total_drg_package_price": 1200.0,
                    "pricing_status": "exact",
                },
            },
        },
        "patient_optimization": {
            "status": "ready",
            "summary": {
                "copay_exemptions": {
                    "exempt": True,
                    "qualifying_diagnoses": [
                        {"disease": "Diabetes", "icd10": "E11"},
                    ],
                },
            },
        },
    }


def _sample_billing_report() -> dict:
    return {
        "patient_id": "P-001",
        "lab": {
            "exactness_status": "exact",
            "rule_source": "EK-2B hemogram bundling",
            "hemogram_bundling_savings": 100.0,
            "flagged_tests": [
                {"test_name": f"Test-{index}", "flag_type": "hemogram_unbundling", "savings_try": index}
                for index in range(8)
            ],
        },
        "copay": {
            "exactness_status": "exact",
            "is_exempt": True,
            "total_copay_savings_try": 75.0,
        },
        "total_recoverable_try": 225.0,
        "priority": "high",
    }


def test_build_cohort_context_includes_exemption_and_unavailable_surcharge():
    text = build_cohort_context(_sample_cohort_data())
    assert "--- COHORT OPTIMIZATION ---" in text
    assert "2/10 patients exempt" in text
    assert "Diabetes" in text
    assert "Surcharge exposure: UNAVAILABLE" in text
    assert "exact_claim_lines_missing" in text


def test_build_patient_context_includes_drg_and_copay_exemption():
    text = build_patient_context(_sample_patient_data())
    assert "--- PATIENT CONTEXT ---" in text
    assert "Patient ID: P-001" in text
    assert "Total DRG package price: 1200.00 TRY" in text
    assert "Copay exempt: YES" in text
    assert "Diabetes (E11)" in text


def test_billing_summary_caps_flagged_tests_while_full_includes_all():
    report = _sample_billing_report()
    summary = build_billing_context({"billing_report": {"status": "ready", "summary": report}})
    full = build_full_billing_context(report)

    assert "--- BILLING OPTIMIZATION ---" in summary
    assert "BILLING OPTIMIZATION (FULL)" in full
    assert "Test-0" in summary
    assert "Test-7" not in summary
    assert "... and 3 more" in summary
    assert "Test-7" in full
    assert "Patient ID: P-001" in full

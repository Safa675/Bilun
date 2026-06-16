"""Cohort billing flow uses SUTClaimDataset claim-line context."""

from __future__ import annotations

import polars as pl
import pytest

from src.bilun.domain.billing.orchestrator import compute_all_billing_reports
from src.bilun.domain.claims import load_sut_claim_dataset

pytestmark = pytest.mark.unit


def test_compute_all_billing_reports_builds_claim_context_from_dataset() -> None:
    dataset = load_sut_claim_dataset()
    patient_id = next(
        pid
        for pid, claims in dataset.claims_by_patient.items()
        if claims and dataset.procedure_lines_by_patient.get(pid)
    )

    reports, summary = compute_all_billing_reports(
        {
            "sut_claim_dataset": dataset,
            "sut_by_pid": {patient_id: dataset.patient_totals[patient_id]},
            "patient_alerts_cache": {
                "patients": [
                    {
                        "patient_id": patient_id,
                        "copay_exemption": {
                            "exempt": False,
                            "n_qualifying": 0,
                            "qualifying_diagnoses": [],
                        },
                        "icd10_chapters": [],
                    }
                ]
            },
            "lab_df_pl": pl.DataFrame(),
        }
    )

    report = reports[patient_id]
    assert report.copay.exactness_status == "exact"
    assert report.billing_strategy.exactness_status == "exact"
    assert report.session_uplift.exactness_status == "exact"
    assert report.medula_rejection_ingest_available is True
    assert summary.n_patients == 1
    assert summary.medula_rejection_ingest_available is True
    assert summary.total_sgk_uplift == round(
        sum(item.sgk_uplift_try for item in reports.values()),
        2,
    )
    assert summary.savings_by_category["sgk_uplift"] == summary.total_sgk_uplift


def test_compute_all_billing_reports_without_dataset_marks_missing_inputs() -> None:
    reports, summary = compute_all_billing_reports(
        {
            "sut_by_pid": {"P1": {"total_try": 0}},
            "patient_alerts_cache": {
                "patients": [
                    {
                        "patient_id": "P1",
                        "copay_exemption": {
                            "exempt": False,
                            "n_qualifying": 0,
                            "qualifying_diagnoses": [],
                        },
                        "icd10_chapters": ["I"],
                    }
                ]
            },
            "lab_df_pl": pl.DataFrame(),
        }
    )

    report = reports["P1"]
    assert report.exactness_status == "missing_exact_inputs"
    assert report.total_recoverable_try == 0.0
    assert report.copay.exactness_status == "missing_exact_inputs"
    assert summary.exactness_status == "missing_exact_inputs"

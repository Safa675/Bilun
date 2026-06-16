"""Cohort optimization summary with claim dataset integration."""

from __future__ import annotations

import polars as pl
import pytest

from src.bilun.domain.claims import load_sut_claim_dataset
from src.bilun.domain.optimization.aggregator import compute_optimization_summary

pytestmark = pytest.mark.unit


def test_optimization_summary_exact_with_claim_dataset() -> None:
    dataset = load_sut_claim_dataset()
    patient_ids = sorted(dataset.patient_totals.keys())[:5]

    diagnoses_by_pid = {
        pid: [diag.icd10_code for diag in dataset.diagnoses_by_patient.get(pid, ())]
        for pid in patient_ids
    }
    ana_df = pl.DataFrame(
        {
            "patient_id": patient_ids,
            "TANIKODU": [diagnoses_by_pid[pid][0] if diagnoses_by_pid[pid] else "R69" for pid in patient_ids],
        }
    )

    summary = compute_optimization_summary(
        ana_df,
        patient_ids,
        diagnoses_by_pid=diagnoses_by_pid,
        claim_dataset=dataset,
    )

    assert summary["surcharge_exposure"]["exactness_status"] == "exact"
    assert summary["copay_rate_exposure"]["exactness_status"] == "exact"
    assert summary["drg_unbundling"]["exactness_status"] == "exact"
    assert summary["drug_discount_validation"]["exactness_status"] == "exact"
    assert summary["drug_discount_validation"]["n_drug_lines"] > 0
    assert summary["surcharge_exposure"]["n_total_ek2g"] > 0


def test_optimization_summary_includes_bill_level_copay_exemptions() -> None:
    dataset = load_sut_claim_dataset()
    patient_ids = sorted(dataset.patient_totals.keys())[:5]

    diagnoses_by_pid = {
        pid: [diag.icd10_code for diag in dataset.diagnoses_by_patient.get(pid, ())]
        for pid in patient_ids
    }
    ana_df = pl.DataFrame(
        {
            "patient_id": patient_ids,
            "TANIKODU": [
                diagnoses_by_pid[pid][0] if diagnoses_by_pid[pid] else "R69"
                for pid in patient_ids
            ],
        }
    )

    summary = compute_optimization_summary(
        ana_df,
        patient_ids,
        diagnoses_by_pid=diagnoses_by_pid,
        claim_dataset=dataset,
    )
    copay = summary["copay_exemptions"]
    assert copay["n_total_bills"] > 0
    assert copay["n_total_bills"] >= copay["n_total_patients"]
    assert 0 <= copay["n_exempt_bills"] <= copay["n_total_bills"]
    assert copay["exemption_rate_bills"] == pytest.approx(
        copay["n_exempt_bills"] / copay["n_total_bills"], abs=1e-4
    )
    assert isinstance(copay["exemption_by_category_bills"], list)
    assert sum(c["count"] for c in copay["exemption_by_category_bills"]) >= copay[
        "n_exempt_bills"
    ]

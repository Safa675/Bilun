"""Cohort optimization summary with claim dataset integration.

Expected counts come from the cohort registry (`tests/fixtures/synthetic_cohort.py`, written by the
generator, independent of the loader), from the loaded claim dataset, and from the summary of each
patient on their own: the cohort summary must be the sum of the single-patient summaries for every
additive field. No count is a "greater than zero" floor.
"""

from __future__ import annotations

from typing import Any

import polars as pl
import pytest

from src.bilun.domain.claims import SUTClaimDataset, load_sut_claim_dataset
from src.bilun.domain.optimization.aggregator import compute_optimization_summary
from tests.fixtures import synthetic_cohort as cohort
from tests.fixtures.session_cache import SessionCache

pytestmark = pytest.mark.unit

_EXACT_SECTIONS = (
    "surcharge_exposure",
    "copay_rate_exposure",
    "drg_unbundling",
    "drug_discount_validation",
)
# (section, field) of the summary that add up over patients.
_ADDITIVE_FIELDS = (
    ("copay_exemptions", "n_total_patients"),
    ("copay_exemptions", "n_total_bills"),
    ("copay_exemptions", "n_exempt_bills"),
    ("surcharge_exposure", "n_total_ek2g"),
    ("copay_rate_exposure", "n_total_ek2c1"),
    ("drg_unbundling", "n_patients_with_risk"),
    ("drg_unbundling", "total_potential_savings"),
)


def _summary(dataset: SUTClaimDataset, patient_ids: list[str]) -> dict[str, Any]:
    diagnoses_by_pid = {
        pid: [diag.icd10_code for diag in dataset.diagnoses_by_patient.get(pid, ())]
        for pid in patient_ids
    }
    ana_df = pl.DataFrame(
        {
            "patient_id": patient_ids,
            "TANIKODU": [
                diagnoses_by_pid[pid][0] if diagnoses_by_pid[pid] else "R69" for pid in patient_ids
            ],
        }
    )
    return compute_optimization_summary(
        ana_df,
        patient_ids,
        diagnoses_by_pid=diagnoses_by_pid,
        claim_dataset=dataset,
    )


@pytest.fixture(scope="module")
def dataset() -> SUTClaimDataset:
    return load_sut_claim_dataset()


@pytest.fixture(scope="module")
def single_summaries(dataset: SUTClaimDataset, session_cache: SessionCache) -> dict[str, dict[str, Any]]:
    """The summary of each patient on their own (built once per session, a copy for the module)."""
    return session_cache.get(
        "cohort_claim_integration_single_summaries",
        lambda: {pid: _summary(dataset, [pid]) for pid in sorted(dataset.patient_totals)},
    )


@pytest.fixture(scope="module")
def cohort_summary(dataset: SUTClaimDataset, session_cache: SessionCache) -> dict[str, Any]:
    """`_summary(dataset, <every patient>)`: the summary of the whole cohort (built once per session)."""
    return session_cache.get(
        "cohort_claim_integration_cohort_summary",
        lambda: _summary(dataset, sorted(dataset.patient_totals)),
    )


def _sum_of_singles(
    singles: dict[str, dict[str, Any]], patient_ids: list[str], section: str, field: str
) -> Any:
    return sum(singles[pid][section][field] for pid in patient_ids)


def test_optimization_summary_exact_with_claim_dataset(
    dataset: SUTClaimDataset,
    single_summaries: dict[str, dict[str, Any]],
    cohort_summary: dict[str, Any],
) -> None:
    patient_ids = sorted(dataset.patient_totals)
    assert patient_ids == cohort.patient_ids()

    summary = cohort_summary  # _summary(dataset, patient_ids)

    for section in _EXACT_SECTIONS:
        assert summary[section]["exactness_status"] == "exact", section
    counts = cohort.counts()
    # Every procedure line of every patient is counted once, by the surcharge and copay-rate motors.
    assert summary["surcharge_exposure"]["n_total_ek2g"] == counts["procedure_claim_lines.parquet"]
    assert (
        summary["copay_rate_exposure"]["n_total_ek2c1"] == counts["procedure_claim_lines.parquet"]
    )
    assert summary["drg_unbundling"]["n_patients_checked"] == len(patient_ids)
    drugs = summary["drug_discount_validation"]
    assert drugs["n_total_patients"] == len(patient_ids)
    assert drugs["n_drug_lines"] == counts["drug_claim_lines.parquet"]
    assert drugs["n_evaluable_lines"] == sum(
        line.billed_amount_try > 0 for line in dataset.drug_lines.values()
    )
    for section, field in _ADDITIVE_FIELDS:
        assert summary[section][field] == pytest.approx(
            _sum_of_singles(single_summaries, patient_ids, section, field)
        ), (section, field)


def test_optimization_summary_counts_only_the_requested_patients(
    dataset: SUTClaimDataset, single_summaries: dict[str, dict[str, Any]]
) -> None:
    everyone = sorted(single_summaries)
    patient_ids = everyone[:3]
    lines = sum(len(dataset.procedure_lines_by_patient.get(pid, ())) for pid in patient_ids)
    bills = sum(len(dataset.claims_by_patient.get(pid, ())) for pid in patient_ids)
    # The patients left out must hold part of the cohort's lines and bills, or the test shows nothing.
    assert 0 < lines < len(dataset.procedure_lines)
    assert 0 < bills < len(dataset.claims)

    summary = _summary(dataset, patient_ids)

    assert summary["surcharge_exposure"]["n_total_ek2g"] == lines
    assert summary["copay_rate_exposure"]["n_total_ek2c1"] == lines
    assert summary["copay_exemptions"]["n_total_bills"] == bills
    assert summary["drg_unbundling"]["n_patients_checked"] == len(patient_ids)
    for section, field in _ADDITIVE_FIELDS:
        expected = _sum_of_singles(single_summaries, patient_ids, section, field)
        assert summary[section][field] == pytest.approx(expected), (section, field)
        # The patients left out add to every field, so a summary that ignored the list would differ.
        assert expected < _sum_of_singles(single_summaries, everyone, section, field), (
            section,
            field,
        )


def test_optimization_summary_includes_bill_level_copay_exemptions(
    dataset: SUTClaimDataset, cohort_summary: dict[str, Any]
) -> None:
    patient_ids = sorted(dataset.patient_totals)
    # The emergency bills are the cohort's copay-exempt ones (the visit-type rule, category
    # "acil_servis"); without one the exempt part of this test would show nothing.
    emergency_bills = sum(claim.claim_type == "acil" for claim in dataset.claims.values())
    assert emergency_bills > 0

    copay = cohort_summary["copay_exemptions"]  # _summary(dataset, patient_ids)

    assert copay["n_total_patients"] == len(patient_ids)
    assert copay["n_total_bills"] == cohort.claim_count()
    assert copay["n_total_bills"] >= copay["n_total_patients"]
    assert emergency_bills <= copay["n_exempt_bills"] <= copay["n_total_bills"]
    assert copay["exemption_rate_bills"] == pytest.approx(
        copay["n_exempt_bills"] / copay["n_total_bills"], abs=1e-4
    )
    by_category = {row["category"]: row["count"] for row in copay["exemption_by_category_bills"]}
    assert by_category["acil_servis"] == emergency_bills
    assert sum(by_category.values()) >= copay["n_exempt_bills"]

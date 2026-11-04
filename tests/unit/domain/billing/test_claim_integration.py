"""Billing integration with exact claim lines."""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims import (
    build_bill_claim_context,
    build_patient_claim_context,
    load_sut_claim_dataset,
)
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit

_EXEMPT_HYPERTENSION = {
    "exempt": True,
    "qualifying_diagnoses": [{"disease": "Hypertension", "range": "I10-I15"}],
}


def test_billing_report_uses_exact_copay_from_claim_context() -> None:
    dataset = load_sut_claim_dataset()
    patient_id = cohort.role("default_landing").patient_id
    ctx = build_patient_claim_context(patient_id, dataset)
    assert ctx is not None

    report = compute_patient_billing_report(
        patient_id,
        claim_context=ctx,
        copay_exemption=_EXEMPT_HYPERTENSION,
    )

    assert report.copay.exactness_status == "exact"
    assert report.billing_strategy.exactness_status == "exact"


# The stories whose injected fault is a revenue uplift on the bill. Each one feeds another component
# of the uplift: billing strategy (S1), bed points (S2), anaesthesia points (S3). S4's companion is a
# 0 TL check, since no 510121 line shows it (#301).
@pytest.mark.parametrize("story", ["S1", "S2", "S3"])
def test_total_recoverable_is_the_sum_of_the_uplift_components(story: str) -> None:
    fault = cohort.fault(story)
    assert fault["effect_kind"] == "revenue_uplift"
    dataset = load_sut_claim_dataset()
    patient_id = cohort.role(f"showcase_{story}").patient_id
    ctx = build_patient_claim_context(patient_id, dataset)
    assert ctx is not None

    report = compute_patient_billing_report(
        patient_id,
        claim_context=ctx,
        copay_exemption=_EXEMPT_HYPERTENSION,
    )

    # What the fault left unbilled is recovered, and the total is the sum of the components.
    assert report.sgk_uplift_try == float(Decimal(fault["amount_try"]))
    assert report.total_recoverable_try == report.sgk_uplift_try
    assert report.sgk_uplift_try == round(
        report.billing_strategy.uplift_savings_try
        + report.session_uplift.confirmed_uplift_try
        + report.drg_uplift.confirmed_uplift_try
        + report.blood_uplift.confirmed_uplift_try
        + report.yatak_puani.confirmed_yatak_try
        + report.icu_puani.confirmed_icu_try
        + report.yenidogan_yatak.confirmed_yenidogan_yatak_try
        + report.refakatci.confirmed_refakat_try
        + report.anestezi_puani.confirmed_anestezi_try
        + report.material_uplift.confirmed_uplift_try
        + report.procedure_addon_uplift.confirmed_uplift_try,
        2,
    )


def test_exempt_patient_rx_copay_in_total() -> None:
    """The copay of a drug line is in the waived total, and not in what is recoverable from SGK.

    The cohort's drug lines are billed at 0 TL, so none has a copay. One line of the drug-bearing
    patient is priced here, in memory: 50.00 billed and 40.00 paid is 10.00 of copay, which the
    inpatient rule (SUT 1.8.5(8)) waives because the patient's claim is an inpatient one.
    """
    dataset = load_sut_claim_dataset()
    role = cohort.role("showcase_S6")
    patient_id = role.patient_id
    # the stay of S6, read as its bill: the patient's later bills (the visits S45 and S46) bill no drug
    ctx = build_bill_claim_context(patient_id, role.claim_id, dataset)
    assert ctx is not None
    assert {claim.claim_type for claim in ctx.claims} == {"yatis"}
    priced_line = dataclasses.replace(
        ctx.drug_lines[0],
        unit_price_try=Decimal("50.00"),
        billed_amount_try=Decimal("50.00"),
        expected_payable_try=Decimal("40.00"),
    )
    priced_ctx = dataclasses.replace(ctx, drug_lines=(priced_line, *ctx.drug_lines[1:]))
    copay_of_line = float(priced_line.billed_amount_try - priced_line.expected_payable_try)

    unpriced = compute_patient_billing_report(
        patient_id, claim_context=ctx, copay_exemption=_EXEMPT_HYPERTENSION
    )
    report = compute_patient_billing_report(
        patient_id, claim_context=priced_ctx, copay_exemption=_EXEMPT_HYPERTENSION
    )

    rx = report.copay.rx_copay_savings_try
    visit = report.copay.visit_copay_savings_try
    assert unpriced.copay.rx_copay_savings_try == 0.0
    assert rx == copay_of_line > 0
    assert report.copay.rx_copay_savings_by_ground == {"inpatient_drug_1_8_5_8": copay_of_line}
    assert report.copay.patient_copay_waived_total_try == round(visit + rx, 2)
    assert report.copay.total_copay_savings_try == visit
    # The copay is the patient's: the amount recoverable from SGK does not move.
    assert report.total_recoverable_try == unpriced.total_recoverable_try
    assert report.sgk_uplift_try == unpriced.sgk_uplift_try


def test_billing_strategy_without_claim_context_stays_unavailable() -> None:
    report = compute_patient_billing_report("P1")

    assert report.billing_strategy.exactness_status == "missing_exact_inputs"
    assert report.billing_strategy.recommendations == []
    assert report.total_recoverable_try is None

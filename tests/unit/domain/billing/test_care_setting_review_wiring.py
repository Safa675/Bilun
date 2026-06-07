"""Phase 2.2 — care-setting review wiring (advisory, excluded from SGK headline)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext

pytestmark = pytest.mark.unit

TIER_3 = "egitim_arastirma"


def _claim(**overrides) -> ClaimHeader:
    base = dict(
        claim_id="CLM-CS",
        patient_id="P1",
        episode_id="E1",
        claim_type="gunubirlik",
        facility_tier=TIER_3,
        provider_type="Universite",
        department="cardiology",
        admission_date=date(2026, 1, 10),
        discharge_date=date(2026, 1, 10),
        claim_start_date=date(2026, 1, 10),
        claim_end_date=date(2026, 1, 10),
        primary_icd10="I21.9",
        package_candidate=True,
        expected_total_billed_try=Decimal("12000"),
        expected_total_payable_try=Decimal("12000"),
        expected_denial_reason="",
        scenario_tag="sgk_care_setting_review_gunubirlik",
    )
    base.update(overrides)
    return ClaimHeader(**base)


def _proc(**overrides) -> ProcedureClaimLine:
    base = dict(
        procedure_line_id="PL1",
        claim_id="CLM-CS",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 10),
        procedure_code="600150",
        procedure_name="Itemized A",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("4500"),
        billed_amount_try=Decimal("0"),
        expected_payable_try=Decimal("4500"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    base.update(overrides)
    return ProcedureClaimLine(**base)


def _ctx() -> PatientClaimContext:
    claim = _claim()
    procs = [
        _proc(),
        _proc(
            procedure_line_id="PL2",
            procedure_code="600160",
            procedure_name="Itemized B",
            expected_payable_try=Decimal("3500"),
        ),
        _proc(
            procedure_line_id="PL3",
            procedure_code="609270",
            procedure_name="Package",
            procedure_category="paket",
            billed_amount_try=Decimal("3500"),
            expected_payable_try=Decimal("3500"),
        ),
    ]
    return PatientClaimContext(
        patient_id="P1",
        claims=(claim,),
        procedure_lines=tuple(procs),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


class TestCareSettingReviewWiring:
    def test_review_excluded_from_sgk_headline(self) -> None:
        ctx = _ctx()
        report = compute_patient_billing_report(
            "P1",
            claim_context=ctx,
            copay_exemption={"exempt": False},
            chapters={"I"},
        )
        assert report.care_setting_review.review_opportunity_count == 1
        assert report.care_setting_review.confirmed_uplift_try == 0.0
        assert report.care_setting_review.review_uplift_try > 0
        assert report.sgk_uplift_try == 0.0

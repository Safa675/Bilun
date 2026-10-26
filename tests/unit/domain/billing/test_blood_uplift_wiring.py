"""Phase 1.4 — blood component uplift billing wiring."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.billing.claim_blood_uplift import recommend_blood_uplift_from_claims
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from tests.unit._helpers.catalog_prices import list_text

pytestmark = pytest.mark.unit


def _claim(**overrides) -> ClaimHeader:
    base = dict(
        claim_id="CLM-BLOOD",
        patient_id="P1",
        episode_id="E1",
        claim_type="yatis",
        facility_tier="2_basamak_kamu",
        provider_type="Kamu",
        department="hematology",
        admission_date=date(2026, 1, 10),
        discharge_date=date(2026, 1, 12),
        claim_start_date=date(2026, 1, 10),
        claim_end_date=date(2026, 1, 12),
        primary_icd10="D64.9",
        package_candidate=True,
        expected_total_billed_try=Decimal("500"),
        expected_total_payable_try=Decimal("500"),
        expected_denial_reason="",
        scenario_tag="sgk_blood_uplift_yatis",
    )
    base.update(overrides)
    return ClaimHeader(**base)


def _proc(**overrides) -> ProcedureClaimLine:
    base = dict(
        procedure_line_id="PL1",
        claim_id="CLM-BLOOD",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 10),
        procedure_code="705371",
        procedure_name="Eritrosit süspansiyonu",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("50"),
        expected_payable_try=Decimal("1000"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    base.update(overrides)
    return ProcedureClaimLine(**base)


def _ctx(claim: ClaimHeader, *lines: ProcedureClaimLine) -> PatientClaimContext:
    return PatientClaimContext(
        patient_id=claim.patient_id,
        claims=(claim,),
        procedure_lines=tuple(lines),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


class TestBloodUpliftWiring:
    def test_blood_uplift_in_sgk_headline_not_audit(self) -> None:
        claim = _claim()
        lines = [
            _proc(),
            _proc(procedure_line_id="package", procedure_code="P610070",
                  procedure_category="paket", procedure_date=date(2026, 1, 11),
                  billed_amount_try=Decimal("10000"), expected_payable_try=Decimal("10000")),
        ]
        ctx = _ctx(claim, *lines)
        blood = recommend_blood_uplift_from_claims(ctx)
        # 36 % of 705371's list price on the line date (#336, curated catalog history), less the 50 billed.
        share = (Decimal(list_text("705371", "2026-01-10")) * Decimal("0.36")).quantize(
            Decimal("0.01"), rounding="ROUND_HALF_UP"
        )
        uplift = float(share - 50)
        assert blood.confirmed_uplift_try == pytest.approx(uplift)

        report = compute_patient_billing_report(
            "P1",
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )
        assert report.blood_uplift.confirmed_uplift_try == pytest.approx(uplift)
        assert report.sgk_uplift_try >= uplift
        assert report.audit_exposure_try == 0.0

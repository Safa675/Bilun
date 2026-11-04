"""EK-4/D copay-exempt drug membership."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.claim_copay import optimize_copay_from_claims
from src.bilun.domain.claims.models import ClaimDiagnosis, ClaimHeader, DrugClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.drugs.ek4d_exempt import match_ek4d_copay_exempt_drug

pytestmark = pytest.mark.unit


def test_tuberculosis_drug_matches_with_health_report() -> None:
    hit = match_ek4d_copay_exempt_drug(
        ["A16.9"],
        drug_name="Morfozinamid",
        has_health_report=True,
    )
    assert hit is not None
    assert hit["counts_toward_exempt"] is True
    assert hit["evidence"]["section_id"] == 1


def test_ek4d_requires_health_report_for_savings_flag() -> None:
    hit = match_ek4d_copay_exempt_drug(
        ["A16"],
        drug_name="Morfozinamid",
        has_health_report=False,
    )
    assert hit is not None
    assert hit["counts_toward_exempt"] is False


def test_claim_copay_applies_ek4d_rx_savings() -> None:
    ctx = PatientClaimContext(
        patient_id="P1",
        claims=(
            ClaimHeader(
                claim_id="C1",
                patient_id="P1",
                episode_id="E1",
                claim_type="yatis",
                facility_tier="2",
                provider_type="kamu",
                department="",
                admission_date=date(2026, 1, 1),
                discharge_date=date(2026, 1, 5),
                claim_start_date=date(2026, 1, 1),
                claim_end_date=date(2026, 1, 5),
                primary_icd10="A16.9",
                expected_total_billed_try=Decimal("0"),
                expected_total_payable_try=Decimal("0"),
                expected_denial_reason="",
                scenario_tag="test",
            ),
        ),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(
            DrugClaimLine(
                drug_claim_line_id="D1",
                prescription_id="RX1",
                claim_id="C1",
                patient_id="P1",
                episode_id="E1",
                drug_claim_date=date(2026, 1, 2),
                drug_name="Morfozinamid",
                drug_code="",
                barkod="",
                equivalence_group="",
                quantity=1,
                unit_price_try=Decimal("100"),
                billed_amount_try=Decimal("100"),
                expected_payable_try=Decimal("60"),
                discount_tier_expected=Decimal("0"),
                denial_reason_expected="",
                rule_trace_expected="",
            ),
        ),
        diagnoses=(
            ClaimDiagnosis(
                diagnosis_id="DX1",
                claim_id="C1",
                patient_id="P1",
                episode_id="E1",
                icd10_code="A16.9",
                is_primary=True,
                diagnosis_role="primary",
                diagnosis_date=date(2026, 1, 1),
                exemption_eligible=False,
            ),
        ),
    )
    result = optimize_copay_from_claims(
        ctx,
        {
            "exempt": False,
            "partial_exempt": False,
            "qualifying_diagnoses": [],
            "has_chronic_health_report": True,
        },
    )
    assert result.rx_copay_savings_try == pytest.approx(40.0)
    assert result.total_copay_savings_try == 0.0
    assert result.visit_copay_savings_try == 0.0

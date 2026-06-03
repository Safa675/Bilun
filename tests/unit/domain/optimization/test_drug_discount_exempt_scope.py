"""Drug discount cohort savings must not double-count EK-1A exempt Rx copay."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import DrugClaimLine
from src.bilun.domain.optimization.drugs import validate_drug_discount_tiers

pytestmark = pytest.mark.unit


def _line(
    *,
    patient_id: str,
    billed: str,
    payable: str,
) -> DrugClaimLine:
    billed_dec = Decimal(billed)
    payable_dec = Decimal(payable)
    return DrugClaimLine(
        drug_claim_line_id=f"DL-{patient_id}",
        prescription_id="RX1",
        claim_id="C1",
        patient_id=patient_id,
        episode_id="E1",
        drug_claim_date=date(2026, 1, 1),
        drug_name="Drug",
        drug_code="D1",
        barkod="",
        equivalence_group="G1",
        quantity=1,
        unit_price_try=billed_dec,
        billed_amount_try=billed_dec,
        expected_payable_try=payable_dec,
        discount_tier_expected=Decimal("0.20"),
        denial_reason_expected="",
        rule_trace_expected="",
    )


def test_discount_savings_exclude_ek1a_exempt_patient_lines() -> None:
    lines = (
        _line(patient_id="EXEMPT", billed="100", payable="80"),
        _line(patient_id="STANDARD", billed="200", payable="150"),
    )
    result = validate_drug_discount_tiers(lines, exempt_patient_ids={"EXEMPT"})

    assert result["total_discount_savings_try"] == 50.0
    assert result["exempt_patient_rx_share_try"] == 20.0

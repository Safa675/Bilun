"""Drug discount validation from exact claim lines."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import DrugClaimLine
from src.bilun.domain.optimization.drug_discounts import validate_drug_discount_tiers

pytestmark = pytest.mark.unit


def _drug_line(
    *,
    billed: str = "100.00",
    payable: str = "72.00",
    discount: str = "0.28",
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D1",
        prescription_id="RX1",
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=date(2026, 1, 17),
        drug_name="Example drug",
        drug_code="A00001",
        barkod="8690000000000",
        equivalence_group="EQ1",
        quantity=1,
        unit_price_try=Decimal(billed),
        billed_amount_try=Decimal(billed),
        expected_payable_try=Decimal(payable),
        discount_tier_expected=Decimal(discount),
        denial_reason_expected="",
        rule_trace_expected="EK-4A:A00001",
    )


def test_drug_discount_validation_exact_for_matching_line() -> None:
    result = validate_drug_discount_tiers([_drug_line()], n_total_patients=1)

    assert result["exactness_status"] == "exact"
    assert result["n_drug_lines"] == 1
    assert result["n_discounted_lines"] == 1
    assert result["n_violations"] == 0
    assert result["total_expected_discount_try"] == 28.0


def test_drug_discount_validation_flags_mismatch() -> None:
    result = validate_drug_discount_tiers(
        [_drug_line(payable="80.00", discount="0.28")],
        n_total_patients=1,
    )

    assert result["exactness_status"] == "exact"
    assert result["n_violations"] == 1
    assert result["top_violations"][0]["expected_discount_pct"] == 28.0
    assert result["top_violations"][0]["implied_discount_pct"] == 20.0


def test_drug_discount_validation_unavailable_without_lines() -> None:
    result = validate_drug_discount_tiers([], n_total_patients=3)

    assert result["exactness_status"] == "missing_exact_inputs"
    assert result["n_total_patients"] == 3
    assert result["required_inputs_missing"]

"""Exact EK-4A drug discount validation from claim-line data.

CODE-ONLY BY DESIGN — this motor computes discount tiers from pre-baked
``discount_tier_expected`` on each DrugClaimLine. The ~38 unencoded §4.4
clauses are discount-tier arithmetic (52,44 TL / 100,39 TL thresholds) that
the code resolves; encoding them as prose rules would duplicate the arithmetic
and risk drift. See plans/refactor/rule-encoding-gap-closure-roadmap.md.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from src.bilun.domain.claims.models import DrugClaimLine
from src.bilun.domain.money import money_round_half_up as _money

from .exactness import EXACTNESS_STATUS_MISSING_INPUTS

DRUG_DISCOUNT_REQUIRED_INPUTS = (
    "dispensed_drug_claim_lines",
    "billed_drug_amounts",
    "expected_payable_drug_amounts",
    "discount_tier_expected",
)
DRUG_DISCOUNT_UNAVAILABLE_REASON = (
    "Drug discount validation requires exact dispensed-drug claim lines, billed "
    "drug amounts, expected payable amounts, and expected EK-4A discount tiers, "
    "which are not available in the active SUT runtime inputs."
)
_DISCOUNT_TOLERANCE = Decimal("0.01")


def unavailable_drug_discount_validation(
    *, n_total_patients: int = 0
) -> dict[str, Any]:
    """Structured unavailable payload for cohorts without exact drug lines."""

    return {
        "exactness_status": EXACTNESS_STATUS_MISSING_INPUTS,
        "unavailable_reason": DRUG_DISCOUNT_UNAVAILABLE_REASON,
        "required_inputs_missing": list(DRUG_DISCOUNT_REQUIRED_INPUTS),
        "n_total_patients": n_total_patients,
        "n_drug_lines": None,
        "n_discounted_lines": None,
        "n_violations": None,
        "total_billed_try": None,
        "total_expected_payable_try": None,
        "total_expected_discount_try": None,
        "mean_expected_discount_pct": None,
        "top_violations": [],
        "methodology": DRUG_DISCOUNT_UNAVAILABLE_REASON,
    }


def validate_drug_discount_tiers(
    drug_lines: Iterable[DrugClaimLine] | None,
    *,
    n_total_patients: int = 0,
) -> dict[str, Any]:
    """Validate implied claim-line discounts against expected EK-4A tiers."""

    lines = tuple(drug_lines or ())
    if not lines:
        return unavailable_drug_discount_validation(n_total_patients=n_total_patients)

    total_billed = Decimal("0")
    total_payable = Decimal("0")
    total_discount_amount = Decimal("0")
    expected_discount_sum = Decimal("0")
    n_discounted = 0
    violations: list[dict[str, Any]] = []

    for line in lines:
        billed = Decimal(line.billed_amount_try)
        payable = Decimal(line.expected_payable_try)
        expected_discount = Decimal(line.discount_tier_expected)

        if billed <= 0:
            continue

        total_billed += billed
        total_payable += payable
        discount_amount = max(Decimal("0"), billed - payable)
        total_discount_amount += discount_amount
        expected_discount_sum += expected_discount
        if expected_discount > 0:
            n_discounted += 1

        implied_discount = discount_amount / billed
        delta = abs(implied_discount - expected_discount)
        if delta > _DISCOUNT_TOLERANCE:
            violations.append(
                {
                    "drug_claim_line_id": line.drug_claim_line_id,
                    "claim_id": line.claim_id,
                    "patient_id": line.patient_id,
                    "drug_code": line.drug_code,
                    "drug_name": line.drug_name,
                    "billed_try": _money(billed),
                    "expected_payable_try": _money(payable),
                    "expected_discount_pct": _money(float(expected_discount) * 100),
                    "implied_discount_pct": _money(float(implied_discount) * 100),
                    "delta_pct": _money(float(delta) * 100),
                }
            )

    n_evaluable = sum(1 for line in lines if Decimal(line.billed_amount_try) > 0)
    mean_discount = (
        expected_discount_sum / Decimal(n_evaluable) if n_evaluable else Decimal("0")
    )

    return {
        "exactness_status": "exact",
        "n_total_patients": n_total_patients,
        "n_drug_lines": len(lines),
        "n_evaluable_lines": n_evaluable,
        "n_discounted_lines": n_discounted,
        "n_violations": len(violations),
        "total_billed_try": _money(total_billed),
        "total_expected_payable_try": _money(total_payable),
        "total_expected_discount_try": _money(total_discount_amount),
        "mean_expected_discount_pct": _money(float(mean_discount) * 100),
        "top_violations": violations[:10],
        "methodology": (
            "Validates each exact drug claim line by comparing the implied "
            "discount (billed minus expected payable, divided by billed) against "
            "the expected EK-4A discount tier carried on the claim line."
        ),
        "rule_source": "SUT §4.4 drug discount prose + EK-4A discount tiers",
    }

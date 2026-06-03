"""Feature 6: drug discount validation from exact drug claim lines."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from .exactness import (
    DRUG_DISCOUNT_REQUIRED_INPUTS,
    DRUG_DISCOUNT_UNAVAILABLE_REASON,
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    unavailable_drug_discount_validation,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import DrugClaimLine

# Backward compatibility for modules that imported the old module-level cache.
_drug_discount_cache: dict[str, Any] | None = None


def validate_drug_discount_tiers(
    drug_lines: tuple[DrugClaimLine, ...] | None = None,
    *,
    exempt_patient_ids: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    """Validate EK-4A discount tiers against exact drug claim lines when present."""

    if not drug_lines:
        return unavailable_drug_discount_validation()

    exempt_ids = frozenset(exempt_patient_ids or ())
    tier_counter: Counter[str] = Counter()
    mismatches = 0
    total_savings = Decimal("0")
    exempt_patient_share = Decimal("0")
    sample_drugs: list[dict[str, Any]] = []

    for line in drug_lines:
        tier = float(line.discount_tier_expected)
        tier_key = f"{tier:.2%}"
        tier_counter[tier_key] += 1
        expected_payable = line.billed_amount_try * (Decimal("1") - line.discount_tier_expected)
        diff = abs(line.expected_payable_try - expected_payable.quantize(Decimal("0.01")))
        if diff > Decimal("0.02"):
            mismatches += 1
        savings = line.billed_amount_try - line.expected_payable_try
        if line.patient_id in exempt_ids:
            exempt_patient_share += savings
        else:
            total_savings += savings
        if len(sample_drugs) < 10:
            sample_drugs.append(
                {
                    "drug_name": line.drug_name,
                    "drug_code": line.drug_code,
                    "equivalence_group": line.equivalence_group,
                    "billed_try": float(line.billed_amount_try),
                    "payable_try": float(line.expected_payable_try),
                    "discount_tier": tier,
                }
            )

    return {
        "exactness_status": EXACTNESS_STATUS_EXACT,
        "n_drugs_total": len(drug_lines),
        "n_active_drugs": len({line.drug_code for line in drug_lines}),
        "n_tier_mismatches": mismatches,
        "total_discount_savings_try": round(float(total_savings), 2),
        "exempt_patient_rx_share_try": round(float(exempt_patient_share), 2),
        "mean_discount_tier_1": round(
            sum(float(line.discount_tier_expected) for line in drug_lines) / len(drug_lines),
            4,
        ),
        "tier_distribution": dict(tier_counter),
        "discount_status_distribution": {"claim_lines": len(drug_lines)},
        "sample_drugs": sample_drugs,
        "methodology": (
            "Validates discount_tier_expected and payable math on exact drug claim "
            "lines. Discount savings exclude EK-1A-exempt patients because billed "
            "minus payable on their drug lines reflects recoverable Rx copay (counted "
            "under copay savings), not additional EK-4A tier recovery."
        ),
    }


def unavailable_drug_discount_validation_cohort() -> dict[str, Any]:
    return {
        **unavailable_drug_discount_validation(),
        "exactness_status": EXACTNESS_STATUS_MISSING_INPUTS,
        "unavailable_reason": DRUG_DISCOUNT_UNAVAILABLE_REASON,
        "required_inputs_missing": list(DRUG_DISCOUNT_REQUIRED_INPUTS),
    }

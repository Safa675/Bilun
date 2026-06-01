"""
src/bilun/domain/billing/strategy.py
Algorithm 4: Package vs itemized billing strategy recommender.
"""

from __future__ import annotations

from typing import Any

from .types import BillingStrategyRecommendation

EXACTNESS_STATUS_MISSING_INPUTS = "missing_exact_inputs"
_BILLING_STRATEGY_REQUIRED_INPUTS = (
    "itemized_billed_procedure_lines",
    "episode_package_eligibility_context",
    "admission_dates",
)
_BILLING_STRATEGY_UNAVAILABLE_REASON = (
    "Billing strategy comparison requires exact itemized billed procedure lines, "
    "package eligibility context, and admission dates, which are not available "
    "in the active SUT runtime inputs."
)


def _recommend_billing_strategy(
    patient_id: str,
    chapters: set[str] | None = None,
) -> BillingStrategyRecommendation:
    """Algorithm 4 is gated until exact claim-line itemized totals exist."""
    _ = patient_id
    recommendations: list[dict[str, Any]] = []
    if chapters:
        for chapter in sorted(chapters):
            recommendations.append(
                {
                    "chapter": chapter,
                    "recommendation": "review_package_eligibility",
                    "savings_try": None,
                    "detail": (
                        f"Review EK-2C package vs itemized billing eligibility for "
                        f"ICD-10 chapter {chapter}."
                    ),
                }
            )

    return BillingStrategyRecommendation(
        recommendations=recommendations,
        exactness_status=EXACTNESS_STATUS_MISSING_INPUTS,
        unavailable_reason=_BILLING_STRATEGY_UNAVAILABLE_REASON,
        required_inputs_missing=list(_BILLING_STRATEGY_REQUIRED_INPUTS),
    )

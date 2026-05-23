"""Package vs itemized billing strategy from exact claim lines."""

from __future__ import annotations

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.pricing import get_drg_package_price_for_date

from .types import EXACTNESS_STATUS_EXACT, BillingStrategyRecommendation


def _money(value) -> float:
    return round(float(value), 2)


def recommend_billing_strategy_from_claims(
    ctx: PatientClaimContext,
) -> BillingStrategyRecommendation:
    """Compare package vs itemized totals per package-candidate claim."""

    recommendations: list[dict] = []

    for claim in ctx.claims:
        if not claim.package_candidate:
            continue

        claim_procs = [line for line in ctx.procedure_lines if line.claim_id == claim.claim_id]
        if not claim_procs:
            continue

        itemized_total = sum(
            float(line.expected_payable_try)
            for line in claim_procs
            if line.procedure_category != "paket" and not line.is_package_included
        )
        package_lines = [
            line for line in claim_procs if line.procedure_category == "paket"
        ]
        package_total = sum(float(line.expected_payable_try) for line in package_lines)

        if package_total <= 0 and claim.admission_date is not None:
            chapter = (claim.primary_icd10 or "R69")[:1].upper()
            drg_price = get_drg_package_price_for_date(
                chapter,
                claim.admission_date,
                icd10_code=claim.primary_icd10,
            )
            if drg_price is not None:
                package_total = float(drg_price)

        if package_total <= 0 and itemized_total <= 0:
            continue

        if package_total <= itemized_total:
            recommendation = "package"
            savings = itemized_total - package_total
            detail = (
                f"Package billing ({package_total:.2f} TRY) is cheaper than "
                f"itemized ({itemized_total:.2f} TRY) for claim {claim.claim_id}."
            )
        else:
            recommendation = "itemized"
            savings = package_total - itemized_total
            detail = (
                f"Itemized billing ({itemized_total:.2f} TRY) yields higher recovery "
                f"than package ({package_total:.2f} TRY) for claim {claim.claim_id}."
            )

        recommendations.append(
            {
                "claim_id": claim.claim_id,
                "recommendation": recommendation,
                "package_total_try": _money(package_total),
                "itemized_total_try": _money(itemized_total),
                "savings_try": _money(max(0.0, savings)),
                "detail": detail,
            }
        )

    if not recommendations:
        return BillingStrategyRecommendation(
            recommendations=[],
            exactness_status=EXACTNESS_STATUS_EXACT,
            unavailable_reason=None,
            required_inputs_missing=[],
        )

    return BillingStrategyRecommendation(
        recommendations=recommendations,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
    )

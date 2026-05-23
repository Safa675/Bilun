"""Drug billing optimization from exact drug claim lines."""

from __future__ import annotations

from decimal import Decimal

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.materials import lookup_drug_bulk

from .drug import _optimize_drug_costs
from .types import EXACTNESS_STATUS_EXACT, DrugOptimization


def optimize_drug_from_claims(ctx: PatientClaimContext) -> DrugOptimization:
    """Compute drug optimization using exact dispensed drug claim lines."""

    if not ctx.drug_lines:
        return DrugOptimization()

    drug_names = [line.drug_name for line in ctx.drug_lines if line.drug_name]
    heuristic = _optimize_drug_costs(ctx.patient_id, drug_names)

    total_billed = Decimal("0")
    total_payable = Decimal("0")
    recommendations: list[dict] = list(heuristic.drug_recommendations)

    records = lookup_drug_bulk(list({name for name in drug_names if name}))

    for line in ctx.drug_lines:
        billed = line.billed_amount_try
        payable = line.expected_payable_try
        total_billed += billed
        total_payable += payable
        tier_savings = billed - payable
        if tier_savings > Decimal("0.01"):
            recommendations.append(
                {
                    "drug_name": line.drug_name,
                    "issue": "discount_tier_applied",
                    "alternative": line.drug_name,
                    "savings_try": round(float(tier_savings), 2),
                    "detail": (
                        f"Claim line {line.drug_claim_line_id}: billed "
                        f"{float(billed):.2f} TRY, payable {float(payable):.2f} TRY "
                        f"(tier {float(line.discount_tier_expected):.2%})."
                    ),
                }
            )
        record = records.get(line.drug_name)
        if record is None and line.drug_code:
            record = records.get(line.drug_code)

    discount_from_claims = total_billed - total_payable
    substitution_savings = max(
        Decimal(str(heuristic.generic_substitution_savings)),
        discount_from_claims,
    )

    return DrugOptimization(
        generic_substitution_savings=round(float(substitution_savings), 2),
        n_generics_available=heuristic.n_generics_available,
        passivated_drug_count=heuristic.passivated_drug_count,
        drug_recommendations=recommendations[:20],
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
    )

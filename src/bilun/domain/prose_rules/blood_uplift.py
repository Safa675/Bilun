"""SUT §2.2.2.B-1.e blood component fraction under-billing (SGK uplift)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .session_pricing import blood_component_billable_fraction
from .types import SAVINGS_BASIS_SOURCED, SAVINGS_CATEGORY_SGK_UPLIFT

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ProcedureClaimLine

_BILLING_TOLERANCE = 0.02
_OPPORTUNITY_TYPE = "blood_component_underbilling"


def _money(value: float | int) -> float:
    return round(float(value), 2)


def _line_billed(line: ProcedureClaimLine) -> float:
    return float(line.billed_amount_try)


def _line_payable(line: ProcedureClaimLine) -> float:
    return float(line.expected_payable_try)


def detect_blood_component_underbilling_opportunities(
    lines: list[ProcedureClaimLine],
    *,
    claim_id: str = "",
) -> list[dict[str, Any]]:
    """Flag blood component lines billed below allowed package-context fraction."""
    opportunities: list[dict[str, Any]] = []

    for line in lines:
        if line.is_package_included:
            continue
        fraction = blood_component_billable_fraction(line.procedure_code)
        if fraction is None:
            continue

        payable = _line_payable(line)
        billed = _line_billed(line)
        if payable <= 0 and billed <= 0:
            continue

        reference = payable if payable > 0 else billed
        max_billable = reference * fraction
        if billed >= max_billable * (1.0 - _BILLING_TOLERANCE):
            continue

        recoverable = _money(max_billable - billed)
        if recoverable <= 0:
            continue

        opportunities.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim_id or line.claim_id,
                "procedure_line_id": line.procedure_line_id,
                "procedure_code": line.procedure_code,
                "procedure_name": line.procedure_name,
                "allowed_fraction": fraction,
                "reference_payable_try": _money(reference),
                "max_billable_try": _money(max_billable),
                "actual_billed_try": _money(billed),
                "recoverable_uplift_try": recoverable,
                "included_in_sgk_total": True,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "sut_section_id": "2.2.2.B-1.e",
                "rule_id": "blood_component_partial_bill",
                "detail": (
                    f"Blood component {line.procedure_code} billed at "
                    f"{billed:.2f} TRY; up to {max_billable:.2f} TRY "
                    f"({fraction:.0%} of reference) may be recoverable per "
                    f"SUT §2.2.2.B-1.e."
                ),
            }
        )

    return opportunities

"""SUT §2.2.2.B-1.e blood component fraction under-billing (SGK uplift)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .claim_utils import line_billed_amount
from .session_pricing import (
    billed_package_scopes, blood_component_billable_fraction, blood_component_list_amount_try,
    blood_component_max_billable_try,
)
from .session_uplift import iter_session_secondary_assessments
from .types import SAVINGS_BASIS_SOURCED, SAVINGS_CATEGORY_SGK_UPLIFT

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

from src.bilun.domain.money import money_round_half_up as _money
_BILLING_TOLERANCE = 0.02
_OPPORTUNITY_TYPE = "blood_component_underbilling"



def _line_payable(line: ProcedureClaimLine) -> float:
    return float(line.expected_payable_try)


def detect_blood_component_underbilling_opportunities(
    lines: list[ProcedureClaimLine],
    *,
    claim_id: str = "",
    same_incision: bool = True,
    cross_specialty: bool | None = None,
    claim: ClaimHeader | None = None,
) -> list[dict[str, Any]]:
    """Flag blood component lines billed below allowed package-context fraction.

    The ceiling is the share of the component's EK-2/B list price on the line's
    date (``blood_component_max_billable_try``, #336), never the line's payable,
    which equals billed on most exports and made this block dark for any bill.
    ``reference_payable_try`` is that list amount (unit price x quantity). A
    line whose list price is unknown that day is not assessed.
    """
    opportunities: list[dict[str, Any]] = []
    package_scopes = billed_package_scopes(lines)
    blood_lines = [
        line for line in lines
        if (line.patient_id, line.claim_id, line.episode_id) in package_scopes
        and not line.is_package_included
        and blood_component_billable_fraction(line.procedure_code) is not None
    ]
    if not blood_lines:
        return opportunities
    # Session-owned secondaries already compose both ceilings, including
    # zero-gap and review-only cases. Object identity denotes the exact input
    # occurrence, so repeated codes or missing/reused IDs cannot suppress peers.
    session_owned = {
        id(assessment.line) for assessment in iter_session_secondary_assessments(
            lines, same_incision=same_incision, cross_specialty=cross_specialty, claim=claim,
        )
    }

    for line in blood_lines:
        if id(line) in session_owned:
            continue
        fraction = blood_component_billable_fraction(line.procedure_code)
        if fraction is None:
            continue

        billed = line_billed_amount(line)
        if _line_payable(line) <= 0 and billed <= 0:
            continue

        max_billable = blood_component_max_billable_try(line, package_context=True)
        reference = blood_component_list_amount_try(line)
        if max_billable is None or reference is None:
            continue
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
                    f"({fraction:.0%} of its list price {reference:.2f} TRY) may be recoverable per "
                    f"SUT §2.2.2.B-1.e."
                ),
            }
        )

    return opportunities

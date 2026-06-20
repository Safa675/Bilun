"""SUT §2.2.2.B / §2.2.2.A(5) session under-billing (recoverable SGK uplift)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .catalog_membership import normalize_procedure_code
from .claim_utils import group_procedure_lines_by_session
from ..money import money_round_half_up as _money
from .session_pricing import (
    compute_session_point_factors,
    expected_session_billed_try,
)
from .session_specialty import detect_cross_specialty_session
from .types import SAVINGS_BASIS_SOURCED, SAVINGS_CATEGORY_SGK_UPLIFT

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_BILLING_TOLERANCE = 0.02
_OPPORTUNITY_TYPE = "session_underbilling"
REVIEW_KIND_CLINICAL = "needs_clinical_review"
# Tiny secondary vs high-primary pairs (e.g. poliklinik + PCI same date) need chart review.
_MIN_PRIMARY_FOR_RATIO_REVIEW_TRY = 2_000.0
_MAX_SECONDARY_RATIO_FOR_REVIEW = 0.05
_MIN_UPLIFT_FOR_RATIO_REVIEW_TRY = 200.0
_MAX_SECONDARY_ABSOLUTE_FOR_REVIEW_TRY = 100.0



def _line_billed(line: ProcedureClaimLine) -> float:
    return float(line.billed_amount_try)


def needs_clinical_review(
    *,
    primary_billed_try: float,
    actual_billed_try: float,
    recoverable_uplift_try: float,
) -> bool:
    """Heuristic: low-ticket secondary on same date as high-primary procedure."""
    if primary_billed_try <= 0 or recoverable_uplift_try <= 0:
        return False
    ratio = actual_billed_try / primary_billed_try
    if (
        primary_billed_try >= _MIN_PRIMARY_FOR_RATIO_REVIEW_TRY
        and ratio < _MAX_SECONDARY_RATIO_FOR_REVIEW
        and recoverable_uplift_try >= _MIN_UPLIFT_FOR_RATIO_REVIEW_TRY
    ):
        return True
    if (
        actual_billed_try <= _MAX_SECONDARY_ABSOLUTE_FOR_REVIEW_TRY
        and primary_billed_try >= _MIN_PRIMARY_FOR_RATIO_REVIEW_TRY
        and recoverable_uplift_try >= _MIN_UPLIFT_FOR_RATIO_REVIEW_TRY
    ):
        return True
    return False


def detect_session_underbilling_opportunities(
    lines: list[ProcedureClaimLine],
    *,
    claim_id: str = "",
    same_incision: bool = True,
    cross_specialty: bool | None = None,
    claim: ClaimHeader | None = None,
) -> list[dict[str, Any]]:
    """Flag secondary procedures billed below allowed same-session point factors."""
    opportunities: list[dict[str, Any]] = []

    for session_date, session_lines in group_procedure_lines_by_session(lines).items():
        billable = [
            line
            for line in session_lines
            if not line.is_package_included and _line_billed(line) > 0
        ]
        if len(billable) < 2:
            continue

        codes = [line.procedure_code for line in billable]
        session_cross = (
            detect_cross_specialty_session(billable, claim)
            if cross_specialty is None
            else cross_specialty
        )
        session = compute_session_point_factors(
            codes,
            same_incision=same_incision,
            cross_specialty=session_cross,
        )
        if session.rule_id == "single_procedure":
            continue

        factors = {
            normalize_procedure_code(f.procedure_code): f for f in session.factors
        }
        primary_line = None
        primary_factor = 1.0
        for line in billable:
            factor = factors.get(normalize_procedure_code(line.procedure_code))
            if factor is not None and factor.is_primary:
                primary_line = line
                primary_factor = factor.point_factor
                break

        if primary_line is None or _line_billed(primary_line) <= 0:
            continue

        primary_billed = _line_billed(primary_line)
        resolved_claim_id = claim_id or primary_line.claim_id

        for line in billable:
            if line.procedure_line_id == primary_line.procedure_line_id:
                continue
            factor = factors.get(normalize_procedure_code(line.procedure_code))
            if factor is None or factor.point_factor >= primary_factor:
                continue

            expected_billed = expected_session_billed_try(
                line,
                point_factor=factor.point_factor,
            )
            actual_billed = _line_billed(line)
            if actual_billed >= expected_billed * (1.0 - _BILLING_TOLERANCE):
                continue

            uplift = expected_billed - actual_billed
            if uplift <= _BILLING_TOLERANCE:
                continue

            uplift_money = _money(uplift)
            clinical_review = needs_clinical_review(
                primary_billed_try=primary_billed,
                actual_billed_try=actual_billed,
                recoverable_uplift_try=uplift_money,
            )
            detail = (
                f"Secondary procedure billed below SUT §{session.sut_section} "
                f"allowed {factor.point_factor:.0%} point factor; "
                f"recoverable uplift {uplift_money:.2f} TRY."
            )
            if clinical_review:
                detail += (
                    " Clinical session boundaries not verified — "
                    "chart review before rebill."
                )

            opportunities.append(
                {
                    "type": _OPPORTUNITY_TYPE,
                    "claim_id": resolved_claim_id,
                    "procedure_line_id": line.procedure_line_id,
                    "procedure_code": line.procedure_code,
                    "procedure_name": line.procedure_name,
                    "session_date": str(session_date),
                    "expected_point_factor": factor.point_factor,
                    "primary_procedure_code": primary_line.procedure_code,
                    "primary_billed_try": _money(primary_billed),
                    "expected_billed_try": _money(expected_billed),
                    "actual_billed_try": _money(actual_billed),
                    "recoverable_uplift_try": 0.0 if clinical_review else uplift_money,
                    "review_uplift_try": uplift_money if clinical_review else 0.0,
                    "review_kind": REVIEW_KIND_CLINICAL if clinical_review else None,
                    "included_in_sgk_total": not clinical_review,
                    "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                    "savings_basis": SAVINGS_BASIS_SOURCED,
                    "sut_section_id": session.sut_section,
                    "rule_id": session.rule_id,
                    "detail": detail,
                }
            )

    return opportunities

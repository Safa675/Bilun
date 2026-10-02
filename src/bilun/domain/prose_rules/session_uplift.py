"""SUT §2.2.2.B / §2.2.2.A(5) session under-billing (recoverable SGK uplift)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

from .catalog_membership import normalize_procedure_code
from .claim_utils import group_procedure_lines_by_session
from ..money import money_round_half_up as _money
from .session_pricing import (
    blood_component_max_billable_try,
    compute_session_point_factors,
    expected_session_billed_try,
)
from .session_specialty import detect_cross_specialty_session
from .types import SAVINGS_BASIS_SOURCED, SAVINGS_CATEGORY_SGK_UPLIFT

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

    from .types import SessionPricingResult, SessionProcedureFactor

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


@dataclass(frozen=True)
class SessionSecondaryAssessment:
    """An applicable session constraint, including lines with no positive gap."""

    line: ProcedureClaimLine
    primary_line: ProcedureClaimLine
    factor: SessionProcedureFactor
    session_date: date
    session: SessionPricingResult


def iter_session_secondary_assessments(
    lines: list[ProcedureClaimLine],
    *,
    same_incision: bool = True,
    cross_specialty: bool | None = None,
    claim: ClaimHeader | None = None,
) -> Iterator[SessionSecondaryAssessment]:
    """Share session ownership by line occurrence, never by procedure code.

    Keep non-underbilled secondaries too: another detector cannot claim money
    above their applicable session ceiling just because this gap is zero.
    """
    by_claim: dict[str, list[ProcedureClaimLine]] = defaultdict(list)
    for line in lines:
        by_claim[line.claim_id].append(line)
    for claim_lines in by_claim.values():
        for session_date, session_lines in group_procedure_lines_by_session(claim_lines).items():
            billable = [
                line for line in session_lines
                if not line.is_package_included and _line_billed(line) > 0
            ]
            if len(billable) < 2:
                continue
            session_cross = (
                detect_cross_specialty_session(billable, claim)
                if cross_specialty is None else cross_specialty
            )
            session = compute_session_point_factors(
                [line.procedure_code for line in billable],
                same_incision=same_incision,
                cross_specialty=session_cross,
            )
            if session.rule_id == "single_procedure":
                continue

            # Factors retain input occurrence order and omit empty codes.
            # A code-keyed map loses the primary when normalized codes repeat.
            factors = iter(session.factors)
            assessed = [
                (line, next(factors)) for line in billable
                if normalize_procedure_code(line.procedure_code)
            ]
            primary = next(((line, factor) for line, factor in assessed if factor.is_primary), None)
            if primary is None:
                continue
            primary_line, primary_factor = primary
            for line, factor in assessed:
                if factor.is_primary or factor.point_factor >= primary_factor.point_factor:
                    continue
                yield SessionSecondaryAssessment(line, primary_line, factor, session_date, session)


def detect_session_underbilling_opportunities(
    lines: list[ProcedureClaimLine],
    *,
    claim_id: str = "",
    same_incision: bool = True,
    cross_specialty: bool | None = None,
    claim: ClaimHeader | None = None,
) -> list[dict[str, Any]]:
    """Flag one composed underbilling gap for each applicable secondary line."""
    opportunities: list[dict[str, Any]] = []
    for assessment in iter_session_secondary_assessments(
        lines, same_incision=same_incision, cross_specialty=cross_specialty, claim=claim,
    ):
        line = assessment.line
        primary_line = assessment.primary_line
        factor = assessment.factor
        session = assessment.session
        session_expected = expected_session_billed_try(line, point_factor=factor.point_factor)
        blood_ceiling = blood_component_max_billable_try(line)
        # These are constraints on the same line, not additive opportunities.
        # Compose actual amounts: session list×quantity and blood payable can differ.
        expected_billed = (
            min(session_expected, blood_ceiling) if blood_ceiling is not None
            else session_expected
        )
        actual_billed = _line_billed(line)
        if actual_billed >= expected_billed * (1.0 - _BILLING_TOLERANCE):
            continue
        uplift = expected_billed - actual_billed
        if uplift <= _BILLING_TOLERANCE:
            continue

        uplift_money = _money(uplift)
        primary_billed = _line_billed(primary_line)
        # A lower blood ceiling must not promote an existing chart-review-only
        # session into confirmed money by reducing the review heuristic's gap.
        clinical_review = needs_clinical_review(
            primary_billed_try=primary_billed,
            actual_billed_try=actual_billed,
            recoverable_uplift_try=_money(session_expected - actual_billed),
        )
        detail = (
            f"Secondary procedure billed below SUT §{session.sut_section} "
            f"allowed {factor.point_factor:.0%} point factor; "
            f"recoverable uplift {uplift_money:.2f} TRY."
        )
        if blood_ceiling is not None:
            detail += (
                f" Blood component ceiling {blood_ceiling:.2f} TRY per "
                "SUT §2.2.2.B-1.e also applies; counted once at the lower ceiling."
            )
        if clinical_review:
            detail += " Clinical session boundaries not verified — chart review before rebill."

        row = {
            "type": _OPPORTUNITY_TYPE,
            "claim_id": claim_id or line.claim_id,
            "procedure_line_id": line.procedure_line_id,
            "procedure_code": line.procedure_code,
            "procedure_name": line.procedure_name,
            "session_date": str(assessment.session_date),
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
        if blood_ceiling is not None:
            row["session_expected_billed_try"] = _money(session_expected)
            row["blood_max_billable_try"] = _money(blood_ceiling)
        opportunities.append(row)
    return opportunities

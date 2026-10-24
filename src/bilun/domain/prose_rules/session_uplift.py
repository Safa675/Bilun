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
from .mandated_package_gap import mandated_package_scope
from .session_pricing import (
    MISSING_BRANCH,
    MISSING_INCISION,
    billed_package_scopes,
    blood_component_max_billable_try,
    compute_session_readings,
    expected_session_billed_try,
)
from .session_scope import line_billed_as_package, session_operation_lines
from .types import SAVINGS_BASIS_SOURCED, SAVINGS_CATEGORY_SGK_UPLIFT
from .yatak_puani import c000672_hizmet_basi_lines, must_be_billed_as_package

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
    """An applicable session constraint, including lines with no positive gap.

    ``factor`` is the line's factor under the strictest legal reading and
    ``lenient_factor`` under the most lenient one (``SessionReadings``); they are
    one factor when the bill shows the incision and the branches
    (``missing_facts`` empty).
    """

    line: ProcedureClaimLine
    primary_line: ProcedureClaimLine
    factor: SessionProcedureFactor
    session_date: date
    session: SessionPricingResult
    lenient_factor: SessionProcedureFactor | None = None
    missing_facts: tuple[str, ...] = ()

    @property
    def lenient(self) -> SessionProcedureFactor:
        return self.lenient_factor or self.factor


def iter_session_secondary_assessments(
    lines: list[ProcedureClaimLine],
    *,
    same_incision: bool | None = None,
    cross_specialty: bool | None = None,
    claim: ClaimHeader | None = None,
) -> Iterator[SessionSecondaryAssessment]:
    """Share session ownership by line occurrence, never by procedure code.

    Keep non-underbilled secondaries too: another detector cannot claim money
    above their applicable session ceiling just because this gap is zero.
    ``same_incision`` None means the bill does not show the incision, which no
    claim line carries; each assessment then has both readings.
    """
    by_claim: dict[str, list[ProcedureClaimLine]] = defaultdict(list)
    for line in lines:
        by_claim[line.claim_id].append(line)
    for claim_lines in by_claim.values():
        for session_date, session_lines in group_procedure_lines_by_session(claim_lines).items():
            billable = [
                line for line in session_operation_lines(session_lines)
                if not line.is_package_included and _line_billed(line) > 0
            ]
            if len(billable) < 2:
                continue
            readings = compute_session_readings(
                billable,
                same_incision=same_incision,
                cross_specialty=cross_specialty,
                claim=claim,
                as_of_date=session_date,
                billed_as_package=[line_billed_as_package(line) for line in billable],
            )
            session = readings.strict
            if session.rule_id == "single_procedure":
                continue

            # Factors retain input occurrence order and omit empty codes.
            # A code-keyed map loses the primary when normalized codes repeat.
            # Both readings rank by puan, so they share the primary and the order.
            factors, lenient_factors = iter(session.factors), iter(readings.lenient.factors)
            assessed = [
                (line, next(factors), next(lenient_factors)) for line in billable
                if normalize_procedure_code(line.procedure_code)
            ]
            primary = next(
                ((line, factor) for line, factor, _ in assessed if factor.is_primary), None,
            )
            if primary is None:
                continue
            primary_line, primary_factor = primary
            for line, factor, lenient_factor in assessed:
                if factor.is_primary or factor.point_factor >= primary_factor.point_factor:
                    continue
                yield SessionSecondaryAssessment(
                    line, primary_line, factor, session_date, session,
                    lenient_factor=lenient_factor, missing_facts=readings.missing_facts,
                )


# Turkish wording of the facts a bill may not show, for the "kontrol et" text.
_MISSING_TR = {
    (MISSING_INCISION,): ("kesi bilgisi", "ayrı kesi", "aynı kesi",
                          "Ameliyat notundaki kesi bilgisini kontrol edin."),
    (MISSING_BRANCH,): ("branş bilgisi", "farklı branş (+25 puan)", "aynı branş",
                        "İşlemi yapan hekimin branşını kontrol edin."),
    (MISSING_INCISION, MISSING_BRANCH): (
        "kesi ve branş bilgisi",
        "ayrı kesi ve farklı branş (+25 puan)",
        "aynı kesi ve aynı branş",
        "Ameliyat notundaki kesi bilgisini ve işlemi yapan hekimin branşını kontrol edin.",
    ),
}


def missing_fact_wording(missing_facts: tuple[str, ...]) -> tuple[str, str, str, str]:
    """(missing fact, lenient reading, strict reading, what to check), in Turkish."""
    return _MISSING_TR[missing_facts]


def _percent_tr(factor: float) -> str:
    return f"%{factor * 100:.0f}"


def _sentence_start(text: str) -> str:
    return text[:1].upper() + text[1:]


def session_reading_clause(factor: SessionProcedureFactor) -> str:
    """"SUT §2.2.2.B.b %50": the clause and percentage of one reading."""
    return f"SUT §{factor.trace.sut_section} {_percent_tr(factor.point_factor)}"


def session_review_detail_tr(
    assessment: SessionSecondaryAssessment,
    *,
    actual_billed_try: float,
    strict_expected_try: float,
    lenient_expected_try: float,
    overbilled: bool,
) -> str:
    """Turkish "kontrol et" detail of a 0-TL session review row.

    The billed amount lies between the strict and the lenient reading, so it is
    correct under one and wrong under the other; the row names the missing fact.
    """
    missing, lenient, strict, check = missing_fact_wording(assessment.missing_facts)
    line, primary = assessment.line, assessment.primary_line
    head = (
        f"Kontrol et: faturada {missing} yok. {line.procedure_code} aynı seansta "
        f"{primary.procedure_code} ile birlikte {actual_billed_try:.2f} TRY faturalanmış. "
    )
    strict_clause = session_reading_clause(assessment.factor)
    lenient_clause = session_reading_clause(assessment.lenient)
    if overbilled:
        gap = actual_billed_try - strict_expected_try
        body = (
            f"{_sentence_start(strict)} ise {strict_clause} ile {strict_expected_try:.2f} TRY "
            f"ödenir ve {gap:.2f} TRY fazla faturalanmıştır; {lenient} ise "
            f"{lenient_clause} ile en çok {lenient_expected_try:.2f} TRY ödenir."
        )
    else:
        gap = lenient_expected_try - actual_billed_try
        body = (
            f"{_sentence_start(lenient)} ise {lenient_clause} ile "
            f"{lenient_expected_try:.2f} TRY ödenir ve {gap:.2f} TRY eksik faturalanmıştır; "
            f"{strict} ise {strict_clause} ile {strict_expected_try:.2f} TRY ödenir."
        )
    return f"{head}{body} {check}"


def session_money_note_tr(
    assessment: SessionSecondaryAssessment,
    *,
    other_reading_extra_try: float,
    overbilled: bool,
) -> str:
    """Turkish note on a money row whose amount rests on one reading only.

    Over-billing is claimed above the lenient reading, under-billing below the
    strict one; the note says what the other reading would add.
    """
    missing, lenient, strict, check = missing_fact_wording(assessment.missing_facts)
    if overbilled:
        return (
            f"Kontrol et: faturada {missing} yok; tutar en lehe okumaya göredir ({lenient}, "
            f"{session_reading_clause(assessment.lenient)}). {_sentence_start(strict)} ise "
            f"{session_reading_clause(assessment.factor)} uygulanır ve "
            f"{other_reading_extra_try:.2f} TRY daha fazla faturalanmıştır. {check}"
        )
    return (
        f"Kontrol et: faturada {missing} yok; tutar en katı okumaya göredir ({strict}, "
        f"{session_reading_clause(assessment.factor)}). {_sentence_start(lenient)} ise "
        f"{session_reading_clause(assessment.lenient)} ile {other_reading_extra_try:.2f} TRY "
        f"daha ödenir. {check}"
    )


def _lines_priced_by_the_package(
    claim: ClaimHeader | None,
    lines: list[ProcedureClaimLine],
) -> set[int]:
    """Lines whose under-billing belongs to the package, not to a session uplift.

    A line billed hizmet başı though its package is mandated is rebilled as that
    package, as its payment-method row says, so it has no hizmet başı uplift
    (review item 9); a session C000672 bills hizmet başı keeps its uplift. On a
    claim the mandated-package comparison covers (#269),
    every line inside the package window is priced on the package side and the
    strategy row reports the gap, so an uplift there would count it twice.
    """
    if claim is None:
        return set()
    claim_lines = [line for line in lines if line.claim_id == claim.claim_id]
    hizmet_basi = {id(line) for line in c000672_hizmet_basi_lines(claim, claim_lines)}
    priced = {
        id(line) for line in claim_lines
        if id(line) not in hizmet_basi and must_be_billed_as_package(claim, line)
    }
    scope = mandated_package_scope(claim, claim_lines)
    if scope is not None:
        priced |= {id(line) for line in scope.lines}
    return priced


def _session_review_row(
    assessment: SessionSecondaryAssessment,
    *,
    claim_id: str,
    actual_billed: float,
    strict_expected: float,
    lenient_expected: float,
) -> dict[str, Any]:
    """0-TL "kontrol et" row: billed at or above the strict reading, below the lenient.

    SGK uplift is claimed only below the strictest legal reading (Safa, 2026-10-16,
    "2b"); the part the lenient reading would add waits for the missing fact.
    """
    line, factor = assessment.line, assessment.lenient
    review = _money(lenient_expected - actual_billed)
    return {
        "type": _OPPORTUNITY_TYPE,
        "claim_id": claim_id or line.claim_id,
        "procedure_line_id": line.procedure_line_id,
        "procedure_code": line.procedure_code,
        "procedure_name": line.procedure_name,
        "session_date": str(assessment.session_date),
        "expected_point_factor": factor.point_factor,
        "primary_procedure_code": assessment.primary_line.procedure_code,
        "primary_billed_try": _money(_line_billed(assessment.primary_line)),
        "expected_billed_try": _money(lenient_expected),
        "actual_billed_try": _money(actual_billed),
        "recoverable_uplift_try": 0.0,
        "review_uplift_try": review,
        "review_kind": REVIEW_KIND_CLINICAL,
        "included_in_sgk_total": False,
        "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
        "savings_basis": SAVINGS_BASIS_SOURCED,
        "sut_section_id": factor.trace.sut_section,
        "rule_id": factor.trace.rule_id,
        "detail": session_review_detail_tr(
            assessment, actual_billed_try=actual_billed, strict_expected_try=strict_expected,
            lenient_expected_try=lenient_expected, overbilled=False,
        ),
        **_reading_fields(assessment, strict_expected, lenient_expected),
    }


def _reading_fields(
    assessment: SessionSecondaryAssessment,
    strict_expected: float,
    lenient_expected: float,
) -> dict[str, Any]:
    """Both readings on a row whose amount depends on a fact the bill does not show."""
    if not assessment.missing_facts:
        return {}
    return {
        "missing_facts": list(assessment.missing_facts),
        "strict_point_factor": assessment.factor.point_factor,
        "strict_expected_billed_try": _money(strict_expected),
        "lenient_point_factor": assessment.lenient.point_factor,
        "lenient_expected_billed_try": _money(lenient_expected),
    }


def detect_session_underbilling_opportunities(
    lines: list[ProcedureClaimLine],
    *,
    claim_id: str = "",
    same_incision: bool | None = None,
    cross_specialty: bool | None = None,
    claim: ClaimHeader | None = None,
) -> list[dict[str, Any]]:
    """Flag one composed underbilling gap for each applicable secondary line.

    Never on a line the package comparison owns (``_lines_priced_by_the_package``).
    Money only below the strictest legal reading; a line billed at or above it but
    below the most lenient one gets a 0-TL review row (``_session_review_row``).
    """
    opportunities: list[dict[str, Any]] = []
    package_scopes = billed_package_scopes(lines)
    priced_by_the_package = _lines_priced_by_the_package(claim, lines)
    for assessment in iter_session_secondary_assessments(
        lines, same_incision=same_incision, cross_specialty=cross_specialty, claim=claim,
    ):
        line = assessment.line
        if id(line) in priced_by_the_package:
            continue
        primary_line = assessment.primary_line
        factor = assessment.factor
        session_expected = expected_session_billed_try(
            line, point_factor=factor.point_factor, claim=claim,
        )
        if session_expected is None:  # No list price: the gap cannot be measured.
            continue
        lenient_session_expected = expected_session_billed_try(
            line, point_factor=assessment.lenient.point_factor, claim=claim,
        ) or session_expected
        blood_ceiling = blood_component_max_billable_try(
            line, package_context=(line.patient_id, line.claim_id, line.episode_id) in package_scopes,
        )
        # These are constraints on the same line, not additive opportunities.
        # Compose actual amounts: session list×quantity and blood payable can differ.
        expected_billed = (
            min(session_expected, blood_ceiling) if blood_ceiling is not None
            else session_expected
        )
        lenient_expected = (
            min(lenient_session_expected, blood_ceiling) if blood_ceiling is not None
            else lenient_session_expected
        )
        actual_billed = _line_billed(line)
        if actual_billed >= expected_billed * (1.0 - _BILLING_TOLERANCE):
            if (
                assessment.missing_facts
                and actual_billed < lenient_expected * (1.0 - _BILLING_TOLERANCE)
                and lenient_expected - actual_billed > _BILLING_TOLERANCE
            ):
                opportunities.append(_session_review_row(
                    assessment, claim_id=claim_id, actual_billed=actual_billed,
                    strict_expected=expected_billed, lenient_expected=lenient_expected,
                ))
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
            f"Secondary procedure billed below SUT §{factor.trace.sut_section} "
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
        if assessment.missing_facts and lenient_expected - expected_billed > _BILLING_TOLERANCE:
            detail += " " + session_money_note_tr(
                assessment, other_reading_extra_try=lenient_expected - expected_billed,
                overbilled=False,
            )

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
            "sut_section_id": factor.trace.sut_section,
            "rule_id": factor.trace.rule_id,
            "detail": detail,
            **_reading_fields(assessment, expected_billed, lenient_expected),
        }
        if blood_ceiling is not None:
            row["session_expected_billed_try"] = _money(session_expected)
            row["blood_max_billable_try"] = _money(blood_ceiling)
        opportunities.append(row)
    return opportunities

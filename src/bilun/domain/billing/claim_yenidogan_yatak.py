"""Yenidoğan (newborn) bed billing from exact inpatient claim dates.

Wraps :func:`detect_yenidogan_yatak_opportunities` in the same exactness-gated
review shape used across the billing layer; ``YenidoganYatakReview`` lives in
``billing/types.py`` next to ``YatakPuaniReview``. The motor sees the claim's
procedure lines (netting of the billed bed lines, ICU and package gates), and
``claim_yatak_newborn_overlap`` takes its days out of the standard-bed
expectation.
"""

from __future__ import annotations


from src.bilun.domain.billing.types import (
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    YenidoganYatakReview,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.yenidogan_yatak import (
    detect_yenidogan_yatak_opportunities,
)

_PROSE_RULE_SOURCE = (
    "SUT EK-2B newborn bed tariff (510070 Kuvöz / 510081 Kot) — inclusive LOS × price_try"
)

YENIDOGAN_YATAK_REQUIRED_INPUTS = (
    "inpatient_claims_with_dates",
    "procedure_claim_lines",
    "newborn_detection_signal",  # Z38/P00-P96 diagnosis or yenidoğan department
)
YENIDOGAN_YATAK_UNAVAILABLE_REASON = (
    "Yenidoğan yatak billing requires inpatient claims with admission/discharge "
    "dates, procedure claim lines, and a newborn detection signal (Z38/P00-P96 "
    "diagnosis or yenidoğan department), which are not available in the active "
    "SUT runtime inputs."
)


def recommend_yenidogan_yatak_from_claims(
    ctx: PatientClaimContext,
) -> YenidoganYatakReview:
    """Compute expected newborn bed charges for inpatient newborn claims.

    Honours the patient_report wiring gate: without procedure lines the
    review is reported as missing-inputs rather than emitting opportunities.
    """
    if not ctx.procedure_lines:
        return YenidoganYatakReview(
            exactness_status=EXACTNESS_STATUS_MISSING_INPUTS,
            unavailable_reason=YENIDOGAN_YATAK_UNAVAILABLE_REASON,
            required_inputs_missing=list(YENIDOGAN_YATAK_REQUIRED_INPUTS),
            rule_source=_PROSE_RULE_SOURCE,
        )

    claim_ids_with_procs = {line.claim_id for line in ctx.procedure_lines}
    opportunities = detect_yenidogan_yatak_opportunities(
        list(ctx.claims),
        list(ctx.diagnoses),
        procedure_lines=list(ctx.procedure_lines),
        claim_ids_with_procs=claim_ids_with_procs,
    )

    return YenidoganYatakReview(
        opportunities=opportunities,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
    )

"""Yatak puanı (bed-day) billing from exact inpatient claim dates."""

from __future__ import annotations

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.yatak_puani import (
    detect_yatak_puani_opportunities,
)

from .types import (
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    YATAK_PUANI_REQUIRED_INPUTS,
    YATAK_PUANI_UNAVAILABLE_REASON,
    YatakPuaniReview,
)

_PROSE_RULE_SOURCE = (
    "SUT §2.2.2 standard bed tariff (510010) — inclusive LOS × price_try"
)


def recommend_yatak_puani_from_claims(
    ctx: PatientClaimContext,
) -> YatakPuaniReview:
    """Compute expected bed-day charges for inpatient claims."""
    if not ctx.procedure_lines:
        return YatakPuaniReview(
            exactness_status=EXACTNESS_STATUS_MISSING_INPUTS,
            unavailable_reason=YATAK_PUANI_UNAVAILABLE_REASON,
            required_inputs_missing=list(YATAK_PUANI_REQUIRED_INPUTS),
            rule_source=_PROSE_RULE_SOURCE,
        )

    claim_ids_with_procs = {line.claim_id for line in ctx.procedure_lines}
    opportunities = detect_yatak_puani_opportunities(
        list(ctx.claims),
        claim_ids_with_procs=claim_ids_with_procs,
    )

    return YatakPuaniReview(
        opportunities=opportunities,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
    )

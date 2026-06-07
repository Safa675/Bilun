"""Prospective gazette repricing opportunities from exact claim lines."""

from __future__ import annotations

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.gazette_repricing import (
    detect_gazette_repricing_opportunities,
)

from .types import (
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    GAZETTE_REPRICING_UNAVAILABLE_REASON,
    GAZETTE_REPRICING_REQUIRED_INPUTS,
    GazetteRepricingOpportunity,
)

_PROSE_RULE_SOURCE = (
    "EK-2B/EK-2C gazette amendment repricing — prospective review only"
)


def recommend_gazette_repricing_from_claims(
    ctx: PatientClaimContext,
) -> GazetteRepricingOpportunity:
    """Detect claim lines priced below post-tebliğ gazette list prices."""
    if not ctx.procedure_lines:
        return GazetteRepricingOpportunity(
            exactness_status=EXACTNESS_STATUS_MISSING_INPUTS,
            unavailable_reason=GAZETTE_REPRICING_UNAVAILABLE_REASON,
            required_inputs_missing=list(GAZETTE_REPRICING_REQUIRED_INPUTS),
            rule_source=_PROSE_RULE_SOURCE,
        )

    opportunities: list[dict] = []
    for claim in ctx.claims:
        claim_procs = [
            line for line in ctx.procedure_lines if line.claim_id == claim.claim_id
        ]
        if not claim_procs:
            continue
        opportunities.extend(
            detect_gazette_repricing_opportunities(claim, claim_procs)
        )

    return GazetteRepricingOpportunity(
        opportunities=opportunities,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
    )

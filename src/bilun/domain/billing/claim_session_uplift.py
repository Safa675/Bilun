"""Session pricing uplift from exact procedure claim lines."""

from __future__ import annotations

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.session_uplift import detect_session_underbilling_opportunities

from .types import (
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    SESSION_UPLIFT_REQUIRED_INPUTS,
    SESSION_UPLIFT_UNAVAILABLE_REASON,
    SessionPricingUplift,
)

_PROSE_RULE_SOURCE = (
    "SUT §2.2.2.B same-session point factors (session_pricing_2_2_2_B) — under-billing uplift"
)


def recommend_session_uplift_from_claims(
    ctx: PatientClaimContext,
) -> SessionPricingUplift:
    """Detect recoverable SGK uplift when secondaries are under-billed in a session."""
    if not ctx.procedure_lines:
        return SessionPricingUplift(
            exactness_status=EXACTNESS_STATUS_MISSING_INPUTS,
            unavailable_reason=SESSION_UPLIFT_UNAVAILABLE_REASON,
            required_inputs_missing=list(SESSION_UPLIFT_REQUIRED_INPUTS),
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
            detect_session_underbilling_opportunities(
                claim_procs,
                claim_id=claim.claim_id,
                same_incision=True,
                cross_specialty=None,
                claim=claim,
            )
        )

    return SessionPricingUplift(
        opportunities=opportunities,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
    )

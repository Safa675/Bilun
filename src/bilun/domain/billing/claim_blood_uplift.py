"""Blood component fraction uplift from exact procedure claim lines."""

from __future__ import annotations

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.blood_uplift import (
    detect_blood_component_underbilling_opportunities,
)

from .types import (
    BLOOD_UPLIFT_REQUIRED_INPUTS,
    BLOOD_UPLIFT_UNAVAILABLE_REASON,
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    BloodComponentUplift,
)

_PROSE_RULE_SOURCE = (
    "SUT §2.2.2.B-1.e blood component partial billing (session_pricing_2_2_2_B) — under-billing"
)


def recommend_blood_uplift_from_claims(
    ctx: PatientClaimContext,
) -> BloodComponentUplift:
    """Detect recoverable SGK uplift when blood components are under-billed."""
    if not ctx.procedure_lines:
        return BloodComponentUplift(
            exactness_status=EXACTNESS_STATUS_MISSING_INPUTS,
            unavailable_reason=BLOOD_UPLIFT_UNAVAILABLE_REASON,
            required_inputs_missing=list(BLOOD_UPLIFT_REQUIRED_INPUTS),
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
            detect_blood_component_underbilling_opportunities(
                claim_procs,
                claim_id=claim.claim_id,
                claim=claim,
            )
        )

    return BloodComponentUplift(
        opportunities=opportunities,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
    )

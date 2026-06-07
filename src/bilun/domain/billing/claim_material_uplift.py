"""Missing billable material uplift from exact claim lines."""

from __future__ import annotations

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.material_uplift import (
    detect_missing_billable_material_opportunities,
)

from .types import (
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    MATERIAL_UPLIFT_REQUIRED_INPUTS,
    MATERIAL_UPLIFT_UNAVAILABLE_REASON,
    MaterialUplift,
)

_PROSE_RULE_SOURCE = (
    "SUT §3.1 missing billable material pairing (inverse EK-3B-1) — uplift-only"
)


def recommend_material_uplift_from_claims(
    ctx: PatientClaimContext,
) -> MaterialUplift:
    """Detect recoverable SGK uplift when expected materials were not billed."""
    if not ctx.procedure_lines:
        return MaterialUplift(
            exactness_status=EXACTNESS_STATUS_MISSING_INPUTS,
            unavailable_reason=MATERIAL_UPLIFT_UNAVAILABLE_REASON,
            required_inputs_missing=list(MATERIAL_UPLIFT_REQUIRED_INPUTS),
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
            detect_missing_billable_material_opportunities(
                claim,
                claim_procs,
                list(ctx.material_lines),
            )
        )

    return MaterialUplift(
        opportunities=opportunities,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
    )

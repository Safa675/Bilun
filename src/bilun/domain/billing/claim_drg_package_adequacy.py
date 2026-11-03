"""Advisory DRG / EK-2/C package code adequacy review from exact claim lines."""

from __future__ import annotations

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.drg_package_adequacy import (
    detect_drg_package_adequacy_opportunities,
)

from .types import (
    DRG_PACKAGE_ADEQUACY_REQUIRED_INPUTS,
    DRG_PACKAGE_ADEQUACY_UNAVAILABLE_REASON,
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    DrgPackageAdequacyReview,
)

_PROSE_RULE_SOURCE = (
    "SUT §2.2.1.B EK-2/C package adequacy — documentation review only"
)


def recommend_drg_package_adequacy_from_claims(
    ctx: PatientClaimContext,
) -> DrgPackageAdequacyReview:
    """Detect under-coded package codes when clinical footprint supports a higher candidate."""
    if not ctx.procedure_lines:
        return DrgPackageAdequacyReview(
            exactness_status=EXACTNESS_STATUS_MISSING_INPUTS,
            unavailable_reason=DRG_PACKAGE_ADEQUACY_UNAVAILABLE_REASON,
            required_inputs_missing=list(DRG_PACKAGE_ADEQUACY_REQUIRED_INPUTS),
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
            detect_drg_package_adequacy_opportunities(claim, claim_procs)
        )

    return DrgPackageAdequacyReview(
        opportunities=opportunities,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
    )

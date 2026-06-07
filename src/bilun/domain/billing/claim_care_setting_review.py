"""Advisory care-setting review from exact claim lines."""

from __future__ import annotations

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.care_setting_review import (
    detect_care_setting_review_opportunities,
)

from .types import (
    CARE_SETTING_REVIEW_REQUIRED_INPUTS,
    CARE_SETTING_REVIEW_UNAVAILABLE_REASON,
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    CareSettingReview,
)

_PROSE_RULE_SOURCE = (
    "SUT §2.2.1.B / §2.2.2 care-setting ambiguity — coding review only"
)


def recommend_care_setting_review_from_claims(
    ctx: PatientClaimContext,
) -> CareSettingReview:
    """Detect advisory uplift when alternate care setting is legally higher."""
    if not ctx.procedure_lines:
        return CareSettingReview(
            exactness_status=EXACTNESS_STATUS_MISSING_INPUTS,
            unavailable_reason=CARE_SETTING_REVIEW_UNAVAILABLE_REASON,
            required_inputs_missing=list(CARE_SETTING_REVIEW_REQUIRED_INPUTS),
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
            detect_care_setting_review_opportunities(claim, claim_procs)
        )

    return CareSettingReview(
        opportunities=opportunities,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
    )

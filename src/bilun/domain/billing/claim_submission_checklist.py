"""Proactive claim submission checklist wiring for billing reports."""

from __future__ import annotations

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.claim_readiness import detect_claim_readiness_for_context

from .types import (
    CLAIM_SUBMISSION_CHECKLIST_REQUIRED_INPUTS,
    CLAIM_SUBMISSION_CHECKLIST_UNAVAILABLE_REASON,
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    EXACTNESS_STATUS_NOT_APPLICABLE,
    ClaimSubmissionChecklist,
)

_RULE_SOURCE = (
    "Claim submission checklist — proactive MEDULA risk triggers from claim-line flags"
)


def recommend_claim_submission_checklist_from_claims(
    ctx: PatientClaimContext,
) -> ClaimSubmissionChecklist:
    """Surface pre-submission MEDULA risk reminders when claim-shape signals exist."""
    has_lines = bool(ctx.procedure_lines or ctx.material_lines or ctx.drug_lines)
    if not has_lines:
        return ClaimSubmissionChecklist(
            exactness_status=EXACTNESS_STATUS_NOT_APPLICABLE,
            unavailable_reason=CLAIM_SUBMISSION_CHECKLIST_UNAVAILABLE_REASON,
            required_inputs_missing=list(CLAIM_SUBMISSION_CHECKLIST_REQUIRED_INPUTS),
            rule_source=_RULE_SOURCE,
        )

    if not ctx.claims:
        return ClaimSubmissionChecklist(
            exactness_status=EXACTNESS_STATUS_MISSING_INPUTS,
            unavailable_reason=CLAIM_SUBMISSION_CHECKLIST_UNAVAILABLE_REASON,
            required_inputs_missing=["claims"],
            rule_source=_RULE_SOURCE,
        )

    items = detect_claim_readiness_for_context(ctx)
    return ClaimSubmissionChecklist(
        items=items,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_RULE_SOURCE,
    )

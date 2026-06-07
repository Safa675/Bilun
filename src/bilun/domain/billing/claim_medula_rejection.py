"""MEDULA rejection corrective rebill playbook from exact claim ingest."""

from __future__ import annotations

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.medula_rejection import (
    detect_medula_rejection_playbook_entries,
)

from .types import (
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_NOT_APPLICABLE,
    MEDULA_PLAYBOOK_UNAVAILABLE_REASON,
    MEDULA_PLAYBOOK_REQUIRED_INPUTS,
    MedulaRejectionPlaybook,
)

_PROSE_RULE_SOURCE = (
    "MEDULA rejection → corrective rebill playbook — operational template only"
)


def recommend_medula_rejection_playbook_from_claims(
    ctx: PatientClaimContext,
) -> MedulaRejectionPlaybook:
    """Map ingested MEDULA rejection events to SUT-anchored corrective templates."""
    if not ctx.medula_rejection_events:
        return MedulaRejectionPlaybook(
            exactness_status=EXACTNESS_STATUS_NOT_APPLICABLE,
            unavailable_reason=MEDULA_PLAYBOOK_UNAVAILABLE_REASON,
            required_inputs_missing=list(MEDULA_PLAYBOOK_REQUIRED_INPUTS),
            rule_source=_PROSE_RULE_SOURCE,
        )

    entries: list[dict] = []
    for claim in ctx.claims:
        claim_events = [
            event
            for event in ctx.medula_rejection_events
            if event.claim_id == claim.claim_id
        ]
        if not claim_events:
            continue
        entries.extend(
            detect_medula_rejection_playbook_entries(claim, list(claim_events))
        )

    return MedulaRejectionPlaybook(
        entries=entries,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
    )

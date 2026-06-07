"""Performed-not-submitted procedure capture gap from EMR/OR logs."""

from __future__ import annotations

from typing import Any

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.procedure_capture_gap import detect_procedure_capture_gaps

from .types import (
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_NOT_APPLICABLE,
    PROCEDURE_CAPTURE_GAP_REQUIRED_INPUTS,
    PROCEDURE_CAPTURE_GAP_UNAVAILABLE_REASON,
    ProcedureCaptureGap,
)

_PROSE_RULE_SOURCE = (
    "EMR/OR performed procedure log vs claim submission — capture gap (display-only)"
)


def recommend_procedure_capture_gap_from_claims(
    ctx: PatientClaimContext,
) -> ProcedureCaptureGap:
    """Detect performed procedures not submitted on claims when EMR log is present."""
    if not ctx.performed_procedure_lines:
        return ProcedureCaptureGap(
            opportunities=[],
            exactness_status=EXACTNESS_STATUS_NOT_APPLICABLE,
            unavailable_reason=PROCEDURE_CAPTURE_GAP_UNAVAILABLE_REASON,
            required_inputs_missing=list(PROCEDURE_CAPTURE_GAP_REQUIRED_INPUTS),
            rule_source=_PROSE_RULE_SOURCE,
        )

    opportunities: list[dict] = []
    for claim in ctx.claims:
        claim_performed = [
            line
            for line in ctx.performed_procedure_lines
            if line.claim_id == claim.claim_id
        ]
        if not claim_performed:
            continue
        claim_procs = [
            line for line in ctx.procedure_lines if line.claim_id == claim.claim_id
        ]
        opportunities.extend(
            detect_procedure_capture_gaps(claim, claim_performed, claim_procs)
        )

    return ProcedureCaptureGap(
        opportunities=opportunities,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
    )

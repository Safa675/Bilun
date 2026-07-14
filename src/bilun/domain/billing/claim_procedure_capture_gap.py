"""Performed-not-submitted capture gap from EMR/OR logs and clinical lab feed."""

from __future__ import annotations


import polars as pl

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.lab_capture_gap import detect_lab_capture_gaps
from src.bilun.domain.prose_rules.procedure_capture_gap import detect_procedure_capture_gaps

from .types import (
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_NOT_APPLICABLE,
    PROCEDURE_CAPTURE_GAP_REQUIRED_INPUTS,
    PROCEDURE_CAPTURE_GAP_UNAVAILABLE_REASON,
    ProcedureCaptureGap,
)

_PROSE_RULE_SOURCE = (
    "EMR/OR performed procedure log and clinical lab feed vs claim submission — capture gap (display-only)"
)


def recommend_procedure_capture_gap_from_claims(
    ctx: PatientClaimContext,
    lab_df_pl: pl.DataFrame | None = None,
) -> ProcedureCaptureGap:
    """Detect performed procedures/labs not submitted on claims.

    Sources:
    - ``ctx.performed_procedure_lines`` (EMR/OR log) for non-lab procedures.
    - ``lab_df_pl`` (clinical lab feed) for lab tests with results but no claim line.

    The section is unavailable only when both sources are absent.
    """
    has_performed = bool(ctx.performed_procedure_lines)
    has_lab = lab_df_pl is not None and not lab_df_pl.is_empty()

    if not has_performed and not has_lab:
        return ProcedureCaptureGap(
            opportunities=[],
            exactness_status=EXACTNESS_STATUS_NOT_APPLICABLE,
            unavailable_reason=PROCEDURE_CAPTURE_GAP_UNAVAILABLE_REASON,
            required_inputs_missing=list(PROCEDURE_CAPTURE_GAP_REQUIRED_INPUTS),
            rule_source=_PROSE_RULE_SOURCE,
        )

    opportunities: list[dict] = []

    # EMR/OR performed procedure gaps.
    if has_performed:
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

    # Clinical lab gaps.
    if has_lab:
        for claim in ctx.claims:
            claim_procs = [
                line for line in ctx.procedure_lines if line.claim_id == claim.claim_id
            ]
            service_date = claim.claim_start_date or claim.admission_date
            opportunities.extend(
                detect_lab_capture_gaps(
                    lab_df_pl,
                    claim_procs,
                    claim.episode_id,
                    service_date=service_date,
                )
            )

    return ProcedureCaptureGap(
        opportunities=opportunities,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
    )

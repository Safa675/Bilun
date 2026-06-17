"""Per-bill lab optimization and procedure capture-gap merge."""

from __future__ import annotations

import polars as pl

from src.bilun.domain.claims.patient_context import PatientClaimContext

from .claim_lab import _optimize_lab_billing_from_claims
from .claim_procedure_capture_gap import recommend_procedure_capture_gap_from_claims
from .types import EXACTNESS_STATUS_EXACT, LabOptimization, ProcedureCaptureGap


def compute_lab_and_capture_gap_from_claims(
    claim_context: PatientClaimContext,
    lab_df_pl: pl.DataFrame | None,
) -> tuple[LabOptimization, ProcedureCaptureGap]:
    """Compute lab optimization and capture gap by summing per-bill results.

    Each claim is treated as its own bill for lab purposes. Lab optimization
    uses billed lab claim lines; capture gap compares the clinical lab feed
    against those billed lines per episode.
    """
    merged_lab = LabOptimization()
    merged_gap = ProcedureCaptureGap()

    if not claim_context.claims:
        return merged_lab, merged_gap

    lab_by_visit: dict[str | None, pl.DataFrame] = {}
    if lab_df_pl is not None and not lab_df_pl.is_empty() and "visit_id" in lab_df_pl.columns:
        for vid, group in lab_df_pl.group_by("visit_id"):
            lab_by_visit[str(vid[0]) if isinstance(vid, tuple) else str(vid)] = group

    for claim in claim_context.claims:
        bill_context = claim_context.slice_for_claim(claim.claim_id)
        if bill_context is None:
            continue

        lab_result = _optimize_lab_billing_from_claims(bill_context)
        merged_lab.normative_cost_try = round(
            merged_lab.normative_cost_try + lab_result.normative_cost_try, 2
        )
        merged_lab.session_fraction_savings = round(
            merged_lab.session_fraction_savings + lab_result.session_fraction_savings, 2
        )
        merged_lab.hemogram_bundling_savings = round(
            merged_lab.hemogram_bundling_savings + lab_result.hemogram_bundling_savings, 2
        )
        merged_lab.flagged_tests.extend(lab_result.flagged_tests)

        lab_for_claim = lab_by_visit.get(claim.episode_id)
        if lab_for_claim is not None or bill_context.performed_procedure_lines:
            gap_result = recommend_procedure_capture_gap_from_claims(
                bill_context,
                lab_df_pl=lab_for_claim,
            )
            merged_gap.opportunities.extend(gap_result.opportunities)

    if merged_lab.flagged_tests or merged_gap.opportunities:
        merged_lab.exactness_status = EXACTNESS_STATUS_EXACT
        merged_gap.exactness_status = EXACTNESS_STATUS_EXACT

    return merged_lab, merged_gap

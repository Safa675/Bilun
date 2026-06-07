"""Aggregate audit exposure (over-billing risk) from exact claim lines — display only."""

from __future__ import annotations

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.drg_unbundling import analyze_claim_unbundling


def _money(value: float | int) -> float:
    return round(float(value), 2)


def compute_audit_exposure_from_claims(ctx: PatientClaimContext) -> float:
    """Sum sourced/heuristic over-billing risk — not SGK uplift."""
    if not ctx.procedure_lines:
        return 0.0

    total = 0.0
    for claim in ctx.claims:
        claim_procs = [
            line for line in ctx.procedure_lines if line.claim_id == claim.claim_id
        ]
        if not claim_procs:
            continue

        finding = analyze_claim_unbundling(claim, claim_procs, same_incision=True)
        if finding is None:
            continue

        for bucket in (
            finding.session_violations,
            finding.blood_component_violations,
            finding.payment_method_violations,
            finding.bundled_violations,
        ):
            total += sum(float(entry.get("risk_amount_try") or 0.0) for entry in bucket)

    return _money(total)

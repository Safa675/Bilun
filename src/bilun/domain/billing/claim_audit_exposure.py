"""Aggregate audit exposure (over-billing risk) from exact claim lines — display only."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules.drg_unbundling import (
    ClaimUnbundlingFinding,
    analyze_claim_unbundling,
)

# The four buckets of an unbundling finding that add to ``audit_exposure_try``, in the
# order ``audit_exposure_total`` adds them.
_EXPOSURE_BUCKETS: tuple[str, ...] = (
    "session_violations",
    "blood_component_violations",
    "payment_method_violations",
    "bundled_violations",
)

# The buckets that become action rows, with the row kind. ``payment_method_violations`` is
# left out on purpose: the same ``mandated_package_gap`` already gives the bill a
# ``billing_strategy`` ``compliance_violation`` row, and a second row would list one
# finding twice. Its money stays in ``audit_exposure_try``.
_ROW_BUCKETS: tuple[tuple[str, str], ...] = (
    ("session_violations", "session_point_violation"),
    ("blood_component_violations", "blood_component_partial_bill"),
    ("bundled_violations", "bundled_line_flag"),
)


def unbundling_findings_from_claims(ctx: PatientClaimContext) -> list[ClaimUnbundlingFinding]:
    """One unbundling finding per claim that has procedure lines, in claim order."""
    if not ctx.procedure_lines:
        return []

    findings: list[ClaimUnbundlingFinding] = []
    for claim in ctx.claims:
        claim_procs = [
            line for line in ctx.procedure_lines if line.claim_id == claim.claim_id
        ]
        if not claim_procs:
            continue

        # No claim line carries the incision: session money is taken above the
        # most lenient reading (``detect_session_point_violations``).
        finding = analyze_claim_unbundling(
            claim,
            claim_procs,
            drug_lines=ctx.drug_lines,
            material_lines=ctx.material_lines,
        )
        if finding is not None:
            findings.append(finding)
    return findings


def audit_exposure_total(findings: list[ClaimUnbundlingFinding]) -> float:
    """Sum sourced/heuristic over-billing risk — not SGK uplift."""
    total = 0.0
    for finding in findings:
        for attr in _EXPOSURE_BUCKETS:
            total += sum(
                float(entry.get("risk_amount_try") or 0.0) for entry in getattr(finding, attr)
            )
    return _money(total)


def audit_exposure_rows(findings: list[ClaimUnbundlingFinding]) -> list[dict[str, Any]]:
    """The entries behind ``audit_exposure_total``, one row per entry that carries risk.

    ``collect_billing_actions`` turns each row into an ``audit_exposure`` action row.
    """
    rows: list[dict[str, Any]] = []
    for finding in findings:
        for attr, kind in _ROW_BUCKETS:
            for entry in getattr(finding, attr):
                risk = float(entry.get("risk_amount_try") or 0.0)
                if risk <= 0:
                    continue
                rows.append(
                    {
                        "kind": kind,
                        "claim_id": finding.claim_id,
                        "procedure_line_id": entry.get("procedure_line_id"),
                        "procedure_code": entry.get("procedure_code"),
                        "procedure_name": entry.get("procedure_name"),
                        "risk_amount_try": _money(risk),
                        "sut_section": entry.get("sut_section"),
                        "rule_id": entry.get("rule_id"),
                        "detail": entry.get("detail"),
                    }
                )
    return rows


@dataclass(frozen=True)
class AuditExposureReview:
    """The over-billing exposure of a claim context: its total and the rows behind it."""

    total_try: float = 0.0
    rows: list[dict[str, Any]] = field(default_factory=list)


def recommend_audit_exposure_from_claims(ctx: PatientClaimContext) -> AuditExposureReview:
    """One unbundling pass: the exposure total and the rows that explain it."""
    findings = unbundling_findings_from_claims(ctx)
    return AuditExposureReview(
        total_try=audit_exposure_total(findings),
        rows=audit_exposure_rows(findings),
    )


def compute_audit_exposure_from_claims(ctx: PatientClaimContext) -> float:
    """Sum sourced/heuristic over-billing risk of a claim context — not SGK uplift."""
    return audit_exposure_total(unbundling_findings_from_claims(ctx))

"""Aggregate audit exposure (over-billing risk) from exact claim lines — display only.

Three sources add into one total and one list of rows: the unbundling findings (session factor, blood component,
bundled line, mandated-package payment method), the standard-bed lines billed on a day a newborn bed covers
(``prose_rules.yatak_newborn_overlap``, the same detector ``analyze_claim`` calls) and the EK-2/B codes billed on a
day above the daily cap of their Açıklama (``prose_rules.ek2b_daily_limits``). The risk of one line is counted
once: a line already at risk under an earlier source keeps only what it billed beyond that.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules.drg_unbundling import (
    ClaimUnbundlingFinding,
    analyze_claim_unbundling,
)
from src.bilun.domain.prose_rules.ek2b_daily_limits import detect_ek2b_daily_limit_violations
from src.bilun.domain.prose_rules.yatak_newborn_overlap import detect_yatak_newborn_overlap

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


def _risk_by_line(findings: list[ClaimUnbundlingFinding]) -> dict[tuple[str, str], float]:
    """The risk the unbundling findings already count per ``(claim_id, procedure_line_id)``, over all four buckets.

    The payment-method bucket has money in the total and no row, so it is counted here too. A line is
    identified by the pair, as everywhere in the claim data: two claims may reuse a line id.
    """
    by_line: dict[tuple[str, str], float] = defaultdict(float)
    for finding in findings:
        for attr in _EXPOSURE_BUCKETS:
            for entry in getattr(finding, attr):
                if line_id := entry.get("procedure_line_id"):
                    by_line[(finding.claim_id, str(line_id))] += float(entry.get("risk_amount_try") or 0.0)
    return by_line


def newborn_bed_overlap_rows(
    ctx: PatientClaimContext, counted_by_line: dict[tuple[str, str], float]
) -> list[dict[str, Any]]:
    """The 510010 lines of the bill's claims billed on a day a newborn bed (510070 / 510081) covers.

    The detector reads the patient's history, so a newborn bed on another claim of the patient is seen, and
    emits for the claims of ``ctx`` only. A line is at risk for at most what it billed: money the unbundling
    findings already count on the same line (``counted_by_line``) is taken off, so a package-included bed that
    is also on a newborn bed day is not counted twice.
    """
    if not ctx.procedure_lines:
        return []

    rows: list[dict[str, Any]] = []
    for violation in detect_yatak_newborn_overlap(
        list(ctx.history.procedure_lines),
        claim_ids_with_procs={line.claim_id for line in ctx.procedure_lines},
    ):
        counted = counted_by_line.get((violation["claim_id"], violation["procedure_line_id"]), 0.0)
        room = violation["billed_amount_try"] - counted
        risk = _money(min(violation["risk_amount_try"], max(0.0, room)))
        if risk <= 0:
            continue
        rows.append(
            {
                "kind": violation["type"],
                "claim_id": violation["claim_id"],
                "procedure_line_id": violation["procedure_line_id"],
                "procedure_code": violation["procedure_code"],
                "procedure_name": violation["procedure_name"],
                "risk_amount_try": risk,
                "sut_section": violation["sut_section_id"],
                "rule_id": violation["rule_id"],
                "detail": violation["detail"],
            }
        )
    return rows


def daily_limit_rows(
    ctx: PatientClaimContext, counted_by_line: dict[tuple[str, str], float]
) -> list[dict[str, Any]]:
    """The EK-2/B codes of the bill's claims billed on a day above the daily cap of their Açıklama (#303).

    One row per claim and code (``prose_rules.ek2b_daily_limits``). A line is at risk for at most what it billed:
    money the earlier rows already count on the same line (``counted_by_line``) is taken off.
    """
    billed = {(line.claim_id, line.procedure_line_id): float(line.billed_amount_try) for line in ctx.procedure_lines}
    rows: list[dict[str, Any]] = []
    for violation in detect_ek2b_daily_limit_violations(list(ctx.procedure_lines)):
        claim_id = violation["claim_id"]
        risk = _money(
            sum(
                min(line_risk, max(0.0, billed[(claim_id, line_id)] - counted_by_line.get((claim_id, line_id), 0.0)))
                for line_id, line_risk in violation["line_risks"].items()
            )
        )
        if risk <= 0:
            continue
        rows.append(
            {
                "kind": violation["type"],
                "claim_id": claim_id,
                "procedure_line_id": violation["procedure_line_id"],
                "procedure_code": violation["procedure_code"],
                "procedure_name": violation["procedure_name"],
                "risk_amount_try": risk,
                "sut_section": violation["sut_section_id"],
                "rule_id": violation["rule_id"],
                "detail": violation["detail"],
            }
        )
    return rows


def recommend_audit_exposure_from_claims(ctx: PatientClaimContext) -> AuditExposureReview:
    """One unbundling pass, one bed pass and one daily-cap pass: the exposure total and the rows that explain it."""
    findings = unbundling_findings_from_claims(ctx)
    counted = _risk_by_line(findings)
    bed_rows = newborn_bed_overlap_rows(ctx, counted)
    for row in bed_rows:
        key = (row["claim_id"], str(row["procedure_line_id"]))
        counted[key] = counted.get(key, 0.0) + row["risk_amount_try"]
    cap_rows = daily_limit_rows(ctx, counted)
    extra_rows = [*bed_rows, *cap_rows]
    return AuditExposureReview(
        total_try=_money(audit_exposure_total(findings) + sum(row["risk_amount_try"] for row in extra_rows)),
        rows=[*audit_exposure_rows(findings), *extra_rows],
    )


def compute_audit_exposure_from_claims(ctx: PatientClaimContext) -> float:
    """Sum sourced/heuristic over-billing risk of a claim context — not SGK uplift."""
    return recommend_audit_exposure_from_claims(ctx).total_try

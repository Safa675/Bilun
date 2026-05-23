"""Feature 5: DRG unbundling detection from exact claim lines."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .exactness import (
    DRG_UNBUNDLING_UNAVAILABLE_REASON,
    DRG_UNBUNDLING_REQUIRED_INPUTS,
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    unavailable_patient_drg_unbundling,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.patient_context import PatientClaimContext


def detect_drg_unbundling(
    patient_icd10_chapters: set[str],
    claim_context: PatientClaimContext | None = None,
) -> dict[str, Any]:
    """Detect DRG package unbundling risk from exact claim lines when available."""

    _ = patient_icd10_chapters
    if claim_context is None:
        return unavailable_patient_drg_unbundling()

    chapter_analysis: list[dict[str, Any]] = []
    total_potential_savings = 0.0
    has_risk = False

    for claim in claim_context.claims:
        if not claim.package_candidate:
            continue

        claim_procs = [
            line for line in claim_context.procedure_lines if line.claim_id == claim.claim_id
        ]
        if not claim_procs:
            continue

        bundled_violations = [
            line
            for line in claim_procs
            if line.is_package_included and float(line.billed_amount_try) > 0
        ]
        itemized_total = sum(
            float(line.expected_payable_try)
            for line in claim_procs
            if line.procedure_category != "paket" and not line.is_package_included
        )
        package_total = sum(
            float(line.expected_payable_try)
            for line in claim_procs
            if line.procedure_category == "paket"
        )

        claim_savings = 0.0
        if bundled_violations:
            has_risk = True
            claim_savings += sum(
                float(line.billed_amount_try - line.expected_payable_try)
                for line in bundled_violations
            )
        if package_total > 0 and itemized_total > package_total:
            has_risk = True
            claim_savings += itemized_total - package_total

        if claim_savings > 0:
            chapter = (claim.primary_icd10 or "R")[:1].upper()
            chapter_analysis.append(
                {
                    "claim_id": claim.claim_id,
                    "chapter": chapter,
                    "bundled_violations": len(bundled_violations),
                    "itemized_total_try": round(itemized_total, 2),
                    "package_total_try": round(package_total, 2),
                    "potential_savings_try": round(claim_savings, 2),
                }
            )
            total_potential_savings += claim_savings

    if not chapter_analysis and not has_risk:
        return {
            "exactness_status": EXACTNESS_STATUS_EXACT,
            "has_unbundling_risk": False,
            "n_chapters_analyzed": len({c.primary_icd10[:1] for c in claim_context.claims if c.primary_icd10}),
            "total_potential_savings": 0.0,
            "chapter_analysis": [],
            "methodology": (
                "Compared package-candidate claims for bundled-line violations and "
                "itemized vs package payable totals using exact claim lines."
            ),
        }

    return {
        "exactness_status": EXACTNESS_STATUS_EXACT,
        "has_unbundling_risk": has_risk,
        "n_chapters_analyzed": len({entry["chapter"] for entry in chapter_analysis}),
        "total_potential_savings": round(total_potential_savings, 2),
        "chapter_analysis": chapter_analysis,
        "methodology": (
            "Flags bundled procedures billed separately and itemized totals exceeding "
            "package totals on package-candidate claims."
        ),
    }


def unavailable_cohort_drg_unbundling_with_context(
    *,
    n_total_patients: int,
    n_patients_with_risk: int,
    total_potential_savings: float,
    top_risky_chapters: list[dict[str, Any]],
) -> dict[str, Any]:
    if n_total_patients == 0:
        return {
            "exactness_status": EXACTNESS_STATUS_MISSING_INPUTS,
            "unavailable_reason": DRG_UNBUNDLING_UNAVAILABLE_REASON,
            "required_inputs_missing": list(DRG_UNBUNDLING_REQUIRED_INPUTS),
            "n_patients_checked": 0,
            "n_patients_with_risk": None,
            "risk_rate": None,
            "total_potential_savings": None,
            "top_risky_chapters": [],
        }

    return {
        "exactness_status": EXACTNESS_STATUS_EXACT,
        "n_patients_checked": n_total_patients,
        "n_patients_with_risk": n_patients_with_risk,
        "risk_rate": round(n_patients_with_risk / n_total_patients, 4),
        "total_potential_savings": round(total_potential_savings, 2),
        "top_risky_chapters": top_risky_chapters,
        "methodology": (
            "Aggregated per-patient DRG unbundling findings from exact claim lines."
        ),
    }

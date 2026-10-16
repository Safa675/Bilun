"""Feature 5: DRG unbundling detection from exact claim lines."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.bilun.domain.prose_rules.drg_unbundling import (
    analyze_claim_unbundling,
    finding_to_dict,
)
from src.bilun.domain.prose_rules.yatak_puani import claim_package_window

from .exactness import (
    DRG_UNBUNDLING_UNAVAILABLE_REASON,
    DRG_UNBUNDLING_REQUIRED_INPUTS,
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    unavailable_patient_drg_unbundling,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.patient_context import PatientClaimContext

_PROSE_METHODOLOGY = (
    "Uses exact claim lines with SUT §2.2 prose rules: package-included bundling, "
    "payment-method compliance (EK-2/B vs EK-2/C), same-session point factors "
    "(§2.2.2.B), and blood-component partial billing limits."
)


def detect_drg_unbundling(
    patient_icd10_chapters: set[str],
    claim_context: PatientClaimContext | None = None,
) -> dict[str, Any]:
    """Detect DRG package unbundling risk from exact claim lines when available."""

    _ = patient_icd10_chapters
    if claim_context is None:
        return unavailable_patient_drg_unbundling()

    patient_chapters = {
        str(ch).strip().upper()[:1]
        for ch in patient_icd10_chapters
        if ch and str(ch).strip()
    }
    chapter_analysis: list[dict[str, Any]] = []
    total_potential_savings = 0.0
    total_sourced_savings = 0.0
    has_risk = False
    payment_method_violations = 0
    session_violations = 0
    blood_component_violations = 0
    bundled_violations = 0

    for claim in claim_context.claims:
        claim_procs = [
            line for line in claim_context.procedure_lines if line.claim_id == claim.claim_id
        ]
        # Package claims by their codes: a line billed as an EK-2/C package, or
        # one that must be (#286); never the synthetic-only package_candidate flag.
        if not claim_procs or claim_package_window(claim, claim_procs) is None:
            continue

        # Same-incision (kesi) is not on claim lines yet; assume same session until wired.
        finding = analyze_claim_unbundling(
            claim,
            claim_procs,
            same_incision=True,
            drug_lines=claim_context.drug_lines,
            material_lines=claim_context.material_lines,
        )
        if finding is None or not finding.has_risk:
            continue

        has_risk = True
        total_potential_savings += finding.sourced_savings_try
        total_sourced_savings += finding.sourced_savings_try
        bundled_violations += len(finding.bundled_violations)
        payment_method_violations += len(finding.payment_method_violations)
        session_violations += len(finding.session_violations)
        blood_component_violations += len(finding.blood_component_violations)
        chapter_analysis.append(finding_to_dict(finding))

    claim_chapters = {
        str(c.primary_icd10).strip().upper()[:1]
        for c in claim_context.claims
        if c.primary_icd10
    }
    chapters_analyzed = patient_chapters | claim_chapters

    if not chapter_analysis and not has_risk:
        return {
            "exactness_status": EXACTNESS_STATUS_EXACT,
            "has_unbundling_risk": False,
            "n_chapters_analyzed": len(chapters_analyzed),
            "patient_icd10_chapters": sorted(patient_chapters),
            "total_potential_savings": 0.0,
            "total_sourced_savings": 0.0,
            "chapter_analysis": [],
            "payment_method_violations": 0,
            "session_violations": 0,
            "blood_component_violations": 0,
            "bundled_violations": 0,
            "methodology": _PROSE_METHODOLOGY,
            "rule_source": "SUT §2.2 prose_rules/drg_unbundling + EK-2B/EK-2C catalogs",
        }

    return {
        "exactness_status": EXACTNESS_STATUS_EXACT,
        "has_unbundling_risk": has_risk,
        "n_chapters_analyzed": len(
            chapters_analyzed | {entry["chapter"] for entry in chapter_analysis}
        ),
        "patient_icd10_chapters": sorted(patient_chapters),
        "total_potential_savings": round(total_potential_savings, 2),
        "total_sourced_savings": round(total_sourced_savings, 2),
        "chapter_analysis": chapter_analysis,
        "payment_method_violations": payment_method_violations,
        "session_violations": session_violations,
        "blood_component_violations": blood_component_violations,
        "bundled_violations": bundled_violations,
        "methodology": _PROSE_METHODOLOGY,
        "rule_source": "SUT §2.2 prose_rules/drg_unbundling + EK-2B/EK-2C catalogs",
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
            "Aggregated per-patient DRG unbundling findings from exact claim lines "
            "with SUT §2.2 prose rule checks."
        ),
        "rule_source": "SUT §2.2 prose_rules/drg_unbundling + EK-2B/EK-2C catalogs",
    }

"""
src/bilun/domain/optimization/copay_exemptions.py
Composable copay exemption evaluation (EK-1A + status / visit rules).
"""

from __future__ import annotations

from typing import Any

from .copay_exemption_context import CopayExemptionInput
from .copay_exemption_rules import (
    evaluate_ek1a_exemption,
    evaluate_occupational_exemption,
    evaluate_patient_status_exemptions,
    evaluate_visit_type_exemptions,
)
from .copay_exemption_types import empty_copay_exemption_result

__all__ = [
    "check_copay_exemptions",
    "evaluate_copay_exemption",
]


def _exempts_every_claim(source: dict[str, Any]) -> bool:
    """A ground that counts exempts the evaluated claims, unless it is claim-scoped and leaves one out.

    The emergency ground (SUT 1.8.5.(5)) waives its own bills: over a patient with other bills it is listed
    but does not make the patient exempt.
    """
    return bool(source.get("counts_toward_exempt", True)) and bool(
        source.get("covers_every_claim", True)
    )


def evaluate_copay_exemption(inp: CopayExemptionInput) -> dict[str, Any]:
    """Evaluate all applicable copay exemption grounds for one patient."""
    sources: list[dict[str, Any]] = []
    not_evaluated: list[dict[str, Any]] = []

    ek1a = evaluate_ek1a_exemption(
        inp.diagnoses,
        has_health_report=inp.has_chronic_health_report,
    )
    if ek1a is not None:
        sources.append(ek1a)

    sources.extend(
        evaluate_visit_type_exemptions(
            inp.claim_visit_types,
            inp.claim_procedure_codes,
        )
    )

    occ = evaluate_occupational_exemption(
        inp.claim_visit_types,
        inp.occupational_contexts,
    )
    if occ is not None:
        sources.append(occ)

    status_sources, status_missing = evaluate_patient_status_exemptions(
        inp.patient_profile,
        age_at_latest_claim=inp.age_at_latest_claim,
    )
    sources.extend(status_sources)
    not_evaluated.extend(status_missing)

    qualifying: list[dict[str, str]] = []
    if ek1a is not None:
        qualifying = list(ek1a.get("evidence", {}).get("qualifying_diagnoses", []))

    exempt = any(_exempts_every_claim(s) for s in sources)
    partial_exempt = bool(qualifying) and not exempt
    primary = next(
        (s["category"] for s in sources if _exempts_every_claim(s)),
        sources[0]["category"] if sources else None,
    )

    result = empty_copay_exemption_result()
    result.update(
        {
            "exempt": exempt,
            "partial_exempt": partial_exempt,
            "n_qualifying": len(qualifying),
            "qualifying_diagnoses": qualifying,
            "exemption_sources": sources,
            "categories_not_evaluated": not_evaluated,
            "primary_exemption_category": primary,
            "has_chronic_health_report": inp.has_chronic_health_report,
        }
    )
    return result


def check_copay_exemptions(patient_diagnoses: list[str]) -> dict[str, Any]:
    """Backward-compatible diagnosis-only exemption check."""
    return evaluate_copay_exemption(CopayExemptionInput(diagnoses=patient_diagnoses))

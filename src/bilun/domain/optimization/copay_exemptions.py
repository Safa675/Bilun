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
from .copay_exemption_rules.ek1a import _get_ek1a_by_letter, _precompute_exemption_map
from .copay_exemption_types import empty_copay_exemption_result

__all__ = [
    "check_copay_exemptions",
    "evaluate_copay_exemption",
    "_get_ek1a_by_letter",
    "_precompute_exemption_map",
]


def evaluate_copay_exemption(inp: CopayExemptionInput) -> dict[str, Any]:
    """Evaluate all applicable copay exemption grounds for one patient."""
    sources: list[dict[str, Any]] = []
    not_evaluated: list[dict[str, Any]] = []

    ek1a = evaluate_ek1a_exemption(inp.diagnoses)
    if ek1a is not None:
        sources.append(ek1a)

    sources.extend(evaluate_visit_type_exemptions(inp.claim_visit_types))

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

    exempt = len(sources) > 0
    primary = sources[0]["category"] if sources else None

    result = empty_copay_exemption_result()
    result.update(
        {
            "exempt": exempt,
            "n_qualifying": len(qualifying),
            "qualifying_diagnoses": qualifying,
            "exemption_sources": sources,
            "categories_not_evaluated": not_evaluated,
            "primary_exemption_category": primary,
        }
    )
    return result


def check_copay_exemptions(patient_diagnoses: list[str]) -> dict[str, Any]:
    """Backward-compatible diagnosis-only exemption check."""
    return evaluate_copay_exemption(CopayExemptionInput(diagnoses=patient_diagnoses))

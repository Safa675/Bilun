"""
src/bilun/domain/billing/copay.py
Algorithm 3: Copay savings calculator with EK-1A exemptions.
"""

from __future__ import annotations

from typing import Any

from .types import CopayOptimization


def _optimize_copay(
    patient_id: str,
    copay_exemption: dict[str, Any],
) -> CopayOptimization:
    """Return unavailable copay savings until exact claim inputs are wired.

    Args:
        patient_id: Patient identifier.
        copay_exemption: Pre-computed result from check_copay_exemptions()
            or patient_alerts_cache entry.

    Returns:
        CopayOptimization with explicit missing exact-input metadata.
    """
    result = CopayOptimization()
    _ = patient_id

    is_exempt = copay_exemption.get("exempt", False)
    result.is_exempt = is_exempt

    if is_exempt:
        qualifying = copay_exemption.get("qualifying_diagnoses", [])
        if qualifying:
            result.exemption_disease = qualifying[0].get("disease", "")
            result.exemption_range = qualifying[0].get("range", "")

        disease = result.exemption_disease or "qualifying chronic condition"
        icd_range = result.exemption_range or "EK-1A range"
        result.rate_corrections.append(
            {
                "detail": (
                    f"EK-1A exemption may apply for {disease} ({icd_range}). "
                    "Verify billed copay components against exact claim lines."
                ),
            }
        )

    return result

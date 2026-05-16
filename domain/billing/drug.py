"""
src/bilun/domain/billing/drug.py
Algorithm 2: Drug cost optimizer with generic substitution + passivation detection.
"""

from __future__ import annotations

import logging
from typing import Any

from ..materials import get_ek4a_drugs, lookup_drug_bulk, classify_drug_tier
from .types import DrugOptimization

logger = logging.getLogger("ilay.sut_billing_optimizer")

_ek4a_by_equiv_group: dict[str, list[dict[str, Any]]] | None = None


def _get_ek4a_by_equiv_group() -> dict[str, list[dict[str, Any]]]:
    """Build index: equivalence_group -> list of active EK-4A drugs."""
    global _ek4a_by_equiv_group
    if _ek4a_by_equiv_group is not None:
        return _ek4a_by_equiv_group

    drugs = get_ek4a_drugs()
    index: dict[str, list[dict[str, Any]]] = {}
    for d in drugs:
        pass_date = d.get("passivation_date", "")
        if pass_date and pass_date not in ("", "nan", "None"):
            continue
        eq_group = d.get("equivalence_group", "").strip()
        if eq_group:
            index.setdefault(eq_group, []).append(d)

    _ek4a_by_equiv_group = index
    return _ek4a_by_equiv_group


def _optimize_drug_costs(
    patient_id: str,
    patient_drug_names: list[str],
) -> DrugOptimization:
    """Algorithm 2: Drug cost optimization via generic substitution + passivation detection.

    Args:
        patient_id: Patient identifier.
        patient_drug_names: List of drug names from prescriptions.

    Returns:
        DrugOptimization with per-drug recommendations and savings.
    """
    result = DrugOptimization()

    if not patient_drug_names:
        return result

    unique_drugs = list({d.strip() for d in patient_drug_names if d and d.strip()})
    if not unique_drugs:
        return result

    drug_records = lookup_drug_bulk(unique_drugs)
    equiv_index = _get_ek4a_by_equiv_group()
    all_ek4a = get_ek4a_drugs()

    recommendations: list[dict[str, Any]] = []

    for drug_name in unique_drugs:
        record = drug_records.get(drug_name)
        if record is None:
            continue

        drug_tier = classify_drug_tier(record)

        pass_date = record.get("passivation_date", "")
        if pass_date and pass_date not in ("", "nan", "None"):
            result.passivated_drug_count += 1
            eq_group = record.get("equivalence_group", "").strip()
            alternatives = equiv_index.get(eq_group, [])
            alt_name = (
                alternatives[0]["drug_name"] if alternatives else "No alternative found"
            )
            recommendations.append(
                {
                    "drug_name": drug_name,
                    "issue": "passivated",
                    "alternative": alt_name,
                    "savings_try": 0.0,
                    "detail": f"Drug passivated on {pass_date}. Active alternative available.",
                }
            )
            continue

        eq_group = record.get("equivalence_group", "").strip()
        if not eq_group:
            continue

        alternatives = equiv_index.get(eq_group, [])
        if len(alternatives) <= 1:
            continue

        current_d1 = record.get("discount_tier_1") or 0.0
        current_status = record.get("discount_status", "")

        cheaper_alts = []
        for alt in alternatives:
            if alt["drug_name"] == record["drug_name"]:
                continue
            alt_status = alt.get("discount_status", "")
            alt_d1 = alt.get("discount_tier_1") or 0.0
            if alt_status == "ESDEĞER" and current_status != "ESDEĞER":
                cheaper_alts.append(alt)
            elif alt_d1 > current_d1 + 0.05:
                cheaper_alts.append(alt)

        if cheaper_alts:
            result.n_generics_available += 1
            best_alt = cheaper_alts[0]
            current_tier_mid = {
                "basic": 25.0,
                "moderate": 95.0,
                "specialty": 475.0,
            }.get(drug_tier, 25.0)
            alt_tier = classify_drug_tier(best_alt)
            alt_tier_mid = {"basic": 25.0, "moderate": 95.0, "specialty": 475.0}.get(
                alt_tier, 25.0
            )
            estimated_savings = max(0.0, current_tier_mid - alt_tier_mid)

            result.generic_substitution_savings += estimated_savings
            recommendations.append(
                {
                    "drug_name": drug_name,
                    "issue": "generic_available",
                    "alternative": best_alt["drug_name"],
                    "savings_try": round(estimated_savings, 2),
                    "detail": (
                        f"Generic equivalent in group {eq_group}. "
                        f"Current: {current_status or 'N/A'}, "
                        f"Alternative: {best_alt.get('discount_status', 'N/A')}"
                    ),
                }
            )

    result.generic_substitution_savings = round(result.generic_substitution_savings, 2)
    result.drug_recommendations = recommendations
    return result
"""
exclusion_rules.py — Detect non-reimbursable materials per EK-3B-2.

SUT Rule (EK-3/B-2):
    13 categories of medical materials are NOT covered by SGK:
      - Viskosüplemantasyon ürünleri
      - Spor protezi
      - Kök hücre malzemeleri
      - etc.

    If a claim includes materials from these categories, SGK will not
    reimburse the cost. The hospital bears the full expense.
"""

from __future__ import annotations

import logging
from typing import Any

from src.bilun.domain.materials import (
    get_non_reimbursable_materials,
    is_material_reimbursable,
)
from src.bilun.domain.utils import turkish_lower

logger = logging.getLogger("ilay.sut_optimization.exclusion")


def check_exclusion_violations(
    materials: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Check a list of claim materials for non-reimbursable items per EK-3B-2.

    A material is non-reimbursable if it matches an entry in the EK-3B-2
    exclusion catalog. Such items will NOT be covered by SGK — the
    hospital (or patient) must bear the cost.

    Args:
        materials: List of dicts, each with at least:
            - "name" (str): Material name.
            - "unit_price" (float, optional): Billed unit price.
            - "quantity" (int, optional): Number of units.

    Returns:
        List of violation dicts, each with:
            - rule: "exclusion"
            - severity: "error"
            - material_name: The offending material name.
            - matched_exclusion_entry: The EK-3B-2 entry it matched.
            - billed_amount: Total billed amount for this line.
            - risk_amount: Amount at risk of non-reimbursement.
            - message: Human-readable explanation.
    """
    exclusions = get_non_reimbursable_materials()
    violations: list[dict[str, Any]] = []

    for mat in materials:
        mat_name = str(mat.get("name", "")).strip()
        if not mat_name:
            continue

        unit_price = float(mat.get("unit_price", 0.0))
        quantity = int(mat.get("quantity", 1))
        billed = round(unit_price * quantity, 2)

        if not is_material_reimbursable(mat_name):
            # Find which exclusion entry matched
            matched_entry = _find_matching_exclusion_entry(mat_name, exclusions)
            violations.append(
                {
                    "rule": "exclusion",
                    "severity": "error",
                    "material_name": mat_name,
                    "matched_exclusion_entry": matched_entry,
                    "billed_amount": billed,
                    "risk_amount": billed,
                    "message": (
                        f"'{mat_name}' is non-reimbursable per EK-3B-2 "
                        f"({matched_entry}). "
                        f"SGK will not cover {billed:.2f} TRY."
                    ),
                }
            )

    if violations:
        logger.info(
            "Exclusion check: %d non-reimbursable item(s) found, total risk: %.2f TRY",
            len(violations),
            sum(v["risk_amount"] for v in violations),
        )

    return violations


def _find_matching_exclusion_entry(
    material_name: str,
    exclusions: list[dict[str, Any]],
) -> str:
    """Find which EK-3B-2 exclusion entry a material name matched against."""
    needle = turkish_lower(material_name.strip())
    for entry in exclusions:
        mat_name = turkish_lower((entry.get("material_name") or "").strip())
        if not mat_name:
            continue
        if needle in mat_name or mat_name in needle:
            return entry.get("material_name") or "EK-3B-2 (unknown entry)"
    return "EK-3B-2 (matched)"

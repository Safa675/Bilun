"""
bundling_rules.py — Detect consumables billed separately that should be
bundled into the procedure price per EK-3B-1.

SUT Rule (EK-3/B-1):
    54 categories of simple medical consumables are INCLUDED in the
    procedure fee (EK-2B puan). Hospitals may NOT bill these separately.
    If a claim line-item matches a bundled consumable, it is a billing
    violation and the line-item cost represents potential savings.

Examples of bundled items:
    - Bistüri ucu (scalpel tips)
    - Disposable enjektör (syringes)
    - Eldiven (gloves, non-sterile surgical)
    - Antiseptik solüsyonlar (antiseptic solutions)
"""

from __future__ import annotations

import logging
from typing import Any

from src.bilun.domain.materials import get_bundled_consumables
from src.bilun.domain.utils import turkish_lower, fuzzy_match_name

logger = logging.getLogger("ilay.sut_optimization.bundling")


def check_bundling_violations(
    materials: list[dict[str, Any]],
    procedure_code: str | None = None,
) -> list[dict[str, Any]]:
    """
    Check a list of claim materials for bundling violations.

    A bundling violation occurs when a material that is included in the
    procedure price (per EK-3B-1) is billed as a separate line item.

    Args:
        materials: List of dicts, each with at least:
            - "name" (str): Material/consumable name.
            - "unit_price" (float, optional): Billed unit price.
            - "quantity" (int, optional): Number of units.
        procedure_code: Optional SUT procedure code for context.

    Returns:
        List of violation dicts, each with:
            - rule: "bundling"
            - severity: "warning" or "error"
            - material_name: The offending material name.
            - matched_bundled_item: The EK-3B-1 item it matched.
            - billed_amount: Total billed amount for this line.
            - savings_try: Potential savings (= billed_amount).
            - message: Human-readable explanation.
    """
    bundled_items = get_bundled_consumables()
    if not bundled_items:
        return []

    # Build Turkish-lowercased index for matching
    bundled_index: list[tuple[str, dict[str, Any]]] = []
    for item in bundled_items:
        item_name = turkish_lower((item.get("item_name") or "").strip())
        if item_name:
            bundled_index.append((item_name, item))

    violations: list[dict[str, Any]] = []

    for mat in materials:
        mat_name = str(mat.get("name", "")).strip()
        if not mat_name:
            continue

        mat_lower = turkish_lower(mat_name)
        unit_price = float(mat.get("unit_price", 0.0))
        quantity = int(mat.get("quantity", 1))
        billed = round(unit_price * quantity, 2)

        # Check against bundled items (substring match both directions)
        for bundled_name, bundled_entry in bundled_index:
            if mat_lower in bundled_name or bundled_name in mat_lower:
                _add_bundling_violation(violations, bundled_entry, mat_name, billed,
                                        procedure_code)
                break
        else:
            fuzzy = fuzzy_match_name(mat_lower, bundled_index, threshold=0.80)
            if fuzzy:
                _add_bundling_violation(violations, fuzzy[1], mat_name, billed,
                                        procedure_code)

    if violations:
        logger.info(
            "Bundling check: %d violation(s) found across %d materials, "
            "total potential savings: %.2f TRY",
            len(violations),
            len(materials),
            sum(v["savings_try"] for v in violations),
        )

    return violations


def _add_bundling_violation(
    violations: list[dict[str, Any]],
    bundled_entry: dict[str, Any],
    mat_name: str,
    billed: float,
    procedure_code: str | None,
) -> None:
    category = bundled_entry.get("description") or "Unknown"
    violations.append(
        {
            "rule": "bundling",
            "severity": "error" if billed > 50.0 else "warning",
            "material_name": mat_name,
            "matched_bundled_item": bundled_entry.get("item_name", ""),
            "bundled_category": category,
            "billed_amount": billed,
            "savings_try": billed,
            "procedure_code": procedure_code or "",
            "message": (
                f"'{mat_name}' is bundled into the procedure price "
                f"(EK-3B-1: {category}). "
                f"Cannot be billed separately. "
                f"Potential savings: {billed:.2f} TRY."
            ),
        }
    )

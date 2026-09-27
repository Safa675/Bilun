"""
Claim-line material pricing for validation and analytics surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.bilun.domain.billing.types import (
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
)


@dataclass
class MaterialLinePricing:
    """Exact or unavailable pricing for a single billed material line."""

    material_code: str = ""
    material_name: str = ""
    unit_price: float = 0.0
    quantity: int = 1
    total_price: float = 0.0
    is_reimbursable: bool | None = None
    is_bundled: bool | None = None
    source: str = ""
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    notes: str = ""


def price_material_lines(materials: list[dict[str, Any]]) -> list[MaterialLinePricing]:
    """Price material lines from billed amounts or exact EK-3 code lookup.

    No fuzzy name matching. Lines without a SUT material code are marked
    ``missing_exact_inputs`` and excluded from exact totals.
    """
    from src.bilun.domain.materials import is_consumable_bundled, is_material_reimbursable
    from src.bilun.domain.materials.catalog_lookup import (
        lookup_ek3_list_price_try,
        resolve_material_name_by_code,
    )

    results: list[MaterialLinePricing] = []

    for item in materials:
        name = str(item.get("name", "")).strip()
        code = str(item.get("code", "")).strip().upper()
        qty = max(1, int(item.get("quantity", 1) or 1))
        billed_unit = round(float(item.get("unit_price", 0) or 0), 2)
        billed_total = round(float(item.get("billed_amount", 0) or 0), 2)
        if billed_total <= 0 and billed_unit > 0:
            billed_total = round(billed_unit * qty, 2)

        reimbursable = is_material_reimbursable(name, material_code=code or None)
        bundled = is_consumable_bundled(name, material_code=code or None)

        notes_parts: list[str] = []
        if reimbursable is None:
            notes_parts.append("EK-3B-2 exception applicability unavailable")
        elif not reimbursable:
            notes_parts.append("non-reimbursable (EK-3B)")
        if bundled is None:
            notes_parts.append("EK-3B-1 applicability unavailable (identity, setting or use)")
        elif bundled:
            notes_parts.append("bundled into procedure price (EK-3B-1)")

        if not code:
            notes_parts.append("material code required for exact EK-3 pricing")
            results.append(
                MaterialLinePricing(
                    material_code="",
                    material_name=name,
                    unit_price=billed_unit,
                    quantity=qty,
                    total_price=billed_total,
                    is_reimbursable=reimbursable,
                    is_bundled=bundled,
                    source="missing_code",
                    exactness_status=EXACTNESS_STATUS_MISSING_INPUTS,
                    notes="; ".join(notes_parts),
                )
            )
            continue

        canonical_name = resolve_material_name_by_code(code) or name
        catalog_unit = lookup_ek3_list_price_try(code)

        if billed_unit > 0:
            unit_price = billed_unit
            total_price = billed_total
            source = "billed_amount"
            exactness = EXACTNESS_STATUS_EXACT
        elif catalog_unit is not None:
            unit_price = round(float(catalog_unit), 2)
            total_price = round(unit_price * qty, 2)
            source = "ek3_code"
            exactness = EXACTNESS_STATUS_EXACT
        else:
            unit_price = 0.0
            total_price = 0.0
            source = "ek3_catalog_miss"
            exactness = EXACTNESS_STATUS_MISSING_INPUTS
            notes_parts.append(f"no EK-3 list price for code {code}")

        results.append(
            MaterialLinePricing(
                material_code=code,
                material_name=canonical_name,
                unit_price=unit_price,
                quantity=qty,
                total_price=total_price,
                is_reimbursable=reimbursable,
                is_bundled=bundled,
                source=source,
                exactness_status=exactness,
                notes="; ".join(notes_parts),
            )
        )

    return results

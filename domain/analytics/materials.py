"""
src/bilun/domain/analytics/materials.py
Material cost estimation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..utils import turkish_lower


@dataclass
class MaterialCostEstimate:
    """Cost estimate for a single material item against SUT rules."""

    material_code: str = ""
    material_name: str = ""
    unit_price: float = 0.0
    quantity: int = 1
    total_price: float = 0.0
    is_reimbursable: bool = True
    is_bundled: bool = False
    source: str = ""
    notes: str = ""


def estimate_material_costs(
    materials: list[dict[str, Any]],
) -> list[MaterialCostEstimate]:
    """Estimate costs for a list of material items using SUT rules."""
    from ..materials import (
        get_all_specialty_materials,
        is_consumable_bundled,
        is_material_reimbursable,
    )

    ek3_price_index: dict[str, tuple[float, str]] = {}
    for mat in get_all_specialty_materials():
        mat_name = (mat.get("name") or mat.get("material_name") or "").strip()
        mat_name_lower = turkish_lower(mat_name) if mat_name else ""
        price = mat.get("price_try", 0.0)
        if mat_name_lower and price and price > 0:
            ek3_price_index[mat_name_lower] = (price, mat.get("source", "ek3"))

    results: list[MaterialCostEstimate] = []

    for item in materials:
        name = str(item.get("name", "")).strip()
        code = str(item.get("code", "")).strip()
        qty = int(item.get("quantity", 1))
        hospital_price = float(item.get("unit_price", 0.0))

        reimbursable = is_material_reimbursable(name)
        bundled = is_consumable_bundled(name)

        unit_price = hospital_price
        source = "hospital"
        name_lower = turkish_lower(name)
        if name_lower in ek3_price_index:
            unit_price, source = ek3_price_index[name_lower]
        else:
            for idx_name, (idx_price, idx_src) in ek3_price_index.items():
                if name_lower in idx_name or idx_name in name_lower:
                    unit_price = idx_price
                    source = idx_src
                    break

        if unit_price <= 0:
            unit_price = hospital_price
            source = "hospital" if hospital_price > 0 else "unknown"

        total = round(unit_price * qty, 2)

        notes_parts: list[str] = []
        if not reimbursable:
            notes_parts.append("non-reimbursable (EK-3B)")
        if bundled:
            notes_parts.append("bundled into procedure price (EK-3B-1)")

        results.append(
            MaterialCostEstimate(
                material_code=code,
                material_name=name,
                unit_price=round(unit_price, 2),
                quantity=qty,
                total_price=total,
                is_reimbursable=reimbursable,
                is_bundled=bundled,
                source=source,
                notes="; ".join(notes_parts) if notes_parts else "",
            )
        )

    return results
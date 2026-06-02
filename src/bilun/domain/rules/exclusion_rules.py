"""
exclusion_rules.py — Detect non-reimbursable materials per EK-3B-2.

SUT §3.1.1(7)/(9) — EK-3/B list materials are not reimbursed (13 curated rows).
"""

from __future__ import annotations

import logging
from typing import Any

from src.bilun.domain.materials import get_non_reimbursable_materials
from src.bilun.domain.materials.catalog_lookup import resolve_material_name_by_code
from src.bilun.domain.materials.exclusions import match_exclusion_entry
logger = logging.getLogger("ilay.sut_optimization.exclusion")


def check_exclusion_violations(
    materials: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Check claim materials for EK-3B-2 non-reimbursable items."""
    exclusions = get_non_reimbursable_materials()
    violations: list[dict[str, Any]] = []

    for mat in materials:
        mat_name = str(mat.get("name", "")).strip()
        mat_code = str(mat.get("code") or mat.get("material_code") or "").strip()
        if not mat_name and not mat_code:
            continue

        unit_price = float(mat.get("unit_price", 0.0))
        quantity = int(mat.get("quantity", 1))
        billed = round(unit_price * quantity, 2)

        lookup_name = mat_name
        match_kind = "name"
        if mat_code:
            resolved = resolve_material_name_by_code(mat_code)
            if resolved:
                lookup_name = resolved
                match_kind = "code_resolved"

        matched_entry = match_exclusion_entry(lookup_name, exclusions)
        if matched_entry is None and mat_name and lookup_name != mat_name:
            matched_entry = match_exclusion_entry(mat_name, exclusions)
            match_kind = "name"

        if matched_entry is None:
            continue

        label = matched_entry.get("material_name") or "EK-3B-2"
        violations.append(
            {
                "rule": "exclusion",
                "severity": "error",
                "material_name": mat_name or lookup_name,
                "material_code": mat_code,
                "matched_exclusion_entry": label,
                "match_kind": match_kind,
                "billed_amount": billed,
                "risk_amount": billed,
                "message": (
                    f"'{mat_name or lookup_name}' is non-reimbursable per EK-3B-2 "
                    f"({label}, match={match_kind}). "
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

"""
bundling_rules.py — Detect consumables billed separately that should be
bundled into the procedure price per EK-3B-1.

SUT annex EK-3B-1 (54 consumable categories) + supporting prose §3.1.4.
"""

from __future__ import annotations

import logging
from typing import Any

from src.bilun.domain.materials import get_bundled_consumables
from src.bilun.domain.materials.catalog_lookup import resolve_material_name_by_code
from src.bilun.domain.utils import fuzzy_match_name, token_bound_substring_match, turkish_lower

logger = logging.getLogger("ilay.sut_optimization.bundling")


def check_bundling_violations(
    materials: list[dict[str, Any]],
    procedure_code: str | None = None,
) -> list[dict[str, Any]]:
    """
    Check claim materials for EK-3B-1 bundling violations.

    Match priority:
      1. SUT material code → catalog name → bundled list (error)
      2. Exact / substring name match (error)
      3. Fuzzy name-only match (warning)
    """
    bundled_items = get_bundled_consumables()
    if not bundled_items:
        return []

    bundled_index: list[tuple[str, dict[str, Any]]] = []
    for item in bundled_items:
        item_name = turkish_lower((item.get("item_name") or "").strip())
        if item_name:
            bundled_index.append((item_name, item))

    violations: list[dict[str, Any]] = []

    for mat in materials:
        mat_name = str(mat.get("name", "")).strip()
        mat_code = str(mat.get("code") or mat.get("material_code") or "").strip()
        if not mat_name and not mat_code:
            continue

        unit_price = float(mat.get("unit_price", 0.0))
        quantity = int(mat.get("quantity", 1))
        billed = round(unit_price * quantity, 2)

        matched: tuple[dict[str, Any], str, str] | None = None

        if mat_code:
            resolved_name = resolve_material_name_by_code(mat_code)
            if resolved_name:
                matched = _match_bundled_name(resolved_name, bundled_index)
                if matched is not None:
                    entry, match_kind = matched
                    _add_bundling_violation(
                        violations,
                        entry,
                        mat_name or resolved_name,
                        billed,
                        procedure_code,
                        match_kind="code_resolved",
                        severity="error",
                    )
                    continue

        if mat_name:
            matched = _match_bundled_name(mat_name, bundled_index)
            if matched is not None:
                entry, match_kind = matched
                severity = "warning" if match_kind == "name_fuzzy" else "error"
                _add_bundling_violation(
                    violations,
                    entry,
                    mat_name,
                    billed,
                    procedure_code,
                    match_kind=match_kind,
                    severity=severity,
                )

    if violations:
        logger.info(
            "Bundling check: %d violation(s) found across %d materials, "
            "total potential savings: %.2f TRY",
            len(violations),
            len(materials),
            sum(v["savings_try"] for v in violations),
        )

    return violations


def _match_bundled_name(
    material_name: str,
    bundled_index: list[tuple[str, dict[str, Any]]],
) -> tuple[dict[str, Any], str] | None:
    needle = turkish_lower(material_name.strip())
    if not needle:
        return None

    for bundled_name, bundled_entry in bundled_index:
        # Token-bound match in BOTH directions so a short catalog entry like
        # "lam" no longer matches "melamin", while a long entry like
        # "süt sağma seti" still matches "süt sağma seti (disposable)".
        # Plain `in` substring was bidirectional and produced false positives
        # (e.g. "tel" -> "metal stent", "cam" -> "camaflaj").
        if token_bound_substring_match(needle, bundled_name) or token_bound_substring_match(
            bundled_name, needle
        ):
            return bundled_entry, "name_substring"

    fuzzy = fuzzy_match_name(needle, bundled_index, threshold=0.80)
    if fuzzy:
        return fuzzy[1], "name_fuzzy"
    return None


def _add_bundling_violation(
    violations: list[dict[str, Any]],
    bundled_entry: dict[str, Any],
    mat_name: str,
    billed: float,
    procedure_code: str | None,
    *,
    match_kind: str,
    severity: str,
) -> None:
    category = bundled_entry.get("description") or "Unknown"
    savings = billed if billed > 0 else None
    violations.append(
        {
            "rule": "bundling",
            "severity": severity,
            "material_name": mat_name,
            "matched_bundled_item": bundled_entry.get("item_name", ""),
            "bundled_category": category,
            "billed_amount": billed,
            "savings_try": savings,
            "match_kind": match_kind,
            "procedure_code": procedure_code or "",
            "message": (
                f"'{mat_name}' is bundled into the procedure price "
                f"(EK-3B-1: {category}, match={match_kind}). "
                f"Cannot be billed separately."
                + (f" Potential savings: {billed:.2f} TRY." if billed > 0 else "")
            ),
        }
    )

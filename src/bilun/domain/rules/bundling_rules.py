"""
bundling_rules.py — Detect consumables billed separately that should be
bundled into the procedure price per EK-3B-1.

SUT annex EK-3B-1 (54 consumable categories) + supporting prose §3.1.4.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from src.bilun.domain.materials import get_bundled_consumables
from src.bilun.domain.materials.catalog_lookup import resolve_material_name_by_code
from src.bilun.domain.materials.exclusions import match_bundled_material

if TYPE_CHECKING:
    from src.bilun.domain.claims.patient_context import PatientClaimContext

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

    Delegates to the canonical ``match_bundled_material`` so the runtime check
    and the build-time ``MaterialClaimLine.is_bundled`` enricher share one
    matcher (Phase 2.1 of the unified-claim-engine roadmap).
    """
    bundled_items = get_bundled_consumables()
    if not bundled_items:
        return []

    violations: list[dict[str, Any]] = []

    for mat in materials:
        mat_name = str(mat.get("name", "")).strip()
        mat_code = str(mat.get("code") or mat.get("material_code") or "").strip()
        if not mat_name and not mat_code:
            continue

        unit_price = float(mat.get("unit_price", 0.0))
        quantity = int(mat.get("quantity", 1))
        # Parity with the adapter path (claims/adapter.py:161) and the legacy
        # pricer (analytics/materials.py:50-53): prefer an explicit billed_amount
        # (the amount actually submitted to MEDULA) over unit_price × quantity.
        billed = round(float(mat.get("billed_amount", 0.0) or 0.0), 2)
        if billed <= 0.0:
            billed = round(unit_price * quantity, 2)

        matched = match_bundled_material(mat_name, material_code=mat_code or None)
        if matched is None:
            continue
        entry, match_kind = matched

        # The canonical matcher distinguishes three match kinds; map to the
        # severity/match_kind this function historically emitted.
        if match_kind == "code_resolved":
            resolved_name = resolve_material_name_by_code(mat_code) if mat_code else mat_name
            _add_bundling_violation(
                violations,
                entry,
                mat_name or (resolved_name or ""),
                billed,
                procedure_code,
                match_kind="code_resolved",
                severity="error",
            )
        else:
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


def check_bundling_violations_for_context(ctx: PatientClaimContext) -> list[dict[str, Any]]:
    """EK-3B-1 bundling check over a PatientClaimContext (Phase 2.1e wrapper).

    Reads each MaterialClaimLine's build-time-derived ``is_ek3b1_bundled`` flag
    (populated by ``dataset_builder._enrich_material_regulatory_flags`` from
    the same ``match_bundled_material`` the dict-based
    ``check_bundling_violations`` uses). Parity is structural: both paths
    resolve to the same canonical matcher, so a clause flagged bundled here is
    exactly the set the dict-based check would flag for the same name+code.

    The violation shape mirrors ``check_bundling_violations`` so the
    ``validate_claim`` adapter (Phase 2.4) can use either path interchangeably.
    """
    violations: list[dict[str, Any]] = []
    for line in ctx.material_lines:
        if not line.is_ek3b1_bundled:
            continue
        billed = float(line.billed_amount_try)
        violations.append(
            {
                "rule": "bundling",
                "severity": "error",
                "material_name": line.material_name,
                "matched_bundled_item": line.material_name,
                "bundled_category": "EK-3B-1",
                "billed_amount": billed,
                "savings_try": billed if billed > 0 else None,
                "match_kind": "build_time_derived",
                "procedure_code": "",
                "message": (
                    f"'{line.material_name}' is bundled into the procedure price "
                    f"(EK-3B-1, build-time derived). Cannot be billed separately."
                    + (f" Potential savings: {billed:.2f} TRY." if billed > 0 else "")
                ),
            }
        )
    return violations

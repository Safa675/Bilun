"""
exclusion_rules.py — Detect non-reimbursable materials per EK-3B-2.

SUT §3.1.1(7)/(9) — EK-3/B list materials are not reimbursed (13 curated rows).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from src.bilun.domain.materials import get_non_reimbursable_materials
from src.bilun.domain.materials.catalog_lookup import resolve_material_name_by_code
from src.bilun.domain.materials.exclusions import match_exclusion_entry

if TYPE_CHECKING:
    from src.bilun.domain.claims.patient_context import PatientClaimContext
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
        # Parity with the adapter path (claims/adapter.py:161) and the legacy
        # pricer (analytics/materials.py:50-53): prefer an explicit billed_amount
        # (the amount actually submitted to MEDULA) over unit_price × quantity.
        billed = round(float(mat.get("billed_amount", 0.0) or 0.0), 2)
        if billed <= 0.0:
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


def check_exclusion_violations_for_context(ctx: PatientClaimContext) -> list[dict[str, Any]]:
    """EK-3B-2 exclusion check over a PatientClaimContext (Phase 2.1e wrapper).

    Reads each MaterialClaimLine's build-time-derived ``is_excluded`` flag
    (populated by ``dataset_builder._enrich_material_regulatory_flags`` from
    the same ``is_material_reimbursable`` / ``match_exclusion_entry`` the
    dict-based ``check_exclusion_violations`` uses). Parity is structural: both
    paths resolve to the same canonical matcher.

    The violation shape mirrors ``check_exclusion_violations`` so the
    ``validate_claim`` adapter (Phase 2.4) can use either path interchangeably.
    """
    violations: list[dict[str, Any]] = []
    for line in ctx.material_lines:
        if not line.is_excluded:
            continue
        risk = float(line.billed_amount_try)
        violations.append(
            {
                "rule": "exclusion",
                "severity": "error",
                "material_name": line.material_name,
                "material_code": line.material_code,
                "matched_exclusion_entry": line.material_name,
                "match_kind": "build_time_derived",
                "billed_amount": risk,
                "risk_amount": risk,
                "message": (
                    f"'{line.material_name}' is non-reimbursable (EK-3B-2, "
                    f"build-time derived). Should not be billed."
                ),
            }
        )
    return violations

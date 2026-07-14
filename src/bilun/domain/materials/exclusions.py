"""
src/bilun/domain/materials/exclusions.py
EK-3B-1 bundled consumables and EK-3B-2 non-reimbursable materials.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import pandas as pd

from ..constants import EK3B1_BUNDLED_PATH, EK3B2_NON_REIMBURSABLE_PATH
from ..utils import _safe_str, turkish_lower, fuzzy_match_name, token_bound_substring_match

logger = logging.getLogger("ilay.sut_catalog")


@lru_cache(maxsize=1)
def get_non_reimbursable_materials() -> tuple[dict[str, Any], ...]:
    """Get the list of non-reimbursable materials from EK-3B-2.

    Returns:
        Tuple of dicts with keys: sira_no, material_name. (Tuple for
        hashability so ``@lru_cache`` can memoize — thread-safe by design,
        replacing the prior mutable-global + ``global`` pattern that raced
        under ``ThreadPoolExecutor`` cohort runs.)
    """
    if not EK3B2_NON_REIMBURSABLE_PATH.exists():
        logger.warning(
            "EK-3B-2 non-reimbursable catalog not found: %s",
            EK3B2_NON_REIMBURSABLE_PATH,
        )
        return ()

    try:
        df = pd.read_parquet(EK3B2_NON_REIMBURSABLE_PATH)
        records = tuple(
            {
                "sira_no": row.get("sira_no"),
                "material_name": _safe_str(row.get("material_name")),
            }
            for _, row in df.iterrows()
        )
        logger.info("EK-3B-2 non-reimbursable materials loaded: %d items", len(records))
        return records
    except Exception as e:
        logger.warning("Failed to load EK-3B-2 non-reimbursable materials: %s", e)
        return ()


@lru_cache(maxsize=1)
def get_bundled_consumables() -> tuple[dict[str, Any], ...]:
    """Get the list of consumables bundled into procedure prices from EK-3B-1.

    Returns:
        Tuple of dicts with keys: sira_no, item_name, description.
    """
    if not EK3B1_BUNDLED_PATH.exists():
        logger.warning("EK-3B-1 bundled consumables not found: %s", EK3B1_BUNDLED_PATH)
        return ()

    try:
        df = pd.read_parquet(EK3B1_BUNDLED_PATH)
        records = tuple(
            {
                "sira_no": row.get("sira_no"),
                "item_name": _safe_str(row.get("item_name")),
                "description": _safe_str(row.get("description")),
            }
            for _, row in df.iterrows()
        )
        logger.info("EK-3B-1 bundled consumables loaded: %d items", len(records))
        return records
    except Exception as e:
        logger.warning("Failed to load EK-3B-1 bundled consumables: %s", e)
        return ()


def match_exclusion_entry(
    material_name: str,
    exclusions: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Return the EK-3B-2 entry matched by name, or None if reimbursable."""
    catalog = exclusions if exclusions is not None else get_non_reimbursable_materials()
    if not catalog:
        return None

    needle = turkish_lower(material_name.strip())
    if not needle:
        return None

    for entry in catalog:
        mat_name = turkish_lower((entry.get("material_name") or "").strip())
        if not mat_name:
            continue
        # Token-bound match (both directions) — plain `in` substring matched
        # short catalog entries against unrelated materials ("tel" -> "metal stent").
        if token_bound_substring_match(needle, mat_name) or token_bound_substring_match(
            mat_name, needle
        ):
            return entry

    fuzzy_candidates = [
        (turkish_lower((e.get("material_name") or "").strip()), e)
        for e in catalog
    ]
    fuzzy_candidates = [(n, e) for n, e in fuzzy_candidates if n]
    fuzzy = fuzzy_match_name(needle, fuzzy_candidates, threshold=0.80)
    return fuzzy[1] if fuzzy else None


def is_material_reimbursable(
    material_name: str,
    *,
    material_code: str | None = None,
) -> bool:
    """Check whether a material is reimbursable (not on EK-3B-2 list)."""
    from .catalog_lookup import resolve_material_name_by_code

    lookup_name = material_name
    if material_code:
        resolved = resolve_material_name_by_code(material_code)
        if resolved:
            lookup_name = resolved

    if match_exclusion_entry(lookup_name) is not None:
        return False
    if lookup_name != material_name and match_exclusion_entry(material_name) is not None:
        return False
    return True


def is_consumable_bundled(item_name: str) -> bool:
    """Check whether a consumable is bundled into procedure prices (EK-3B-1).

    Args:
        item_name: Consumable name to check.

    Returns:
        True if the consumable IS bundled, False if can be billed separately.
    """
    return match_bundled_material(item_name) is not None


def match_bundled_material(
    material_name: str,
    *,
    material_code: str | None = None,
) -> tuple[dict[str, Any], str] | None:
    """Canonical EK-3B-1 bundled-consumable matcher.

    Single source of truth for "is this material bundled?" — used by both the
    runtime ``check_bundling_violations`` (via ``rules/bundling_rules.py``) and
    the build-time ``MaterialClaimLine.is_bundled`` enricher (Phase 2.1 of the
    unified-claim-engine roadmap). Returns ``(entry, match_kind)`` so callers
    can distinguish exact vs fuzzy matches (the runtime check emits
    ``severity="warning"`` for fuzzy), or ``None`` if not bundled.

    Match priority:
    1. ``code_resolved`` — if ``material_code`` resolves to a catalog name via
       ``resolve_material_name_by_code``, that canonical name is matched first.
    2. ``name_substring`` — token-bound bidirectional substring match against
       the material's billed name.
    3. ``name_fuzzy`` — fuzzy match (threshold 0.80) as a last resort.

    Args:
        material_name: The material's billed name.
        material_code: Optional SUT material code; when present the catalog
            canonical name is resolved and tried first.

    Returns:
        ``(bundled_entry, match_kind)`` or ``None``.
    """
    bundled = get_bundled_consumables()
    if not bundled:
        return None

    # Build the normalized index once.
    bundled_index: list[tuple[str, dict[str, Any]]] = []
    for entry in bundled:
        entry_name = turkish_lower((entry.get("item_name") or "").strip())
        if entry_name:
            bundled_index.append((entry_name, entry))

    # Tier 1 — code-resolved canonical name.
    if material_code:
        from .catalog_lookup import resolve_material_name_by_code

        resolved = resolve_material_name_by_code(material_code)
        if resolved:
            matched = _match_bundled_index(resolved, bundled_index)
            if matched is not None:
                return matched[0], "code_resolved"

    # Tiers 2 & 3 — billed name.
    return _match_bundled_index(material_name, bundled_index)


def _match_bundled_index(
    needle_name: str,
    bundled_index: list[tuple[str, dict[str, Any]]],
) -> tuple[dict[str, Any], str] | None:
    """Token-bound substring + fuzzy match against a prebuilt bundled index."""
    needle = turkish_lower(needle_name.strip())
    if not needle:
        return None
    for bundled_name, bundled_entry in bundled_index:
        if token_bound_substring_match(needle, bundled_name) or token_bound_substring_match(
            bundled_name, needle
        ):
            return bundled_entry, "name_substring"
    fuzzy = fuzzy_match_name(needle, bundled_index, threshold=0.80)
    if fuzzy:
        return fuzzy[1], "name_fuzzy"
    return None
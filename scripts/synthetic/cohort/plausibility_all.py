"""One entry point for both plausibility families of the showcase cohort (P4 slices E1 to E3).

`plausibility.py` checks the claims tables (and the patient's sex and age from `anadata_clean`): its
problems are rooted at a claim (`Problem.claim_id`). `plausibility_clean.py` checks the clean clinical
tables (lab results, prescriptions, vitals) against the bills: its problems are rooted at a patient
(`Problem.patient_id`). The two registries are disjoint (checked at import), so a check id names one
family, and `check_all_plausibility` routes the ids of `only` to the family they belong to.

The two modules stay separate on purpose: each has its own registry-coverage and mutation tests, and the
clean-table checks must not depend on the claims checks (or on the generator).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import polars as pl

from . import plausibility as _claims
from . import plausibility_clean as _clean

CLAIMS_CHECKS: dict[str, str] = dict(_claims.CHECKS)
CLEAN_CHECKS: dict[str, str] = dict(_clean.CHECKS)
_SHARED = sorted(CLAIMS_CHECKS.keys() & CLEAN_CHECKS.keys())
if _SHARED:  # pragma: no cover - a registry clash is a programming error, found at import
    raise RuntimeError(f"check id(s) {_SHARED} are registered by both plausibility modules")
ALL_CHECKS: dict[str, str] = {**CLAIMS_CHECKS, **CLEAN_CHECKS}


def check_all_plausibility(
    tables: Mapping[str, pl.DataFrame],
    clean_tables: Mapping[str, pl.DataFrame],
    *,
    registry: Mapping[str, Any] | None = None,
    only: Iterable[str] | str | None = None,
    context: _claims.PlausibilityContext | None = None,
    clean_context: _clean.CleanPlausibilityContext | None = None,
) -> list[_claims.Problem | _clean.Problem]:
    """Every plausibility problem of the claims `tables` and of the `clean_tables` (both families).

    `only` restricts the run to some check ids of either family; an unknown id raises `KeyError`, and a
    family none of whose ids is wanted is not run at all. `registry` is the parsed
    `cohort_registry.json`: without it the `labels.*` ids of the claims family are skipped. The claims
    problems come first, then the clean-table problems, each family in the order of its registry.
    """
    if only is None:
        claims_only = clean_only = None
    else:
        wanted = {only} if isinstance(only, str) else set(only)
        unknown = sorted(wanted - ALL_CHECKS.keys())
        if unknown:
            raise KeyError(f"unregistered check id(s) {unknown}")
        claims_only = sorted(wanted & CLAIMS_CHECKS.keys())
        clean_only = sorted(wanted & CLEAN_CHECKS.keys())
    found: list[_claims.Problem | _clean.Problem] = []
    if claims_only is None or claims_only:
        found.extend(
            _claims.check_plausibility(
                tables, clean_tables, context=context, only=claims_only, registry=registry
            )
        )
    if clean_only is None or clean_only:
        found.extend(
            _clean.check_clean_plausibility(
                tables, clean_tables, context=clean_context, only=clean_only
            )
        )
    return found

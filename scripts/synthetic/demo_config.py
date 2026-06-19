"""Load synthetic demo vignette and manifest JSON (P1/P2 credibility cohort)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from vignettes import BillingVignette, VignetteRegistry, get_vignette_registry

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = PROJECT_ROOT / "data" / "synthetic" / "demo_manifest.json"


@lru_cache(maxsize=1)
def load_demo_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {}
    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def vignette_registry() -> VignetteRegistry:
    return get_vignette_registry()


def vignette_for_patient_id(patient_id: str) -> BillingVignette | None:
    return get_vignette_registry().get_for_patient_id(patient_id)


def vignette_for_patient_index(patient_index: str) -> BillingVignette | None:
    return get_vignette_registry().get(patient_index)


def vignette_for_scenario_tag(scenario_tag: str) -> BillingVignette | None:
    return get_vignette_registry().get_by_scenario_tag(scenario_tag)


def load_demo_vignettes() -> dict[str, dict[str, Any]]:
    """Backward-compatible dict view for legacy callers."""
    return {
        index: vignette.as_dict()
        for index, vignette in get_vignette_registry().by_index.items()
    }


def tier_a_patient_indices() -> list[str]:
    manifest = load_demo_manifest()
    return list(manifest.get("tier_a_patient_indices") or [])


def tier_b_patient_indices() -> list[str]:
    manifest = load_demo_manifest()
    return list(manifest.get("tier_b_patient_indices") or [])


def tier_a_patient_ids() -> set[str]:
    return {f"SENTETIK-HASTA-{index}" for index in tier_a_patient_indices()}


def tier_b_patient_ids() -> set[str]:
    return {f"SENTETIK-HASTA-{index}" for index in tier_b_patient_indices()}

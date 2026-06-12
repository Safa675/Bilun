"""§3.3 specialty annex prose scope — L4.4 fact-check boundary."""

from __future__ import annotations

import json
from typing import Any

from src.bilun.domain.constants import PROSE_MANIFESTS_DIR, _PROSE_RULES_DIR

PROSE_RULE_ID = "specialty_materials_prose"
PROSE_SECTION_PREFIXES = ("3.3",)
L44_PLAN_PATH = "plans/billing/specialty-materials-prose-l4.4-plan.md"
MEDULA_OVERLAP_CLASSIFICATION = "additive"
_PROSE_JSON = _PROSE_RULES_DIR / "specialty_materials_prose.json"
_MANIFEST = PROSE_MANIFESTS_DIR / "L4.4_specialty_prose_encoded_manifest.json"


def _load_prose_payload() -> dict[str, Any] | None:
    if not _PROSE_JSON.is_file():
        return None
    try:
        return json.loads(_PROSE_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def specialty_prose_rule_count() -> int:
    payload = _load_prose_payload()
    if not payload:
        return 0
    return len(payload.get("rules") or [])


def specialty_prose_engine_status() -> str:
    return "implemented" if specialty_prose_rule_count() > 0 else "out_of_scope"


def specialty_prose_coverage_tier() -> str:
    return "partial" if specialty_prose_engine_status() == "implemented" else "none"


def encoded_corpus_row_count() -> int:
    if not _MANIFEST.is_file():
        return 0
    try:
        manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    clause_ids: set[str] = set()
    for key, value in manifest.items():
        if not key.endswith("_clause_ids") or not isinstance(value, list):
            continue
        clause_ids.update(str(item) for item in value)
    return len(clause_ids)


def specialty_materials_coverage_scope() -> dict[str, Any]:
    """Machine-readable L4.4 scope for APIs and billing reports."""
    payload = _load_prose_payload() or {}
    rule_count = specialty_prose_rule_count()
    status = specialty_prose_engine_status()

    return {
        "prose_rule_id": PROSE_RULE_ID,
        "prose_section_prefixes": list(PROSE_SECTION_PREFIXES),
        "prose_engine_status": status,
        "prose_coverage_tier": specialty_prose_coverage_tier(),
        "prose_rules_implemented": rule_count,
        "prose_effective_date": str(payload.get("effective_date") or ""),
        "encoded_corpus_rows": encoded_corpus_row_count(),
        "implemented_annexes": ["EK-3/A", "EK-3/F", "EK-3/H", "EK-3/O"],
        "l44_plan_path": L44_PLAN_PATH,
        "medula_overlap_classification": MEDULA_OVERLAP_CLASSIFICATION,
        "medula_savings_note": (
            "Pre-submission §3.3 specialty annex compliance flags; additive vs MEDULA "
            "material blocking. Not guaranteed SGK recovery."
        ),
        "sibling_engine": "material_bundling_prose",
        "sibling_sections": ["3.1", "3.2"],
    }

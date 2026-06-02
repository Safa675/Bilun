"""Material bundling / payment scope — L1.4 fact-check boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.bilun.domain.constants import _PROSE_RULES_DIR

EK3B1_ROW_COUNT = 54
EK3B2_ROW_COUNT = 13
PROSE_RULE_ID = "material_bundling_prose"
PROSE_SECTION_PREFIXES = ("3.1", "3.2")
P2_PLAN_PATH = "plans/billing/material-bundling-prose-p2-plan.md"
MEDULA_BOUNDARY_DOC = "docs/medula/material_bundling_medula_boundary.md"
MEDULA_OVERLAP_CLASSIFICATION = "additive"
_PROSE_JSON = _PROSE_RULES_DIR / "material_bundling_prose.json"
_MANIFEST = Path("evidence/clauses/L1.4_material_bundling_encoded_manifest.json")


def _load_prose_payload() -> dict[str, Any] | None:
    if not _PROSE_JSON.is_file():
        return None
    try:
        return json.loads(_PROSE_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def prose_rule_count() -> int:
    payload = _load_prose_payload()
    if not payload:
        return 0
    return len(payload.get("rules") or [])


def prose_engine_status() -> str:
    """Integration status: implemented when JSON rules ship; use prose_coverage_tier for legal breadth."""
    return "implemented" if prose_rule_count() > 0 else "out_of_scope"


def prose_coverage_tier() -> str:
    """Legal breadth vs §3.1–3.2 corpus (partial until decision tables cover the long tail)."""
    return "partial" if prose_engine_status() == "implemented" else "none"


def gate_b_deferred_clause_count() -> int:
    if not _MANIFEST.is_file():
        return 0
    try:
        manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    deferred = manifest.get("gate_b_deferred_clause_ids")
    return len(deferred) if isinstance(deferred, list) else 0


def material_bundling_coverage_scope() -> dict[str, Any]:
    """Machine-readable scope boundary for APIs and billing reports."""
    status = prose_engine_status()
    prose_rule_count_val = prose_rule_count()
    payload = _load_prose_payload() or {}
    effective_date = str(payload.get("effective_date") or "")

    return {
        "prose_rule_id": PROSE_RULE_ID,
        "prose_section_prefixes": list(PROSE_SECTION_PREFIXES),
        "prose_engine_status": status,
        "prose_coverage_tier": prose_coverage_tier(),
        "prose_rules_implemented": prose_rule_count_val,
        "prose_effective_date": effective_date,
        "implemented_annexes": ["EK-3B-1", "EK-3B-2"],
        "ek3b1_row_count": EK3B1_ROW_COUNT,
        "ek3b2_row_count": EK3B2_ROW_COUNT,
        "p2_plan_path": P2_PLAN_PATH,
        "medula_overlap_classification": MEDULA_OVERLAP_CLASSIFICATION,
        "medula_boundary_doc": MEDULA_BOUNDARY_DOC,
        "medula_savings_note": (
            "Pre-submission compliance flags; not guaranteed SGK recovery "
            "(MEDULA may block ICU/procedure/ÜTS at Hizmet Kayıt)."
        ),
        "gate_b_deferred_clauses": gate_b_deferred_clause_count(),
    }

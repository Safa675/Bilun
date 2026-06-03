#!/usr/bin/env python3
"""Merge L4.4 specialty materials prose rules into specialty_materials_prose.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.specialty_materials_331_wound_batch_rules import (  # noqa: E402
    WOUND_331_BATCH_RULES,
    WOUND_331_PILOT_CLAUSE_IDS,
)
from scripts.sut.prose.specialty_materials_vision_optik_batch_rules import (  # noqa: E402
    VISION_OPTIK_BATCH_CLAUSE_IDS,
    VISION_OPTIK_BATCH_RULES,
)
from scripts.sut.prose.specialty_materials_334_orthobiologic_batch_rules import (  # noqa: E402
    SPECIALTY_334_BATCH_CLAUSE_IDS,
    SPECIALTY_334_BATCH_RULES,
)
from scripts.sut.prose.specialty_materials_glucose_337_batch_rules import (  # noqa: E402
    GLUCOSE_337_BATCH_RULES,
    GLUCOSE_METER_BATCH_CLAUSE_IDS,
    SPECIALTY_337_BATCH_CLAUSE_IDS,
)
from scripts.sut.prose.specialty_materials_338_336_batch_rules import (  # noqa: E402
    RULE_SOURCE_PATCHES,
    SPECIALTY_336_BATCH_CLAUSE_IDS,
    SPECIALTY_338_336_BATCH_RULES,
    SPECIALTY_338_BATCH_CLAUSE_IDS,
)
from scripts.sut.prose.specialty_materials_other_3_3_tail_batch_rules import (  # noqa: E402
    OTHER_3_3_TAIL_BATCH_RULES,
    OTHER_3_3_TAIL_CLAUSE_IDS,
)

_PROSE_PATH = _PROJECT_ROOT / "data/gazette/prose_rules/specialty_materials_prose.json"
_MANIFEST_PATH = _PROJECT_ROOT / "evidence/clauses/L4.4_specialty_prose_encoded_manifest.json"


def _bootstrap_payload() -> dict:
    return {
        "rule_set_id": "specialty_materials_prose",
        "title": "SUT §3.3 specialty annex material prose (partial)",
        "effective_date": "2026-06-02",
        "coverage_note": "L4.4 partial encode.",
        "sut_anchors": [],
        "rules": [],
    }


def _apply_rule_source_patches(rules: list[dict]) -> int:
    patched = 0
    by_id = {rule["rule_id"]: rule for rule in rules}
    for rule_id, clause_ids in RULE_SOURCE_PATCHES.items():
        rule = by_id.get(rule_id)
        if not rule:
            continue
        sources = list(rule.get("gate_b_sources") or [])
        for clause_id in clause_ids:
            if clause_id not in sources:
                sources.append(clause_id)
                patched += 1
        rule["gate_b_sources"] = sources
    return patched


def main() -> None:
    if _PROSE_PATH.is_file():
        payload = json.loads(_PROSE_PATH.read_text(encoding="utf-8"))
    else:
        payload = _bootstrap_payload()

    existing_ids = {rule["rule_id"] for rule in payload.get("rules", [])}
    added = 0
    for rule in [
        *WOUND_331_BATCH_RULES,
        *VISION_OPTIK_BATCH_RULES,
        *SPECIALTY_334_BATCH_RULES,
        *GLUCOSE_337_BATCH_RULES,
        *SPECIALTY_338_336_BATCH_RULES,
        *OTHER_3_3_TAIL_BATCH_RULES,
    ]:
        if rule["rule_id"] in existing_ids:
            continue
        payload.setdefault("rules", []).append(rule)
        existing_ids.add(rule["rule_id"])
        added += 1

    patched = _apply_rule_source_patches(payload.get("rules", []))

    sources: set[str] = set()
    for rule in payload["rules"]:
        sources.update(rule.get("gate_b_sources") or [])

    payload["coverage_note"] = (
        f"L4.4 partial encode: {len(payload['rules'])} §3.3 prose rules "
        f"({added} added, {patched} source patches). §3.3.1–3.3.8 partial batches."
    )
    anchors = set(payload.get("sut_anchors") or [])
    anchors.update(
        {
            "3.3.1",
            "3.3.2",
            "3.3.3",
            "3.3.3.A",
            "3.3.3.B",
            "3.3.3.C",
            "3.3.4",
            "3.3.4.A",
            "3.3.4.B",
            "3.3.4.C",
            "3.3.6",
            "3.3.6.A-1",
            "3.3.7.B",
            "3.3.8.A",
            "3.3.8.B",
            "3.3.11",
            "3.3.12",
            "3.3.14",
            "3.3.16",
            "3.3.34",
            "3.3.35",
            "3.3.36.B",
            "3.3.36.C",
            "3.3.36.D",
            "3.3.37",
        }
    )
    payload["sut_anchors"] = sorted(anchors)

    _PROSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PROSE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "rules_in_json": len(payload["rules"]),
        "rules_added": added,
        "rules_patched": patched,
        "pilot_331_clause_ids": sorted(WOUND_331_PILOT_CLAUSE_IDS),
        "vision_optik_batch_clause_ids": sorted(VISION_OPTIK_BATCH_CLAUSE_IDS),
        "specialty_334_batch_clause_ids": sorted(SPECIALTY_334_BATCH_CLAUSE_IDS),
        "glucose_meter_batch_clause_ids": sorted(GLUCOSE_METER_BATCH_CLAUSE_IDS),
        "specialty_337_batch_clause_ids": sorted(SPECIALTY_337_BATCH_CLAUSE_IDS),
        "specialty_338_batch_clause_ids": sorted(SPECIALTY_338_BATCH_CLAUSE_IDS),
        "specialty_336_batch_clause_ids": sorted(SPECIALTY_336_BATCH_CLAUSE_IDS),
        "other_3_3_tail_clause_ids": sorted(OTHER_3_3_TAIL_CLAUSE_IDS),
        "gate_b_sources_encoded": sorted(sources),
    }
    _MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Merged {added} rules → {len(payload['rules'])} total; "
        f"{len(sources)} encoded clause sources"
    )
    print(f"Manifest: {_MANIFEST_PATH}")


if __name__ == "__main__":
    main()

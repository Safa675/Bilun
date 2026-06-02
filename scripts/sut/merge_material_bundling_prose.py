#!/usr/bin/env python3
"""Merge Gate B batch rules into material_bundling_prose.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.material_bundling_batch_rules import GATE_B_BATCH_RULES  # noqa: E402
from scripts.sut.prose.material_bundling_deferred_batch_rules import (  # noqa: E402
    GATE_B_DEFERRED_BATCH_RULES,
    GATE_B_RULE_PATCHES,
    GATE_B_STILL_DEFERRED_CLAUSE_IDS,
)

_PROSE_PATH = _PROJECT_ROOT / "data/gazette/prose_rules/material_bundling_prose.json"
_MANIFEST_PATH = (
    _PROJECT_ROOT / "evidence/clauses/L1.4_material_bundling_encoded_manifest.json"
)


def _apply_rule_patches(rules: list[dict]) -> int:
    patched = 0
    by_id = {rule["rule_id"]: rule for rule in rules}
    for rule_id, patch in GATE_B_RULE_PATCHES.items():
        rule = by_id.get(rule_id)
        if not rule:
            continue
        for clause_id in patch.get("gate_b_sources_append") or []:
            sources = list(rule.get("gate_b_sources") or [])
            if clause_id not in sources:
                sources.append(clause_id)
                rule["gate_b_sources"] = sources
                patched += 1
        for keyword in patch.get("material_name_any_append") or []:
            condition = rule.setdefault("condition", {})
            names = list(condition.get("material_name_any") or [])
            if keyword not in names:
                names.append(keyword)
                condition["material_name_any"] = names
                patched += 1
    return patched


def main() -> None:
    payload = json.loads(_PROSE_PATH.read_text(encoding="utf-8"))
    existing_ids = {rule["rule_id"] for rule in payload.get("rules", [])}
    added = 0
    for rule in [*GATE_B_BATCH_RULES, *GATE_B_DEFERRED_BATCH_RULES]:
        if rule["rule_id"] in existing_ids:
            continue
        payload.setdefault("rules", []).append(rule)
        existing_ids.add(rule["rule_id"])
        added += 1

    patch_count = _apply_rule_patches(payload.get("rules", []))

    sources: set[str] = set()
    for rule in payload["rules"]:
        sources.update(rule.get("gate_b_sources") or [])

    payload["coverage_note"] = (
        "Gate B partial encode: EK-3B-1/2 annex lists plus "
        f"{len(payload['rules'])} §3.1–3.2 prose rules "
        f"({added} added this merge). Full SUT corpus not encoded."
    )
    anchors = set(payload.get("sut_anchors") or [])
    for rule in GATE_B_BATCH_RULES:
        anchors.add(rule["sut_section"])
    payload["sut_anchors"] = sorted(anchors)

    _PROSE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "rules_in_json": len(payload["rules"]),
        "rules_added": added,
        "rules_patched": patch_count,
        "gate_b_sources_encoded": sorted(sources),
        "gate_b_deferred_clause_ids": sorted(GATE_B_STILL_DEFERRED_CLAUSE_IDS),
    }
    _MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Merged {added} rules, {patch_count} patch ops → {len(payload['rules'])} total; "
        f"{len(GATE_B_STILL_DEFERRED_CLAUSE_IDS)} still deferred"
    )
    print(f"Manifest: {_MANIFEST_PATH}")


if __name__ == "__main__":
    main()

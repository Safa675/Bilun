#!/usr/bin/env python3
"""Merge WAVE2A_BATCH_RULES into specialty_materials_prose.json + update manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.specialty_materials_wave2a_batch_rules import (
    WAVE2A_BATCH_CLAUSE_IDS,
    WAVE2A_BATCH_RULES,
)

RULES_JSON = _PROJECT_ROOT / "data/gazette/prose_rules/specialty_materials_prose.json"
MANIFEST = _PROJECT_ROOT / "data/gazette/prose_manifests/L4.4_specialty_prose_encoded_manifest.json"


def main() -> None:
    # sanity: every batch clause id appears in exactly one rule's gate_b_sources
    src_to_rule = {}
    for r in WAVE2A_BATCH_RULES:
        for c in r["gate_b_sources"]:
            if c in src_to_rule:
                raise SystemExit(f"clause {c} duplicated in {src_to_rule[c]} and {r['rule_id']}")
            src_to_rule[c] = r["rule_id"]
    missing = WAVE2A_BATCH_CLAUSE_IDS - set(src_to_rule)
    if missing:
        raise SystemExit(f"clause ids not in any rule: {sorted(missing)}")
    extra = set(src_to_rule) - WAVE2A_BATCH_CLAUSE_IDS
    if extra:
        raise SystemExit(f"rule references unknown clause ids: {sorted(extra)}")

    # 1. merge rules json (dedup by rule_id)
    payload = json.loads(RULES_JSON.read_text(encoding="utf-8"))
    existing = {r["rule_id"]: r for r in payload.get("rules", [])}
    added = 0
    for rule in WAVE2A_BATCH_RULES:
        if rule["rule_id"] not in existing:
            payload["rules"].append(rule)
            existing[rule["rule_id"]] = rule
            added += 1
    payload["rules_added"] = payload.get("rules_added", 0) + added
    payload["rules_in_json"] = len(payload["rules"])
    RULES_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"rules appended: {added}; total rules now: {len(payload['rules'])}")

    # 2. update manifest gate_b_sources_encoded
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    gate = set(man.get("gate_b_sources_encoded", []))
    before = len(gate)
    gate |= WAVE2A_BATCH_CLAUSE_IDS
    man["gate_b_sources_encoded"] = sorted(gate)
    man.setdefault("wave2a_batch_clause_ids", []).extend(
        sorted(WAVE2A_BATCH_CLAUSE_IDS - set(man.get("wave2a_batch_clause_ids", [])))
    )
    man["wave2a_batch_clause_ids"] = sorted(set(man["wave2a_batch_clause_ids"]))
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"manifest gate_b_sources_encoded: {before} -> {len(gate)} (+{len(gate)-before})")


if __name__ == "__main__":
    main()

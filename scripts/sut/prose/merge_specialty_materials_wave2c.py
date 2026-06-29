"""Merge §3.3 specialty-materials wave-2c batch rules into
specialty_materials_prose.json + update the L4.4 manifest.

Idempotent: dedups by rule_id (new rules overwrite any pre-existing same-id rule).
Adds the 29 wave-2c clause_ids to the manifest ``gate_b_sources_encoded`` list
(union, deduped) so the coverage builder reflects them as encoded.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.sut.prose.specialty_materials_wave2c_batch_rules import (
    WAVE2C_BATCH_CLAUSE_IDS,
    WAVE2C_BATCH_RULES,
    _all_gate_b_sources,
)

REPO = Path(__file__).resolve().parents[3]
RULES_PATH = REPO / "data/gazette/prose_rules/specialty_materials_prose.json"
MANIFEST_PATH = (
    REPO / "data/gazette/prose_manifests/L4.4_specialty_prose_encoded_manifest.json"
)


def merge() -> tuple[int, int]:
    # --- append rules (dedup by rule_id) ---
    payload = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    existing = payload.get("rules") or []
    existing_by_id = {r["rule_id"]: r for r in existing}

    for rule in WAVE2C_BATCH_RULES:
        existing_by_id[rule["rule_id"]] = rule

    payload["rules"] = list(existing_by_id.values())
    RULES_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # --- update manifest gate_b_sources_encoded (union, deduped, ordered) ---
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    encoded: list[str] = manifest.get("gate_b_sources_encoded") or []
    for cid in _all_gate_b_sources():
        if cid not in encoded:
            encoded.append(cid)
    manifest["gate_b_sources_encoded"] = encoded
    manifest["specialty_wave2c_tail_batch_clause_ids"] = sorted(WAVE2C_BATCH_CLAUSE_IDS)
    manifest["rules_in_json"] = len(payload["rules"])
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    return len(payload["rules"]), len(WAVE2C_BATCH_RULES)


if __name__ == "__main__":
    total_rules, added = merge()
    print(f"specialty_materials_prose.json now has {total_rules} rules")
    print(f"wave-2c batch added {added} rules")
    print(f"wrote {MANIFEST_PATH.name}")

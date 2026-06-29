"""Merge §4.2.14 wave-2 batch rules into drug_indication_prose.json + write manifest.

Idempotent: dedups by rule_id (new rules overwrite any pre-existing same-id rule).
Writes the wave-2 manifest with the union of all gate_b_sources from the batch.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.sut.prose.drug_indication_4_2_14_wave2_batch_rules import (
    WAVE2_BATCH_RULES,
    _all_gate_b_sources,
)

REPO = Path(__file__).resolve().parents[3]
RULES_PATH = REPO / "data/gazette/prose_rules/drug_indication_prose.json"
MANIFEST_PATH = (
    REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4_2_14_wave2_manifest.json"
)


def merge() -> tuple[int, int]:
    payload = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    existing = payload.get("rules") or []
    existing_by_id = {r["rule_id"]: r for r in existing}

    new_ids: list[str] = []
    for rule in WAVE2_BATCH_RULES:
        existing_by_id[rule["rule_id"]] = rule
        new_ids.append(rule["rule_id"])

    payload["rules"] = list(existing_by_id.values())
    RULES_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    encoded_ids = _all_gate_b_sources()
    manifest = {
        "manifest_id": "L4.2_drug_indication_4_2_14_wave2",
        "rule_set_id": "drug_indication_prose",
        "source_csv": "tasks/encode_waves/A1a_4_2_14_oncology.csv",
        "batch_module": (
            "scripts/sut/prose/drug_indication_4_2_14_wave2_batch_rules.py"
        ),
        "description": (
            "Wave-2 §4.2.14 oncology encodes — chemotherapy/targeted/immunotherapy "
            "report, prescriber, line-of-therapy and NO_PAY combination exclusions."
        ),
        "rule_count": len(WAVE2_BATCH_RULES),
        "rule_ids": new_ids,
        "encoded_clause_ids": encoded_ids,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return len(payload["rules"]), len(encoded_ids)


if __name__ == "__main__":
    total_rules, encoded = merge()
    print(f"drug_indication_prose.json now has {total_rules} rules")
    print(f"manifest encoded_clause_ids: {encoded}")
    print(f"wrote {MANIFEST_PATH.name}")

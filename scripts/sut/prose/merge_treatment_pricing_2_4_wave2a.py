#!/usr/bin/env python3
"""Merge §2.4.4 wave-2a treatment-pricing rules into runtime JSON.

Appends the WAVE2A_BATCH_RULES from treatment_pricing_2_4_wave2a_batch_rules.py
into data/gazette/prose_rules/treatment_pricing_2_4.json, deduplicating by
rule_id. Also writes the §2.4 wave-2 manifest so coverage.py can mark these
§2.4.4 clauses as has_rule_encoding.
"""

from __future__ import annotations
import json, sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.treatment_pricing_2_4_wave2a_batch_rules import WAVE2A_BATCH_RULES

_RULES_DIR = _PROJECT_ROOT / "data/gazette/prose_rules"
_GOLDEN_DIR = _RULES_DIR / "golden"
_MANIFEST_DIR = _PROJECT_ROOT / "data/gazette/prose_manifests"
_TARGET_JSON = _RULES_DIR / "treatment_pricing_2_4.json"
_MANIFEST_PATH = _MANIFEST_DIR / "L2.4_treatment_pricing_wave2_manifest.json"


def _strip_batch(rule: dict) -> dict:
    return {k: v for k, v in rule.items() if k != "encode_batch"}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    payload = json.loads(_TARGET_JSON.read_text(encoding="utf-8"))
    existing_rules = list(payload.get("rules") or [])
    existing_ids = {r.get("rule_id") for r in existing_rules}

    added, skipped = [], []
    for rule in WAVE2A_BATCH_RULES:
        if rule["rule_id"] in existing_ids:
            skipped.append(rule["rule_id"])
            continue
        added.append(_strip_batch(rule))

    payload["rules"] = existing_rules + added

    # Keep sut_anchors list tidy (append any new 2.4.4.* sections once).
    anchors = list(dict.fromkeys(payload.get("sut_anchors") or []))
    new_sections = sorted({r["sut_section"] for r in added if r["sut_section"] not in anchors})
    payload["sut_anchors"] = anchors + [s for s in new_sections if s not in anchors]

    _write_json(_TARGET_JSON, payload)

    # Manifest: all §2.4.4 clauses encoded by this rule set (existing + new),
    # so the section-specific override in coverage.py marks every one of them.
    sources_by_rule: dict[str, list[str]] = {}
    encoded: set[str] = set()
    for r in payload["rules"]:
        srcs = r.get("gate_b_sources") or []
        if srcs and str(r.get("sut_section", "")).startswith("2.4.4"):
            sources_by_rule[r["rule_id"]] = srcs
            encoded.update(srcs)

    manifest = {
        "manifest_version": "wave2-v1",
        "rule_set_id": "treatment_pricing_2_4_wave2",
        "scope_note": (
            "§2.4.4 treatment package pricing & coverage rules — batch 1 (T1) + "
            "wave-2a (W2A). Covers ESWL, HBO, radyocerrahi, hemodiyaliz/periton "
            "diyalizi, anjiyo/PKG, fizik tedavi rapor & seans kuralları."
        ),
        "rules_in_json": len(payload["rules"]),
        "rules_added_wave2a": len(added),
        "rules_skipped_dup": skipped,
        "encoded_clause_ids": sorted(encoded),
        "gate_b_sources_by_rule": sources_by_rule,
    }
    _write_json(_MANIFEST_PATH, manifest)

    print(f"Existing rules: {len(existing_rules)}")
    print(f"Added (wave-2a): {len(added)}")
    print(f"Skipped (dup rule_id): {skipped}")
    print(f"Total rules in JSON: {len(payload['rules'])}")
    print(f"§2.4.4 encoded clause IDs: {len(encoded)}")
    print(f"Manifest: {_MANIFEST_PATH}")


if __name__ == "__main__":
    main()

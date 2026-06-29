#!/usr/bin/env python3
"""Merge §2.4.4 wave-2b treatment-pricing rules into runtime JSON.

Appends the WAVE2B_BATCH_RULES from
treatment_pricing_2_4_wave2b_batch_rules.py into
data/gazette/prose_rules/treatment_pricing_2_4.json, deduplicating by rule_id.

Then rewrites the §2.4 wave-2 manifest
(L2.4_treatment_pricing_wave2_manifest.json) so its encoded_clause_ids is the
full union of gate_b_sources across every §2.4.4 rule in the JSON — this is
what coverage.py's _section_2_4_4_manifest_encoding reads to mark each clause
has_rule_encoding. Existing part-1 / wave-2a clause_ids are preserved.
"""

from __future__ import annotations
import json, sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.treatment_pricing_2_4_wave2b_batch_rules import WAVE2B_BATCH_RULES

_RULES_DIR = _PROJECT_ROOT / "data/gazette/prose_rules"
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
    for rule in WAVE2B_BATCH_RULES:
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

    # Manifest: union of every §2.4.4 rule's gate_b_sources (existing + new),
    # so the section-specific override in coverage.py marks all of them.
    sources_by_rule: dict[str, list[str]] = {}
    encoded: set[str] = set()
    for r in payload["rules"]:
        srcs = r.get("gate_b_sources") or []
        if srcs and str(r.get("sut_section", "")).startswith("2.4.4"):
            sources_by_rule[r["rule_id"]] = srcs
            encoded.update(srcs)

    prior_manifest = {}
    if _MANIFEST_PATH.exists():
        prior_manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    prior_added_wave2a = prior_manifest.get("rules_added_wave2a", 0)
    prior_skipped = prior_manifest.get("rules_skipped_dup", [])

    manifest = {
        "manifest_version": "wave2-v1",
        "rule_set_id": "treatment_pricing_2_4_wave2",
        "scope_note": (
            "§2.4.4 treatment package pricing & coverage rules — batch 1 (T1) + "
            "wave-2a (W2A) + wave-2b (W2B). Covers ESWL, HBO, radyocerrahi, "
            "hemodiyaliz/periton diyalizi, anjiyo/PKG, fizik tedavi rapor & seans "
            "kuralları, özel sunucu FTR, ESWT, robotik rehab, spor hekimliği/tıbbi "
            "ekoloji, sitogenetik/moleküler genetik, yoğun bakım, göz ayaktan, "
            "kaplıca ve palyatif bakım."
        ),
        "rules_in_json": len(payload["rules"]),
        "rules_added_wave2a": prior_added_wave2a,
        "rules_added_wave2b": len(added),
        "rules_skipped_dup": sorted(set(prior_skipped) | set(skipped)),
        "encoded_clause_ids": sorted(encoded),
        "gate_b_sources_by_rule": sources_by_rule,
    }
    _write_json(_MANIFEST_PATH, manifest)

    print(f"Existing rules: {len(existing_rules)}")
    print(f"Added (wave-2b): {len(added)}")
    print(f"Skipped (dup rule_id): {skipped}")
    print(f"Total rules in JSON: {len(payload['rules'])}")
    print(f"§2.4.4 encoded clause IDs (union): {len(encoded)}")
    print(f"Manifest: {_MANIFEST_PATH}")


if __name__ == "__main__":
    main()

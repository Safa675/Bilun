#!/usr/bin/env python3
"""Merge §4.2 drug combination/sequential/endikasyon rules into runtime JSON.

Creates data/gazette/prose_rules/drug_combination_4_2.json + golden + manifest.
Mirrors the merge pattern used by merge_treatment_pricing_2_4.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.drug_combination_4_2_batch_rules import BATCH_RULES

_RULES_DIR = _PROJECT_ROOT / "data/gazette/prose_rules"
_GOLDEN_DIR = _RULES_DIR / "golden"
_MANIFEST_DIR = _PROJECT_ROOT / "data/gazette/prose_manifests"
_EFFECTIVE = "2026-05-23"


def _strip_batch(rule: dict) -> dict:
    return {k: v for k, v in rule.items() if k != "encode_batch"}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_golden(rule_set_id: str, rules: list[dict]) -> None:
    cases = []
    for r in rules:
        for clause_id in (r.get("gate_b_sources") or []):
            cases.append({
                "clause_id": clause_id,
                "expected_rule_id": r["rule_id"],
                "encode_batch": r.get("encode_batch"),
            })
    _write_json(_GOLDEN_DIR / f"{rule_set_id}.json", {
        "description": f"Gate B golden — {rule_set_id} clause → rule_id provenance",
        "cases": cases,
    })


def _write_manifest(rule_set_id: str, rules: list[dict]) -> None:
    sources_by_rule: dict[str, list[str]] = {}
    encoded: set[str] = set()
    for r in rules:
        srcs = r.get("gate_b_sources") or []
        if srcs:
            sources_by_rule[r["rule_id"]] = srcs
            encoded.update(srcs)
    _write_json(_MANIFEST_DIR / f"{rule_set_id}_manifest.json", {
        "manifest_version": "d42-v1",
        "rule_set_id": rule_set_id,
        "rules_in_json": len(rules),
        "encoded_clause_ids": sorted(encoded),
        "gate_b_sources_by_rule": sources_by_rule,
    })


def main() -> None:
    payload = {
        "rule_set_id": "drug_combination_4_2",
        "title": "§4.2 İlaç kombinasyon/ardışık/endikasyon-dışı NO_PAY + Tier C biomarker kuralları",
        "effective_date": _EFFECTIVE,
        "sut_anchors": ["4.2.1.C", "4.2.3", "4.2.5", "4.2.7", "4.2.9.A", "4.2.9.Ç",
                        "4.2.9.E", "4.2.10.B-3", "4.2.12.B-1", "4.2.12.B-2", "4.2.14.C",
                        "4.2.15.D-1", "4.2.16", "4.2.17.A", "4.2.17.B", "4.2.23",
                        "4.2.24.A", "4.2.24.B", "4.2.25", "4.2.28.C", "4.2.30.A",
                        "4.2.33", "4.2.34", "4.2.35.A", "4.2.38", "4.2.49.C", "4.2.71"],
        "rules": [_strip_batch(r) for r in BATCH_RULES],
    }
    _write_json(_RULES_DIR / "drug_combination_4_2.json", payload)
    _write_golden("drug_combination_4_2", BATCH_RULES)
    _write_manifest("drug_combination_4_2", BATCH_RULES)

    clauses = set()
    for r in BATCH_RULES:
        clauses.update(r.get("gate_b_sources") or [])
    print(f"§4.2 drug combination: {len(BATCH_RULES)} rules, {len(clauses)} clauses encoded")
    tier_c = sum(1 for r in BATCH_RULES if r.get("action", {}).get("tier") == "C")
    print(f"  Tier C advisory rules: {tier_c}")


if __name__ == "__main__":
    main()

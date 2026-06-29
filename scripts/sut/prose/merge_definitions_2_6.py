#!/usr/bin/env python3
"""Merge §2.6 definition/scope rules (wave-1 batch) into runtime JSON.

Creates ``data/gazette/prose_rules/definitions_2_6.json`` (a fresh
gap_closing-style rule file — the 47 still-unencoded §2.6 deontic clauses),
plus the matching golden + manifest.

9 of the 56 §2.6 target clauses were already encoded as NO_PAY exclusions
inside ``gap_closing_treatment_2.json``; this wave closes the remaining 47
(COVERAGE / MANDATORY / REGULATORY_ACTION definitional-scope rules).

Pattern mirrors ``merge_gap_closing.py``: free-form condition/action dicts,
dedup by rule_id, manifest carries ``encoded_clause_ids`` +
``gate_b_sources_by_rule``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.definitions_2_6_wave1_batch_rules import WAVE1_BATCH_RULES
from scripts.sut.prose.definitions_2_6_wave1_tail_batch_rules import WAVE1_TAIL_BATCH_RULES

_RULES_DIR = _PROJECT_ROOT / "data/gazette/prose_rules"
_GOLDEN_DIR = _RULES_DIR / "golden"
_MANIFEST_DIR = _PROJECT_ROOT / "data/gazette/prose_manifests"
_EFFECTIVE = "2026-05-23"
_RULE_SET_ID = "definitions_2_6"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_golden(rule_set_id: str, rules: list[dict]) -> None:
    cases = [
        {"clause_id": cid, "expected_rule_id": r["rule_id"]}
        for r in rules
        for cid in (r.get("gate_b_sources") or [])
    ]
    _write_json(
        _GOLDEN_DIR / f"{rule_set_id}.json",
        {"description": f"Gate B golden — {rule_set_id}", "cases": cases},
    )


def _write_manifest(rule_set_id: str, rules: list[dict]) -> None:
    sources_by_rule: dict[str, list[str]] = {}
    encoded: set[str] = set()
    for r in rules:
        srcs = r.get("gate_b_sources") or []
        if srcs:
            sources_by_rule[r["rule_id"]] = srcs
            encoded.update(srcs)
    _write_json(
        _MANIFEST_DIR / f"L{rule_set_id}_manifest.json".replace("definitions_2_6", "2.6_definitions"),
        {
            "manifest_version": "gap-v1",
            "rule_set_id": rule_set_id,
            "rules_in_json": len(rules),
            "encoded_clause_ids": sorted(encoded),
            "gate_b_sources_by_rule": sources_by_rule,
        },
    )


def main() -> None:
    # Wave-1 tail batch (9 remaining NO_PAY/MUST_NOT_BILL §2.6 clauses) is
    # appended after the original wave-1 batch; dedup by rule_id so re-runs
    # stay idempotent.
    seen: set[str] = set()
    rules: list[dict] = []
    for r in [*WAVE1_BATCH_RULES, *WAVE1_TAIL_BATCH_RULES]:
        rid = r["rule_id"]
        if rid in seen:
            continue
        seen.add(rid)
        rules.append(r)

    payload = {
        "rule_set_id": _RULE_SET_ID,
        "title": "§2.6 tanım/kapsam — yol, gündelik, refakatçi, kontrol, nakil, kaplıca, cenaze kuralları",
        "effective_date": _EFFECTIVE,
        "sut_anchors": [
            "2.6.1", "2.6.1.A", "2.6.1.B", "2.6.1.B-1", "2.6.1.B-2",
            "2.6.1.B-3", "2.6.1.B-4", "2.6.2", "2.6.3", "2.6.4",
            "2.6.5", "2.6.6", "2.6.8", "2.6.9",
        ],
        "rules": rules,
    }
    _write_json(_RULES_DIR / "definitions_2_6.json", payload)
    _write_golden(_RULE_SET_ID, rules)
    _write_manifest(_RULE_SET_ID, rules)

    g: set[str] = set()
    for r in rules:
        g.update(r.get("gate_b_sources") or [])
    print(f"definitions_2_6: {len(rules)} rules, {len(g)} clauses")
    print(f"manifest: data/gazette/prose_manifests/L2.6_definitions_manifest.json")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Merge the gap-closing batches (§2 + §1/§3/§4/§5/§6) into runtime JSON.

Creates two runtime rule files + golden + manifests, closing the remaining
un-encoded billable clauses.
"""

from __future__ import annotations
import json, sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.gap_closing_batch_rules import BATCH_RULES as TREATMENT_GAP_RULES
from scripts.sut.prose.gap_closing_misc_batch_rules import BATCH_RULES as MISC_RULES

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
    cases = [{"clause_id": cid, "expected_rule_id": r["rule_id"], "encode_batch": r.get("encode_batch")}
             for r in rules for cid in (r.get("gate_b_sources") or [])]
    _write_json(_GOLDEN_DIR / f"{rule_set_id}.json",
                {"description": f"Gate B golden — {rule_set_id}", "cases": cases})


def _write_manifest(rule_set_id: str, rules: list[dict]) -> None:
    sources_by_rule, encoded = {}, set()
    for r in rules:
        srcs = r.get("gate_b_sources") or []
        if srcs:
            sources_by_rule[r["rule_id"]] = srcs
            encoded.update(srcs)
    _write_json(_MANIFEST_DIR / f"{rule_set_id}_manifest.json", {
        "manifest_version": "gap-v1", "rule_set_id": rule_set_id,
        "rules_in_json": len(rules), "encoded_clause_ids": sorted(encoded),
        "gate_b_sources_by_rule": sources_by_rule,
    })


def main() -> None:
    # §2 gap-closing
    payload2 = {
        "rule_set_id": "gap_closing_treatment_2",
        "title": "§2 tedavi/yurt dışı/yol-gündelik — kalan faturalandırma/dışlama kuralları",
        "effective_date": _EFFECTIVE,
        "sut_anchors": ["2.2.1.B-3", "2.2.2.B", "2.2.2.B-1", "2.2.2.B-2", "2.2.2.B-3",
                        "2.3", "2.3.1", "2.4.2.A", "2.4.2.B-2", "2.4.4.F-3", "2.4.4.Ğ",
                        "2.4.4.H", "2.4.4.J", "2.4.4.İ-2", "2.5.1", "2.5.2", "2.5.3.A",
                        "2.5.3.A-2", "2.5.3.A-3", "2.5.3.B", "2.6.1.A", "2.6.1.B-3",
                        "2.6.2", "2.6.3", "2.6.4", "2.6.6", "2.6.8", "2.6.9"],
        "rules": [_strip_batch(r) for r in TREATMENT_GAP_RULES],
    }
    _write_json(_RULES_DIR / "gap_closing_treatment_2.json", payload2)
    _write_golden("gap_closing_treatment_2", TREATMENT_GAP_RULES)
    _write_manifest("gap_closing_treatment_2", TREATMENT_GAP_RULES)

    # §1/§3/§4/§5/§6 gap-closing
    payload_m = {
        "rule_set_id": "gap_closing_misc",
        "title": "§1/§3/§4/§5/§6 — kalan hüküm/malzeme/liste/MEDULA/KDV kuralları",
        "effective_date": _EFFECTIVE,
        "sut_anchors": ["1.5.1", "1.5.2", "1.6", "1.8.2", "1.8.3", "1.8.5", "1.9.1", "1.10",
                        "3.1.1", "3.1.3", "3.3.10", "3.3.11", "4.1", "4.1.3", "4.1.4",
                        "4.1.5", "4.1.7", "4.1.8", "4.1.9", "4.3", "4.4.2", "4.5.1",
                        "4.6", "5.2", "5.2.2", "5.3.1.C", "6.3.2"],
        "rules": [_strip_batch(r) for r in MISC_RULES],
    }
    _write_json(_RULES_DIR / "gap_closing_misc.json", payload_m)
    _write_golden("gap_closing_misc", MISC_RULES)
    _write_manifest("gap_closing_misc", MISC_RULES)

    g2 = set(); [g2.update(r.get("gate_b_sources") or []) for r in TREATMENT_GAP_RULES]
    gm = set(); [gm.update(r.get("gate_b_sources") or []) for r in MISC_RULES]
    print(f"§2 gap-closing:  {len(TREATMENT_GAP_RULES)} rules, {len(g2)} clauses")
    print(f"misc gap-closing: {len(MISC_RULES)} rules, {len(gm)} clauses")
    print(f"Total: {len(TREATMENT_GAP_RULES)+len(MISC_RULES)} rules, {len(g2|gm)} clauses")


if __name__ == "__main__":
    main()

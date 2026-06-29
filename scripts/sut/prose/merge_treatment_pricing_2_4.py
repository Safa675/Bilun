#!/usr/bin/env python3
"""Merge §2.4 treatment-pricing + dental rules into runtime JSON + golden + manifest.

Creates two new runtime rule files:
  - data/gazette/prose_rules/treatment_pricing_2_4.json   (§2.4.4, ~40 rules)
  - data/gazette/prose_rules/dental_2_4_1.json            (§2.4.1, ~10 rules)

Plus golden test fixtures and encode manifests with clause provenance.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.dental_2_4_1_batch_rules import BATCH1_RULES as DENTAL_RULES
from scripts.sut.prose.treatment_pricing_2_4_batch1_rules import BATCH1_RULES as TREATMENT_RULES

_RULES_DIR = _PROJECT_ROOT / "data/gazette/prose_rules"
_GOLDEN_DIR = _RULES_DIR / "golden"
_MANIFEST_DIR = _PROJECT_ROOT / "data/gazette/prose_manifests"

_EFFECTIVE = "2026-05-23"


def _strip_batch(rule: dict) -> dict:
    return {k: v for k, v in rule.items() if k != "encode_batch"}


def _build_rule_file(rule_set_id: str, title: str, anchors: list[str], rules: list[dict]) -> dict:
    return {
        "rule_set_id": rule_set_id,
        "title": title,
        "effective_date": _EFFECTIVE,
        "sut_anchors": anchors,
        "rules": [_strip_batch(r) for r in rules],
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_golden(rule_set_id: str, rules: list[dict]) -> None:
    """Golden fixture: clause_id → expected_rule_id mapping for regression."""
    cases = []
    for r in rules:
        srcs = r.get("gate_b_sources") or []
        for clause_id in srcs:
            cases.append({
                "clause_id": clause_id,
                "expected_rule_id": r["rule_id"],
                "encode_batch": r.get("encode_batch"),
            })
    payload = {
        "description": f"Gate B golden — {rule_set_id} clause → rule_id provenance",
        "cases": cases,
    }
    _write_json(_GOLDEN_DIR / f"{rule_set_id}.json", payload)


def _write_manifest(rule_set_id: str, rules: list[dict]) -> None:
    """Encode manifest: which clauses are covered, by which rule."""
    sources_by_rule: dict[str, list[str]] = {}
    encoded: set[str] = set()
    for r in rules:
        rid = r["rule_id"]
        srcs = r.get("gate_b_sources") or []
        if srcs:
            sources_by_rule[rid] = srcs
            encoded.update(srcs)
    payload = {
        "manifest_version": "t1-v1",
        "rule_set_id": rule_set_id,
        "rules_in_json": len(rules),
        "encoded_clause_ids": sorted(encoded),
        "gate_b_sources_encoded": sorted(encoded),
        "gate_b_sources_by_rule": sources_by_rule,
    }
    _write_json(_MANIFEST_DIR / f"{rule_set_id}_manifest.json", payload)


def main() -> None:
    # §2.4.4 treatment pricing
    treatment = _build_rule_file(
        rule_set_id="treatment_pricing_2_4",
        title="§2.4.4 Bazı tetkik ve tedavi yöntemleri — fiyatlandırma/dışlama kuralları",
        anchors=["2.4.4.A", "2.4.4.B", "2.4.4.C", "2.4.4.Ç", "2.4.4.D-1", "2.4.4.D-2",
                 "2.4.4.E", "2.4.4.F-2", "2.4.4.F-4", "2.4.4.F-5", "2.4.4.F-6",
                 "2.4.4.G-1", "2.4.4.G-2", "2.4.4.H", "2.4.4.I", "2.4.4.İ-1",
                 "2.4.4.J", "2.4.4.K", "2.4.4.N"],
        rules=TREATMENT_RULES,
    )
    _write_json(_RULES_DIR / "treatment_pricing_2_4.json", treatment)
    _write_golden("treatment_pricing_2_4", TREATMENT_RULES)
    _write_manifest("treatment_pricing_2_4", TREATMENT_RULES)

    # §2.4.1 dental
    dental = _build_rule_file(
        rule_set_id="dental_2_4_1",
        title="§2.4.1 Diş tedavileri — dışlama/fiyatlandırma kuralları",
        anchors=["2.4.1", "2.4.1.A", "2.4.1.B-1", "2.4.1.B-2", "2.4.1.B-3"],
        rules=DENTAL_RULES,
    )
    _write_json(_RULES_DIR / "dental_2_4_1.json", dental)
    _write_golden("dental_2_4_1", DENTAL_RULES)
    _write_manifest("dental_2_4_1", DENTAL_RULES)

    # Summary
    t_clauses = set()
    for r in TREATMENT_RULES:
        t_clauses.update(r.get("gate_b_sources") or [])
    d_clauses = set()
    for r in DENTAL_RULES:
        d_clauses.update(r.get("gate_b_sources") or [])
    print(f"§2.4.4 treatment pricing: {len(TREATMENT_RULES)} rules, {len(t_clauses)} clauses encoded")
    print(f"§2.4.1 dental:            {len(DENTAL_RULES)} rules, {len(d_clauses)} clauses encoded")
    print(f"Total new rules:          {len(TREATMENT_RULES) + len(DENTAL_RULES)}")
    print(f"Total new clauses:        {len(t_clauses | d_clauses)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Merge C2 batch-1 §2.2 payment-method rules into payment_method_2_2.json + manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.payment_method_2_2_batch1_rules import BATCH1_RULES
from scripts.sut.prose.payment_method_gate_b import run_gate_b_pipeline

_RULES_PATH = _PROJECT_ROOT / "data/gazette/prose_rules/payment_method_2_2.json"
_MANIFEST_PATH = (
    _PROJECT_ROOT / "data/gazette/prose_manifests/L2.2_payment_method_encoded_manifest.json"
)
_CORPUS_PATH = _PROJECT_ROOT / "data/gazette/prose_corpus/L2.2_payment_method_prose.csv"
_CLAUSES_PATH = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"
_GOLDEN_PATH = _PROJECT_ROOT / "data/gazette/prose_rules/golden/payment_method_2_2_batch1.json"


def _merge_rules(existing: list[dict], batch: list[dict]) -> tuple[list[dict], int]:
    by_id = {str(rule["rule_id"]): rule for rule in existing}
    added = 0
    for rule in batch:
        clean = {k: v for k, v in rule.items() if k != "encode_batch"}
        rule_id = str(clean["rule_id"])
        if rule_id in by_id:
            continue
        by_id[rule_id] = clean
        added += 1
    merged = sorted(by_id.values(), key=lambda r: str(r.get("rule_id", "")))
    return merged, added


def _write_golden(rules: list[dict], batch: list[dict]) -> None:
    batch_ids = {str(r["rule_id"]) for r in batch}
    cases = [
        {
            "clause_id": (rule.get("gate_b_sources") or [None])[0],
            "expected_rule_id": rule["rule_id"],
            "encode_batch": next(
                (b["encode_batch"] for b in batch if b["rule_id"] == rule["rule_id"]),
                None,
            ),
        }
        for rule in rules
        if str(rule["rule_id"]) in batch_ids and rule.get("gate_b_sources")
    ]
    payload = {
        "description": "Gate B golden — C2 batch-1 payment_method_2_2 clause → rule_id",
        "cases": cases,
    }
    _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _GOLDEN_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    existing = list(payload.get("rules") or [])
    merged, added = _merge_rules(existing, BATCH1_RULES)
    payload["rules"] = merged
    _RULES_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    result = run_gate_b_pipeline(
        clauses_path=_CLAUSES_PATH,
        prose_json_path=_RULES_PATH,
        corpus_csv_path=_CORPUS_PATH,
        manifest_path=_MANIFEST_PATH,
        write_prose_json=True,
    )
    manifest = result["manifest"]
    manifest["scope_note"] = (
        f"§2.2 package vs itemized vs tier-override ({len(merged)} JSON rules, C2 batch-1)"
    )
    manifest["rules_in_json"] = len(merged)
    _MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    _write_golden(merged, BATCH1_RULES)
    encoded = manifest.get("gate_b_sources_encoded") or []
    print(f"Merged {added} new rules ({len(merged)} total)")
    print(f"Encoded clause IDs ({len(encoded)}): {', '.join(encoded)}")


if __name__ == "__main__":
    main()

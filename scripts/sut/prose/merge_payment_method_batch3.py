#!/usr/bin/env python3
"""Merge C2 batch-3 §2.2 payment-method rules into payment_method_2_2.json + manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.payment_method_2_2_batch3_rules import BATCH3_RULES
from scripts.sut.prose.payment_method_gate_b import run_gate_b_pipeline

_RULES_PATH = _PROJECT_ROOT / "data/gazette/prose_rules/payment_method_2_2.json"
_MANIFEST_PATH = (
    _PROJECT_ROOT / "data/gazette/prose_manifests/L2.2_payment_method_encoded_manifest.json"
)
_SESSION_MANIFEST_PATH = (
    _PROJECT_ROOT / "data/gazette/prose_manifests/L2.2_session_pricing_2_2_2_B_encoded_manifest.json"
)
_CORPUS_PATH = _PROJECT_ROOT / "data/gazette/prose_corpus/L2.2_payment_method_prose.csv"
_CLAUSES_PATH = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"
_GOLDEN_PATH = _PROJECT_ROOT / "data/gazette/prose_rules/golden/payment_method_2_2_batch3.json"
_SESSION_JSON = _PROJECT_ROOT / "data/gazette/prose_rules/session_pricing_2_2_2_B.json"

_SESSION_MANIFEST_STUB: dict[str, object] = {
    "manifest_version": "wave2-v1",
    "rule_set_id": "session_pricing_2_2_2_B",
    "scope_note": (
        "§2.2.2.B session-fraction PARTIAL — runtime in session_pricing.py; "
        "4 JSON rules with Gate B clause traces (not merged into payment_method_2_2.json)"
    ),
    "rules_in_json": 4,
    "session_fraction_status": "PARTIAL",
    "gate_b_sources_encoded": [
        "C000654",
        "C000655",
        "C000657",
        "C000658",
        "C000659",
        "C000660",
        "C000661",
    ],
    "encoded_clause_ids": [
        "C000654",
        "C000655",
        "C000657",
        "C000658",
        "C000659",
        "C000660",
        "C000661",
    ],
    "gate_b_sources_by_rule": {
        "2.2.2.B.(1).ek2c_package_basis": ["C000654"],
        "2.2.2.B.(2).non_package_itemized": ["C000655"],
        "2.2.2.B.a": ["C000657"],
        "2.2.2.B.b": ["C000658"],
        "2.2.2.B.c": ["C000659"],
        "2.2.2.B.ç": ["C000660"],
        "2.2.2.B.(3).cross_specialty_uplift": ["C000661"],
    },
}


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
        "description": "Gate B golden — C2 batch-3 payment_method_2_2 clause → rule_id",
        "cases": cases,
    }
    _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _GOLDEN_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_session_manifest() -> None:
    session_payload = json.loads(_SESSION_JSON.read_text(encoding="utf-8"))
    manifest = dict(_SESSION_MANIFEST_STUB)
    manifest["rules_in_json"] = len(session_payload.get("rules") or [])
    _SESSION_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SESSION_MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _apply_manifest_cross_refs(manifest: dict[str, object], rule_count: int) -> dict[str, object]:
    manifest["scope_note"] = (
        f"§2.2 package vs itemized vs tier-override ({rule_count} JSON rules, C2 batch-1+2+3)"
    )
    manifest["rules_in_json"] = rule_count
    manifest["session_fraction_status"] = "PARTIAL"
    manifest["related_rule_sets"] = [
        {
            "rule_set_id": "session_pricing_2_2_2_B",
            "json_path": "session_pricing_2_2_2_B.json",
            "manifest": "L2.2_session_pricing_2_2_2_B_encoded_manifest.json",
            "note": "§2.2.2.B session-fraction remains PARTIAL — see session_pricing.py",
        }
    ]
    return manifest


def main() -> None:
    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    existing = list(payload.get("rules") or [])
    merged, added = _merge_rules(existing, BATCH3_RULES)
    payload["rules"] = merged
    _RULES_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    _write_session_manifest()

    result = run_gate_b_pipeline(
        clauses_path=_CLAUSES_PATH,
        prose_json_path=_RULES_PATH,
        corpus_csv_path=_CORPUS_PATH,
        manifest_path=_MANIFEST_PATH,
        write_prose_json=True,
    )
    manifest = _apply_manifest_cross_refs(result["manifest"], len(merged))
    _MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    _write_golden(merged, BATCH3_RULES)
    encoded = manifest.get("gate_b_sources_encoded") or []
    print(f"Merged {added} new rules ({len(merged)} total)")
    print(f"Encoded clause IDs ({len(encoded)}): {', '.join(encoded)}")


if __name__ == "__main__":
    main()

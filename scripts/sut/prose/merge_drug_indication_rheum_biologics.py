#!/usr/bin/env python3
"""Merge §4.2.1.C* / §4.2.13* / §4.2.33* / §4.2.34 rheumatology/biologics/anti-VEGF
rules into ``drug_indication_prose.json`` and write the wave manifest.

Dedup is by ``rule_id``; when a rule already exists its ``gate_b_sources`` are
unioned with the new batch so re-runs stay idempotent.
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from scripts.sut.prose.drug_indication_rheum_biologics_batch_rules import (
    WAVE_BATCH_RULES,
    all_gate_b_sources,
)

_REPO = Path(__file__).resolve().parents[3]
_RULES_PATH = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_MANIFEST_PATH = (
    _REPO
    / "data/gazette/prose_manifests/"
    / "L4.2_drug_indication_rheum_biologics_manifest.json"
)
_WAVE_CSV = _REPO / "tasks/encode_waves/A1b_rheum_biologics.csv"


def _load_rules() -> list[dict]:
    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    return list(payload.get("rules") or [])


def merge_batch(existing: list[dict], batch: list[dict]) -> tuple[list[dict], int, set[str]]:
    by_id = {str(rule["rule_id"]): dict(rule) for rule in existing}
    added = 0
    covered: set[str] = set()
    for raw in batch:
        clean = {k: v for k, v in raw.items() if k != "encode_batch"}
        rule_id = str(clean["rule_id"])
        sources = list(clean.get("gate_b_sources") or [])
        covered.update(sources)
        if rule_id in by_id:
            before = set(by_id[rule_id].get("gate_b_sources") or [])
            clean["gate_b_sources"] = sorted(before | set(sources))
            by_id[rule_id] = clean
        else:
            by_id[rule_id] = clean
            added += 1
    merged = sorted(by_id.values(), key=lambda r: str(r.get("rule_id", "")))
    return merged, added, covered


def _write_manifest(covered: set[str]) -> dict:
    wave_ids = sorted(
        r["clause_id"]
        for r in csv.DictReader(_WAVE_CSV.open(encoding="utf-8"))
    )
    payload = {
        "manifest_version": "r5-a5-v1",
        "section_id": "4.2.1.C*,4.2.13*,4.2.33*,4.2.34",
        "effective_date": date.today().isoformat(),
        "rules_in_json": len(WAVE_BATCH_RULES),
        "wave_clause_total": len(wave_ids),
        "encoded_clause_count": len(covered),
        "encoded_clause_ids": sorted(covered),
        "gate_b_sources_encoded": sorted(covered),
        "wave_clause_ids": wave_ids,
    }
    _MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MANIFEST_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def main() -> None:
    existing = _load_rules()
    merged, added, covered = merge_batch(existing, WAVE_BATCH_RULES)

    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    anchors = set(payload.get("sut_anchors") or ["4.2"])
    anchors.update({"4.2.1.C", "4.2.13", "4.2.33", "4.2.34"})
    payload["sut_anchors"] = sorted(anchors)
    payload["coverage_note"] = (
        f"Wave A1b — {len(merged)} rules; rheumatology/biologics/anti-VEGF "
        f"(§4.2.1.C*/§4.2.13*/§4.2.33*/§4.2.34) batch merged."
    )
    payload["rules"] = merged
    _RULES_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    manifest = _write_manifest(covered)
    print(
        f"Wave A1b merged: added={added} total_rules={len(merged)} "
        f"encoded_sources={len(covered)}"
    )
    print(f"  manifest encoded={manifest['encoded_clause_count']}")
    print(f"Wrote rules -> {_RULES_PATH}")
    print(f"Wrote manifest -> {_MANIFEST_PATH}")


if __name__ == "__main__":
    main()

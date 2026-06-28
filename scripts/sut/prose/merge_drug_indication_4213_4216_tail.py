#!/usr/bin/env python3
"""Merge §4.2.16 A2b + §4.2.13/4.2.16 Tier B tail batches into drug_indication_prose.json."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.drug_indication_4213_4216_tail_batch_rules import (
    BATCH_4213_4216_TAIL_RULES,
)
from scripts.sut.prose.drug_indication_4213_4216_gate_b import (
    gate_b_summary,
    write_gate_b_artifacts,
)
from scripts.sut.prose.merge_drug_indication_4213_4216 import merge_a2_batch

_REPO = _PROJECT_ROOT
_RULES_PATH = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_CLAUSES_PATH = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS_CSV = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4213_4216.csv"
_MANIFEST_PATH = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4213_4216_manifest.json"


def _load_rules() -> list[dict]:
    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    return list(payload.get("rules") or [])


def main() -> None:
    existing = _load_rules()
    merged, added, covered = merge_a2_batch(existing, BATCH_4213_4216_TAIL_RULES)

    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    anchors = set(payload.get("sut_anchors") or ["4.2", "4.2.14.C"])
    anchors.update(["4.2.13", "4.2.16"])
    payload["sut_anchors"] = sorted(anchors)
    payload["coverage_note"] = (
        f"R5 A2b+TierB tail — {len(merged)} rules; §4.2.16 formula + §4.2.13 HBV switch merged."
    )
    payload["rules"] = merged
    _RULES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    effective = date.today().isoformat()
    frame, manifest = write_gate_b_artifacts(
        clauses_path=_CLAUSES_PATH,
        rules_path=_RULES_PATH,
        corpus_csv=_CORPUS_CSV,
        manifest_path=_MANIFEST_PATH,
        effective_date=effective,
    )

    print(
        f"Tail merged: added={added} total_rules={len(merged)} covered_sources={len(covered)}"
    )
    print(
        f"  manifest encoded={manifest['encoded_clause_count']} "
        f"tier_a_pending={manifest['tier_a_pending_count']} "
        f"tier_b_pending={manifest['tier_b_pending_count']} "
        f"tier_c_deferred={manifest['tier_c_deferred_count']}"
    )
    for key, value in sorted(gate_b_summary(frame).items()):
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

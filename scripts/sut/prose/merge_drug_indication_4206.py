#!/usr/bin/env python3
"""Merge §4.2.6 A6 growth hormone pilot rules into drug_indication_prose.json + manifest."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scripts.sut.prose.drug_indication_4206_batch_rules import BATCH_A6_RULES
from scripts.sut.prose.drug_indication_4206_gate_b import (
    gate_b_summary,
    write_gate_b_artifacts,
)

_REPO = Path(__file__).resolve().parents[3]
_RULES_PATH = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_CLAUSES_PATH = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS_CSV = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4206.csv"
_MANIFEST_PATH = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4206_manifest.json"
_GOLDEN_PATH = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.6_a6.json"


def _load_rules() -> list[dict]:
    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    return list(payload.get("rules") or [])


def merge_a6_batch(existing: list[dict], batch: list[dict]) -> tuple[list[dict], int, set[str]]:
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


def _write_golden() -> None:
    samples = [
        {
            "drug_name": "GENOTROPIN 5.3 MG (SOMATROPIN)",
            "primary_icd10": "E23.0",
            "report_present": False,
            "prescriber_specialty": "endokrinoloji",
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.6.adult_somatropin_board_report",
        },
        {
            "drug_name": "GENOTROPIN 5.3 MG (SOMATROPIN)",
            "primary_icd10": "E23.0",
            "report_present": True,
            "prescriber_specialty": "endokrinoloji",
            "report_duration_months": 12,
            "expect_violation": None,
            "rule_id": "4.2.6.adult_somatropin_board_report",
        },
        {
            "drug_name": "GENOTROPIN 5.3 MG (SOMATROPIN)",
            "primary_icd10": "E23.0",
            "report_present": True,
            "prescriber_specialty": "ortopedi ve travmatoloji",
            "report_duration_months": 12,
            "expect_violation": "prescriber_specialty_mismatch",
            "rule_id": "4.2.6.adult_somatropin_board_report",
        },
        {
            "drug_name": "GENOTROPIN 5.3 MG (SOMATROPIN)",
            "primary_icd10": "J45.9",
            "report_present": True,
            "prescriber_specialty": "endokrinoloji",
            "report_duration_months": 12,
            "expect_violation": "indication_mismatch",
            "rule_id": "4.2.6.adult_somatropin_board_report",
        },
        {
            "drug_name": "NORDITROPIN 10 MG (SOMATROPIN)",
            "primary_icd10": "Q96.9",
            "report_present": False,
            "prescriber_specialty": "çocuk endokrinoloji",
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.6.turner_somatropin_pediatric_board",
        },
        {
            "drug_name": "NORDITROPIN 10 MG (SOMATROPIN)",
            "primary_icd10": "Q96.9",
            "report_present": True,
            "prescriber_specialty": "çocuk endokrinoloji",
            "report_duration_months": 12,
            "expect_violation": None,
            "rule_id": "4.2.6.turner_somatropin_pediatric_board",
        },
        {
            "drug_name": "INCRELEX 10 MG/ML (MECASERMIN)",
            "primary_icd10": "E34.31",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.6.laron_mecasermin_continuation_board",
        },
        {
            "drug_name": "INCRELEX 10 MG/ML (MECASERMIN)",
            "primary_icd10": "E34.31",
            "report_present": True,
            "report_duration_months": 12,
            "expect_violation": None,
            "rule_id": "4.2.6.laron_mecasermin_continuation_board",
        },
        {
            "drug_name": "INCRELEX 10 MG/ML (MECASERMIN)",
            "primary_icd10": "E34.31",
            "report_present": True,
            "report_duration_months": None,
            "expect_violation": "needs_report_verification",
            "rule_id": "4.2.6.laron_mecasermin_continuation_board",
        },
    ]
    _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _GOLDEN_PATH.write_text(
        json.dumps({"samples": samples}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    existing = _load_rules()
    merged, added, covered = merge_a6_batch(existing, BATCH_A6_RULES)

    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    anchors = set(payload.get("sut_anchors") or ["4.2", "4.2.14.C"])
    anchors.add("4.2.6")
    payload["sut_anchors"] = sorted(anchors)
    payload["coverage_note"] = (
        f"R5 A6 pilot — {len(merged)} rules; §4.2.6 growth hormone batch merged."
    )
    payload["rules"] = merged
    _RULES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    effective = date.today().isoformat()
    frame, manifest = write_gate_b_artifacts(
        clauses_path=_CLAUSES_PATH,
        rules=BATCH_A6_RULES,
        corpus_csv=_CORPUS_CSV,
        manifest_path=_MANIFEST_PATH,
        effective_date=effective,
    )
    _write_golden()

    print(f"A6 merged: added={added} total_rules={len(merged)} covered_sources={len(covered)}")
    print(
        f"  manifest encoded={manifest['encoded_clause_count']} "
        f"tier_c_deferred={manifest['tier_c_deferred_count']}"
    )
    print(f"Wrote rules -> {_RULES_PATH}")
    print(f"Wrote manifest -> {_MANIFEST_PATH}")
    print(f"Wrote corpus -> {_CORPUS_CSV}")
    print(f"Wrote golden -> {_GOLDEN_PATH}")
    for key, value in sorted(gate_b_summary(frame).items()):
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

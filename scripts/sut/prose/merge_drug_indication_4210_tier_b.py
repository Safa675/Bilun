#!/usr/bin/env python3
"""Gate B export for §4.2.10 LSD Tier B batch (no prose JSON merge)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scripts.sut.prose.drug_indication_4210_batch_rules import BATCH_LSD4210_RULES
from scripts.sut.prose.drug_indication_4210_gate_b import (
    gate_b_summary,
    write_gate_b_artifacts,
)
from scripts.sut.prose.drug_indication_4210_tier_b_batch_rules import BATCH_4210_TIER_B_RULES

_REPO = Path(__file__).resolve().parents[3]
_CLAUSES_PATH = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS_CSV = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4210.csv"
_MANIFEST_PATH = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4210_manifest.json"
_GOLDEN_PATH = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.10_tier_b.json"

_COMBINED_4210_RULES = BATCH_LSD4210_RULES + BATCH_4210_TIER_B_RULES


def _write_golden() -> None:
    samples = [
        {
            "drug_name": "CEREZYME 400 U (IMIGLUCERASE)",
            "primary_icd10": "E75.22",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.10.gaucher_enzyme_legacy_continuation_report",
        },
        {
            "drug_name": "CEREZYME 400 U (IMIGLUCERASE)",
            "primary_icd10": "E75.22",
            "report_present": True,
            "report_duration_months": 6,
            "expect_violation": None,
            "rule_id": "4.2.10.gaucher_enzyme_legacy_continuation_report",
        },
        {
            "drug_name": "CEREZYME 400 U (IMIGLUCERASE)",
            "primary_icd10": "E75.22",
            "report_present": True,
            "report_duration_months": None,
            "expect_violation": "needs_report_verification",
            "rule_id": "4.2.10.gaucher_enzyme_legacy_continuation_report",
        },
        {
            "drug_name": "CEREZYME 400 U (IMIGLUCERASE)",
            "primary_icd10": "J45.9",
            "report_present": True,
            "report_duration_months": 6,
            "expect_violation": "indication_mismatch",
            "rule_id": "4.2.10.gaucher_enzyme_legacy_continuation_report",
        },
        {
            "drug_name": "ALDURAZYME 2.9 MG (LARONIDASE)",
            "primary_icd10": "E76.0",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.10.mps1_annual_evaluation_continuation",
        },
        {
            "drug_name": "ALDURAZYME 2.9 MG (LARONIDASE)",
            "primary_icd10": "E76.0",
            "report_present": True,
            "report_duration_months": 12,
            "expect_violation": None,
            "rule_id": "4.2.10.mps1_annual_evaluation_continuation",
        },
        {
            "drug_name": "ALDURAZYME 2.9 MG (LARONIDASE)",
            "primary_icd10": "E76.0",
            "report_present": True,
            "report_duration_months": 6,
            "expect_violation": "report_duration_mismatch",
            "rule_id": "4.2.10.mps1_annual_evaluation_continuation",
        },
        {
            "drug_name": "ALDURAZYME 2.9 MG (LARONIDASE)",
            "primary_icd10": "E76.1",
            "report_present": True,
            "report_duration_months": 12,
            "expect_violation": "indication_mismatch",
            "rule_id": "4.2.10.mps1_annual_evaluation_continuation",
        },
    ]
    _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _GOLDEN_PATH.write_text(
        json.dumps({"samples": samples}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    effective = date.today().isoformat()
    frame, manifest = write_gate_b_artifacts(
        clauses_path=_CLAUSES_PATH,
        rules=_COMBINED_4210_RULES,
        corpus_csv=_CORPUS_CSV,
        manifest_path=_MANIFEST_PATH,
        effective_date=effective,
    )
    _write_golden()

    tier_b_sources = {
        clause_id
        for rule in BATCH_4210_TIER_B_RULES
        for clause_id in (rule.get("gate_b_sources") or [])
    }
    encoded = set(manifest["gate_b_sources_encoded"])
    trace_total = manifest["section_clause_total"]
    traced = (
        manifest["encoded_clause_count"]
        + manifest["tier_c_deferred_count"]
        + manifest["tier_a_pending_count"]
        + manifest["tier_b_pending_count"]
    )
    trace_pct = round(100.0 * traced / trace_total, 1) if trace_total else 0.0

    print(
        f"TierB export: rules={manifest['rules_in_json']} "
        f"encoded={manifest['encoded_clause_count']} "
        f"tier_b_pending={manifest['tier_b_pending_count']} "
        f"tier_c={manifest['tier_c_deferred_count']}"
    )
    print(f"  tier_b_sources={sorted(tier_b_sources)} covered={tier_b_sources <= encoded}")
    print(f"  trace_completeness={trace_pct}% ({traced}/{trace_total})")
    print(f"Wrote manifest -> {_MANIFEST_PATH}")
    print(f"Wrote corpus -> {_CORPUS_CSV}")
    print(f"Wrote golden -> {_GOLDEN_PATH}")
    for key, value in sorted(gate_b_summary(frame).items()):
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

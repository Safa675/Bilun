#!/usr/bin/env python3
"""Merge §4.2.18 / §4.2.36 A5 orlistat + Parkinson pilot rules into drug_indication_prose.json."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scripts.sut.prose.drug_indication_4218_4236_batch_rules import BATCH_A5_RULES
from scripts.sut.prose.drug_indication_4218_4236_gate_b import (
    gate_b_summary,
    write_gate_b_artifacts,
)

_REPO = Path(__file__).resolve().parents[3]
_RULES_PATH = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_CLAUSES_PATH = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS_CSV = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4218_4236.csv"
_MANIFEST_PATH = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4218_4236_manifest.json"
_GOLDEN_PATH = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.18_4.2.36_a5.json"


def _load_rules() -> list[dict]:
    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    return list(payload.get("rules") or [])


def merge_a5_batch(existing: list[dict], batch: list[dict]) -> tuple[list[dict], int, set[str]]:
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
            "drug_name": "XENICAL 120 MG (ORLISTAT)",
            "primary_icd10": "E66.0",
            "report_present": None,
            "report_duration_months": None,
            "prescriber_specialty": None,
            "expect_violation": "needs_report_verification",
            "rule_id": "4.2.18.orlistat_monthly_prescription",
        },
        {
            "drug_name": "XENICAL 120 MG (ORLISTAT)",
            "primary_icd10": "E66.0",
            "report_present": None,
            "report_duration_months": 1,
            "prescriber_specialty": None,
            "expect_violation": None,
            "rule_id": "4.2.18.orlistat_monthly_prescription",
        },
        {
            "drug_name": "XENICAL 120 MG (ORLISTAT)",
            "primary_icd10": "E66.0",
            "report_present": None,
            "report_duration_months": 3,
            "prescriber_specialty": None,
            "expect_violation": "report_duration_mismatch",
            "rule_id": "4.2.18.orlistat_monthly_prescription",
        },
        {
            "drug_name": "SIFROL 1 MG (PRAMIPEXOLE)",
            "primary_icd10": "G20",
            "report_present": False,
            "report_duration_months": None,
            "prescriber_specialty": None,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.36.parkinson_dopamine_agonists_report",
        },
        {
            "drug_name": "SIFROL 1 MG (PRAMIPEXOLE)",
            "primary_icd10": "G20",
            "report_present": True,
            "report_duration_months": None,
            "prescriber_specialty": None,
            "expect_violation": None,
            "rule_id": "4.2.36.parkinson_dopamine_agonists_report",
        },
        {
            "drug_name": "TASMAR 100 MG (TOLCAPONE)",
            "primary_icd10": "G20",
            "report_present": True,
            "report_duration_months": 1,
            "prescriber_specialty": "nöroloji",
            "expect_violation": None,
            "rule_id": "4.2.36.tolcapone_tertiary_neurology_report",
        },
        {
            "drug_name": "TASMAR 100 MG (TOLCAPONE)",
            "primary_icd10": "G20",
            "report_present": True,
            "report_duration_months": 1,
            "prescriber_specialty": "dahiliye",
            "expect_violation": "prescriber_specialty_mismatch",
            "rule_id": "4.2.36.tolcapone_tertiary_neurology_report",
        },
        {
            "drug_name": "PK-MERZ 100 MG (AMANTADINE)",
            "primary_icd10": "G25.1",
            "report_present": False,
            "report_duration_months": None,
            "prescriber_specialty": None,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.36.amantadine_sulfate_report",
        },
        {
            "drug_name": "PK-MERZ 100 MG (AMANTADINE)",
            "primary_icd10": "G25.1",
            "report_present": True,
            "report_duration_months": None,
            "prescriber_specialty": None,
            "expect_violation": None,
            "rule_id": "4.2.36.amantadine_sulfate_report",
        },
        {
            "drug_name": "AMANTIX 100 MG (AMANTADIN HCL)",
            "primary_icd10": "G20",
            "report_present": True,
            "report_duration_months": None,
            "prescriber_specialty": None,
            "expect_violation": None,
            "rule_id": "4.2.36.amantadine_hcl_parkinson_report",
        },
        {
            "drug_name": "AMANTIX 100 MG (AMANTADIN HCL)",
            "primary_icd10": "G25.1",
            "report_present": True,
            "report_duration_months": None,
            "prescriber_specialty": None,
            "expect_violation": "indication_mismatch",
            "rule_id": "4.2.36.amantadine_hcl_parkinson_report",
        },
    ]
    _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _GOLDEN_PATH.write_text(
        json.dumps({"samples": samples}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    existing = _load_rules()
    merged, added, covered = merge_a5_batch(existing, BATCH_A5_RULES)

    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    anchors = set(payload.get("sut_anchors") or ["4.2", "4.2.14.C"])
    anchors.update({"4.2.18", "4.2.36"})
    payload["sut_anchors"] = sorted(anchors)
    payload["coverage_note"] = (
        f"R5 A5 pilot — {len(merged)} rules; §4.2.18 orlistat + §4.2.36 Parkinson batch merged."
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
        batch_rules=BATCH_A5_RULES,
    )
    _write_golden()

    print(f"A5 merged: added={added} total_rules={len(merged)} covered_sources={len(covered)}")
    print(
        f"  manifest encoded={manifest['encoded_clause_count']} "
        f"tier_c_deferred={manifest['tier_c_deferred_count']}"
    )
    print(f"  §4.2.18: {manifest['section_4.2.18_clause_total']} clauses "
          f"(A={manifest['section_4.2.18_tier_a_count']} C={manifest['section_4.2.18_tier_c_count']})")
    print(f"  §4.2.36: {manifest['section_4.2.36_clause_total']} clauses "
          f"(A={manifest['section_4.2.36_tier_a_count']} C={manifest['section_4.2.36_tier_c_count']})")
    print(f"Wrote rules -> {_RULES_PATH}")
    print(f"Wrote manifest -> {_MANIFEST_PATH}")
    print(f"Wrote corpus -> {_CORPUS_CSV}")
    print(f"Wrote golden -> {_GOLDEN_PATH}")
    for key, value in sorted(gate_b_summary(frame).items()):
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

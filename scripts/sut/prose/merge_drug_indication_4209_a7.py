#!/usr/bin/env python3
"""Merge §4.2.9 ESA A7 continuation rules into drug_indication_prose.json."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.drug_indication_4209_a7_batch_rules import BATCH_A7_RULES
from scripts.sut.prose.drug_indication_4209_4227_gate_b import (
    gate_b_summary,
    write_gate_b_artifacts,
)
from scripts.sut.prose.merge_drug_indication_4209_4227 import merge_a6_batch

_REPO = _PROJECT_ROOT
_RULES_PATH = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_CLAUSES_PATH = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS_CSV = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4209_4227.csv"
_MANIFEST_PATH = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4209_4227_manifest.json"
_GOLDEN_PATH = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.9_a7.json"


def _load_rules() -> list[dict]:
    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    return list(payload.get("rules") or [])


def _write_golden() -> None:
    samples = [
        {
            "drug_name": "EPREX 4000 IU (EPOETIN ALFA)",
            "primary_icd10": "N18.5",
            "report_present": False,
            "report_duration_months": None,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.9.esa_legacy_muadil_monthly_report",
        },
        {
            "drug_name": "EPREX 4000 IU (EPOETIN ALFA)",
            "primary_icd10": "N18.5",
            "report_present": True,
            "prescriber_specialty": "nefroloji",
            "report_duration_months": 1,
            "expect_violation": None,
            "rule_id": "4.2.9.esa_legacy_muadil_monthly_report",
        },
        {
            "drug_name": "EPREX 4000 IU (EPOETIN ALFA)",
            "primary_icd10": "N18.5",
            "report_present": True,
            "report_duration_months": 3,
            "expect_violation": "report_duration_mismatch",
            "rule_id": "4.2.9.esa_legacy_muadil_monthly_report",
        },
        {
            "drug_name": "BINOCRIT 4000 IU (EPOETIN ALFA)",
            "primary_icd10": "N18.4",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.9.esa_ckd_iron_hb_nephrology_report",
        },
        {
            "drug_name": "BINOCRIT 4000 IU (EPOETIN ALFA)",
            "primary_icd10": "N18.4",
            "report_present": True,
            "prescriber_specialty": "nefroloji",
            "report_duration_months": 1,
            "expect_violation": None,
            "rule_id": "4.2.9.esa_ckd_iron_hb_nephrology_report",
        },
        {
            "drug_name": "ARANESP 40 MCG (DARBEPETIN)",
            "primary_icd10": "N18.5",
            "report_present": True,
            "prescriber_specialty": "diyaliz",
            "expect_violation": None,
            "rule_id": "4.2.9.esa_ckd_legacy_nephrology_prescriber",
        },
        {
            "drug_name": "ARANESP 40 MCG (DARBEPETIN)",
            "primary_icd10": "N18.5",
            "report_present": True,
            "prescriber_specialty": "kardiyoloji",
            "expect_violation": "prescriber_specialty_mismatch",
            "rule_id": "4.2.9.esa_ckd_legacy_nephrology_prescriber",
        },
        {
            "drug_name": "EVRENZO 70 MG (ROKSADUSTAT)",
            "primary_icd10": "N18.5",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.9.roksadustat_esa_switch_dialysis_report",
        },
        {
            "drug_name": "EVRENZO 70 MG (ROKSADUSTAT)",
            "primary_icd10": "N18.5",
            "report_present": True,
            "prescriber_specialty": "nefroloji",
            "report_duration_months": 1,
            "expect_violation": None,
            "rule_id": "4.2.9.roksadustat_esa_switch_dialysis_report",
        },
        {
            "drug_name": "BINOCRIT 4000 IU (EPOETIN ALFA)",
            "primary_icd10": "D46.9",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.9.mds_esa_initiation_hematology_report",
        },
        {
            "drug_name": "BINOCRIT 4000 IU (EPOETIN ALFA)",
            "primary_icd10": "D46.9",
            "report_present": True,
            "prescriber_specialty": "hematoloji",
            "expect_violation": None,
            "rule_id": "4.2.9.mds_esa_initiation_hematology_report",
        },
        {
            "drug_name": "ZEMPLAR 2 MCG (PARIKALSITOL)",
            "primary_icd10": "N18.5",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.9.paricalcitol_oral_pd_nephrology_report",
        },
        {
            "drug_name": "ZEMPLAR 2 MCG (PARIKALSITOL)",
            "primary_icd10": "N18.5",
            "report_present": True,
            "prescriber_specialty": "nefroloji",
            "report_duration_months": 3,
            "expect_violation": None,
            "rule_id": "4.2.9.paricalcitol_oral_pd_nephrology_report",
        },
        {
            "drug_name": "ZEMPLAR 2 MCG (PARIKALSITOL)",
            "primary_icd10": "E21.0",
            "report_present": True,
            "expect_violation": "indication_mismatch",
            "rule_id": "4.2.9.paricalcitol_oral_pd_nephrology_report",
        },
    ]
    _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _GOLDEN_PATH.write_text(
        json.dumps({"samples": samples}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    existing = _load_rules()
    merged, added, covered = merge_a6_batch(existing, BATCH_A7_RULES)

    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    anchors = set(payload.get("sut_anchors") or ["4.2", "4.2.14.C"])
    anchors.update({"4.2.9", "4.2.27"})
    payload["sut_anchors"] = sorted(anchors)
    payload["coverage_note"] = (
        f"R5 A7 batch — {len(merged)} rules; §4.2.9 ESA legacy tier-A continuation merged."
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
    _write_golden()

    print(f"A7 merged: added={added} total_rules={len(merged)} covered_sources={len(covered)}")
    print(
        f"  manifest encoded={manifest['encoded_clause_count']} "
        f"tier_a_pending={manifest['tier_a_pending_count']} "
        f"tier_c_deferred={manifest['tier_c_deferred_count']}"
    )
    print(f"Wrote rules -> {_RULES_PATH}")
    print(f"Wrote manifest -> {_MANIFEST_PATH}")
    print(f"Wrote golden -> {_GOLDEN_PATH}")
    for key, value in sorted(gate_b_summary(frame).items()):
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

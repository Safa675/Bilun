#!/usr/bin/env python3
"""Merge §4.2.27 coagulation A8 tier-A continuation rules into drug_indication_prose.json."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.drug_indication_4209_4227_gate_b import (  # noqa: E402
    gate_b_summary,
    write_gate_b_artifacts,
)
from scripts.sut.prose.drug_indication_4227_a8_batch_rules import BATCH_A8_RULES
from scripts.sut.prose.merge_drug_indication_4209_4227 import merge_a6_batch

_REPO = _PROJECT_ROOT
_RULES_PATH = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_CLAUSES_PATH = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS_CSV = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4209_4227.csv"
_MANIFEST_PATH = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4209_4227_manifest.json"
_GOLDEN_PATH = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.27_a8.json"


def _load_rules() -> list[dict]:
    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    return list(payload.get("rules") or [])


def _write_golden() -> None:
    samples = [
        {
            "drug_name": "HEMOFIL M 1000 IU (FACTOR VIII)",
            "primary_icd10": "D66",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.27.coagulation_factor_board_report",
        },
        {
            "drug_name": "HEMOFIL M 1000 IU (FACTOR VIII)",
            "primary_icd10": "D66",
            "report_present": True,
            "prescriber_specialty": "hematoloji",
            "expect_violation": None,
            "rule_id": "4.2.27.coagulation_factor_board_report",
        },
        {
            "drug_name": "HEMOFIL M 1000 IU (FACTOR VIII)",
            "primary_icd10": "D66",
            "report_present": True,
            "prescriber_specialty": "kardiyoloji",
            "expect_violation": "prescriber_specialty_mismatch",
            "rule_id": "4.2.27.coagulation_factor_board_report",
        },
        {
            "drug_name": "ALFINITI 250 IU (FACTOR IX)",
            "primary_icd10": "D67",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.27.prophylaxis_acute_bleed_3day_report",
        },
        {
            "drug_name": "ALFINITI 250 IU (FACTOR IX)",
            "primary_icd10": "D67",
            "report_present": True,
            "expect_violation": None,
            "rule_id": "4.2.27.prophylaxis_acute_bleed_3day_report",
        },
        {
            "drug_name": "HEMOFIL M 1000 IU (FACTOR VIII)",
            "primary_icd10": "D66",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.27.coagulation_emergency_one_day",
        },
        {
            "drug_name": "HEMOFIL M 1000 IU (FACTOR VIII)",
            "primary_icd10": "D66",
            "report_present": True,
            "expect_violation": None,
            "rule_id": "4.2.27.coagulation_emergency_one_day",
        },
        {
            "drug_name": "OCTAPLEX 500 IU (PROTHROMBIN COMPLEX)",
            "primary_icd10": "D68.4",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.27.pcc_acquired_coagulopathy_board",
        },
        {
            "drug_name": "OCTAPLEX 500 IU (PROTHROMBIN COMPLEX)",
            "primary_icd10": "D68.4",
            "report_present": True,
            "expect_violation": None,
            "rule_id": "4.2.27.pcc_acquired_coagulopathy_board",
        },
        {
            "drug_name": "BERIPLEX 500 IU (PROTHROMBIN COMPLEX)",
            "primary_icd10": "T45.515A",
            "report_present": None,
            "expect_violation": None,
            "rule_id": "4.2.27.coumarin_active_bleed_one_day",
        },
        {
            "drug_name": "BERIPLEX 500 IU (PROTHROMBIN COMPLEX)",
            "primary_icd10": "J45.9",
            "report_present": None,
            "expect_violation": "indication_mismatch",
            "rule_id": "4.2.27.coumarin_active_bleed_one_day",
        },
        {
            "drug_name": "HEMOFIL M 1000 IU (FACTOR VIII)",
            "primary_icd10": "D66",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.27.factor_annual_board_report",
        },
        {
            "drug_name": "HEMOFIL M 1000 IU (FACTOR VIII)",
            "primary_icd10": "D66",
            "report_present": True,
            "prescriber_specialty": "iç hastalıkları",
            "report_duration_months": 12,
            "expect_violation": None,
            "rule_id": "4.2.27.factor_annual_board_report",
        },
        {
            "drug_name": "HEMOFIL M 1000 IU (FACTOR VIII)",
            "primary_icd10": "D66",
            "report_present": True,
            "report_duration_months": 6,
            "expect_violation": "report_duration_mismatch",
            "rule_id": "4.2.27.factor_annual_board_report",
        },
        {
            "drug_name": "WILATE 500 IU (VON WILLEBRAND)",
            "primary_icd10": "D68.0",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.27.vwf_weekly_unit_cap_board",
        },
        {
            "drug_name": "WILATE 500 IU (VON WILLEBRAND)",
            "primary_icd10": "D68.0",
            "report_present": True,
            "report_duration_months": 6,
            "expect_violation": None,
            "rule_id": "4.2.27.vwf_weekly_unit_cap_board",
        },
        {
            "drug_name": "HAEMATE P 500 IU (VON WILLEBRAND)",
            "primary_icd10": "D68.0",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.27.vwf_acute_bleed_3day_report",
        },
        {
            "drug_name": "HAEMATE P 500 IU (VON WILLEBRAND)",
            "primary_icd10": "D68.0",
            "report_present": True,
            "expect_violation": None,
            "rule_id": "4.2.27.vwf_acute_bleed_3day_report",
        },
        {
            "drug_name": "HEMLIBRA 105 MG (EMICIZUMAB)",
            "primary_icd10": "D66",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.27.emicizumab_hematology_monthly_prescription",
        },
        {
            "drug_name": "HEMLIBRA 105 MG (EMICIZUMAB)",
            "primary_icd10": "D66",
            "report_present": True,
            "prescriber_specialty": "hematoloji",
            "report_duration_months": 3,
            "expect_violation": None,
            "rule_id": "4.2.27.emicizumab_hematology_monthly_prescription",
        },
        {
            "drug_name": "HEMLIBRA 105 MG (EMICIZUMAB)",
            "primary_icd10": "D66",
            "report_present": True,
            "prescriber_specialty": "iç hastalıkları",
            "report_duration_months": 3,
            "expect_violation": "prescriber_specialty_mismatch",
            "rule_id": "4.2.27.emicizumab_hematology_monthly_prescription",
        },
        {
            "drug_name": "ALBUTEIN 20% (HUMAN ALBUMIN)",
            "primary_icd10": "E86.0",
            "drug_inpatient_supply": True,
            "expect_violation": None,
            "rule_id": "4.2.27.human_albumin_inpatient_hypoalbuminemia",
        },
        {
            "drug_name": "ALBUTEIN 20% (HUMAN ALBUMIN)",
            "primary_icd10": "E86.0",
            "drug_inpatient_supply": False,
            "expect_violation": "inpatient_supply_required",
            "rule_id": "4.2.27.human_albumin_inpatient_hypoalbuminemia",
        },
        {
            "drug_name": "ALBUTEIN 20% (HUMAN ALBUMIN)",
            "primary_icd10": "J45.9",
            "drug_inpatient_supply": True,
            "expect_violation": "indication_mismatch",
            "rule_id": "4.2.27.human_albumin_inpatient_hypoalbuminemia",
        },
    ]
    _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _GOLDEN_PATH.write_text(
        json.dumps({"samples": samples}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    existing = _load_rules()
    merged, added, covered = merge_a6_batch(existing, BATCH_A8_RULES)

    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    anchors = set(payload.get("sut_anchors") or ["4.2", "4.2.14.C"])
    anchors.update({"4.2.9", "4.2.27"})
    payload["sut_anchors"] = sorted(anchors)
    payload["coverage_note"] = (
        f"R5 A8 batch — {len(merged)} rules; §4.2.27 coagulation tier-A continuation merged."
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

    print(f"A8 merged: added={added} total_rules={len(merged)} covered_sources={len(covered)}")
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

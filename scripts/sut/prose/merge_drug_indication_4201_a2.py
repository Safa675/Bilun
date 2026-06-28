#!/usr/bin/env python3
"""Merge §4.2.1 A2 rheumatology/biologic batch rules into drug_indication_prose.json + manifest."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.drug_indication_4201_a2_batch_rules import BATCH_A2_RULES
from scripts.sut.prose.drug_indication_4201_gate_b import (
    gate_b_summary,
    write_gate_b_artifacts,
)
from scripts.sut.prose.merge_drug_indication_4201 import merge_a1_batch

_REPO = _PROJECT_ROOT
_RULES_PATH = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_CLAUSES_PATH = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS_CSV = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4201.csv"
_MANIFEST_PATH = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4201_manifest.json"
_GOLDEN_PATH = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.1_a2.json"


def _load_rules() -> list[dict]:
    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    return list(payload.get("rules") or [])


def _write_golden() -> None:
    samples = [
        {
            "drug_name": "HUMIRA 40 MG (ADALIMUMAB)",
            "primary_icd10": "M06.9",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.anti_tnf_ra_das28_initiation",
        },
        {
            "drug_name": "HUMIRA 40 MG (ADALIMUMAB)",
            "primary_icd10": "M06.9",
            "report_present": True,
            "prescriber_specialty": "romatoloji",
            "report_duration_months": 3,
            "expect_violation": None,
            "rule_id": "4.2.1.anti_tnf_ra_das28_initiation",
        },
        {
            "drug_name": "REMICADE 100 MG (INFLIKSIMAB)",
            "primary_icd10": "M05.9",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.infliximab_ra_das28_second_line",
        },
        {
            "drug_name": "REMICADE 100 MG (INFLIKSIMAB)",
            "primary_icd10": "M05.9",
            "report_present": True,
            "prescriber_specialty": "romatoloji",
            "report_duration_months": 3,
            "expect_violation": None,
            "rule_id": "4.2.1.infliximab_ra_das28_second_line",
        },
        {
            "drug_name": "ENBREL 50 MG (ETANERSEPT)",
            "primary_icd10": "M08.0",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.anti_tnf_jia_start_board",
        },
        {
            "drug_name": "ENBREL 50 MG (ETANERSEPT)",
            "primary_icd10": "M08.0",
            "report_present": True,
            "prescriber_specialty": "çocuk romatoloji",
            "report_duration_months": 3,
            "expect_violation": None,
            "rule_id": "4.2.1.anti_tnf_jia_start_board",
        },
        {
            "drug_name": "HUMIRA 40 MG (ADALIMUMAB)",
            "primary_icd10": "M08.1",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.anti_tnf_jia_dmard_failure_board",
        },
        {
            "drug_name": "HUMIRA 40 MG (ADALIMUMAB)",
            "primary_icd10": "M08.1",
            "report_present": True,
            "prescriber_specialty": "çocuk sağlığı",
            "report_duration_months": 3,
            "expect_violation": None,
            "rule_id": "4.2.1.anti_tnf_jia_dmard_failure_board",
        },
        {
            "drug_name": "HUMIRA 40 MG (ADALIMUMAB)",
            "primary_icd10": "M08.3",
            "report_present": True,
            "prescriber_specialty": "çocuk sağlığı",
            "report_duration_months": 3,
            "expect_violation": None,
            "rule_id": "4.2.1.adalimumab_jia_uveitis_first_line",
        },
        {
            "drug_name": "HUMIRA 40 MG (ADALIMUMAB)",
            "primary_icd10": "J45.9",
            "report_present": True,
            "expect_violation": "indication_mismatch",
            "rule_id": "4.2.1.adalimumab_jia_uveitis_first_line",
        },
        {
            "drug_name": "REMICADE 100 MG (INFLIKSIMAB)",
            "primary_icd10": "M45.9",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.infliximab_as_basdai_second_line",
        },
        {
            "drug_name": "REMICADE 100 MG (INFLIKSIMAB)",
            "primary_icd10": "M45.9",
            "report_present": True,
            "report_duration_months": 3,
            "expect_violation": None,
            "rule_id": "4.2.1.infliximab_as_basdai_second_line",
        },
        {
            "drug_name": "SIMPONI 50 MG (GOLIMUMAB)",
            "primary_icd10": "L40.5",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.inflix_psa_second_line_psarc",
        },
        {
            "drug_name": "SIMPONI 50 MG (GOLIMUMAB)",
            "primary_icd10": "L40.5",
            "report_present": True,
            "report_duration_months": 3,
            "expect_violation": None,
            "rule_id": "4.2.1.inflix_psa_second_line_psarc",
        },
        {
            "drug_name": "HUMIRA 40 MG (ADALIMUMAB)",
            "primary_icd10": "L40.0",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.anti_tnf_psoriasis_vulgaris_board",
        },
        {
            "drug_name": "HUMIRA 40 MG (ADALIMUMAB)",
            "primary_icd10": "L40.0",
            "report_present": True,
            "prescriber_specialty": "dermatoloji",
            "report_duration_months": 6,
            "expect_violation": None,
            "rule_id": "4.2.1.anti_tnf_psoriasis_vulgaris_board",
        },
        {
            "drug_name": "HUMIRA 40 MG (ADALIMUMAB)",
            "primary_icd10": "K50.9",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.adalimumab_pediatric_crohn_board",
        },
        {
            "drug_name": "HUMIRA 40 MG (ADALIMUMAB)",
            "primary_icd10": "K50.9",
            "report_present": True,
            "prescriber_specialty": "çocuk gastroenteroloji",
            "report_duration_months": 4,
            "expect_violation": None,
            "rule_id": "4.2.1.adalimumab_pediatric_crohn_board",
        },
        {
            "drug_name": "REMICADE 100 MG (INFLIKSIMAB)",
            "primary_icd10": "K51.9",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.anti_tnf_uc_conv_failure_board",
        },
        {
            "drug_name": "REMICADE 100 MG (INFLIKSIMAB)",
            "primary_icd10": "K51.9",
            "report_present": True,
            "prescriber_specialty": "gastroenteroloji",
            "report_duration_months": 6,
            "expect_violation": None,
            "rule_id": "4.2.1.anti_tnf_uc_conv_failure_board",
        },
        {
            "drug_name": "HUMIRA 40 MG (ADALIMUMAB)",
            "primary_icd10": "H20.0",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.adalimumab_pediatric_uveitis_board",
        },
        {
            "drug_name": "HUMIRA 40 MG (ADALIMUMAB)",
            "primary_icd10": "H20.0",
            "report_present": True,
            "prescriber_specialty": "göz hastalıkları",
            "report_duration_months": 3,
            "expect_violation": None,
            "rule_id": "4.2.1.adalimumab_pediatric_uveitis_board",
        },
        {
            "drug_name": "HUMIRA 40 MG (ADALIMUMAB)",
            "primary_icd10": "L73.2",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.adalimumab_hs_dermatology_board",
        },
        {
            "drug_name": "HUMIRA 40 MG (ADALIMUMAB)",
            "primary_icd10": "L73.2",
            "report_present": True,
            "prescriber_specialty": "dermatoloji",
            "report_duration_months": 3,
            "expect_violation": None,
            "rule_id": "4.2.1.adalimumab_hs_dermatology_board",
        },
        {
            "drug_name": "ORENCIA 250 MG (ABATACEPT)",
            "primary_icd10": "M06.9",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.abatacept_ra_tnf_failure_board",
        },
        {
            "drug_name": "ORENCIA 250 MG (ABATACEPT)",
            "primary_icd10": "M06.9",
            "report_present": True,
            "prescriber_specialty": "romatoloji",
            "expect_violation": None,
            "rule_id": "4.2.1.abatacept_ra_tnf_failure_board",
        },
        {
            "drug_name": "ACTEMRA 200 MG (TOSILIZUMAB)",
            "primary_icd10": "M06.9",
            "report_present": True,
            "report_duration_months": None,
            "expect_violation": "needs_report_verification",
            "rule_id": "4.2.1.tocilizumab_ra_university_board",
        },
        {
            "drug_name": "ACTEMRA 200 MG (TOSILIZUMAB)",
            "primary_icd10": "M06.9",
            "report_present": True,
            "prescriber_specialty": "romatoloji",
            "report_duration_months": 3,
            "expect_violation": None,
            "rule_id": "4.2.1.tocilizumab_ra_university_board",
        },
        {
            "drug_name": "ACTEMRA 200 MG (TOSILIZUMAB)",
            "primary_icd10": "M08.0",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.tocilizumab_pediatric_anti_tnf_failure",
        },
        {
            "drug_name": "ACTEMRA 200 MG (TOSILIZUMAB)",
            "primary_icd10": "M08.0",
            "report_present": True,
            "prescriber_specialty": "çocuk romatoloji",
            "report_duration_months": 3,
            "expect_violation": None,
            "rule_id": "4.2.1.tocilizumab_pediatric_anti_tnf_failure",
        },
    ]
    _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _GOLDEN_PATH.write_text(
        json.dumps({"samples": samples}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    existing = _load_rules()
    merged, added, covered = merge_a1_batch(existing, BATCH_A2_RULES)

    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    anchors = set(payload.get("sut_anchors") or ["4.2", "4.2.14.C"])
    anchors.add("4.2.1")
    payload["sut_anchors"] = sorted(anchors)
    payload["coverage_note"] = (
        f"R5 A2 batch — {len(merged)} rules; §4.2.1 rheumatology/biologic A2 merged."
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

    print(f"A2 merged: added={added} total_rules={len(merged)} covered_sources={len(covered)}")
    print(
        f"  manifest encoded={manifest['encoded_clause_count']} "
        f"tier_a_pending={manifest['tier_a_pending_count']} "
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

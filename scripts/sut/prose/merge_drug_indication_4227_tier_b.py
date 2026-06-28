#!/usr/bin/env python3
"""Gate B export for §4.2.27 Tier B batch (no prose JSON merge)."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.drug_indication_4209_4227_batch_rules import BATCH_A6_RULES
from scripts.sut.prose.drug_indication_4209_4227_gate_b import (
    audit_4227_gap_parity,
    export_4209_4227_candidates,
    gate_b_summary,
    write_gate_b_artifacts,
)
from scripts.sut.prose.drug_indication_4227_a8_batch_rules import BATCH_A8_RULES
from scripts.sut.prose.drug_indication_4227_tier_b_batch_rules import BATCH_4227_TIER_B_RULES

_REPO = _PROJECT_ROOT
_CLAUSES_PATH = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS_CSV = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4209_4227.csv"
_MANIFEST_PATH = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4209_4227_manifest.json"
_GOLDEN_PATH = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.27_tier_b.json"

_COMBINED_4227_RULES = BATCH_A6_RULES + BATCH_A8_RULES + BATCH_4227_TIER_B_RULES


def _write_golden() -> None:
    samples = [
        {
            "drug_name": "HEMOFIL M 1000 IU (FACTOR VIII)",
            "primary_icd10": "D66",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.27.coagulation_prescribing_principles_header",
        },
        {
            "drug_name": "HEMOFIL M 1000 IU (FACTOR VIII)",
            "primary_icd10": "D66",
            "report_present": True,
            "prescriber_specialty": "hematoloji",
            "expect_violation": None,
            "rule_id": "4.2.27.coagulation_prescribing_principles_header",
        },
        {
            "drug_name": "NOVOSEVEN 1 MG (FACTOR VIIA)",
            "primary_icd10": "D66",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.27.factor_viia_dose_limited_board",
        },
        {
            "drug_name": "NOVOSEVEN 1 MG (FACTOR VIIA)",
            "primary_icd10": "D66",
            "report_present": True,
            "expect_violation": None,
            "rule_id": "4.2.27.factor_viia_dose_limited_board",
        },
        {
            "drug_name": "OCTAPLEX 500 IU (PROTHROMBIN COMPLEX)",
            "primary_icd10": "D68.4",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.27.coagulopathy_hospital_one_day_prescriber",
        },
        {
            "drug_name": "OCTAPLEX 500 IU (PROTHROMBIN COMPLEX)",
            "primary_icd10": "D68.4",
            "report_present": True,
            "prescriber_specialty": "iç hastalıkları",
            "expect_violation": None,
            "rule_id": "4.2.27.coagulopathy_hospital_one_day_prescriber",
        },
        {
            "drug_name": "KONAKION 10 MG (VITAMIN K)",
            "primary_icd10": "K72.9",
            "report_present": None,
            "expect_violation": None,
            "rule_id": "4.2.27.vitamin_k_acquired_coagulopathy_referral",
        },
        {
            "drug_name": "KONAKION 10 MG (VITAMIN K)",
            "primary_icd10": "J45.9",
            "report_present": None,
            "expect_violation": "indication_mismatch",
            "rule_id": "4.2.27.vitamin_k_acquired_coagulopathy_referral",
        },
        {
            "drug_name": "BERIPLEX 500 IU (PROTHROMBIN COMPLEX)",
            "primary_icd10": "K72.9",
            "report_present": None,
            "expect_violation": None,
            "rule_id": "4.2.27.vitamin_k_emergency_one_day_no_report",
        },
        {
            "drug_name": "BERIPLEX 500 IU (PROTHROMBIN COMPLEX)",
            "primary_icd10": "J45.9",
            "report_present": None,
            "expect_violation": "indication_mismatch",
            "rule_id": "4.2.27.vitamin_k_emergency_one_day_no_report",
        },
        {
            "drug_name": "REVOLADE 25 MG (ELTROMBOPAG)",
            "primary_icd10": "D69.3",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.27.eltrombopag_pediatric_dosing_report",
        },
        {
            "drug_name": "REVOLADE 25 MG (ELTROMBOPAG)",
            "primary_icd10": "D69.3",
            "report_present": True,
            "prescriber_specialty": "hematoloji",
            "expect_violation": None,
            "rule_id": "4.2.27.eltrombopag_pediatric_dosing_report",
        },
    ]
    _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _GOLDEN_PATH.write_text(
        json.dumps({"samples": samples}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    frame_before = export_4209_4227_candidates(_CLAUSES_PATH)
    audit_before = audit_4227_gap_parity(
        _CLAUSES_PATH,
        json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
        if _MANIFEST_PATH.is_file()
        else {"clause_traces": []},
        gate_b_frame=frame_before,
    )

    effective = date.today().isoformat()
    frame, manifest = write_gate_b_artifacts(
        clauses_path=_CLAUSES_PATH,
        rules_path=_REPO / "data/gazette/prose_rules/drug_indication_prose.json",
        corpus_csv=_CORPUS_CSV,
        manifest_path=_MANIFEST_PATH,
        effective_date=effective,
        batch_rules=_COMBINED_4227_RULES,
    )
    _write_golden()

    audit_after = audit_4227_gap_parity(_CLAUSES_PATH, manifest, gate_b_frame=frame)
    tier_b_sources = {
        clause_id
        for rule in BATCH_4227_TIER_B_RULES
        for clause_id in (rule.get("gate_b_sources") or [])
    }
    encoded = set(manifest["gate_b_sources_encoded"])
    traces_427 = [
        t
        for t in manifest["clause_traces"]
        if str(t.get("section_id") or "").startswith("4.2.27")
    ]
    tier_b_427 = [
        t["clause_id"]
        for t in traces_427
        if t.get("manifest_status") == "tier_b_pending"
    ]

    print(
        f"4227-W5 TierB export: rules={len(BATCH_4227_TIER_B_RULES)} "
        f"encoded={manifest['encoded_clause_count']} "
        f"tier_b_pending={manifest['tier_b_pending_count']}"
    )
    print(f"  untraced_before={audit_before['untraced_before']}")
    print(f"  untraced_after={audit_after['untraced_after']}")
    print(f"  section_4.2.27_clause_total={manifest['section_4.2.27_clause_total']}")
    print(f"  tier_b_pending_4227={sorted(tier_b_427)}")
    print(f"  tier_b_sources={sorted(tier_b_sources)} covered={tier_b_sources <= encoded}")
    print(f"Wrote manifest -> {_MANIFEST_PATH}")
    print(f"Wrote corpus -> {_CORPUS_CSV}")
    print(f"Wrote golden -> {_GOLDEN_PATH}")
    for key, value in sorted(gate_b_summary(frame).items()):
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

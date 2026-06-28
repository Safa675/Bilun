#!/usr/bin/env python3
"""Gate B export for §4.2.1 W4 Tier B batch (no prose JSON merge)."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.drug_indication_4201_gate_b import (  # noqa: E402
    gate_b_summary,
    is_421_proper,
    write_gate_b_artifacts,
)
from scripts.sut.prose.drug_indication_4201_w4_tier_b_batch_rules import (  # noqa: E402
    BATCH_4201_W4_TIER_B_RULES,
)
from scripts.sut.prose.merge_drug_indication_4201 import merge_a1_batch  # noqa: E402

_REPO = _PROJECT_ROOT
_RULES_PATH = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_CLAUSES_PATH = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS_CSV = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4201.csv"
_MANIFEST_PATH = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4201_manifest.json"
_GOLDEN_PATH = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.1_w4_tier_b.json"


def _load_421_rules() -> list[dict]:
    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    return [
        rule
        for rule in (payload.get("rules") or [])
        if is_421_proper(str(rule.get("sut_section") or ""))
    ]


def _combined_rules() -> list[dict]:
    existing = _load_421_rules()
    merged, _added, _covered = merge_a1_batch(existing, BATCH_4201_W4_TIER_B_RULES)
    return merged


def _write_golden() -> None:
    samples = [
        {
            "drug_name": "HUMIRA 40 MG (ADALIMUMAB)",
            "primary_icd10": "K50.9",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.crohn_fistulizing_month4_cdai_report",
        },
        {
            "drug_name": "HUMIRA 40 MG (ADALIMUMAB)",
            "primary_icd10": "K50.9",
            "report_present": True,
            "report_duration_months": 4,
            "prescriber_specialty": "gastroenteroloji",
            "expect_violation": None,
            "rule_id": "4.2.1.crohn_fistulizing_month4_cdai_report",
        },
        {
            "drug_name": "MABTHERA 500 MG (RITUXIMAB)",
            "primary_icd10": "M06.9",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.rituximab_ra_romatoloji_institution_board",
        },
        {
            "drug_name": "MABTHERA 500 MG (RITUXIMAB)",
            "primary_icd10": "M06.9",
            "report_present": True,
            "prescriber_specialty": "romatoloji",
            "expect_violation": None,
            "rule_id": "4.2.1.rituximab_ra_romatoloji_institution_board",
        },
        {
            "drug_name": "ACTEMRA 200 MG (TOSILIZUMAB)",
            "primary_icd10": "M06.9",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.tocilizumab_ra_das28_06_continuation_c3",
        },
        {
            "drug_name": "ACTEMRA 200 MG (TOSILIZUMAB)",
            "primary_icd10": "M06.9",
            "report_present": True,
            "report_duration_months": 3,
            "prescriber_specialty": "romatoloji",
            "expect_violation": None,
            "rule_id": "4.2.1.tocilizumab_ra_das28_06_continuation_c3",
        },
        {
            "drug_name": "ACTEMRA 200 MG (TOSILIZUMAB)",
            "primary_icd10": "M06.9",
            "report_present": True,
            "report_duration_months": None,
            "expect_violation": "needs_report_verification",
            "rule_id": "4.2.1.tocilizumab_ra_das28_06_continuation_c5",
        },
        {
            "drug_name": "ACTEMRA 200 MG (TOSILIZUMAB)",
            "primary_icd10": "M06.9",
            "report_present": True,
            "report_duration_months": 3,
            "prescriber_specialty": "romatoloji",
            "expect_violation": None,
            "rule_id": "4.2.1.tocilizumab_ra_das28_06_continuation_c5",
        },
        {
            "drug_name": "ACTEMRA 200 MG (TOSILIZUMAB)",
            "primary_icd10": "M08.0",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.tocilizumab_jia_acr_pediatric_3mo_c5",
        },
        {
            "drug_name": "ACTEMRA 200 MG (TOSILIZUMAB)",
            "primary_icd10": "M08.0",
            "report_present": True,
            "report_duration_months": 3,
            "prescriber_specialty": "çocuk romatoloji",
            "expect_violation": None,
            "rule_id": "4.2.1.tocilizumab_jia_acr_pediatric_3mo_c5",
        },
        {
            "drug_name": "XELJANZ 5 MG (TOFACITINIB)",
            "primary_icd10": "M06.9",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.tofacitinib_ra_prescriber_board_c6",
        },
        {
            "drug_name": "XELJANZ 5 MG (TOFACITINIB)",
            "primary_icd10": "M06.9",
            "report_present": True,
            "report_duration_months": 6,
            "prescriber_specialty": "romatoloji",
            "expect_violation": None,
            "rule_id": "4.2.1.tofacitinib_ra_prescriber_board_c6",
        },
        {
            "drug_name": "XELJANZ 5 MG (TOFACITINIB)",
            "primary_icd10": "M08.0",
            "report_present": True,
            "report_duration_months": 6,
            "prescriber_specialty": "çocuk romatoloji",
            "expect_violation": None,
            "rule_id": "4.2.1.jia_acr_pediatric_6mo_continuation_c6",
        },
        {
            "drug_name": "KINERET 100 MG (ANAKINRA)",
            "primary_icd10": "M08.0",
            "report_present": True,
            "report_duration_months": None,
            "expect_violation": "needs_report_verification",
            "rule_id": "4.2.1.fmf_jia_acr_pediatric_stop_c7",
        },
        {
            "drug_name": "KINERET 100 MG (ANAKINRA)",
            "primary_icd10": "M08.0",
            "report_present": True,
            "report_duration_months": 3,
            "prescriber_specialty": "çocuk romatoloji",
            "expect_violation": None,
            "rule_id": "4.2.1.fmf_jia_acr_pediatric_stop_c7",
        },
        {
            "drug_name": "ILARIS 150 MG (KANAKINUMAB)",
            "primary_icd10": "E85.0",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.kanakinumab_fmf_3mo_response_c7",
        },
        {
            "drug_name": "ILARIS 150 MG (KANAKINUMAB)",
            "primary_icd10": "E85.0",
            "report_present": True,
            "report_duration_months": 3,
            "prescriber_specialty": "romatoloji",
            "expect_violation": None,
            "rule_id": "4.2.1.kanakinumab_fmf_3mo_response_c7",
        },
        {
            "drug_name": "COSENTYX 150 MG (SEKUKINUMAB)",
            "primary_icd10": "L73.2",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.1.sekukinumab_hs_16wk_continuation_c9",
        },
        {
            "drug_name": "COSENTYX 150 MG (SEKUKINUMAB)",
            "primary_icd10": "L73.2",
            "report_present": True,
            "report_duration_months": 6,
            "prescriber_specialty": "dermatoloji",
            "expect_violation": None,
            "rule_id": "4.2.1.sekukinumab_hs_16wk_continuation_c9",
        },
        {
            "drug_name": "COSENTYX 150 MG (SEKUKINUMAB)",
            "primary_icd10": "L73.2",
            "report_present": True,
            "report_duration_months": 4,
            "expect_violation": "report_duration_mismatch",
            "rule_id": "4.2.1.sekukinumab_hs_16wk_continuation_c9",
        },
    ]
    _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _GOLDEN_PATH.write_text(
        json.dumps({"samples": samples}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    combined = _combined_rules()
    effective = date.today().isoformat()
    frame, manifest = write_gate_b_artifacts(
        clauses_path=_CLAUSES_PATH,
        batch_rules=combined,
        corpus_csv=_CORPUS_CSV,
        manifest_path=_MANIFEST_PATH,
        effective_date=effective,
    )
    _write_golden()

    tier_b_sources = {
        clause_id
        for rule in BATCH_4201_W4_TIER_B_RULES
        for clause_id in (rule.get("gate_b_sources") or [])
    }
    encoded = set(manifest["gate_b_sources_encoded"])
    trace_total = manifest["section_clause_total"]
    traces = manifest["clause_traces"]
    traced = len(traces)
    trace_pct = round(100.0 * traced / trace_total, 1) if trace_total else 0.0

    print(
        f"W4 TierB export: tier_b_rules={len(BATCH_4201_W4_TIER_B_RULES)} "
        f"combined_rules={manifest['rules_in_json']} "
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

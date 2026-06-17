#!/usr/bin/env python3
"""Merge Phase 1+2 §4.2.14.C batch rules into drug_indication_prose.json + manifest."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scripts.sut.prose.drug_indication_manifest import build_phase5_manifest
from scripts.sut.prose.drug_indication_4214c_batch_rules import PHASE1_BATCH_RULES
from scripts.sut.prose.drug_indication_4214c_tier_b_batch_rules import PHASE2_TIER_B_RULES
from scripts.sut.prose.drug_indication_gate_b import (
    clause_ids_for_drug_names,
    export_4_2_14_c_candidates,
    gate_b_summary,
    write_gate_b_export,
)

_REPO = Path(__file__).resolve().parents[3]
_RULES_PATH = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_CLAUSES_PATH = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS_CSV = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4.2.14.C.csv"
_MANIFEST_PATH = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4.2.14.C_manifest.json"
_GOLDEN_A_PATH = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.14.C_batch_a.json"
_GOLDEN_B_PATH = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.14.C_batch_b.json"


def _load_existing_rules() -> list[dict]:
    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    return list(payload.get("rules") or [])


def _merge_rules(existing: list[dict], batch: list[dict]) -> list[dict]:
    by_id = {str(rule["rule_id"]): rule for rule in existing}
    added = 0
    for rule in batch:
        clean = {k: v for k, v in rule.items() if k != "encode_batch"}
        rule_id = str(clean["rule_id"])
        if rule_id in by_id:
            continue
        sources = clause_ids_for_drug_names(
            _CLAUSES_PATH,
            list(clean.get("drug_names") or []),
        )
        if sources:
            clean["gate_b_sources"] = sources
        by_id[rule_id] = clean
        added += 1
    merged = list(by_id.values())
    merged.sort(key=lambda r: str(r.get("rule_id", "")))
    return merged, added


def _batch_clause_ids(
    rules: list[dict],
    batch_rules: list[dict],
) -> dict[str, list[str]]:
    batch_clause_ids: dict[str, list[str]] = {}
    rules_by_id = {str(r["rule_id"]): r for r in rules}
    for batch_rule in batch_rules:
        batch = str(batch_rule.get("encode_batch") or "")
        rule_id = str(batch_rule.get("rule_id") or "")
        if not batch or rule_id not in rules_by_id:
            continue
        batch_clause_ids.setdefault(batch, []).extend(
            rules_by_id[rule_id].get("gate_b_sources") or []
        )
    for key, values in batch_clause_ids.items():
        batch_clause_ids[key] = sorted(set(values))
    return batch_clause_ids


def _write_golden(rules: list[dict]) -> None:
    samples = []
    for rule in rules:
        if not str(rule.get("rule_id", "")).startswith("4.2.14.C.(15).atezolizumab"):
            continue
        samples.append(
            {
                "drug_name": "TECENTRIQ 1200 MG (ATEZOLIZUMAB)",
                "primary_icd10": "C34.9",
                "report_present": False,
                "expect_violation": "missing_board_report",
                "rule_id": rule["rule_id"],
            }
        )
        samples.append(
            {
                "drug_name": "TECENTRIQ 1200 MG (ATEZOLIZUMAB)",
                "primary_icd10": "J45.9",
                "report_present": True,
                "expect_violation": "indication_mismatch",
                "rule_id": rule["rule_id"],
            }
        )
    for rule in rules:
        if rule.get("rule_id") != "4.2.14.C.(2).daratumumab_mm_board":
            continue
        samples.append(
            {
                "drug_name": "DARZALEX 400 MG (DARATUMUMAB)",
                "primary_icd10": "C90.0",
                "report_present": True,
                "expect_violation": None,
                "rule_id": rule["rule_id"],
            }
        )
    _GOLDEN_A_PATH.parent.mkdir(parents=True, exist_ok=True)
    _GOLDEN_A_PATH.write_text(
        json.dumps({"samples": samples}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_golden_tier_b(rules: list[dict]) -> None:
    by_id = {str(rule["rule_id"]): rule for rule in rules}
    samples: list[dict] = []

    def _sample(
        *,
        rule_id: str,
        drug_name: str,
        primary_icd10: str,
        report_present: bool | None,
        expect_violation: str | None,
        **extra: object,
    ) -> None:
        row: dict = {
            "drug_name": drug_name,
            "primary_icd10": primary_icd10,
            "report_present": report_present,
            "expect_violation": expect_violation,
            "rule_id": rule_id,
        }
        row.update(extra)
        samples.append(row)

    if "4.2.14.C.trastuzumab_3mo_ecg_board" in by_id:
        _sample(
            rule_id="4.2.14.C.trastuzumab_3mo_ecg_board",
            drug_name="HERCEPTIN 440 MG (TRASTUZUMAB)",
            primary_icd10="C50.9",
            report_present=True,
            expect_violation=None,
            drug_report_duration_months=3,
            prescriber_specialty="Tıbbi Onkoloji",
        )
        _sample(
            rule_id="4.2.14.C.trastuzumab_3mo_ecg_board",
            drug_name="HERCEPTIN 440 MG (TRASTUZUMAB)",
            primary_icd10="C50.9",
            report_present=True,
            expect_violation="report_duration_mismatch",
            drug_report_duration_months=12,
        )
    if "4.2.14.C.inpatient_hospital_supply_yatarak" in by_id:
        _sample(
            rule_id="4.2.14.C.inpatient_hospital_supply_yatarak",
            drug_name="KEYTRUDA 100 MG (PEMBROLIZUMAB)",
            primary_icd10="C34.9",
            report_present=True,
            expect_violation="inpatient_supply_required",
            drug_inpatient_supply=False,
        )
    if "4.2.14.C.trastuzumab_metastatic_prescriber_oncology" in by_id:
        _sample(
            rule_id="4.2.14.C.trastuzumab_metastatic_prescriber_oncology",
            drug_name="HERCEPTIN 440 MG (TRASTUZUMAB)",
            primary_icd10="C50.9",
            report_present=True,
            expect_violation="prescriber_specialty_mismatch",
            prescriber_specialty="Dahiliye",
        )

    _GOLDEN_B_PATH.write_text(
        json.dumps({"samples": samples}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    write_gate_b_export(_CLAUSES_PATH, _CORPUS_CSV, rules_path=_RULES_PATH)
    gate_b_frame = export_4_2_14_c_candidates(_CLAUSES_PATH, rules_path=_RULES_PATH)

    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    existing = list(payload.get("rules") or [])
    merged, phase1_added = _merge_rules(existing, PHASE1_BATCH_RULES)
    merged, phase2_added = _merge_rules(merged, PHASE2_TIER_B_RULES)

    payload["title"] = "SUT §4.2 drug indication and report requirements (4.2.14.C Phase 5)"
    payload["coverage_note"] = (
        f"Phase 0–5 — {len(merged)} rules for §4.2.14.C; full clause trace manifest "
        "(encoded + pending + Tier C deferred with theme tags)."
    )
    payload["sut_anchors"] = ["4.2", "4.2.14.C"]
    payload["rules"] = merged
    _RULES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    all_batch_rules = PHASE1_BATCH_RULES + PHASE2_TIER_B_RULES
    effective = date.today().isoformat()
    manifest = build_phase5_manifest(
        gate_b_frame=gate_b_frame,
        rules=merged,
        phase1_added=phase1_added,
        phase2_added=phase2_added,
        batch_clause_ids=_batch_clause_ids(merged, all_batch_rules),
        gate_b_summary_payload=gate_b_summary(gate_b_frame),
        effective_date=effective,
    )
    _MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _write_golden(merged)
    _write_golden_tier_b(merged)

    print(
        f"Merged phase1={phase1_added} phase2={phase2_added} "
        f"-> {len(merged)} total in {_RULES_PATH}"
    )
    print(
        f"  manifest trace complete={manifest['clause_trace_complete']} "
        f"encoded={manifest['encoded_clause_count']} "
        f"tier_c_deferred={manifest['tier_c_deferred_count']}"
    )
    print(f"Wrote manifest -> {_MANIFEST_PATH}")
    print(f"Wrote golden A -> {_GOLDEN_A_PATH}")
    print(f"Wrote golden B -> {_GOLDEN_B_PATH}")
    print(f"Wrote corpus -> {_CORPUS_CSV}")


if __name__ == "__main__":
    main()

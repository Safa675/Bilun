#!/usr/bin/env python3
"""Sprint 1 — merge Tier A/B pending §4.2.14.C rules + rebuild manifest."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scripts.sut.prose.drug_indication_manifest import build_phase5_manifest
from scripts.sut.prose.drug_indication_4214c_sprint1_batch_rules import (
    PENDING_CLAUSE_IDS,
    SOURCE_PATCHES,
    SPRINT1_NEW_RULES,
)
from scripts.sut.prose.drug_indication_gate_b import (
    export_4_2_14_c_candidates,
    gate_b_summary,
    write_gate_b_export,
)

_REPO = Path(__file__).resolve().parents[3]
_RULES_PATH = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_CLAUSES_PATH = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS_CSV = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4.2.14.C.csv"
_MANIFEST_PATH = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4.2.14.C_manifest.json"
_GOLDEN_S1_PATH = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.14.C_sprint1.json"


def _load_rules() -> list[dict]:
    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    return list(payload.get("rules") or [])


def _union_sources(existing: list[str] | None, extra: list[str]) -> list[str]:
    return sorted(set(existing or []) | set(extra))


def merge_sprint1(existing: list[dict]) -> tuple[list[dict], int, int, set[str]]:
    by_id = {str(rule["rule_id"]): dict(rule) for rule in existing}
    added = patched = 0
    covered: set[str] = set()

    for rule_id, clause_ids in SOURCE_PATCHES.items():
        if rule_id not in by_id:
            raise KeyError(f"SOURCE_PATCHES references missing rule_id: {rule_id}")
        before = set(by_id[rule_id].get("gate_b_sources") or [])
        by_id[rule_id]["gate_b_sources"] = _union_sources(before, clause_ids)
        if set(by_id[rule_id]["gate_b_sources"]) != before:
            patched += 1
        covered.update(clause_ids)

    for raw in SPRINT1_NEW_RULES:
        clean = {k: v for k, v in raw.items() if k != "encode_batch"}
        rule_id = str(clean["rule_id"])
        sources = list(clean.get("gate_b_sources") or [])
        covered.update(sources)
        if rule_id in by_id:
            before = set(by_id[rule_id].get("gate_b_sources") or [])
            by_id[rule_id]["gate_b_sources"] = _union_sources(before, sources)
            if set(by_id[rule_id]["gate_b_sources"]) != before:
                patched += 1
        else:
            by_id[rule_id] = clean
            added += 1

    merged = sorted(by_id.values(), key=lambda r: str(r.get("rule_id", "")))
    return merged, added, patched, covered


def _batch_clause_ids(rules: list[dict]) -> dict[str, list[str]]:
    batches: dict[str, list[str]] = {}
    for rule in rules:
        batch = str(rule.get("encode_batch") or "")
        if not batch:
            continue
        batches.setdefault(batch, []).extend(rule.get("gate_b_sources") or [])
    return {key: sorted(set(values)) for key, values in batches.items()}


def _write_golden_sprint1() -> None:
    samples = [
        {
            "drug_name": "YONDELIS 1 MG (TRABECTEDIN)",
            "primary_icd10": "C49.9",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.14.C.trabectedin_sarcoma_board",
        },
        {
            "drug_name": "YONDELIS 1 MG (TRABECTEDIN)",
            "primary_icd10": "C49.9",
            "report_present": True,
            "expect_violation": None,
            "rule_id": "4.2.14.C.trabectedin_sarcoma_board",
        },
        {
            "drug_name": "TRODELVY 200 MG (SACITUZUMAB GOVITEKAN)",
            "primary_icd10": "C50.9",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.14.C.sacituzumab_govitecan_tnbc_board",
        },
        {
            "drug_name": "VIDAZA 100 MG (AZASITIDIN)",
            "primary_icd10": "D46.9",
            "report_present": True,
            "expect_violation": "report_duration_mismatch",
            "drug_report_duration_months": 3,
            "rule_id": "4.2.14.C.azacitidine_mds_4mo_heme",
        },
    ]
    _GOLDEN_S1_PATH.parent.mkdir(parents=True, exist_ok=True)
    _GOLDEN_S1_PATH.write_text(
        json.dumps({"samples": samples}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    existing = _load_rules()
    merged, added, patched, covered = merge_sprint1(existing)
    missing = sorted(PENDING_CLAUSE_IDS - covered)
    if missing:
        raise RuntimeError(f"Sprint 1 merge did not cover pending clause IDs: {missing}")

    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    payload["title"] = "SUT §4.2 drug indication and report requirements (4.2.14.C Sprint 1)"
    payload["coverage_note"] = (
        f"Sprint 1 — {len(merged)} rules for §4.2.14.C; Tier A/B pending manifest clauses encoded."
    )
    payload["rules"] = merged
    _RULES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    write_gate_b_export(_CLAUSES_PATH, _CORPUS_CSV, rules_path=_RULES_PATH)
    gate_b_frame = export_4_2_14_c_candidates(_CLAUSES_PATH, rules_path=_RULES_PATH)

    manifest = build_phase5_manifest(
        gate_b_frame=gate_b_frame,
        rules=merged,
        phase1_added=added,
        phase2_added=0,
        batch_clause_ids=_batch_clause_ids(merged),
        gate_b_summary_payload=gate_b_summary(gate_b_frame),
        effective_date=date.today().isoformat(),
    )
    _MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_golden_sprint1()

    print(f"Sprint 1 merged: added={added} patched={patched} total_rules={len(merged)}")
    print(
        f"  manifest encoded={manifest['encoded_clause_count']} "
        f"tier_a_pending={manifest['tier_a_pending_count']} "
        f"tier_b_pending={manifest['tier_b_pending_count']}"
    )
    print(f"Wrote rules -> {_RULES_PATH}")
    print(f"Wrote manifest -> {_MANIFEST_PATH}")
    print(f"Wrote golden -> {_GOLDEN_S1_PATH}")


if __name__ == "__main__":
    main()

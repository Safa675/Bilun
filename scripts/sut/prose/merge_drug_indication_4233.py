#!/usr/bin/env python3
"""Merge §4.2.33 A2c pilot rules into anti_vegf_prose.json + manifest."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

from scripts.sut.prose.drug_indication_4233_batch_rules import (
    BATCH_A2C_RULES,
    SOURCE_PATCHES,
)
from scripts.sut.prose.drug_indication_gate_b import infer_defer_themes

_REPO = Path(__file__).resolve().parents[3]
_RULES_PATH = _REPO / "data/gazette/prose_rules/anti_vegf_prose.json"
_CLAUSES_PATH = _REPO / "data/gazette/sut_clauses.parquet"
_MANIFEST_PATH = _REPO / "data/gazette/prose_manifests/L4.33_anti_vegf_4.2.33_manifest.json"
_GOLDEN_PATH = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.33_a2c.json"


def _load_rules() -> list[dict]:
    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    return list(payload.get("rules") or [])


def merge_a2c_batch(existing: list[dict], batch: list[dict]) -> tuple[list[dict], int, set[str]]:
    by_id = {str(rule["rule_id"]): dict(rule) for rule in existing}
    added = 0
    covered: set[str] = set()

    for rule_id, clause_ids in SOURCE_PATCHES.items():
        if rule_id not in by_id:
            continue
        before = set(by_id[rule_id].get("gate_b_sources") or [])
        by_id[rule_id]["gate_b_sources"] = sorted(before | set(clause_ids))
        covered.update(clause_ids)

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


def _encoded_clause_ids(rules: list[dict]) -> set[str]:
    encoded: set[str] = set()
    for rule in rules:
        encoded.update(str(cid) for cid in (rule.get("gate_b_sources") or []))
    return encoded


def _build_manifest(
    *,
    rules: list[dict],
    clauses_path: Path,
    effective_date: str,
) -> dict[str, Any]:
    section = pl.read_parquet(clauses_path).filter(
        pl.col("section_id").str.starts_with("4.2.33") & pl.col("is_in_force")
    )
    encoded_ids = _encoded_clause_ids(rules)
    rules_by_clause: dict[str, list[str]] = {}
    for rule in rules:
        rid = str(rule.get("rule_id") or "")
        for cid in rule.get("gate_b_sources") or []:
            rules_by_clause.setdefault(str(cid), []).append(rid)

    clause_traces: dict[str, list[str]] = {}
    for rule in rules:
        rid = str(rule.get("rule_id") or "")
        clause_traces[rid] = sorted(str(c) for c in (rule.get("gate_b_sources") or []))

    tier_c_deferred: list[str] = []
    traces: list[dict[str, Any]] = []
    for row in section.sort("clause_id").iter_rows(named=True):
        clause_id = str(row["clause_id"])
        text = str(row.get("text_tr") or "")
        if clause_id in encoded_ids:
            status = "encoded"
        elif str(row.get("clause_type") or "") in {"section_heading", "chapter"} and not row.get(
            "deontic_modality"
        ):
            status = "non_actionable"
        else:
            status = "tier_c_deferred"
            tier_c_deferred.append(clause_id)

        entry: dict[str, Any] = {
            "clause_id": clause_id,
            "section_id": str(row.get("section_id") or ""),
            "manifest_status": status,
        }
        if status == "encoded":
            entry["linked_rule_ids"] = sorted(rules_by_clause.get(clause_id, []))
        elif status == "tier_c_deferred":
            themes = infer_defer_themes(text)
            entry["defer_themes"] = themes
            entry["defer_reason"] = (
                f"Deferred — dose pathway / combination rule not yet structurable "
                f"({', '.join(themes) if themes else 'clinical_pathway'})."
            )
        traces.append(entry)

    in_force_total = section.height
    traced_in_force = sum(1 for t in traces if t["manifest_status"] != "non_actionable")
    return {
        "manifest_version": "r5-a2c-v1",
        "section_id": "4.2.33",
        "effective_date": effective_date,
        "rule_set_id": "anti_vegf_prose",
        "rules_in_json": len(rules),
        "section_clause_total": in_force_total,
        "clause_trace_complete": len(
            {t["clause_id"] for t in traces}
            - {t["clause_id"] for t in traces if t["manifest_status"] == "non_actionable"}
        ) == len(encoded_ids | set(tier_c_deferred)),
        "manifest_coverage_pct": round(100.0 * len(encoded_ids) / in_force_total, 1)
        if in_force_total
        else 0.0,
        "encoded_clause_count": len(encoded_ids & set(section["clause_id"].to_list())),
        "encoded_clause_ids": sorted(encoded_ids & set(section["clause_id"].to_list())),
        "tier_c_deferred_clause_ids": sorted(tier_c_deferred),
        "tier_c_deferred_count": len(tier_c_deferred),
        "clause_traces": clause_traces,
        "clause_trace_rows": traces,
        "note": (
            f"§4.2.33 anti-VEGF A2c — {len(rules)} rules, {len(encoded_ids)} encoded "
            f"clause sources, {len(tier_c_deferred)} tier-C deferred in-force rows."
        ),
    }


def _write_golden() -> None:
    samples = [
        {
            "drug_name": "AVASTIN (BEVACIZUMAB)",
            "primary_icd10": "H35.3",
            "report_present": True,
            "report_duration_months": 3,
            "prescriber_specialty": "göz hastalıkları",
            "expect_violation": None,
            "rule_id": "4.2.33.A.bevacizumab_first_line_wet_amd",
        },
        {
            "drug_name": "AVASTIN (BEVACIZUMAB)",
            "primary_icd10": "H35.3",
            "report_present": False,
            "prescriber_specialty": "göz hastalıkları",
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.33.A.bevacizumab_first_line_wet_amd",
        },
        {
            "drug_name": "LUCENTIS (RANIBIZUMAB)",
            "primary_icd10": "H35.3",
            "report_present": True,
            "report_duration_months": 3,
            "prescriber_specialty": "göz hastalıkları",
            "annual_application_count": 3,
            "is_loading_phase": True,
            "expect_violation": None,
            "rule_id": "4.2.33.A.anti_vegf_switch_after_bevacizumab_failure",
        },
        {
            "drug_name": "AVASTIN (BEVACIZUMAB)",
            "primary_icd10": "E11.3",
            "report_present": True,
            "report_duration_months": 3,
            "prescriber_specialty": "göz hastalıkları",
            "annual_application_count": 3,
            "is_loading_phase": True,
            "expect_violation": None,
            "rule_id": "4.2.33.general_switch_to_bevacizumab",
        },
        {
            "drug_name": "RESTASIS (SIKLOSPORIN)",
            "primary_icd10": "H04.1",
            "report_present": True,
            "report_duration_months": 12,
            "prescriber_specialty": "göz hastalıkları",
            "expect_violation": None,
            "rule_id": "4.2.33.E.siklosporin_dry_eye_annual_report",
        },
        {
            "drug_name": "OZURDEX (DEKSAMETAZON)",
            "primary_icd10": "E11.3",
            "report_present": True,
            "prescriber_specialty": "göz hastalıkları",
            "annual_application_count": 3,
            "expect_violation": "annual_max_exceeded",
            "rule_id": "4.2.33.Ç.deksametazon_timing_after_anti_vegf",
        },
    ]
    _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _GOLDEN_PATH.write_text(
        json.dumps({"samples": samples}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    existing = _load_rules()
    merged, added, covered = merge_a2c_batch(existing, BATCH_A2C_RULES)

    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    payload["coverage_note"] = (
        f"R5 A2c — {len(merged)} §4.2.33 rules; anti-VEGF tail batch merged."
    )
    payload["rules"] = merged
    _RULES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    effective = date.today().isoformat()
    manifest = _build_manifest(
        rules=merged,
        clauses_path=_CLAUSES_PATH,
        effective_date=effective,
    )
    _MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_golden()

    print(f"A2c merged: added={added} total_rules={len(merged)} covered_sources={len(covered)}")
    print(
        f"  manifest encoded={manifest['encoded_clause_count']} "
        f"tier_c_deferred={manifest['tier_c_deferred_count']}"
    )
    print(f"Wrote rules -> {_RULES_PATH}")
    print(f"Wrote manifest -> {_MANIFEST_PATH}")
    print(f"Wrote golden -> {_GOLDEN_PATH}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Remap §4.2.13 Tier B oral-switch gate_b_sources to in-force clause IDs + regen manifest."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.drug_indication_4213_gate_b import (  # noqa: E402
    gate_b_summary,
    write_gate_b_artifacts,
)
from scripts.sut.prose.drug_indication_4213_tier_b_batch_rules import (  # noqa: E402
    BATCH_4213_TIER_B_RULES,
)

_REPO = _PROJECT_ROOT
_RULES_PATH = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_CLAUSES_PATH = _REPO / "data/gazette/sut_clauses.parquet"
_CORPUS_CSV = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4213.csv"
_MANIFEST_PATH = _REPO / "data/gazette/prose_manifests/L4.2_drug_indication_4213_4216_manifest.json"
_GOLDEN_PATH = _REPO / "data/gazette/prose_rules/golden/drug_indication_4.2.13_tier_b.json"

_ORAL_SWITCH_RULE_IDS = frozenset(
    {
        "4.2.13.hbv_oral_antiviral_switch_adult_report",
        "4.2.13.hbv_oral_antiviral_switch_pediatric_report",
    }
)
_IN_FORCE_ORAL_SWITCH_SOURCES = frozenset({"C004584", "C004593"})


def _load_rules() -> list[dict]:
    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    return list(payload.get("rules") or [])


def remap_tier_b_oral_switch(existing: list[dict]) -> tuple[list[dict], int]:
    """Replace oral-switch gate_b_sources with in-force IDs; sync other Tier B fields."""
    by_id = {str(rule["rule_id"]): dict(rule) for rule in existing}
    updated = 0
    for raw in BATCH_4213_TIER_B_RULES:
        clean = {k: v for k, v in raw.items() if k != "encode_batch"}
        rule_id = str(clean["rule_id"])
        if rule_id not in by_id:
            continue
        if rule_id in _ORAL_SWITCH_RULE_IDS:
            before = set(by_id[rule_id].get("gate_b_sources") or [])
            after = set(clean.get("gate_b_sources") or [])
            if before != after:
                by_id[rule_id] = {**by_id[rule_id], **clean}
                updated += 1
    merged = sorted(by_id.values(), key=lambda r: str(r.get("rule_id", "")))
    return merged, updated


def _write_golden() -> None:
    samples = [
        {
            "drug_name": "BARACLUDE 0.5 MG (ENTEKAVIR)",
            "primary_icd10": "B18.1",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.13.hbv_oral_antiviral_switch_adult_report",
            "gate_b_source": "C004584",
        },
        {
            "drug_name": "BARACLUDE 0.5 MG (ENTEKAVIR)",
            "primary_icd10": "B18.1",
            "report_present": True,
            "expect_violation": None,
            "rule_id": "4.2.13.hbv_oral_antiviral_switch_adult_report",
            "gate_b_source": "C004584",
        },
        {
            "drug_name": "VIREAD 245 MG (TENOFOVIR)",
            "primary_icd10": "B18.0",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.13.hbv_oral_antiviral_switch_adult_report",
            "gate_b_source": "C004584",
        },
        {
            "drug_name": "ZEFFIX 100 MG (LAMIVUDIN)",
            "primary_icd10": "B18.2",
            "report_present": True,
            "expect_violation": "indication_mismatch",
            "rule_id": "4.2.13.hbv_oral_antiviral_switch_adult_report",
            "gate_b_source": "C004584",
        },
        {
            "drug_name": "BARACLUDE 0.5 MG (ENTEKAVIR)",
            "primary_icd10": "B18.1",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.13.hbv_oral_antiviral_switch_pediatric_report",
            "gate_b_source": "C004593",
        },
        {
            "drug_name": "BARACLUDE 0.5 MG (ENTEKAVIR)",
            "primary_icd10": "B18.1",
            "report_present": True,
            "expect_violation": None,
            "rule_id": "4.2.13.hbv_oral_antiviral_switch_pediatric_report",
            "gate_b_source": "C004593",
        },
        {
            "drug_name": "VIREAD 245 MG (TENOFOVIR)",
            "primary_icd10": "B18.0",
            "report_present": False,
            "expect_violation": "missing_board_report",
            "rule_id": "4.2.13.hbv_oral_antiviral_switch_pediatric_report",
            "gate_b_source": "C004593",
        },
    ]
    _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _GOLDEN_PATH.write_text(
        json.dumps({"samples": samples}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    before_manifest: dict | None = None
    if _MANIFEST_PATH.is_file():
        before_manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))

    existing = _load_rules()
    merged, updated = remap_tier_b_oral_switch(existing)

    payload = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    payload["coverage_note"] = (
        f"R5 TierB remap — {len(merged)} rules; §4.2.13 oral-switch sources "
        f"remapped to in-force C004584/C004593."
    )
    payload["rules"] = merged
    _RULES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    effective = date.today().isoformat()
    frame, manifest_4213, shared = write_gate_b_artifacts(
        clauses_path=_CLAUSES_PATH,
        rules_path=_RULES_PATH,
        corpus_csv=_CORPUS_CSV,
        shared_manifest_path=_MANIFEST_PATH,
        effective_date=effective,
    )
    _write_golden()

    oral_switch_sources = {
        clause_id
        for rule in BATCH_4213_TIER_B_RULES
        if str(rule["rule_id"]) in _ORAL_SWITCH_RULE_IDS
        for clause_id in (rule.get("gate_b_sources") or [])
    }
    encoded = set(manifest_4213["gate_b_sources_encoded"])

    tier_b_before = (before_manifest or {}).get("tier_b_pending_count", "?")
    print(
        f"TierB remap: rules_updated={updated} "
        f"tier_b_pending {tier_b_before} -> {manifest_4213['tier_b_pending_count']}"
    )
    print(
        f"  §4.2.13 encoded={manifest_4213['encoded_clause_count']} "
        f"shared_encoded={shared['encoded_clause_count']} "
        f"tier_c={manifest_4213['tier_c_deferred_count']}"
    )
    print(
        f"  oral_switch_sources={sorted(oral_switch_sources)} "
        f"covered={oral_switch_sources <= encoded}"
    )
    print(f"Wrote prose -> {_RULES_PATH}")
    print(f"Wrote manifest -> {_MANIFEST_PATH}")
    print(f"Wrote corpus -> {_CORPUS_CSV}")
    print(f"Wrote golden -> {_GOLDEN_PATH}")
    for key, value in sorted(gate_b_summary(frame).items()):
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

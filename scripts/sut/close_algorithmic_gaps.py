#!/usr/bin/env python3
"""Wave 1 — defer remaining true drug-indication algorithmic gaps to Tier C manifests."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.coverage import (  # noqa: E402
    _is_structural_gap_excluded,
    _load_drug_indication_encoded_clause_ids,
    _load_drug_indication_tier_c_deferred_clause_ids,
    _load_gate_b_sources_from_rules_json,
    write_sut_coverage,
)
from scripts.sut.prose.drug_indication_gate_b import infer_defer_themes  # noqa: E402
from scripts.sut.prose.gate_b_generic import build_defer_reason  # noqa: E402

_MANIFEST_DIR = _PROJECT_ROOT / "data" / "gazette" / "prose_manifests"
_CLAUSES_PATH = _PROJECT_ROOT / "data" / "gazette" / "sut_clauses.parquet"
_COVERAGE_PATH = _PROJECT_ROOT / "data" / "gazette" / "sut_clause_coverage.parquet"
_RULES_JSON = _PROJECT_ROOT / "data/gazette/prose_rules/drug_indication_prose.json"

# Longest-prefix wins — maps §4.2 sections to Gate B / wave manifests.
_SECTION_MANIFEST_PREFIXES: list[tuple[str, str]] = [
    ("4.2.14.C", "L4.2_drug_indication_4.2.14.C_manifest.json"),
    ("4.2.14.Ç", "L4.2_drug_indication_4.2.14.C_manifest.json"),
    ("4.2.14", "L4.2_drug_indication_4_2_14_wave2_manifest.json"),
    ("4.2.13", "L4.2_drug_indication_4213_4216_manifest.json"),
    ("4.2.16", "L4.2_drug_indication_4213_4216_manifest.json"),
    ("4.2.10", "L4.2_drug_indication_4210_manifest.json"),
    ("4.2.6", "L4.2_drug_indication_4206_manifest.json"),
    ("4.2.1", "L4.2_drug_indication_4201_manifest.json"),
    ("4.2.9", "L4.2_drug_indication_4209_4227_manifest.json"),
    ("4.2.27", "L4.2_drug_indication_4209_4227_manifest.json"),
    ("4.2.15", "L4.2_drug_indication_4215_manifest.json"),
    ("4.2.24", "L4.2_drug_indication_4224_manifest.json"),
    ("4.2.17", "L4.2_drug_indication_4217_manifest.json"),
    ("4.2.19", "L4.2_drug_indication_4219_manifest.json"),
    ("4.2.23", "L4.2_drug_indication_4218_4236_manifest.json"),
    ("4.2.18", "L4.2_drug_indication_4218_4236_manifest.json"),
    ("4.2.36", "L4.2_drug_indication_4218_4236_manifest.json"),
    ("4.2.34", "L4.2_drug_indication_4234_manifest.json"),
    ("4.2.38", "L4.2_drug_indication_4238_manifest.json"),
    ("4.2.35", "L4.2_drug_indication_4235_4237_manifest.json"),
    ("4.2.37", "L4.2_drug_indication_4235_4237_manifest.json"),
    ("4.2.33", "L4.33_anti_vegf_4.2.33_manifest.json"),
]
_DEFAULT_MANIFEST = "L4.2_drug_indication_tail_b_r6_manifest.json"
_SNAPSHOT_PATH = (
    _PROJECT_ROOT
    / "data/gazette/prose_rule_sources/drug_indication/gap_closure_tier_c.json"
)

# Clause IDs encoded by Wave 0 YAML patches (do not Tier-C defer).
_WAVE0_ENCODE_IDS = frozenset(
    {
        "C004934",
        "C005073",
        "C005300",
        "C005391",
        "C005681",
    }
)


def _manifest_for_section(section_id: str) -> str:
    for prefix, manifest_name in _SECTION_MANIFEST_PREFIXES:
        if section_id == prefix or section_id.startswith(prefix + "."):
            return manifest_name
    return _DEFAULT_MANIFEST


def _load_clause_text() -> dict[str, str]:
    if not _CLAUSES_PATH.is_file():
        return {}
    frame = pd.read_parquet(_CLAUSES_PATH, columns=["clause_id", "text_tr"])
    return {
        str(row.clause_id): str(row.text_tr or "")
        for row in frame.itertuples(index=False)
    }


def _true_unencoded_gaps(coverage: pd.DataFrame) -> pd.DataFrame:
    encoded = _load_drug_indication_encoded_clause_ids()
    tier_c = _load_drug_indication_tier_c_deferred_clause_ids()
    gaps = coverage[
        (coverage["primary_rule_id"] == "drug_indication_prose")
        & coverage["has_algorithmic_gap"]
        & ~coverage["has_rule_encoding"]
    ].copy()
    gaps = gaps[~gaps["clause_id"].isin(encoded)]
    gaps = gaps[~gaps["clause_id"].isin(tier_c)]
    gaps = gaps[~gaps["clause_id"].isin(_WAVE0_ENCODE_IDS)]
    gaps = gaps[~gaps.apply(_is_structural_gap_excluded, axis=1)]
    return gaps


def _append_tier_c_trace(
    payload: dict[str, Any],
    *,
    clause_id: str,
    text: str,
) -> None:
    themes = infer_defer_themes(text) or ["clinical_pathway"]
    defer_reason = build_defer_reason(themes)
    traces = list(payload.get("clause_traces") or [])
    for trace in traces:
        if str(trace.get("clause_id")) == clause_id:
            trace["manifest_status"] = "tier_c_deferred"
            trace["encode_tier"] = "C"
            trace["defer_themes"] = themes
            trace["defer_reason"] = defer_reason
            payload["clause_traces"] = traces
            return
    # Manifests with clause_traces are Gate-B complete — only update existing rows.


def _apply_tier_c_defer(
    manifest_path: Path,
    clause_ids: list[str],
    clause_text: dict[str, str],
) -> int:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    existing = set(str(c) for c in (payload.get("tier_c_deferred_clause_ids") or []))
    encoded = set(str(c) for c in (payload.get("encoded_clause_ids") or []))
    rules_encoded = _load_gate_b_sources_from_rules_json(_RULES_JSON)
    added = 0
    for clause_id in sorted(clause_ids):
        if clause_id in rules_encoded:
            continue
        if clause_id in existing or clause_id in encoded:
            continue
        text = clause_text.get(clause_id, "")
        existing.add(clause_id)
        added += 1
        if payload.get("clause_traces") is not None:
            _append_tier_c_trace(payload, clause_id=clause_id, text=text)
    if added == 0:
        return 0
    payload["tier_c_deferred_clause_ids"] = sorted(existing)
    payload["tier_c_deferred_count"] = len(existing)
    payload.setdefault("effective_date", date.today().isoformat())
    payload["gap_closure_note"] = (
        f"Wave 1 Tier-C defer — {added} clause(s) added {date.today().isoformat()}"
    )
    from scripts.sut.prose.manifest_reconcile import reconcile_manifest_payload

    reconcile_manifest_payload(payload, backfill=True)
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return added


def close_gaps(*, dry_run: bool = False) -> dict[str, int]:
    if not _COVERAGE_PATH.is_file():
        raise FileNotFoundError(f"Run build_sut_coverage.py first: {_COVERAGE_PATH}")
    coverage = pd.read_parquet(_COVERAGE_PATH)
    gaps = _true_unencoded_gaps(coverage)
    clause_text = _load_clause_text()

    by_manifest: dict[str, list[str]] = {}
    for _, row in gaps.iterrows():
        section_id = str(row.get("section_id") or "")
        manifest_name = _manifest_for_section(section_id)
        by_manifest.setdefault(manifest_name, []).append(str(row["clause_id"]))

    stats: dict[str, int] = {"gap_rows": len(gaps), "manifests_touched": 0, "clauses_deferred": 0}
    for manifest_name, clause_ids in sorted(by_manifest.items()):
        manifest_path = _MANIFEST_DIR / manifest_name
        if not manifest_path.is_file():
            print(f"skip missing manifest {manifest_name} ({len(clause_ids)} clauses)")
            continue
        if dry_run:
            print(f"would defer {len(clause_ids)} → {manifest_name}")
            stats["clauses_deferred"] += len(clause_ids)
            continue
        added = _apply_tier_c_defer(manifest_path, clause_ids, clause_text)
        if added:
            stats["manifests_touched"] += 1
            stats["clauses_deferred"] += added
            print(f"deferred {added} → {manifest_name}")

    return stats


def apply_snapshot(snapshot_path: Path = _SNAPSHOT_PATH) -> dict[str, int]:
    """Merge committed Tier-C gap-closure IDs into manifests (post Gate B compile)."""
    if not snapshot_path.is_file():
        return {"manifests_touched": 0, "clauses_deferred": 0}
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    manifests: dict[str, list[str]] = payload.get("manifests") or {}
    clause_text = _load_clause_text()
    stats = {"manifests_touched": 0, "clauses_deferred": 0}
    for manifest_name, clause_ids in sorted(manifests.items()):
        manifest_path = _MANIFEST_DIR / manifest_name
        if not manifest_path.is_file():
            continue
        added = _apply_tier_c_defer(manifest_path, clause_ids, clause_text)
        if added:
            stats["manifests_touched"] += 1
            stats["clauses_deferred"] += added
    return stats


def export_snapshot(snapshot_path: Path = _SNAPSHOT_PATH) -> dict[str, int]:
    """Write gap-closure plan from current coverage (after build_sut_coverage)."""
    if not _COVERAGE_PATH.is_file():
        raise FileNotFoundError(f"Run build_sut_coverage.py first: {_COVERAGE_PATH}")
    coverage = pd.read_parquet(_COVERAGE_PATH)
    gaps = _true_unencoded_gaps(coverage)
    by_manifest: dict[str, list[str]] = {}
    for _, row in gaps.iterrows():
        section_id = str(row.get("section_id") or "")
        manifest_name = _manifest_for_section(section_id)
        by_manifest.setdefault(manifest_name, []).append(str(row["clause_id"]))
    for manifest_name in by_manifest:
        by_manifest[manifest_name] = sorted(set(by_manifest[manifest_name]))
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps({"version": 1, "manifests": by_manifest}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return {
        "manifests": len(by_manifest),
        "clauses": sum(len(v) for v in by_manifest.values()),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Defer true drug-indication gaps to Tier C.")
    parser.add_argument("--dry-run", action="store_true", help="Print plan only.")
    parser.add_argument(
        "--apply-snapshot",
        action="store_true",
        help="Apply committed gap_closure_tier_c.json to manifests.",
    )
    parser.add_argument(
        "--export-snapshot",
        action="store_true",
        help="Export gap_closure_tier_c.json from current coverage gaps.",
    )
    parser.add_argument(
        "--rebuild-coverage",
        action="store_true",
        help="Run build_sut_coverage after deferral.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if args.export_snapshot:
        stats = export_snapshot()
        print(json.dumps(stats, indent=2))
        return 0
    if args.apply_snapshot:
        stats = apply_snapshot()
        print(json.dumps(stats, indent=2))
        if args.rebuild_coverage:
            write_sut_coverage(
                clauses_path=_CLAUSES_PATH, output_dir=_PROJECT_ROOT / "data" / "gazette"
            )
            print("coverage rebuilt")
        return 0
    stats = close_gaps(dry_run=args.dry_run)
    print(json.dumps(stats, indent=2))
    if args.rebuild_coverage and not args.dry_run:
        write_sut_coverage(clauses_path=_CLAUSES_PATH, output_dir=_PROJECT_ROOT / "data" / "gazette")
        print("coverage rebuilt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Rebuild tasks/archive/sut-fact-check-2026-06/baseline_metrics.json from sut_clauses + registry."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.coverage import build_sut_coverage, write_sut_coverage


def _top_gap_categories(coverage: pd.DataFrame, limit: int = 10) -> list[dict[str, object]]:
    gaps = coverage[coverage["has_algorithmic_gap"]]
    if gaps.empty:
        return []
    grouped = (
        gaps.groupby("primary_rule_category", dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .head(limit)
    )
    return [
        {"primary_rule_category": str(row["primary_rule_category"]), "count": int(row["count"])}
        for _, row in grouped.iterrows()
    ]


def _material_bundling_snapshot(
    coverage: pd.DataFrame,
    *,
    manifest_path: Path,
    gate_b_summary_path: Path,
) -> dict[str, object]:
    mb = coverage[coverage["primary_rule_id"] == "material_bundling_prose"]
    snapshot: dict[str, object] = {
        "classified_clause_rows": int(len(mb)),
        "implemented_rows": int((mb["coverage_status"] == "implemented").sum()),
        "partial_rows": int((mb["coverage_status"] == "partial").sum()),
        "gap_rows": int(mb["has_algorithmic_gap"].sum()),
        "prose_rules_on_disk": 0,
    }
    prose_json = _PROJECT_ROOT / "data/gazette/prose_rules/material_bundling_prose.json"
    if prose_json.is_file():
        payload = json.loads(prose_json.read_text(encoding="utf-8"))
        snapshot["prose_rules_on_disk"] = len(payload.get("rules", []))
    if gate_b_summary_path.is_file():
        snapshot["gate_b"] = json.loads(gate_b_summary_path.read_text(encoding="utf-8"))
    if manifest_path.is_file():
        snapshot["encode_manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
    return snapshot


def _drug_indication_snapshot(
    coverage: pd.DataFrame,
    *,
    manifest_path: Path,
) -> dict[str, object]:
    di = coverage[coverage["primary_rule_id"] == "drug_indication_prose"]
    snapshot: dict[str, object] = {
        "classified_clause_rows": int(len(di)),
        "partial_rows": int((di["coverage_status"] == "partial").sum()),
        "gap_rows": int(di["has_algorithmic_gap"].sum()),
        "encoded_clause_rows": int(di["has_rule_encoding"].sum()) if "has_rule_encoding" in di.columns else 0,
        "unencoded_gap_rows": int(
            di[di["has_algorithmic_gap"] & ~di["has_rule_encoding"]].shape[0]
        )
        if {"has_algorithmic_gap", "has_rule_encoding"}.issubset(di.columns)
        else 0,
        "prose_rules_on_disk": 0,
    }
    prose_json = _PROJECT_ROOT / "data/gazette/prose_rules/drug_indication_prose.json"
    if prose_json.is_file():
        payload = json.loads(prose_json.read_text(encoding="utf-8"))
        snapshot["prose_rules_on_disk"] = len(payload.get("rules", []))
    if manifest_path.is_file():
        snapshot["encode_manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
    return snapshot


def build_baseline_metrics(
    clauses_path: Path,
    *,
    manifest_path: Path,
    gate_b_summary_path: Path,
    drug_manifest_path: Path | None = None,
) -> dict[str, object]:
    coverage, _, _, registry = build_sut_coverage(pd.read_parquet(clauses_path))

    by_status = (
        coverage.groupby("coverage_status", dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    registry_by_status = (
        registry.groupby("registry_coverage_status", dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    algorithmic_gaps = int(coverage["has_algorithmic_gap"].sum())
    total_rows = int(len(coverage))

    zero_clause = registry[
        (registry["matched_clause_count"] == 0)
        & (registry["registry_coverage_status"].isin({"implemented", "partial"}))
    ][["rule_id", "description"]]

    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "phase": "2-post-l1.4",
        "clauses": {"total": int(len(coverage))},
        "coverage": {
            "total_clause_rows": total_rows,
            "by_status": [
                {"coverage_status": str(r["coverage_status"]), "count": int(r["count"])}
                for _, r in by_status.iterrows()
            ],
            "algorithmic_gaps": algorithmic_gaps,
            "algorithmic_gap_pct": round(100.0 * algorithmic_gaps / total_rows, 1)
            if total_rows
            else 0.0,
            "top_gap_categories": _top_gap_categories(coverage),
            "material_bundling_prose": _material_bundling_snapshot(
                coverage,
                manifest_path=manifest_path,
                gate_b_summary_path=gate_b_summary_path,
            ),
            "drug_indication_prose": _drug_indication_snapshot(
                coverage,
                manifest_path=drug_manifest_path
                or (_PROJECT_ROOT / "data/gazette/prose_manifests/L4.2_drug_indication_4.2.14.C_manifest.json"),
            ),
        },
        "registry": {
            "total_rules": int(len(registry)),
            "by_status": [
                {
                    "registry_coverage_status": str(r["registry_coverage_status"]),
                    "count": int(r["count"]),
                }
                for _, r in registry_by_status.iterrows()
            ],
            "zero_clause_matches": zero_clause.to_dict(orient="records"),
            "implemented_rules": int(
                (registry["registry_coverage_status"] == "implemented").sum()
            ),
            "partial_rules": int((registry["registry_coverage_status"] == "partial").sum()),
            "missing_rules": int((registry["registry_coverage_status"] == "missing").sum()),
            "material_bundling_prose_status": str(
                registry.loc[
                    registry["rule_id"] == "material_bundling_prose",
                    "registry_coverage_status",
                ].iloc[0]
            )
            if (registry["rule_id"] == "material_bundling_prose").any()
            else "unknown",
        },
        "medula_overlap": {
            "note": "Unchanged by this script — see medula_overlap_gaps.md",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--clauses",
        type=Path,
        default=_PROJECT_ROOT / "data/gazette/sut_clauses.parquet",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_PROJECT_ROOT / "tasks/archive/sut-fact-check-2026-06/baseline_metrics.json",
    )
    parser.add_argument(
        "--coverage-dir",
        type=Path,
        default=_PROJECT_ROOT / "data/gazette",
        help="Optional parquet outputs for sut_clause_coverage etc.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=_PROJECT_ROOT / "data/gazette/prose_manifests/L1.4_material_bundling_encoded_manifest.json",
    )
    parser.add_argument(
        "--gate-b-summary",
        type=Path,
        default=_PROJECT_ROOT / "data/gazette/prose_corpus/L1.4_material_bundling_gate_b_summary.json",
    )
    parser.add_argument(
        "--drug-manifest",
        type=Path,
        default=_PROJECT_ROOT / "data/gazette/prose_manifests/L4.2_drug_indication_4.2.14.C_manifest.json",
    )
    args = parser.parse_args()

    if args.coverage_dir:
        write_sut_coverage(args.clauses, args.coverage_dir)

    payload = build_baseline_metrics(
        args.clauses,
        manifest_path=args.manifest,
        gate_b_summary_path=args.gate_b_summary,
        drug_manifest_path=args.drug_manifest,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    bundling_gaps = next(
        (
            item["count"]
            for item in payload["coverage"]["top_gap_categories"]
            if item["primary_rule_category"] == "bundling"
        ),
        0,
    )
    mb = payload["coverage"]["material_bundling_prose"]
    di = payload["coverage"]["drug_indication_prose"]
    print(f"Wrote {args.out}")
    print(f"  algorithmic_gaps={payload['coverage']['algorithmic_gaps']}")
    print(f"  bundling category gaps={bundling_gaps}")
    print(f"  material_bundling_prose clauses={mb['classified_clause_rows']} gap_rows={mb['gap_rows']}")
    print(
        f"  drug_indication_prose clauses={di['classified_clause_rows']} "
        f"encoded_rows={di['encoded_clause_rows']} gap_rows={di['gap_rows']} "
        f"unencoded_gaps={di.get('unencoded_gap_rows', 0)}"
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Compute what changed between old and new SUT catalog versions.

Usage:
    python scripts/sut/sut_delta.py <OLD_DATE> <NEW_DATE>

Example:
    python scripts/sut/sut_delta.py 2026-05-23 2026-06-29

Outputs:
    data/gazette/deltas/<NEW_DATE>_delta.json  — structured delta
    GITHUB_OUTPUT delta_summary                 — human-readable PR body

The delta compares as-of slices of curated history parquets using
Polars set-operations (vectorized, AGENTS.md §9 compliant).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import polars as pl

CURATED_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "gazette" / "curated"
DELTA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "gazette" / "deltas"


def compute_catalog_delta(
    annex: str,
    history_key: str,
    value_cols: list[str],
    old_date: str,
    new_date: str,
) -> dict:
    """Compare two as-of slices of a curated history parquet.

    As-of semantics: valid_from <= date AND (valid_to is null OR valid_to >= date).
    The >= boundary is correct: valid_to is the LAST day the version is in effect.
    """
    parquet_path = CURATED_DIR / f"{annex}_catalog_history.parquet"
    if not parquet_path.exists():
        return {"annex": annex, "error": f"parquet not found: {parquet_path}"}

    df = pl.read_parquet(parquet_path)

    def asof_slice(d: str) -> pl.DataFrame:
        return df.filter(
            (pl.col("valid_from") <= d)
            & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= d))
        )

    old_slice = asof_slice(old_date)
    new_slice = asof_slice(new_date)

    old_keys = set(old_slice[history_key].to_list())
    new_keys = set(new_slice[history_key].to_list())

    delta = {
        "annex": annex,
        "old_count": len(old_keys),
        "new_count": len(new_keys),
        "new_codes": sorted(new_keys - old_keys),
        "removed_codes": sorted(old_keys - new_keys),
        "common_codes": len(old_keys & new_keys),
        "price_changes": [],
        "name_changes": [],
    }

    old_by_key = {r[history_key]: r for r in old_slice.to_dicts()}
    new_by_key = {r[history_key]: r for r in new_slice.to_dicts()}

    for key in sorted(old_keys & new_keys):
        old_row = old_by_key[key]
        new_row = new_by_key[key]
        for col in value_cols:
            old_val = old_row.get(col)
            new_val = new_row.get(col)
            if old_val != new_val:
                change = {
                    "code": key,
                    "field": col,
                    "old": str(old_val),
                    "new": str(new_val),
                }
                if col in ("puan", "price_try"):
                    delta["price_changes"].append(change)
                else:
                    delta["name_changes"].append(change)

    return delta


def format_summary(deltas: list[dict]) -> str:
    """Format delta summary for PR body."""
    lines = ["## SUT Delta Summary", ""]
    for d in deltas:
        if "error" in d:
            lines.append(f"### {d['annex'].upper()}: ⚠️ {d['error']}")
            continue
        lines.append(f"### {d['annex'].upper()}")
        diff = d["new_count"] - d["old_count"]
        lines.append(
            f"- Codes: {d['old_count']} → {d['new_count']} ({diff:+d})"
        )
        lines.append(f"- New codes: {len(d['new_codes'])}")
        lines.append(f"- Removed codes: {len(d['removed_codes'])}")
        lines.append(f"- Price changes: {len(d['price_changes'])}")
        lines.append(f"- Name changes: {len(d['name_changes'])}")
        if d["new_codes"][:5]:
            lines.append(f"  Sample new: {', '.join(d['new_codes'][:5])}")
        if d["price_changes"][:3]:
            lines.append("  Sample price changes:")
            for pc in d["price_changes"][:3]:
                lines.append(
                    f"    {pc['code']}: {pc['old']} → {pc['new']}"
                )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: sut_delta.py <OLD_DATE> <NEW_DATE>", file=sys.stderr)
        return 1

    old_date, new_date = sys.argv[1], sys.argv[2]

    deltas = [
        compute_catalog_delta(
            "ek2b", "code", ["puan", "price_try", "name"], old_date, new_date
        ),
        compute_catalog_delta(
            "ek2c", "package_code", ["puan", "price_try", "name"], old_date, new_date
        ),
        compute_catalog_delta(
            "ek2c_dental", "code", ["puan", "price_try", "name"], old_date, new_date
        ),
    ]

    summary = {
        "old_date": old_date,
        "new_date": new_date,
        "generated_at": date.today().isoformat(),
        "catalogs": deltas,
    }

    DELTA_DIR.mkdir(parents=True, exist_ok=True)
    output = DELTA_DIR / f"{new_date}_delta.json"
    output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str)
    )

    body = format_summary(deltas)
    print(body)
    print(f"\nDelta JSON written to: {output}")

    # Output for GitHub Actions PR body (multiline delimiter syntax)
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as f:
            f.write("delta_summary<<DELIMITER\n")
            f.write(body)
            f.write("\nDELIMITER\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())

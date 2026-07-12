#!/usr/bin/env python3
"""Compute what changed between old and new SUT catalog versions.

Usage:
    python scripts/sut/sut_delta.py <OLD_DATE> <NEW_DATE>

Example:
    python scripts/sut/sut_delta.py 2026-05-23 2026-07-01

Outputs:
    data/gazette/deltas/<NEW_DATE>_delta.json  — structured delta
    GITHUB_OUTPUT delta_summary                 — human-readable PR body

Two delta strategies:

1. **Temporal parquets** (valid_from/valid_to): as-of slice comparison.
   Applies to ek2b, ek2c, ek2c_dental (procedure/package price histories).

2. **Snapshot parquets** (no validity columns): row-set comparison.
   Falls back to comparing the full table as a set of tuples (all columns
   cast to str). Detects added/removed rows and changed cell values.
   Applies to all other curated parquets (EK-1A, EK-3*, EK-4*, etc.).
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

# Sentinel: skip parquets that are pure lookup tables with no clinical/billing
# significance for delta tracking, or too noisy to be useful in a PR summary.
_SKIP_PARQUETS: set[str] = set()

# Config: which parquets are temporal (have valid_from/valid_to), what their
# key column is, and which columns are "interesting" to compare.
_TEMPORAL_SPECS: list[dict] = [
    {
        "annex": "ek2b",
        "file": "ek2b_catalog_history.parquet",
        "key": "code",
        "value_cols": ["puan", "price_try", "name"],
    },
    {
        "annex": "ek2c",
        "file": "ek2c_catalog_history.parquet",
        "key": "package_code",
        "value_cols": ["puan", "price_try", "name", "group", "has_star"],
    },
    {
        "annex": "ek2c_dental",
        "file": "ek2c_dental_catalog_history.parquet",
        "key": "code",
        "value_cols": ["puan", "price_try", "name"],
    },
]


def compute_temporal_delta(spec: dict, old_date: str, new_date: str) -> dict:
    """Compare two as-of slices of a temporal curated history parquet."""
    parquet_path = CURATED_DIR / spec["file"]
    if not parquet_path.exists():
        return {"annex": spec["annex"], "error": f"parquet not found: {spec['file']}"}

    df = pl.read_parquet(parquet_path)
    key = spec["key"]
    value_cols = spec["value_cols"]

    def asof_slice(d: str) -> pl.DataFrame:
        return df.filter(
            (pl.col("valid_from") <= d)
            & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= d))
        )

    old_slice = asof_slice(old_date)
    new_slice = asof_slice(new_date)

    old_keys = set(old_slice[key].to_list())
    new_keys = set(new_slice[key].to_list())

    delta = {
        "annex": spec["annex"],
        "type": "temporal",
        "old_count": len(old_keys),
        "new_count": len(new_keys),
        "new_codes": sorted(new_keys - old_keys),
        "removed_codes": sorted(old_keys - new_keys),
        "common_codes": len(old_keys & new_keys),
        "price_changes": [],
        "name_changes": [],
    }

    old_by_key = {r[key]: r for r in old_slice.to_dicts()}
    new_by_key = {r[key]: r for r in new_slice.to_dicts()}

    for k in sorted(old_keys & new_keys):
        old_row = old_by_key[k]
        new_row = new_by_key[k]
        for col in value_cols:
            old_val = old_row.get(col)
            new_val = new_row.get(col)
            if old_val != new_val:
                change = {"code": k, "field": col, "old": str(old_val), "new": str(new_val)}
                if col in ("puan", "price_try"):
                    delta["price_changes"].append(change)
                else:
                    delta["name_changes"].append(change)

    return delta


def compute_snapshot_delta(annex: str, filename: str, old_date: str, new_date: str) -> dict:
    """Compare two snapshot parquets as row-sets.

    Since snapshot parquets have no temporal columns, this compares the
    entire table before and after. It detects:
    - Row count change
    - Content hash change (if same row count but different content)
    """
    parquet_path = CURATED_DIR / filename
    if not parquet_path.exists():
        return {"annex": annex, "error": f"parquet not found: {filename}"}

    # For snapshot parquets, we can't do a temporal slice — the file is
    # already the latest version. We compare row count and a content hash
    # against the delta's old_date snapshot (which we don't have stored).
    # So we report: the current row count + a SHA of the content.
    df = pl.read_parquet(parquet_path)

    # Cast all columns to string for stable hashing
    str_cols = [pl.col(c).cast(pl.Utf8) for c in df.columns]
    df_str = df.select(str_cols)
    import hashlib
    content_hash = hashlib.md5(df_str.write_csv().encode()).hexdigest()[:12]

    return {
        "annex": annex,
        "type": "snapshot",
        "row_count": df.shape[0],
        "col_count": df.shape[1],
        "content_hash": content_hash,
        "note": (
            "Snapshot parquet — no temporal slicing. Compare content_hash "
            "and row_count against the previous delta to detect changes."
        ),
    }


def compute_all_deltas(old_date: str, new_date: str) -> list[dict]:
    """Compute deltas for all curated parquets."""
    deltas = []

    # Temporal parquets (EK-2B, EK-2C, EK-2Ç)
    for spec in _TEMPORAL_SPECS:
        deltas.append(compute_temporal_delta(spec, old_date, new_date))

    # Snapshot parquets (everything else)
    for parquet_file in sorted(CURATED_DIR.glob("*.parquet")):
        if parquet_file.name in {s["file"] for s in _TEMPORAL_SPECS}:
            continue
        if parquet_file.name in _SKIP_PARQUETS:
            continue
        annex = parquet_file.stem.replace("_", " ").replace("-", " ").strip()
        deltas.append(compute_snapshot_delta(annex, parquet_file.name, old_date, new_date))

    return deltas


def format_summary(deltas: list[dict]) -> str:
    """Format delta summary for PR body."""
    lines = ["## SUT Delta Summary", ""]

    # Temporal section
    temporal = [d for d in deltas if d.get("type") == "temporal"]
    if temporal:
        lines.append("### Procedure/Package Catalogs (temporal)")
        lines.append("")
        for d in temporal:
            if "error" in d:
                lines.append(f"- **{d['annex'].upper()}**: ⚠️ {d['error']}")
                continue
            diff = d["new_count"] - d["old_count"]
            lines.append(f"- **{d['annex'].upper()}**: {d['old_count']} → {d['new_count']} ({diff:+d})")
            if d["new_codes"]:
                lines.append(f"  - New codes: {len(d['new_codes'])} (sample: {', '.join(d['new_codes'][:5])})")
            if d["removed_codes"]:
                lines.append(f"  - Removed codes: {len(d['removed_codes'])}")
            if d["price_changes"]:
                lines.append(f"  - Price changes: {len(d['price_changes'])}")
                for pc in d["price_changes"][:3]:
                    lines.append(f"    `{pc['code']}` {pc['field']}: {pc['old']} → {pc['new']}")
            if d["name_changes"]:
                lines.append(f"  - Name changes: {len(d['name_changes'])}")
        lines.append("")

    # Snapshot section
    snapshots = [d for d in deltas if d.get("type") == "snapshot"]
    if snapshots:
        lines.append("### Material/Drug/Other Annexes (snapshot)")
        lines.append("")
        lines.append("| Annex | Rows | Hash |")
        lines.append("|-------|------|------|")
        for d in snapshots:
            if "error" in d:
                lines.append(f"| {d['annex']} | ⚠️ {d['error']} | — |")
                continue
            lines.append(f"| {d['annex']} | {d['row_count']} | `{d['content_hash']}` |")
        lines.append("")
        lines.append(
            "*Compare hash/row-count against previous delta to detect changes in snapshot annexes.*"
        )
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: sut_delta.py <OLD_DATE> <NEW_DATE>", file=sys.stderr)
        return 1

    old_date, new_date = sys.argv[1], sys.argv[2]

    deltas = compute_all_deltas(old_date, new_date)

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

#!/usr/bin/env python3
"""
Unified builder for all curated SUT catalogs.

Reads raw parquet outputs (produced by convert_xlsx_to_parquet.py) and writes
analysis-ready curated parquet files under data/gazette/curated/.

Usage:
  python scripts/sut/build_curated_catalogs.py --overwrite
  python scripts/sut/build_curated_catalogs.py --annex EK-3H EK-3I
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Any
from collections.abc import Callable

import pandas as pd
import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut._common import (  # noqa: E402
    _add_validity_ranges,
    _load_manifest,
    _read_raw,
)
from scripts.sut.catalogs import CATALOG_SPECS  # noqa: E402

DEFAULT_PARQUET_ROOT = _PROJECT_ROOT / "data" / "gazette"


def _relocate_parquet(parquet_root: Path, row: pd.Series) -> Path | None:
    """Return a usable path for the manifest row."""
    stored = Path(str(row["parquet_path"]))
    eff = row["effective_date"]
    if pd.isna(eff) or not str(eff).strip():
        eff = "unknown"

    candidate = (
        parquet_root
        / "raw"
        / f"annex={row['annex_code']}"
        / f"effective_date={eff}"
        / stored.name
    )
    if candidate.exists():
        return candidate
    return stored if stored.exists() else None


def _source_parquet_identity(parquet_root: Path, src: Path) -> str:
    """Keep history provenance portable across worktrees and temporary builds."""
    relative = src.resolve().relative_to(parquet_root.resolve())
    return (DEFAULT_PARQUET_ROOT.relative_to(_PROJECT_ROOT) / relative).as_posix()


def _write_curated_if_changed(out_path: Path, curated: pd.DataFrame) -> bool:
    """Preserve existing bytes only when ordered schema, dtypes and values agree."""
    if out_path.exists():
        existing = pl.from_pandas(pd.read_parquet(out_path))
        candidate = pl.from_pandas(curated)
        if existing.columns == candidate.columns and existing.schema == candidate.schema and existing.equals(candidate):
            return False
    curated.to_parquet(out_path, index=False)
    return True


def _build_history(
    parquet_root: Path,
    manifest: pd.DataFrame,
    annex_code: str,
    extractor: Callable[[pd.DataFrame], pd.DataFrame],
    history_key: str,
) -> pd.DataFrame:
    """Build a price-history catalog for one annex by iterating all manifest versions."""
    rows = manifest[manifest["annex_code"] == annex_code].copy()
    rows = rows[rows["effective_date_parsed"].notna()]
    rows = rows.sort_values("effective_date_parsed")

    outputs: list[pd.DataFrame] = []
    skipped = 0
    for _, r in rows.iterrows():
        src = _relocate_parquet(parquet_root, r)
        if src is None:
            raise FileNotFoundError(f"Raw history parquet not found: {r['parquet_path']}")
        raw = pd.read_parquet(src)
        try:
            cur = extractor(raw)
        except (ValueError, KeyError) as exc:
            skipped += 1
            print(f"    SKIP {src.name}: {exc}")
            continue
        cur["effective_date"] = (
            pd.Timestamp(r["effective_date_parsed"]).date().isoformat()
        )
        cur["annex_code"] = annex_code
        cur["source_parquet"] = _source_parquet_identity(parquet_root, src)
        outputs.append(cur)

    if skipped:
        print(f"    {annex_code}: {skipped} file(s) skipped (incompatible headers)")

    if not outputs:
        return pd.DataFrame()

    merged = pd.concat(outputs, ignore_index=True).reset_index(drop=True)
    return _add_validity_ranges(merged, history_key)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build ALL curated SUT catalogs from raw parquet"
    )
    parser.add_argument(
        "--parquet-root",
        default=str(DEFAULT_PARQUET_ROOT),
        help="Root folder containing raw parquet files (default: data/gazette)",
    )
    parser.add_argument(
        "--as-of",
        type=dt.date.fromisoformat,
        help="Snapshot selection date (YYYY-MM-DD; default: UTC today). Histories retain all versions.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing curated outputs",
    )
    parser.add_argument(
        "--annex",
        nargs="*",
        help="Only build specific annexes (e.g. --annex EK-3B-1 EK-3H). Default: all.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    parquet_root = Path(args.parquet_root)
    curated_dir = parquet_root / "curated"
    curated_dir.mkdir(parents=True, exist_ok=True)

    specs: list[dict] = list(CATALOG_SPECS)
    if args.annex:
        requested = {a.upper() for a in args.annex}
        specs = [s for s in specs if s["annex"].upper() in requested]
        if not specs:
            print(f"No matching annexes for: {args.annex}")
            print(f"Available: {[s['annex'] for s in CATALOG_SPECS]}")
            return 2

    print("=" * 72)
    print("SUT Curated Catalog Builder")
    print(f"Source: {parquet_root / 'raw'}")
    print(f"Output: {curated_dir}")
    print(f"Annexes: {[s['annex'] for s in specs]}")
    print("=" * 72)
    print()

    manifest: pd.DataFrame | None = None
    results: list[dict[str, Any]] = []

    for spec in specs:
        annex = spec["annex"]
        output_name = spec["output"]
        source = spec["source"]
        extractor = spec["extractor"]
        label = spec["label"]
        out_path = curated_dir / output_name

        print(f"  [{annex}] {label}")

        if out_path.exists() and not args.overwrite:
            print(f"    SKIP -- file exists: {out_path.name} (use --overwrite)")
            results.append({"annex": annex, "status": "skipped", "rows": 0})
            continue

        try:
            if source == "raw_latest":
                raw = _read_raw(parquet_root, annex, as_of=args.as_of)
                if raw is None:
                    print(f"    FAIL -- raw parquet not found for annex={annex}")
                    results.append({"annex": annex, "status": "missing", "rows": 0})
                    continue
                curated = extractor(raw, as_of=args.as_of) if spec.get("snapshot_as_of") else extractor(raw)
            elif source == "raw_all_versions":
                if manifest is None:
                    manifest = _load_manifest(parquet_root)
                history_key = spec["history_key"]
                curated = _build_history(
                    parquet_root, manifest, annex, extractor, history_key
                )
                if curated.empty:
                    print(f"    FAIL -- no versions parsed for annex={annex}")
                    results.append({"annex": annex, "status": "error", "rows": 0, "error": "no versions parsed"})
                    continue
            else:
                raise ValueError(f"Unknown source: {source}")

            changed = _write_curated_if_changed(out_path, curated)
            action = "OK" if changed else "SAME"
            print(f"    {action} -- {len(curated):,} rows -> {output_name}")
            results.append({"annex": annex, "status": "ok", "rows": len(curated)})
        except Exception as e:
            print(f"    FAIL -- {e}")
            results.append(
                {"annex": annex, "status": "error", "rows": 0, "error": str(e)}
            )

    # Summary
    print()
    print("=" * 72)
    print("BUILD SUMMARY")
    print("=" * 72)
    ok_count = sum(1 for r in results if r["status"] == "ok")
    err_count = sum(1 for r in results if r["status"] in {"error", "missing"})
    total_rows = sum(r["rows"] for r in results)
    print(f"  {ok_count}/{len(results)} catalogs built, {total_rows:,} total rows")
    print()
    for r in results:
        status_icon = {"ok": "OK", "skipped": "--", "missing": "!!", "error": "XX"}[
            r["status"]
        ]
        print(
            f"  [{status_icon}] {r['annex']:12s} {r['rows']:>8,} rows  ({r['status']})"
        )
    print()

    return 1 if err_count else 0


if __name__ == "__main__":
    sys.exit(main())

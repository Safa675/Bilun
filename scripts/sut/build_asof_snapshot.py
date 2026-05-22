#!/usr/bin/env python3
"""
Build as-of snapshot parquet files from raw SUT parquet history.

Input:
  data/gazette/version_manifest.parquet
  data/gazette/raw/annex=*/effective_date=*/*.parquet

Output:
  data/gazette/snapshots/asof_YYYY-MM-DD/*.parquet
  data/gazette/snapshots/asof_YYYY-MM-DD/snapshot_manifest.parquet

Rule:
  For each annex_code, pick the latest effective_date <= asof_date
  (optionally excluding mulga rows).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PARQUET_ROOT = PROJECT_ROOT / "data" / "gazette"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build SUT as-of snapshot parquet files"
    )
    parser.add_argument(
        "--parquet-root",
        default=str(DEFAULT_PARQUET_ROOT),
        help="Root folder containing raw parquet + version_manifest.parquet",
    )
    parser.add_argument(
        "--asof-date",
        required=True,
        help="As-of date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--include-mulga",
        action="store_true",
        help="Include MULGA files in candidate set",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing as-of snapshot directory",
    )
    return parser.parse_args()


def _load_manifest(manifest_path: Path) -> pd.DataFrame:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    manifest = pd.read_parquet(manifest_path)
    if manifest.empty:
        raise ValueError("Manifest is empty")

    required = {
        "annex_code",
        "effective_date",
        "parquet_path",
        "source_file",
        "is_mulga",
    }
    missing = required - set(manifest.columns)
    if missing:
        raise ValueError(f"Manifest missing required columns: {sorted(missing)}")

    manifest = manifest.copy()
    manifest["effective_date_parsed"] = pd.to_datetime(
        manifest["effective_date"], errors="coerce"
    )
    return manifest


def _select_asof_rows(
    manifest: pd.DataFrame,
    asof_date: pd.Timestamp,
    include_mulga: bool,
) -> pd.DataFrame:
    candidates = manifest.copy()
    if not include_mulga:
        candidates = candidates[~candidates["is_mulga"].fillna(False)]

    candidates = candidates[candidates["effective_date_parsed"].notna()]
    candidates = candidates[candidates["effective_date_parsed"] <= asof_date]
    if candidates.empty:
        return candidates

    candidates = candidates.sort_values(
        ["annex_code", "effective_date_parsed", "source_file"],
        ascending=[True, True, True],
    )
    selected = candidates.groupby("annex_code", as_index=False).tail(1)
    return selected.reset_index(drop=True)


def _compute_validity_table(manifest: pd.DataFrame) -> pd.DataFrame:
    rows = manifest[manifest["effective_date_parsed"].notna()][
        ["annex_code", "effective_date_parsed"]
    ].drop_duplicates()
    rows = rows.sort_values(["annex_code", "effective_date_parsed"]).reset_index(
        drop=True
    )
    rows["valid_from"] = rows["effective_date_parsed"].dt.date.astype(str)
    rows["next_effective"] = rows.groupby("annex_code")["effective_date_parsed"].shift(
        -1
    )
    rows["valid_to"] = (
        rows["next_effective"] - pd.to_timedelta(1, unit="D")
    ).dt.date.astype("string")
    rows.loc[rows["next_effective"].isna(), "valid_to"] = pd.NA
    return rows[["annex_code", "effective_date_parsed", "valid_from", "valid_to"]]


def main() -> None:
    args = parse_args()

    parquet_root = Path(args.parquet_root)
    asof_date = pd.to_datetime(args.asof_date, format="%Y-%m-%d", errors="raise")
    manifest_path = parquet_root / "version_manifest.parquet"

    manifest = _load_manifest(manifest_path)
    selected = _select_asof_rows(
        manifest=manifest,
        asof_date=asof_date,
        include_mulga=args.include_mulga,
    )
    if selected.empty:
        raise SystemExit(f"No eligible rows found for as-of date {args.asof_date}")

    validity = _compute_validity_table(manifest)
    selected = selected.merge(
        validity,
        on=["annex_code", "effective_date_parsed"],
        how="left",
    )

    snapshot_dir = parquet_root / "snapshots" / f"asof_{args.asof_date}"
    if snapshot_dir.exists() and not args.overwrite:
        raise FileExistsError(
            f"Snapshot directory already exists: {snapshot_dir}. Use --overwrite."
        )

    snapshot_dir.mkdir(parents=True, exist_ok=True)

    written_rows: list[dict[str, object]] = []
    for _, row in selected.iterrows():
        src = Path(str(row["parquet_path"]))
        if not src.exists():
            raise FileNotFoundError(f"Parquet listed in manifest does not exist: {src}")

        annex_code = str(row["annex_code"])
        out = snapshot_dir / f"{annex_code}.parquet"

        df = pd.read_parquet(src)
        df["__asof_date"] = args.asof_date
        df["__valid_from"] = row.get("valid_from")
        df["__valid_to"] = row.get("valid_to")
        df.to_parquet(out, index=False)

        written_rows.append(
            {
                "asof_date": args.asof_date,
                "annex_code": annex_code,
                "effective_date": row.get("effective_date"),
                "valid_from": row.get("valid_from"),
                "valid_to": row.get("valid_to"),
                "source_file": row.get("source_file"),
                "source_parquet": str(src),
                "snapshot_parquet": str(out),
                "row_count": len(df),
            }
        )

    snapshot_manifest = pd.DataFrame(written_rows).sort_values("annex_code")
    snapshot_manifest_path = snapshot_dir / "snapshot_manifest.parquet"
    snapshot_manifest.to_parquet(snapshot_manifest_path, index=False)

    print("=" * 72)
    print("SUT AS-OF SNAPSHOT COMPLETE")
    print("=" * 72)
    print(f"As-of date        : {args.asof_date}")
    print(f"Include mulga     : {args.include_mulga}")
    print(f"Annex files written: {len(snapshot_manifest)}")
    print(f"Snapshot dir      : {snapshot_dir}")
    print(f"Snapshot manifest : {snapshot_manifest_path}")


if __name__ == "__main__":
    main()

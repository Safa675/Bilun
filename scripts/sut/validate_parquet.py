#!/usr/bin/env python3
"""
Validate parquet outputs produced by convert_xlsx_to_parquet.py.

Checks:
- manifest existence and required columns
- parquet file existence
- metadata completeness in each parquet
- optional duplicate row-hash scan per parquet
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "gazette"
REQUIRED_MANIFEST_COLS = {
    "source_file",
    "annex_code",
    "annex_family",
    "sheet_name",
    "effective_date",
    "is_mulga",
    "row_count",
    "column_count",
    "parquet_path",
}
REQUIRED_METADATA_COLS = {
    "__annex_code",
    "__annex_family",
    "__effective_date",
    "__source_file",
    "__sheet_name",
    "__is_mulga",
    "__ingested_at",
    "__row_hash",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate SUT parquet outputs")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory containing sut parquet outputs",
    )
    parser.add_argument(
        "--check-row-hash",
        action="store_true",
        help="Check duplicate __row_hash within each parquet file",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    manifest_path = output_dir / "version_manifest.parquet"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    manifest = pd.read_parquet(manifest_path)
    missing_manifest_cols = REQUIRED_MANIFEST_COLS - set(manifest.columns)
    if missing_manifest_cols:
        raise ValueError(
            f"Manifest missing required columns: {sorted(missing_manifest_cols)}"
        )

    print("=" * 72)
    print("SUT Parquet Validation")
    print("=" * 72)
    print(f"Manifest path: {manifest_path}")
    print(f"Manifest rows: {len(manifest)}")

    missing_files: list[str] = []
    bad_metadata_files: list[str] = []
    row_count_mismatch: list[str] = []
    duplicate_hash_files: list[str] = []

    for idx, row in manifest.iterrows():
        parquet_path = Path(str(row["parquet_path"]))
        if not parquet_path.exists():
            missing_files.append(str(parquet_path))
            continue

        df = pd.read_parquet(parquet_path)

        missing_cols = REQUIRED_METADATA_COLS - set(df.columns)
        if missing_cols:
            bad_metadata_files.append(f"{parquet_path} missing {sorted(missing_cols)}")

        expected_rows = int(row["row_count"])
        if len(df) != expected_rows:
            row_count_mismatch.append(
                f"{parquet_path} expected={expected_rows} actual={len(df)}"
            )

        if args.check_row_hash and "__row_hash" in df.columns:
            dup_count = int(df["__row_hash"].duplicated().sum())
            if dup_count > 0:
                duplicate_hash_files.append(
                    f"{parquet_path} duplicate_hash_rows={dup_count}"
                )

        if (idx + 1) % 100 == 0:
            print(f"Validated {idx + 1}/{len(manifest)} files...")

    print("\nSummary")
    print(f"- Missing parquet files: {len(missing_files)}")
    print(f"- Metadata issues: {len(bad_metadata_files)}")
    print(f"- Row-count mismatches: {len(row_count_mismatch)}")
    print(f"- Duplicate hash files: {len(duplicate_hash_files)}")

    by_annex = manifest.groupby("annex_code", dropna=False).agg(
        files=("parquet_path", "count"),
        rows=("row_count", "sum"),
    )
    print("\nRows by annex_code (top 20)")
    print(by_annex.sort_values("rows", ascending=False).head(20).to_string())

    def print_examples(title: str, items: list[str]) -> None:
        if not items:
            return
        print(f"\n{title} (showing up to 20):")
        for item in items[:20]:
            print(f"  - {item}")

    print_examples("Missing files", missing_files)
    print_examples("Metadata issues", bad_metadata_files)
    print_examples("Row-count mismatches", row_count_mismatch)
    print_examples("Duplicate row hashes", duplicate_hash_files)

    has_error = bool(missing_files or bad_metadata_files or row_count_mismatch)
    if has_error:
        raise SystemExit(1)

    print("\nValidation passed.")


if __name__ == "__main__":
    main()

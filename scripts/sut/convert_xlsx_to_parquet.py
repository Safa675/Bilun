#!/usr/bin/env python3
"""
Convert SUT XLSX files into parquet tables with metadata.

Input (default):
  raw data/<latest YYYY.MM.DD-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT>/

Output (default):
  data/gazette/raw/...
  data/gazette/version_manifest.parquet

Notes:
- Reads all .xlsx files recursively.
- Keeps original sheet columns (cleaned for blank rows/cols).
- Adds temporal + provenance metadata required for as-of modeling.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from scripts.sut._common import find_latest_consolidated_sut_dir


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_INPUT_DIR = None
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "gazette"
RAW_DATA_ROOT = PROJECT_ROOT / "raw data"


# NOTE: ``[A-ZC]`` did not match Turkish uppercase letters (Ç, Ş, Ğ, Ü, Ö, İ)
# so the EK-2Ç dental annex was silently bucketed under "EK-2". The explicit
# Turkish set covers every annex suffix used in the SUT (A, B, C, Ç, D, E, F,
# G, K, L, Y, and -N sub-numbered variants). re.IGNORECASE keeps the lower
# form working for mixed-case directory names.
RE_ANNEX = re.compile(r"(EK-\d+[A-ZÇŞĞÜÖİ]?(?:-\d+)*)", re.IGNORECASE)
RE_DATE_PATTERNS = [
    re.compile(
        r"Y[UU]R(?:[UU]RL[UU]K)?\.?\s*[:\-]?\s*(\d{1,2}[./]\d{1,2}[./]\d{4})",
        re.IGNORECASE,
    ),
    re.compile(r"\((?:[^)]*?)\b(\d{1,2}[./]\d{1,2}[./]\d{4})\b(?:[^)]*?)\)"),
]


@dataclass
class SheetResult:
    source_file: str
    annex_code: str
    annex_family: str
    sheet_name: str
    effective_date: str | None
    is_mulga: bool
    row_count: int
    column_count: int
    parquet_path: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert SUT XLSX files to parquet")
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_INPUT_DIR,
        help="Root directory containing SUT XLS/XLSX files (default: latest under raw data/)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output parquet root directory",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of XLSX files to process",
    )
    parser.add_argument(
        "--include-mulga",
        action="store_true",
        help="Include files under MULGA folders (default: excluded)",
    )
    parser.add_argument(
        "--overwrite-manifest",
        action="store_true",
        help="Overwrite existing version_manifest.parquet",
    )
    return parser.parse_args()


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_text).strip("_")
    return ascii_text or "unnamed"


def parse_annex_code(path: Path) -> str:
    combined = f"{path.name} {' '.join(p.name for p in path.parents)}"
    match = RE_ANNEX.search(combined)
    return match.group(1).upper() if match else "UNKNOWN"


def parse_annex_family(annex_code: str) -> str:
    if annex_code.startswith("EK-"):
        parts = annex_code.split("-")
        if len(parts) >= 2:
            return f"EK-{parts[1]}"
    return "UNKNOWN"


def parse_effective_date(path: Path) -> str | None:
    text = path.name
    for pattern in RE_DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        date_text = match.group(1).replace("/", ".")
        try:
            parsed = dt.datetime.strptime(date_text, "%d.%m.%Y").date()
            return parsed.isoformat()
        except ValueError:
            continue
    return None


def is_mulga_path(path: Path) -> bool:
    joined = " / ".join(p.name.upper() for p in [path, *path.parents])
    return "MULGA" in joined or "MULGA" in joined


def clean_sheet(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    cleaned = df.copy()
    cleaned = cleaned.dropna(axis=0, how="all")
    cleaned = cleaned.dropna(axis=1, how="all")

    if cleaned.empty:
        return cleaned

    cleaned.columns = [
        str(col).strip() if col is not None else "" for col in cleaned.columns
    ]
    cleaned.columns = [
        col if col else f"unnamed_{idx}" for idx, col in enumerate(cleaned.columns)
    ]
    return cleaned.reset_index(drop=True)


def add_metadata(
    df: pd.DataFrame,
    annex_code: str,
    annex_family: str,
    effective_date: str | None,
    source_file: str,
    sheet_name: str,
    is_mulga: bool,
) -> pd.DataFrame:
    out = df.copy()

    hash_frame = out.fillna("").astype(str)
    row_hash = hash_frame.apply(
        lambda row: hashlib.sha1("||".join(row.values).encode("utf-8")).hexdigest(),
        axis=1,
    )

    out["__annex_code"] = annex_code
    out["__annex_family"] = annex_family
    out["__effective_date"] = effective_date
    out["__source_file"] = source_file
    out["__sheet_name"] = sheet_name
    out["__is_mulga"] = bool(is_mulga)
    out["__ingested_at"] = (
        dt.datetime.now(dt.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    out["__row_hash"] = row_hash
    return out


def normalize_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize dataframe dtypes to avoid mixed-object pyarrow conversion errors.

    We keep numeric/bool/datetime columns as-is. For generic object columns,
    cast non-null values to string and keep nulls as None.
    """
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_object_dtype(out[col].dtype):
            out[col] = out[col].map(
                lambda x: None if (x is None or (isinstance(x, float) and pd.isna(x))) else str(x)
            )
    return out


def output_path_for_sheet(
    output_root: Path,
    annex_code: str,
    effective_date: str | None,
    source_file: Path,
    sheet_name: str,
) -> Path:
    date_token = effective_date or "unknown"
    source_slug = slugify(source_file.stem)
    sheet_slug = slugify(sheet_name)
    return (
        output_root
        / "raw"
        / f"annex={annex_code}"
        / f"effective_date={date_token}"
        / f"{source_slug}__{sheet_slug}.parquet"
    )


def convert_one_workbook(xlsx_path: Path, output_root: Path) -> list[SheetResult]:
    annex_code = parse_annex_code(xlsx_path)
    annex_family = parse_annex_family(annex_code)
    effective_date = parse_effective_date(xlsx_path)
    mulga = is_mulga_path(xlsx_path)

    xls = pd.ExcelFile(xlsx_path)
    results: list[SheetResult] = []

    try:
        for sheet_name in xls.sheet_names:
            raw_df = pd.read_excel(xls, sheet_name=sheet_name, dtype=object)
            clean_df = clean_sheet(raw_df)
            if clean_df.empty:
                continue

            enriched_df = add_metadata(
                clean_df,
                annex_code=annex_code,
                annex_family=annex_family,
                effective_date=effective_date,
                source_file=str(xlsx_path),
                sheet_name=sheet_name,
                is_mulga=mulga,
            )
            parquet_df = normalize_for_parquet(enriched_df)

            out_path = output_path_for_sheet(
                output_root=output_root,
                annex_code=annex_code,
                effective_date=effective_date,
                source_file=xlsx_path,
                sheet_name=sheet_name,
            )
            out_path.parent.mkdir(parents=True, exist_ok=True)
            parquet_df.to_parquet(out_path, index=False)

            results.append(
                SheetResult(
                    source_file=str(
                        xlsx_path.resolve().relative_to(PROJECT_ROOT)
                    ),
                    annex_code=annex_code,
                    annex_family=annex_family,
                    sheet_name=sheet_name,
                    effective_date=effective_date,
                    is_mulga=mulga,
                    row_count=len(parquet_df),
                    column_count=len(parquet_df.columns),
                    parquet_path=str(
                        out_path.resolve().relative_to(PROJECT_ROOT)
                    ),
                )
            )
    finally:
        xls.close()

    return results


def build_manifest(results: list[SheetResult]) -> pd.DataFrame:
    rows = [
        {
            "source_file": r.source_file,
            "annex_code": r.annex_code,
            "annex_family": r.annex_family,
            "sheet_name": r.sheet_name,
            "effective_date": r.effective_date,
            "is_mulga": r.is_mulga,
            "row_count": r.row_count,
            "column_count": r.column_count,
            "parquet_path": r.parquet_path,
        }
        for r in results
    ]
    manifest = pd.DataFrame(rows)
    if not manifest.empty:
        manifest = manifest.sort_values(
            [
                "annex_family",
                "annex_code",
                "effective_date",
                "source_file",
                "sheet_name",
            ],
            na_position="last",
        ).reset_index(drop=True)
    return manifest


def main() -> None:
    args = parse_args()
    default_input = find_latest_consolidated_sut_dir(RAW_DATA_ROOT)
    input_dir = Path(args.input_dir) if args.input_dir else default_input
    output_dir = Path(args.output_dir)

    if input_dir is None or not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    # Include both .xlsx and .xls files
    xlsx_files = sorted(
        list(input_dir.rglob("*.xlsx")) + list(input_dir.rglob("*.xls"))
    )
    if not args.include_mulga:
        xlsx_files = [p for p in xlsx_files if not is_mulga_path(p)]
    if args.limit is not None:
        xlsx_files = xlsx_files[: args.limit]

    print("=" * 72)
    print("SUT XLSX -> Parquet Converter")
    print("=" * 72)
    print(f"Input dir: {input_dir}")
    print(f"Output dir: {output_dir}")
    print(f"XLSX files to process: {len(xlsx_files)}")

    all_results: list[SheetResult] = []
    failed: list[tuple[str, str]] = []

    for idx, file_path in enumerate(xlsx_files, start=1):
        print(f"[{idx}/{len(xlsx_files)}] {file_path.name}")
        try:
            sheet_results = convert_one_workbook(file_path, output_dir)
            all_results.extend(sheet_results)
            print(f"  -> {len(sheet_results)} sheet(s) written")
        except Exception as exc:
            failed.append((str(file_path), str(exc)))
            print(f"  !! failed: {exc}")

    manifest = build_manifest(all_results)
    manifest_path = output_dir / "version_manifest.parquet"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    if manifest_path.exists() and not args.overwrite_manifest:
        existing = pd.read_parquet(manifest_path)
        merged = pd.concat([existing, manifest], ignore_index=True)
        merged = merged.drop_duplicates(subset=["parquet_path"], keep="last")
        # Write to a temp file then atomically rename, so a crash or
        # concurrent run can't leave a half-written manifest at the final path.
        tmp_path = manifest_path.with_suffix(".parquet.tmp")
        merged.to_parquet(tmp_path, index=False)
        os.replace(tmp_path, manifest_path)
        manifest_rows = len(merged)
    else:
        tmp_path = manifest_path.with_suffix(".parquet.tmp")
        manifest.to_parquet(tmp_path, index=False)
        os.replace(tmp_path, manifest_path)
        manifest_rows = len(manifest)

    # ── Atomic ingest-state write ────────────────────────────────────
    # Only update ingest_state.json after the full manifest is durably
    # committed. Uses the same temp-then-rename pattern as the manifest.
    # On a mid-run crash, state still points at the OLD version → the
    # next run retries cleanly.
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()[:16]
        latest_sut_dir = find_latest_consolidated_sut_dir(RAW_DATA_ROOT)
        latest_folder = latest_sut_dir.name if latest_sut_dir else ""
        latest_date = (
            latest_folder.split("-")[0].replace(".", "-")
            if latest_folder
            else ""
        )
        state = {
            "last_ingested_folder": latest_folder,
            "last_ingested_date": latest_date,
            "last_ingested_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "manifest_row_count": manifest_rows,
            "manifest_sha256": manifest_sha,
            "pipeline_version": 2,
        }
        state_path = output_dir / "ingest_state.json"
        with open(state_path.with_suffix(".json.tmp"), "w") as sf:
            json.dump(state, sf, indent=2, ensure_ascii=False)
            sf.flush()
            os.fsync(sf.fileno())
        os.replace(state_path.with_suffix(".json.tmp"), state_path)
        print(f"Ingest state written: {state_path}")
    except Exception as exc:
        print(f"WARNING: Failed to write ingest_state.json: {exc}")

    print("\n" + "=" * 72)
    print("CONVERSION COMPLETE")
    print("=" * 72)
    print(f"Sheets converted: {len(all_results)}")
    print(f"Manifest rows: {manifest_rows}")
    print(f"Manifest path: {manifest_path}")
    if failed:
        print(f"Failures: {len(failed)}")
        for src, err in failed[:20]:
            print(f"  - {src}: {err}")
    else:
        print("Failures: 0")


if __name__ == "__main__":
    main()

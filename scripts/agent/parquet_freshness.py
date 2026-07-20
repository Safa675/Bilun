#!/usr/bin/env python3
"""Parquet freshness checker for the SUT data pipeline.

A deterministic *reporter* (never a gate) that the Data Engineer agent runs to
answer two questions before re-running the curator pipeline:

  1. **Not-yet-ingested raw packages.** Are there consolidated SUT packages on
     disk under ``raw data/`` whose effective date is absent from
     ``data/gazette/version_manifest.parquet``? Such a package was fetched but
     never converted → the curated parquets are stale.
  2. **Curated-vs-raw drift.** For each curated parquet under
     ``data/gazette/curated/``, is its mtime older than the raw-source parquet
     it was built from (matched by annex code)? A curated file older than its
     raw input means a re-run of ``build_curated_catalogs`` is owed.

Outputs a markdown report to ``reports/agent/data/freshness.md`` (creating the
parent dir if needed) and prints a one-line summary. Always exits 0 — it only
*reports*, the consumer decides what to do.

The checker is read-only: it never writes to ``data/gazette/``. Per the
2026-06-30 lesson, investigations must not mutate committed parquets.
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

import polars as pl

# scripts/agent/parquet_freshness.py → repo root is 3 parents up.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "gazette" / "version_manifest.parquet"
DEFAULT_RAW_DATA_DIR = PROJECT_ROOT / "raw data"
DEFAULT_GAZETTE_DIR = PROJECT_ROOT / "data" / "gazette"
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "agent" / "data" / "freshness.md"

# Folder pattern: YYYY.MM.DD-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT
# The date prefix is the on-disk "effective date" of the package.
_DATE_PREFIX_RE = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})-")
# Match the annex code embedded in raw partition paths (e.g. ``annex=EK-2C``)
# and curated filenames (e.g. ``ek2c_catalog_history.parquet``).
_RAW_ANNEX_RE = re.compile(r"annex=(EK-[\dA-ZÇŞĞÜÖİ]+(?:-\d+)*)", re.IGNORECASE)
_CURATED_ANNEX_RE = re.compile(r"^(ek[\dA-ZÇŞĞÜÖİ]+(?:-\d+)*)", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report SUT parquet freshness: not-ingested packages + stale curated."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to version_manifest.parquet",
    )
    parser.add_argument(
        "--raw-data-dir",
        type=Path,
        default=DEFAULT_RAW_DATA_DIR,
        help="Directory holding consolidated SUT packages (default: raw data/)",
    )
    parser.add_argument(
        "--gazette-dir",
        type=Path,
        default=DEFAULT_GAZETTE_DIR,
        help="data/gazette root holding raw/ and curated/ partitions",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Markdown report path (default: reports/agent/data/freshness.md)",
    )
    return parser.parse_args()


def load_manifest_effective_dates(manifest_path: Path) -> pl.DataFrame:
    """Read the manifest and return one row per distinct non-null effective_date."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    df = pl.read_parquet(manifest_path)
    if "effective_date" not in df.columns:
        raise ValueError(f"Manifest missing effective_date column: {manifest_path}")
    return df


def find_on_disk_packages(raw_data_dir: Path) -> list[tuple[str, Path]]:
    """Return (date_iso, path) for each consolidated SUT package on disk.

    Only directories whose name starts with ``YYYY.MM.DD-`` are considered.
    """
    packages: list[tuple[str, Path]] = []
    if not raw_data_dir.exists():
        return packages
    for entry in sorted(raw_data_dir.iterdir()):
        if not entry.is_dir():
            continue
        m = _DATE_PREFIX_RE.match(entry.name)
        if m is None:
            continue
        date_iso = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        packages.append((date_iso, entry))
    return packages


def find_not_ingested(
    manifest_dates: set[str], packages: list[tuple[str, Path]]
) -> list[tuple[str, Path]]:
    """Packages whose date is absent from the manifest's effective_date set."""
    return [(d, p) for d, p in packages if d not in manifest_dates]


def annex_from_raw_path(path: Path) -> str | None:
    """Extract the annex code from a raw partition path (``annex=EK-2C``)."""
    for part in path.parts:
        m = _RAW_ANNEX_RE.search(part)
        if m:
            return m.group(1).upper()
    return None


def annex_from_curated_name(name: str) -> str | None:
    """Normalize a curated filename stem into a manifest ``annex_code`` form.

    Curated files look like ``ek2c_catalog_history.parquet``. We map the
    leading ``ek2c`` token back to ``EK-2C`` by reinserting the dash that the
    curated naming convention strips.
    """
    m = _CURATED_ANNEX_RE.match(name)
    if not m:
        return None
    token = m.group(1).upper()
    # ek2c -> EK-2C ; ek2c1 -> EK-2C-1 ; ek3b1 -> EK-3B-1 ; ek1a -> EK-1A
    # The numeric suffix may or may not have a dash (EK-2C-1 vs EK2C1) — accept both.
    # Caught by PR #37 review: prior regex required the dash, so dash-less tokens
    # like EK2C1 returned unnormalized and never matched the annex= dir.
    inner = re.match(r"^EK(\d)([A-ZÇŞĞÜÖİ]?)(?:-(\d+)|(\d+))?$", token)
    if not inner:
        return token
    num, letter, sub_dash, sub_nodash = inner.groups()
    base = f"EK-{num}{letter}" if letter else f"EK-{num}"
    sub = sub_dash or sub_nodash
    return f"{base}-{sub}" if sub else base


def latest_raw_mtime_for_annex(gazette_dir: Path, annex_code: str) -> tuple[Path | None, float | None]:
    """Newest raw parquet mtime for an annex; returns (path, mtime) or (None, None)."""
    annex_dir = gazette_dir / "raw" / f"annex={annex_code}"
    if not annex_dir.exists():
        return None, None
    raw_parquets = sorted(annex_dir.rglob("*.parquet"))
    if not raw_parquets:
        return None, None
    newest = max(raw_parquets, key=lambda p: p.stat().st_mtime)
    return newest, newest.stat().st_mtime


def find_stale_curated(gazette_dir: Path) -> list[dict]:
    """Curated parquets whose mtime is older than their newest raw source.

    Each result row:
        curated_path, raw_source_path, curated_mtime, raw_mtime, lag_seconds
    """
    curated_dir = gazette_dir / "curated"
    if not curated_dir.exists():
        return []

    stale: list[dict] = []
    for curated in sorted(curated_dir.glob("*.parquet")):
        annex_code = annex_from_curated_name(curated.stem)
        if annex_code is None:
            continue
        raw_path, raw_mtime = latest_raw_mtime_for_annex(gazette_dir, annex_code)
        if raw_path is None or raw_mtime is None:
            continue
        curated_mtime = curated.stat().st_mtime
        if curated_mtime < raw_mtime:
            stale.append(
                {
                    "curated_path": str(curated.relative_to(PROJECT_ROOT)),
                    "raw_source_path": str(raw_path.relative_to(PROJECT_ROOT)),
                    "curated_mtime": curated_mtime,
                    "raw_mtime": raw_mtime,
                    "lag_seconds": int(raw_mtime - curated_mtime),
                }
            )
    return stale


def fmt_time(epoch: float) -> str:
    """Render an epoch mtime as a local ISO-ish timestamp for the report."""
    import datetime as dt

    return dt.datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M:%S")


def write_report(
    output: Path,
    manifest_rows: int,
    manifest_dates: list[str],
    packages: list[tuple[str, Path]],
    not_ingested: list[tuple[str, Path]],
    stale_curated: list[dict],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# SUT Parquet Freshness Report")
    lines.append("")
    lines.append(f"- Generated: {fmt_time(time.time())}")
    lines.append(f"- Manifest rows: {manifest_rows}")
    lines.append(f"- Distinct effective_dates in manifest: {len(manifest_dates)}")
    lines.append(f"- Consolidated SUT packages on disk: {len(packages)}")
    lines.append("")

    # (a) not-ingested
    lines.append("## On-disk packages not yet ingested")
    lines.append("")
    if not_ingested:
        lines.append("| date | package_dir |")
        lines.append("|------|-------------|")
        for date_iso, pkg in not_ingested:
            lines.append(f"| {date_iso} | `{pkg.name}` |")
    else:
        lines.append("_All on-disk SUT packages have their effective_date in the manifest._")
    lines.append("")

    # (b) stale curated
    lines.append("## Curated parquets stale relative to raw")
    lines.append("")
    if stale_curated:
        lines.append("| curated_path | raw_source_path | curated_mtime | raw_mtime | lag_seconds |")
        lines.append("|--------------|-----------------|---------------|-----------|-------------|")
        for row in sorted(stale_curated, key=lambda r: -r["lag_seconds"]):
            lines.append(
                f"| `{row['curated_path']}` | `{row['raw_source_path']}` | "
                f"{fmt_time(row['curated_mtime'])} | {fmt_time(row['raw_mtime'])} | "
                f"{row['lag_seconds']} |"
            )
    else:
        lines.append("_No curated parquet is older than its raw source._")
    lines.append("")

    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()

    manifest_df = load_manifest_effective_dates(args.manifest)
    # Non-null effective_date values only. Nulls are present for rows whose
    # source XLSX had no parseable date and are not comparable to on-disk
    # package dates — they're an orthogonal data-quality issue.
    manifest_dates_series = manifest_df.filter(
        pl.col("effective_date").is_not_null()
    )["effective_date"]
    manifest_dates = set(manifest_dates_series.cast(pl.Utf8).to_list())
    distinct_dates = sorted(manifest_dates)

    packages = find_on_disk_packages(args.raw_data_dir)
    not_ingested = find_not_ingested(manifest_dates, packages)
    stale_curated = find_stale_curated(args.gazette_dir)

    write_report(
        output=args.output,
        manifest_rows=manifest_df.height,
        manifest_dates=distinct_dates,
        packages=packages,
        not_ingested=not_ingested,
        stale_curated=stale_curated,
    )

    # Display path: relative if inside repo, absolute otherwise (e.g. /tmp/ in tests)
    try:
        display = str(args.output.relative_to(PROJECT_ROOT))
    except ValueError:
        display = str(args.output)
    print(
        f"freshness: not_ingested={len(not_ingested)} "
        f"stale_curated={len(stale_curated)} "
        f"packages_on_disk={len(packages)} "
        f"manifest_dates={len(distinct_dates)} "
        f"-> {display}"
    )


if __name__ == "__main__":
    main()

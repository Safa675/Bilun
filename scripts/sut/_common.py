"""
Shared helpers for scripts/sut/ curators and builders.

Provides:
  - Value coercion (_safe_str, _safe_float)
  - Column filtering (_data_cols)
  - Raw parquet discovery (_find_raw_parquet, _read_raw)
  - Manifest-driven loading (_load_manifest, _add_validity_ranges)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def _data_cols(df: pd.DataFrame) -> list[str]:
    """Return columns that are NOT ingestion metadata (__*)."""
    return [c for c in df.columns if not c.startswith("__")]


def _safe_str(val: Any) -> str:
    """Convert value to stripped string, treating None/NaN as ''."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def _safe_float(val: Any) -> float | None:
    """Convert to float, returning None for non-numeric."""
    try:
        v = float(val)
        return v if pd.notna(v) else None
    except (ValueError, TypeError):
        return None


def _find_raw_parquet(parquet_root: Path, annex_code: str) -> Path | None:
    """Walk annex=<CODE>/ dir tree and return the latest .parquet file found.

    Files are sorted by effective_date (YYYY-MM-DD prefix). Directories
    with ``effective_date=unknown`` are skipped — they are legacy dumps
    with different column layouts that produce empty curated output.
    """
    annex_dir = parquet_root / "raw" / f"annex={annex_code}"
    if not annex_dir.exists():
        return None

    def _date_sort_key(fp: Path) -> str:
        # Extract effective_date from path components: .../effective_date=YYYY-MM-DD/...
        for part in fp.parts:
            if part.startswith("effective_date=") and not part.endswith("unknown"):
                return part.removeprefix("effective_date=")
        return ""

    found = sorted(
        (fp for fp in annex_dir.rglob("*.parquet") if _date_sort_key(fp)),
        key=_date_sort_key,
    )
    return found[-1] if found else None


def _read_raw(parquet_root: Path, annex_code: str) -> pd.DataFrame | None:
    """Read raw parquet for an annex, returning None if not found."""
    fp = _find_raw_parquet(parquet_root, annex_code)
    if fp is None:
        return None
    return pd.read_parquet(fp)


def _load_manifest(parquet_root: Path) -> pd.DataFrame:
    """Load version_manifest.parquet and parse effective_date."""
    manifest_path = parquet_root / "version_manifest.parquet"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    manifest = pd.read_parquet(manifest_path)
    manifest["effective_date_parsed"] = pd.to_datetime(
        manifest["effective_date"], errors="coerce"
    )
    return manifest


def _add_validity_ranges(df: pd.DataFrame, key_col: str) -> pd.DataFrame:
    """Attach valid_from / valid_to columns based on consecutive effective_dates."""
    work = df.copy()
    work["effective_date_parsed"] = pd.to_datetime(
        work["effective_date"], errors="coerce"
    )
    work = work.sort_values([key_col, "effective_date_parsed"]).reset_index(drop=True)
    work["valid_from"] = work["effective_date"]
    next_eff = work.groupby(key_col)["effective_date_parsed"].shift(-1)
    work["valid_to"] = (next_eff - pd.to_timedelta(1, unit="D")).dt.date.astype(
        "string"
    )
    work.loc[next_eff.isna(), "valid_to"] = pd.NA
    return work.drop(columns=["effective_date_parsed"])

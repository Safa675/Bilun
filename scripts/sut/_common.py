"""
Shared helpers for scripts/sut/ curators and builders.

Provides:
  - Value coercion (_safe_str, _safe_float)
  - Column filtering (_data_cols)
  - Raw parquet discovery (_find_raw_parquet, _read_raw)
  - Manifest-driven loading (_load_manifest, _add_validity_ranges)
"""

from __future__ import annotations

import re
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
    with different column layouts that produce empty curated output —
    *unless* the annex has no dated version at all, in which case the
    ``unknown`` partition is a legitimate fallback (e.g. EK-1A, an
    undated single-version .xls annex).
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

    all_parquets = list(annex_dir.rglob("*.parquet"))
    dated = sorted((fp for fp in all_parquets if _date_sort_key(fp)), key=_date_sort_key)
    if dated:
        return dated[-1]

    # No dated version: fall back to the unknown partition if one exists
    # (legitimately undated single-version annexes like EK-1A).
    unknown = [fp for fp in all_parquets if not _date_sort_key(fp)]
    return unknown[-1] if unknown else None


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


_CONSOLIDATED_SUT_DIR_SUFFIX = "Değişiklik Tebliği İşlenmiş Güncel 2013 SUT"
_DATE_PREFIX_RE = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})-")


def find_latest_consolidated_sut_dir(raw_data_root: Path) -> Path | None:
    """Return latest consolidated SUT directory under ``raw data/``.

    Expected folder shape:
      YYYY.MM.DD-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT
    """
    if not raw_data_root.exists():
        return None

    candidates: list[tuple[str, Path]] = []
    for entry in raw_data_root.iterdir():
        if not entry.is_dir():
            continue
        if not entry.name.endswith(_CONSOLIDATED_SUT_DIR_SUFFIX):
            continue
        m = _DATE_PREFIX_RE.match(entry.name)
        if m is None:
            continue
        date_key = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        candidates.append((date_key, entry))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[-1][1]


def find_latest_consolidated_sut_docx(raw_data_root: Path) -> Path | None:
    """Return main consolidated SUT .docx inside latest SUT directory."""
    sut_dir = find_latest_consolidated_sut_dir(raw_data_root)
    if sut_dir is None:
        return None

    # Use rglob to handle SGK zip nesting variations (some zips add an
    # extra inner folder layer). Prefer depth-1 matches but fall back
    # to deeper matches.
    root_docx = sorted(p for p in sut_dir.rglob("*.docx") if p.is_file())
    if not root_docx:
        return None

    # Prefer a filename that explicitly contains "İşlenmiş Güncel 2013 SUT".
    preferred = [
        p
        for p in root_docx
        if "İşlenmiş Güncel 2013 SUT" in p.name or "Islenmis Guncel 2013 SUT" in p.name
    ]
    if preferred:
        # Among preferred, pick the shallowest (closest to root)
        preferred.sort(key=lambda p: len(p.relative_to(sut_dir).parts))
        return preferred[0]
    # Among all, pick the shallowest
    root_docx.sort(key=lambda p: len(p.relative_to(sut_dir).parts))
    return root_docx[0]

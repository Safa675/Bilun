"""
Shared helpers for scripts/sut/ curators and builders.

Provides:
  - Value coercion (_safe_str, _safe_float)
  - Column filtering (_data_cols)
  - Raw parquet discovery (_find_raw_parquet, _read_raw)
  - Manifest-driven loading (_load_manifest, _add_validity_ranges)
  - Amendment markers in list cells (amendment_markers, strip_amendment_marker)
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


def _data_cols(df: pd.DataFrame) -> list[str]:
    """Return columns that are NOT ingestion metadata (__*)."""
    return [c for c in df.columns if not c.startswith("__")]


def _safe_str(val: Any) -> str:
    """Convert value to stripped string, treating None/NaN as ''."""
    if val is None or val is pd.NA or val is pd.NaT or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def _safe_float(val: Any) -> float | None:
    """Convert to float, returning None for non-numeric."""
    try:
        v = float(val)
        return v if pd.notna(v) else None
    except (ValueError, TypeError):
        return None


def _is_mulga_parquet(fp: Path) -> bool:
    """Return True if the parquet filename marks a MÜLGA (repealed) source.

    The converter slugifies the source-workbook stem into the parquet
    filename (``slugify`` ASCII-folds Ü→U), so repealed sources are
    written as ``MULGA_...parquet``. The ``__is_mulga`` column is NOT a
    reliable signal for older partitions (written before the Turkish-fold
    fix in ``convert_xlsx_to_parquet.is_mulga_path`` — 273 on-disk files
    carry a stale ``False``), whereas the filename was verified faithful
    to ``__source_file`` provenance across the whole raw tree. Same
    substring semantics as ``is_mulga_path`` (ASCII-folded containment).
    """
    folded = (
        fp.name.upper()
        .replace("Ü", "U")
        .replace("İ", "I")
        .replace("Ş", "S")
        .replace("Ç", "C")
        .replace("Ğ", "G")
        .replace("Ö", "O")
    )
    return "MULGA" in folded


def _source_package_is_future(fp: Path, as_of: dt.date) -> bool:
    """Check the dated source package even for an undated annex filename."""
    if "__source_file" not in pq.read_schema(fp).names:
        return False
    sources = pd.read_parquet(fp, columns=["__source_file"])["__source_file"]
    for source in sources.dropna().unique():
        for part in Path(str(source)).parts:
            if not part.endswith(_CONSOLIDATED_SUT_DIR_SUFFIX):
                continue
            match = _DATE_PREFIX_RE.match(part)
            if match is not None:
                package_date = dt.date(*(int(value) for value in match.groups()))
                if package_date > as_of:
                    return True
    return False


def _find_raw_parquet(
    parquet_root: Path, annex_code: str, *, as_of: dt.date | None = None
) -> Path | None:
    """Walk annex=<CODE>/ dir tree and return the latest .parquet file found.

    Files after ``as_of`` (UTC today by default), including undated files
    from a future consolidated source package, are not active candidates.
    Files are sorted by effective_date (YYYY-MM-DD prefix). MÜLGA
    (repealed) candidates are excluded up front: for EK-4/4A/4B/4C the
    current source converts to ``effective_date=unknown`` (no date in the
    filename) while every dated partition is a repealed list, so picking
    ``dated[-1]`` without this filter serves repealed content to live
    catalogs (ek4a_drugs.parquet -> get_ek4a_drugs API). Annexes whose
    partitions are *all* MÜLGA keep resolving (MÜLGA pool as fallback)
    so nothing regresses to None.

    Among the surviving candidates, directories with
    ``effective_date=unknown`` are skipped — they are legacy dumps with
    different column layouts that produce empty curated output —
    *unless* the annex has no dated version at all, in which case the
    ``unknown`` partition is a legitimate fallback (e.g. EK-1A, an
    undated single-version .xls annex).
    """
    annex_dir = parquet_root / "raw" / f"annex={annex_code}"
    if not annex_dir.exists():
        return None
    cutoff = as_of if as_of is not None else dt.datetime.now(dt.UTC).date()

    def _date_sort_key(fp: Path) -> str:
        # Extract effective_date from path components: .../effective_date=YYYY-MM-DD/...
        for part in fp.parts:
            if part.startswith("effective_date=") and not part.endswith("unknown"):
                return part.removeprefix("effective_date=")
        return ""

    all_parquets = []
    for fp in sorted(annex_dir.rglob("*.parquet")):
        effective_date = _date_sort_key(fp)
        if effective_date and dt.date.fromisoformat(effective_date) > cutoff:
            continue
        if not _source_package_is_future(fp, cutoff):
            all_parquets.append(fp)
    # Prefer current (non-MÜLGA) partitions; fall back to MÜLGA only when
    # an annex has nothing else, preserving resolvability.
    pool = [fp for fp in all_parquets if not _is_mulga_parquet(fp)] or all_parquets
    dated = sorted((fp for fp in pool if _date_sort_key(fp)), key=_date_sort_key)
    if dated:
        return dated[-1]

    # No dated version: fall back to the unknown partition if one exists
    # (legitimately undated single-version annexes like EK-1A).
    unknown = [fp for fp in pool if not _date_sort_key(fp)]
    return unknown[-1] if unknown else None


def _read_raw(
    parquet_root: Path, annex_code: str, *, as_of: dt.date | None = None
) -> pd.DataFrame | None:
    """Read raw parquet for an annex, returning None if not found."""
    fp = _find_raw_parquet(parquet_root, annex_code, as_of=as_of)
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


# SGK writes each later amendment into the list it changes, in the row's code cell:
# "603331 (Ek: RG-29/08/2026- 33355/ 14-a md. Yürürlük: 05/09/2026)". "Ek" adds the row,
# "Değişik" amends it (the list keeps the older clean row of the same code next to it)
# and "Mülga" repeals it, each from the marker's Yürürlük date.
MARKER_FROM = "_marker_from"  # latest Yürürlük date of the cell's Ek/Değişik markers
MARKER_ADDED = "_marker_added"  # that latest marker adds the row ("Ek")
MARKER_REPEALED = "_marker_repealed"  # earliest Yürürlük date of the cell's Mülga markers
MARKER_UNDATED = "_marker_undated"  # the cell has a marker whose Yürürlük date cannot be read
MARKER_COLUMNS = (MARKER_FROM, MARKER_ADDED, MARKER_REPEALED, MARKER_UNDATED)

_MARKER = re.compile(
    r"\(\s*(?:(?P<kind>[^\W\d_]+)\s*:)?[^()]*?Y[üu]r[üu]rl[üu]k\s*:?\s*"
    r"(?P<day>\d{1,2})\s*[./]\s*(?P<month>\d{1,2})\s*[./]\s*(?P<year>\d{4})",
    re.IGNORECASE,
)
_ANY_MARKER = re.compile(r"\([^()]*(?:\bRG\s*-|Y[üu]r[üu]rl[üu]k)", re.IGNORECASE)
_REPEAL_KINDS = ("mülga", "mulga")


def strip_amendment_marker(cells: pd.Series) -> pd.Series:
    """The value before a cell's marker: "603331  (Ek: RG-…)" -> "603331"."""
    return cells.fillna("").astype(str).str.replace(r"\s*\(.*$", "", regex=True).str.strip()


def count_amendment_markers(cells: pd.Series) -> pd.Series:
    """How many amendment markers, dated or not, each cell carries."""
    return cells.fillna("").astype(str).str.count(_ANY_MARKER)


def amendment_markers(cells: pd.Series) -> pd.DataFrame:
    """MARKER_COLUMNS for each cell, on the cells' index (NaT / False without a marker)."""
    text = cells.fillna("").astype(str).reset_index(drop=True)
    found = text.str.extractall(_MARKER)
    kind = found["kind"].fillna("").str.casefold()
    dates = pd.to_datetime(found[["year", "month", "day"]].astype(int), errors="coerce")
    repeal = kind.isin(_REPEAL_KINDS)
    starts = pd.DataFrame({"date": dates.where(~repeal), "added": kind.eq("ek")})
    latest = starts[starts["date"].notna()].sort_values("date", kind="stable")
    latest = latest.groupby(level=0).tail(1).droplevel(1)
    out = pd.DataFrame(index=text.index)
    out[MARKER_FROM] = latest["date"].reindex(text.index)
    out[MARKER_ADDED] = latest["added"].reindex(text.index, fill_value=False).astype(bool)
    out[MARKER_REPEALED] = dates.where(repeal).groupby(level=0).min().reindex(text.index)
    out[MARKER_UNDATED] = (
        text.str.contains(_ANY_MARKER) & out[MARKER_FROM].isna() & out[MARKER_REPEALED].isna()
    )
    out.index = cells.index
    return out


def _marker_values(work: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """(MARKER_FROM, MARKER_ADDED, MARKER_REPEALED, MARKER_UNDATED) of a frame; no marker if absent."""
    no_date = pd.Series(pd.NaT, index=work.index, dtype="datetime64[ns]")
    no = pd.Series(False, index=work.index)
    return (
        pd.to_datetime(work[MARKER_FROM]) if MARKER_FROM in work.columns else no_date,
        work[MARKER_ADDED].astype(bool) if MARKER_ADDED in work.columns else no,
        pd.to_datetime(work[MARKER_REPEALED]) if MARKER_REPEALED in work.columns else no_date,
        work[MARKER_UNDATED].astype(bool) if MARKER_UNDATED in work.columns else no,
    )


def _last_day_before(ends: pd.Series) -> pd.Series:
    """valid_to for exclusive end dates: the day before, as YYYY-MM-DD; <NA> when open."""
    days = (ends - pd.to_timedelta(1, unit="D")).dt.date.astype("string")
    days[ends.isna()] = pd.NA
    return days


def _earlier(ends: pd.Series, other: pd.Series) -> pd.Series:
    """The earlier of two exclusive end dates, NaT meaning none."""
    return ends.where(other.isna() | (ends <= other), other)


def _add_validity_ranges(df: pd.DataFrame, key_col: str) -> pd.DataFrame:
    """Attach valid_from / valid_to to a history built from every version of a list.

    A row applies from its list's effective_date or, when later, from the Yürürlük
    date of its own Ek/Değişik marker (MARKER_FROM, see amendment_markers), until the
    day before the next row of its key starts; a key missing from the next list ends
    the day before that list. A Mülga marker ends the row the day before its date.
    Until a marked row starts, the older row of its key goes on: the clean row SGK
    keeps beside it, or the previous list's row; an added key is absent. A row that
    cannot apply within its list (a marker date on or after the next list's date, a
    repeal on or before its start, a marker date that cannot be read) is dropped. Of
    two rows of one key that start on the same day, the amended one is kept.
    """
    work = df.copy()
    marker_from, _added, repealed, undated = _marker_values(work)
    version = pd.to_datetime(work["effective_date"], errors="coerce")
    dates = sorted(version.dropna().unique())
    next_version = pd.to_datetime(version.map(dict(zip(dates, dates[1:]))))
    start = marker_from.where(marker_from > version, version)
    in_list = (next_version.isna() | (start < next_version)) & (repealed.isna() | (repealed > start))
    work = work.assign(
        _start=start,
        _repealed=repealed,
        _next_version=next_version,
        _amended=marker_from.notna(),
        _position=range(len(work)),
    )[~undated & in_list]
    work = (
        work.sort_values([key_col, "_start", "_amended", "_position"])
        .drop_duplicates(subset=[key_col, "_start"], keep="last")
        .reset_index(drop=True)
    )
    ends = work.groupby(key_col)["_start"].shift(-1).fillna(work["_next_version"])
    ends = _earlier(ends, work["_repealed"])
    moved = work["_start"] != pd.to_datetime(work["effective_date"], errors="coerce")
    work["valid_from"] = work["effective_date"].where(~moved, work["_start"].dt.strftime("%Y-%m-%d"))
    work["valid_to"] = _last_day_before(ends)
    helpers = ["_start", "_repealed", "_next_version", "_amended", "_position"]
    return work.drop(columns=helpers + [c for c in MARKER_COLUMNS if c in work.columns])


def _add_list_validity(df: pd.DataFrame, key_cols: list[str]) -> pd.DataFrame:
    """Attach valid_from / valid_to to the rows of one list kept without older versions.

    An added row (Ek) applies from its marker's Yürürlük date. An amended row
    (Değişik) applies from its date when the list keeps an older row of its key,
    which then ends the day before; without one it has no start, because its key was
    in force before with values the list no longer shows. A Mülga marker ends the row
    the day before its date. Other rows keep null dates, in force on every date as
    before. Of two marked rows of one key with the same date the later one is kept.
    The list's row order is kept.
    """
    work = df.copy()
    marker_from, added, repealed, undated = _marker_values(work)
    if undated.any():
        rows = work.loc[undated, key_cols].to_dict("records")
        raise ValueError(f"amendment marker without a readable Yürürlük date: {rows}")
    work = work.assign(
        _start=marker_from,
        _added=added,
        _repealed=repealed,
        _amended=marker_from.notna(),
        _position=range(len(work)),
    ).sort_values([*key_cols, "_start", "_amended", "_position"], na_position="first")
    tied = work["_start"].notna() & work.duplicated(subset=[*key_cols, "_start"], keep="last")
    work = work[~tied]
    first = ~work.duplicated(subset=key_cols, keep="first")
    work.loc[first & ~work["_added"], "_start"] = pd.NaT
    ends = work.groupby(key_cols, dropna=False)["_start"].shift(-1)
    ends = ends.groupby([work[c] for c in key_cols], dropna=False).bfill()
    ends = _earlier(ends, work["_repealed"])
    work["valid_from"] = work["_start"].dt.date.astype("string")
    work.loc[work["_start"].isna(), "valid_from"] = pd.NA
    work["valid_to"] = _last_day_before(ends)
    helpers = ["_start", "_added", "_repealed", "_amended", "_position"]
    work = work.sort_values("_position").reset_index(drop=True)
    return work.drop(columns=helpers + [c for c in MARKER_COLUMNS if c in work.columns])


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

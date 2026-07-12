"""EK-2B / EK-2C procedure membership lookups for prose rule evaluation."""

from __future__ import annotations

import logging
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import pandas as pd

from ..constants import EK2B_CURATED_HISTORY_PATH, EK2C_CURATED_HISTORY_PATH, _GAZETTE_DIR
from .ek2c_prose_drg_locked import load_prose_drg_locked_code_set

logger = logging.getLogger("bilun.domain.prose_rules.catalog_membership")

# Snapshot path for the EK-2/A-2 "ayaktan ilave işlemler" list (outpatient
# add-on procedures separately billable per SUT §2.2.1.B-1). The parquet stores
# the procedure code in its first column (a long Turkish header string) with a
# sentinel ``İŞLEM KODU`` header row.


def _resolve_latest_snapshot_dir() -> Path:
    """Dynamically find the latest asof snapshot directory.

    Avoids hardcoding ``asof_2026-01-31`` — picks the newest by name sort.
    """
    snapshots_root = _GAZETTE_DIR / "snapshots"
    if not snapshots_root.exists():
        return snapshots_root / "asof_2026-01-31"  # fallback (doesn't exist)
    asof_dirs = sorted(
        d for d in snapshots_root.iterdir() if d.is_dir() and d.name.startswith("asof_")
    )
    return asof_dirs[-1] if asof_dirs else snapshots_root / "asof_2026-01-31"


_LATEST_SNAPSHOT_DIR = _resolve_latest_snapshot_dir()
_EK2A2_SNAPSHOT_PATH = _LATEST_SNAPSHOT_DIR / "EK-2A-2.parquet"
_EK2A2_HEADER_SENTINEL = "İŞLEM KODU"

# Raw EK-2/D-3 HBO (hiperbarik oksijen) indication list. The parquet carries
# the indication name in column 0, the ICD-10 code in column 1 (``Unnamed: 1``),
# initial sessions in column 2, and max sessions in column 3.
_EK2D3_RAW_GLOB = "annex=EK-2D-3/**/*.parquet"
_EK2D3_ICD10_HEADER = "ICD - 10 Tanı Kodları"

# HBO indications that are time-critical EMERGENCIES (acute trauma/poisoning
# where the board-report requirement is waived per §2.4.4.B(4)). These map to
# ICD-10 prefixes; a billed code matching any prefix flags the claim as an
# emergency-listed indication. Sourced from the EK-2/D-3 list's acute entries:
# decompression sickness, air/gas embolism, CO/cyanide poisoning, smoke
# inhalation, gas gangrene, crush/compartment syndrome, sudden hearing loss,
# CRAO, anoxic encephalopathy, thermal burns, brain abscess.
_EK2D3_EMERGENCY_INDICATIONS = frozenset({
    "Dekompresyon hastalığı",
    "Hava veya gaz embolisi",
    "Karbonmonoksit, siyanid zehirlenmesi, akut duman İnhalasyonu",
    "Gazlı gangren",
    "Crush yaralanmaları, kompartman sendromu, travmatik iskemi",
    "Termal yanık",
    "Beyin apsesi",
    "Anoksik ansefalopati",
    "Ani işitme kaybı",
    "Retinal arter oklüzyonu",
})


def normalize_procedure_code(raw: str) -> str:
    code = str(raw or "").strip().replace(".", "").replace(" ", "").replace("-", "")
    if code.startswith(("P", "p")):
        code = code[1:]
    return code


def _coerce_asof_key(as_of_date: date | str | None) -> str:
    if as_of_date is None:
        return date.today().isoformat()
    if isinstance(as_of_date, date):
        return as_of_date.isoformat()
    text = str(as_of_date).strip()
    if not text:
        return date.today().isoformat()
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date().isoformat()
    except ValueError:
        return date.today().isoformat()


def _eligible_history_rows(
    history_path: Path,
    code_column: str,
    asof_key: str,
) -> pd.DataFrame:
    if not history_path.exists():
        logger.warning("Catalog history not found: %s", history_path)
        return pd.DataFrame()

    df = pd.read_parquet(history_path)
    if df.empty or code_column not in df.columns:
        return pd.DataFrame()

    work = df.copy()
    if "effective_date" not in work.columns:
        return work.drop_duplicates(subset=[code_column], keep="last")

    work["effective_date_parsed"] = pd.to_datetime(work["effective_date"], errors="coerce")
    cutoff = pd.to_datetime(asof_key)
    work = work[work["effective_date_parsed"].notna()]
    eligible = work[work["effective_date_parsed"] <= cutoff]
    if eligible.empty:
        # B-H2: no amendment is effective on or before the cutoff (e.g. a
        # claim dated before the earliest curated gazette, or a date.min
        # sentinel). Returning the OLDEST amendment as a fallback silently
        # served a price that was never effective on the service date and is
        # inconsistent with pricing/temporal.py (_is_effective_on_or_before
        # returns None there). Return empty so callers (get_ek2b_codes_as_of
        # -> empty frozenset, get_ek2c_entry -> None) correctly signal "no
        # price as of this date".
        return eligible.reset_index(drop=True)
    eligible = eligible.sort_values(
        [code_column, "effective_date_parsed"]
    ).drop_duplicates(subset=[code_column], keep="last")
    return eligible.reset_index(drop=True)


@lru_cache(maxsize=64)
def get_ek2b_codes_as_of(asof_key: str) -> frozenset[str]:
    eligible = _eligible_history_rows(EK2B_CURATED_HISTORY_PATH, "code", asof_key)
    if eligible.empty:
        return frozenset()
    codes = {
        normalize_procedure_code(str(value))
        for value in eligible["code"].dropna()
        if str(value).strip()
    }
    codes.discard("")
    return frozenset(codes)


@lru_cache(maxsize=64)
def _ek2c_frame_asof(asof_key: str) -> pd.DataFrame:
    return _eligible_history_rows(EK2C_CURATED_HISTORY_PATH, "package_code", asof_key)


@lru_cache(maxsize=64)
def get_ek2c_codes_as_of(asof_key: str) -> frozenset[str]:
    work = _ek2c_frame_asof(asof_key)
    if work.empty:
        return frozenset()
    codes = {
        normalize_procedure_code(str(value))
        for value in work["package_code"].dropna()
        if str(value).strip()
    }
    codes.discard("")
    return frozenset(codes)


@lru_cache(maxsize=64)
def _ek2c_entry_map_asof(asof_key: str) -> dict[str, dict[str, object]]:
    work = _ek2c_frame_asof(asof_key)
    if work.empty:
        return {}

    entries: dict[str, dict[str, object]] = {}
    locked_seed = load_prose_drg_locked_code_set()
    for row in work.itertuples(index=False):
        normalized = normalize_procedure_code(str(getattr(row, "package_code", "")))
        if not normalized:
            continue
        parquet_locked = bool(getattr(row, "prose_drg_locked", False))
        entries[normalized] = {
            "package_code": str(getattr(row, "package_code", "")),
            "name": str(getattr(row, "name", "")),
            "group": str(getattr(row, "group", "")),
            "has_star": bool(getattr(row, "has_star", False)),
            "prose_drg_locked": parquet_locked or normalized in locked_seed,
            "puan": getattr(row, "puan", None),
            "price_try": getattr(row, "price_try", None),
            "effective_date": str(getattr(row, "effective_date", "")),
        }
    return entries


def get_ek2b_codes() -> frozenset[str]:
    """Latest EK-2B membership (as of today)."""
    return get_ek2b_codes_as_of(_coerce_asof_key(None))


def get_ek2c_codes() -> frozenset[str]:
    """Latest EK-2C membership (as of today)."""
    return get_ek2c_codes_as_of(_coerce_asof_key(None))


@lru_cache(maxsize=1)
def get_ek2a2_codes() -> frozenset[str]:
    """Return normalized EK-2/A-2 procedure codes (outpatient add-on list).

    Loads the snapshot at ``data/gazette/snapshots/asof_2026-01-31/EK-2A-2.parquet``.
    The parquet stores the code in its FIRST column (whose header is the long
    Turkish annex title); the ``İŞLEM KODU`` sentinel header row is skipped.
    Returns an empty frozenset when the file is missing or unreadable (honest
    skip — the ``procedure_in_annex: "EK-2/A-2"`` predicate then fails to match).
    """
    if not _EK2A2_SNAPSHOT_PATH.is_file():
        logger.warning("EK-2/A-2 snapshot not found: %s", _EK2A2_SNAPSHOT_PATH)
        return frozenset()
    try:
        import polars as pl

        df = pl.read_parquet(_EK2A2_SNAPSHOT_PATH)
    except Exception:  # noqa: BLE001 — any parquet/IO failure → honest skip
        logger.exception("Failed to load EK-2/A-2 snapshot %s", _EK2A2_SNAPSHOT_PATH)
        return frozenset()

    if not df.columns:
        return frozenset()
    code_col = df.columns[0]
    codes: set[str] = set()
    for value in df[code_col].to_list():
        text = str(value or "").strip()
        if not text or text == _EK2A2_HEADER_SENTINEL:
            continue
        normalized = normalize_procedure_code(text)
        # Only keep digit-ish procedure codes (skip stray annotation rows).
        if normalized and normalized.replace(".", "").replace("-", "").isdigit():
            codes.add(normalized)
    return frozenset(codes)


@lru_cache(maxsize=1)
def load_ek2d3_indication_map() -> dict[str, dict[str, object]]:
    """Return the EK-2/D-3 HBO indication map keyed by normalized ICD-10 code.

    Loads the raw parquet at ``data/gazette/raw/annex=EK-2D-3/``. The map is
    ``{icd10_code → {"indication": str, "initial_sessions": int|None,
    "max_sessions": int|None, "is_emergency": bool}}``.

    Sub-code rows (empty indication name, only an ICD-10 code) inherit the
    indication name from the most recent non-empty row above them. The header
    row (``ICD - 10 Tanı Kodları``) is skipped. Returns ``{}`` when the file is
    missing or unreadable (honest skip — ``indication_in_ek2d3`` then fails).
    """
    import glob

    pattern = str(_GAZETTE_DIR / "raw" / "annex=EK-2D-3" / "**" / "*.parquet")
    files = glob.glob(pattern, recursive=True)
    if not files:
        logger.warning("EK-2/D-3 raw parquet not found under data/gazette/raw/annex=EK-2D-3/")
        return {}
    try:
        import polars as pl

        df = pl.read_parquet(files[0])
    except Exception:  # noqa: BLE001 — any parquet/IO failure → honest skip
        logger.exception("Failed to load EK-2/D-3 parquet %s", files[0])
        return {}
    if df.height == 0 or len(df.columns) < 2:
        return {}

    import re

    col_indication = df.columns[0]
    col_icd = df.columns[1]
    col_initial = df.columns[2] if len(df.columns) > 2 else None
    col_max = df.columns[3] if len(df.columns) > 3 else None
    code_re = re.compile(r"^\s*([A-Z]\d{2,4}(?:\.\d{1,4})?)")

    indication_map: dict[str, dict[str, object]] = {}
    current_indication = ""
    for row in df.iter_rows(named=True):
        indication = str(row[col_indication] or "").strip()
        if indication:
            current_indication = indication
        icd_raw = str(row[col_icd] or "").strip().upper()
        if not icd_raw or icd_raw == _EK2D3_ICD10_HEADER.upper():
            continue
        m = code_re.match(icd_raw)
        if not m:
            continue
        code = m.group(1)
        initial = _to_int(row.get(col_initial)) if col_initial else None
        max_sess = _to_int(row.get(col_max)) if col_max else None
        # Avoid overwriting a code that already has session data with a later
        # None-valued duplicate row; keep the first non-None values.
        if code in indication_map:
            existing = indication_map[code]
            if existing["initial_sessions"] is None and initial is not None:
                existing["initial_sessions"] = initial
            if existing["max_sessions"] is None and max_sess is not None:
                existing["max_sessions"] = max_sess
            continue
        indication_map[code] = {
            "indication": current_indication,
            "initial_sessions": initial,
            "max_sessions": max_sess,
            "is_emergency": current_indication in _EK2D3_EMERGENCY_INDICATIONS,
        }
    return indication_map


def _to_int(value: object) -> int | None:
    """Coerce a parquet cell to int; return None when not numeric."""
    if value is None:
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def get_ek2d3_icd10_codes() -> frozenset[str]:
    """Return the set of normalized ICD-10 codes covered by EK-2/D-3."""
    return frozenset(load_ek2d3_indication_map().keys())


@lru_cache(maxsize=1)
def get_ek2d3_emergency_icd10_codes() -> frozenset[str]:
    """Return the ICD-10 codes flagged as emergency-listed in EK-2/D-3."""
    return frozenset(
        code
        for code, meta in load_ek2d3_indication_map().items()
        if meta.get("is_emergency")
    )


def get_ek2c_entry(
    procedure_code: str,
    *,
    as_of_date: date | str | None = None,
) -> dict[str, object] | None:
    """Return EK-2C metadata for a procedure code as of the given date."""
    normalized = normalize_procedure_code(procedure_code)
    if not normalized:
        return None
    asof_key = _coerce_asof_key(as_of_date)
    return _ek2c_entry_map_asof(asof_key).get(normalized)


def procedure_has_star(
    procedure_code: str,
    *,
    as_of_date: date | str | None = None,
) -> bool:
    entry = get_ek2c_entry(procedure_code, as_of_date=as_of_date)
    return bool(entry and entry.get("has_star"))


def procedure_prose_drg_locked(
    procedure_code: str,
    *,
    as_of_date: date | str | None = None,
) -> bool:
    """True when SUT prose requires EK-2/C package billing (§2.2.2 proviso list)."""
    entry = get_ek2c_entry(procedure_code, as_of_date=as_of_date)
    if entry and entry.get("prose_drg_locked"):
        return True
    normalized = normalize_procedure_code(procedure_code)
    return bool(normalized) and normalized in load_prose_drg_locked_code_set()


def procedure_annex_membership(
    procedure_code: str,
    *,
    as_of_date: date | str | None = None,
) -> tuple[bool, bool]:
    """Return (in_ek2b, in_ek2c) for a normalized procedure code as of date."""
    normalized = normalize_procedure_code(procedure_code)
    if not normalized:
        return False, False
    asof_key = _coerce_asof_key(as_of_date)
    ek2b = get_ek2b_codes_as_of(asof_key)
    ek2c = get_ek2c_codes_as_of(asof_key)
    return normalized in ek2b, normalized in ek2c


def codes_in_annex(annex: str, *, as_of_date: date | str | None = None) -> frozenset[str]:
    """Return the normalized code set for a named annex.

    Supports the annex identifiers that appear in the ``procedure_in_annex``
    JSON predicate: ``EK-2/A-2``, ``EK-2/A``, ``EK-2/B``, ``EK-2/C-1``,
    ``EK-2/C``. Unknown annex identifiers return an empty frozenset (the
    caller honest-skips rather than guessing).

    ``EK-2/A-2`` is loaded from the outpatient add-on snapshot; ``EK-2/B`` and
    ``EK-2/C`` use the curated history with as-of-date filtering; ``EK-2/C-1``
    is the surcharge list (no curated history, so it falls back to the EK-2/C
    set — C-1 is a strict subset of C and membership is conservative-correct).
    """
    key = (annex or "").strip().upper().replace(" ", "")
    asof_key = _coerce_asof_key(as_of_date)
    if key == "EK-2/A-2":
        return get_ek2a2_codes()
    if key == "EK-2/A":
        # EK-2/A is the outpatient visit-fee annex — not a procedure list.
        return frozenset()
    if key == "EK-2/B":
        return get_ek2b_codes_as_of(asof_key)
    if key in ("EK-2/C", "EK-2/C-1"):
        return get_ek2c_codes_as_of(asof_key)
    return frozenset()


def any_procedure_in_annex(
    procedure_codes: list[str],
    annex: str,
    *,
    as_of_date: date | str | None = None,
) -> bool:
    """True when ANY of ``procedure_codes`` is a member of ``annex``.

    Used by the ``procedure_in_annex`` JSON predicate: it checks whether ANY
    procedure line's code is in the specified annex. Codes are normalized
    (stripped of P/dots/spaces) before membership testing. Returns ``False``
    when ``annex`` is unknown or empty and when no codes match — the caller
    treats False as "predicate not satisfied" (honest skip on the rule).
    """
    annex_codes = codes_in_annex(annex, as_of_date=as_of_date)
    if not annex_codes:
        return False
    for raw in procedure_codes or []:
        normalized = normalize_procedure_code(str(raw or ""))
        if normalized and normalized in annex_codes:
            return True
    return False

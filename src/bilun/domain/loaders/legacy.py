"""
Fallback/legacy annex loaders used by optimization features.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from ..constants import EK1A_CURATED_PATH, EK2C1_CURATED_PATH, EK2G_CURATED_PATH
from ..labels import normalize_sut_display_text
from .validity import change_days, rows_in_force, version_day

logger = logging.getLogger("ilay.sut_catalog")

_ek1a_cache: pd.DataFrame | None = None
_ek2g_cache: _DatedList | None = None
_ek2c1_cache: _DatedList | None = None


def _load_ek1a_exemptions(as_of: date | str | None = None) -> pd.DataFrame:
    """EK-1A chronic disease ICD-10 exemption ranges in force on ``as_of`` (default today).

    A range SGK added later carries valid_from (e.g. G11.3 from 2018-02-15); others are
    in force on every date.
    """
    return rows_in_force(_load_ek1a_list(), as_of)


def ek1a_version_day(as_of: date | str | None = None) -> str:
    """The first day of the EK-1A version in force on ``as_of`` (default today, #292).

    Every service date from one change (a row's valid_from, the day after its valid_to)
    to the next reads the same ranges, so an index cached by this day is built once per
    version, not once per claim date.
    """
    frame = _load_ek1a_list()
    return version_day(change_days(frame.get("valid_from", ()), frame.get("valid_to", ())), as_of)


def _load_ek1a_list() -> pd.DataFrame:
    """The whole curated EK-1A list (cached)."""
    global _ek1a_cache
    if _ek1a_cache is not None:
        return _ek1a_cache

    if not EK1A_CURATED_PATH.exists():
        logger.warning("EK-1A curated parquet not found: %s", EK1A_CURATED_PATH)
        _ek1a_cache = pd.DataFrame(
            columns=["icd10_start", "icd10_end", "disease_name_tr"]
        )
        return _ek1a_cache

    try:
        _ek1a_cache = pd.read_parquet(EK1A_CURATED_PATH)
        if "disease_name_tr" in _ek1a_cache.columns:
            _ek1a_cache = _ek1a_cache.copy()
            _ek1a_cache["disease_name_tr"] = _ek1a_cache["disease_name_tr"].map(
                normalize_sut_display_text
            )
        logger.info(
            "Loaded EK-1A: %d chronic disease exemption ranges", len(_ek1a_cache)
        )
    except Exception as e:
        logger.warning("Failed to load EK-1A: %s", e)
        _ek1a_cache = pd.DataFrame(
            columns=["icd10_start", "icd10_end", "disease_name_tr"]
        )
    return _ek1a_cache


@dataclass
class _DatedList:
    """A curated list with valid_from / valid_to, the days it changes, and its rows per version."""

    frame: pd.DataFrame
    changes: tuple[str, ...]
    by_day: dict[str, Any] = field(default_factory=dict)  # keyed by the version's first day

    @classmethod
    def read(cls, path: Path, label: str, columns: list[str]) -> _DatedList:
        """The list at ``path``, empty with ``columns`` when it is missing or unreadable."""
        frame = pd.DataFrame(columns=columns)
        if not path.exists():
            logger.warning("%s curated parquet not found: %s", label, path)
        else:
            try:
                frame = pd.read_parquet(path)
                logger.info("Loaded %s: %d rows", label, len(frame))
            except Exception as e:
                logger.warning("Failed to load %s: %s", label, e)
        return cls(frame, change_days(frame.get("valid_from", ()), frame.get("valid_to", ())))

    def version_day(self, as_of: date | str | None) -> str:
        return version_day(self.changes, as_of)


def _load_ek2g_no_surcharge(as_of: date | str | None = None) -> dict[str, str]:
    """EK-2G procedures where additional fees are prohibited, in force on ``as_of`` (default today).

    614980 is on the list until 2022-02-15 (Mülga), 614981 from 2022-02-16 (Ek); the other
    rows are in force on every date. A procedure keeps the name of its first row.
    """
    ek2g = _load_ek2g_list()
    day = ek2g.version_day(as_of)
    if day not in ek2g.by_day:
        rows = rows_in_force(ek2g.frame, day).drop_duplicates(subset=["procedure_code"])
        ek2g.by_day[day] = dict(zip(rows["procedure_code"], rows["procedure_name"]))
    return ek2g.by_day[day]


def ek2g_version_day(as_of: date | str | None = None) -> str:
    """The first day of the EK-2G version in force on ``as_of`` (default today), see ek1a_version_day."""
    return _load_ek2g_list().version_day(as_of)


def _load_ek2g_list() -> _DatedList:
    global _ek2g_cache
    if _ek2g_cache is None:
        _ek2g_cache = _DatedList.read(EK2G_CURATED_PATH, "EK-2G", ["procedure_code", "procedure_name"])
    return _ek2g_cache


def _load_ek2c1_copay_rates(as_of: date | str | None = None) -> dict[str, dict[str, Any]]:
    """EK-2C-1 procedures with explicit copayment rate percentages, in force on ``as_of`` (default today).

    P552001-3 and P552006-8 are 60 until 2022-09-02 and 100 from 2022-09-03 (Değişik);
    P619410 is on the list until 2025-03-14 (Mülga).
    """
    ek2c1 = _load_ek2c1_list()
    day = ek2c1.version_day(as_of)
    if day not in ek2c1.by_day:
        ek2c1.by_day[day] = {
            row["procedure_code"]: {
                "procedure_name": row["procedure_name"],
                "copay_rate_pct": float(row["copay_rate_pct"]),
            }
            for _, row in rows_in_force(ek2c1.frame, day).iterrows()
        }
    return ek2c1.by_day[day]


def ek2c1_version_day(as_of: date | str | None = None) -> str:
    """The first day of the EK-2C-1 version in force on ``as_of`` (default today), see ek1a_version_day."""
    return _load_ek2c1_list().version_day(as_of)


def _load_ek2c1_list() -> _DatedList:
    global _ek2c1_cache
    if _ek2c1_cache is None:
        columns = ["procedure_code", "procedure_name", "copay_rate_pct"]
        _ek2c1_cache = _DatedList.read(EK2C1_CURATED_PATH, "EK-2C-1", columns)
    return _ek2c1_cache

"""Service-date filtering of curated lists that carry valid_from / valid_to.

The EK-1A and EK-3O curated lists date the rows SGK added, amended or repealed after the
list's own date (scripts/sut/_common.py::_add_list_validity); the EK-2/A-2 history dates
every version's rows (_add_validity_ranges). Both columns hold YYYY-MM-DD strings; null
means open, so an undated row is in force on every date. A claim line reads them on its
service date (``service_date_of``); today is the default only where no date exists.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable
from datetime import date, datetime, timedelta

import pandas as pd
import polars as pl


def as_of_iso(as_of: date | datetime | str | None) -> str:
    """The date a dated list is read on, as YYYY-MM-DD: the given date, or today."""
    if as_of is None:
        return date.today().isoformat()
    if isinstance(as_of, datetime):
        return as_of.date().isoformat()
    if isinstance(as_of, date):
        return as_of.isoformat()
    return str(as_of).strip()[:10]


def service_date_of(line_date: object, claim: object | None = None) -> date | None:
    """The date a claim line's dated lists are read on (#292): its own date, else its claim's.

    The claim's date is its admission date, else its start date. None and ``date.min`` (the
    claims loader's "date unknown" marker) are no date; None when neither has one, so the
    reader falls back to today.
    """
    candidates = [line_date]
    if claim is not None:
        candidates += [
            getattr(claim, "admission_date", None),
            getattr(claim, "claim_start_date", None),
        ]
    for day in candidates:
        if isinstance(day, datetime):
            return day.date()
        if isinstance(day, date) and day != date.min:
            return day
    return None


# The day of a list's first version: no dated row has started or ended yet.
FIRST_VERSION_DAY = "0001-01-01"


def change_days(valid_from: Iterable[object], valid_to: Iterable[object]) -> tuple[str, ...]:
    """The days a dated list changes, sorted: a row's valid_from, the day after its valid_to."""
    days: set[str] = set()
    for values, shift in ((valid_from, 0), (valid_to, 1)):
        for value in values:
            try:
                day = date.fromisoformat(str(value).strip()[:10])
            except ValueError:  # null (None, NaN, <NA>) or not a date
                continue
            days.add((day + timedelta(days=shift)).isoformat())
    return tuple(sorted(days))


def version_day(changes: tuple[str, ...], as_of: date | datetime | str | None) -> str:
    """The first day of the list version in force on ``as_of`` (default today).

    Every day from one change day to the next reads the same rows, so an index cached by
    this day holds one entry per list version, not one per service date of the bills.
    """
    index = bisect_right(changes, as_of_iso(as_of))
    return changes[index - 1] if index else FIRST_VERSION_DAY


def rows_in_force(frame: pd.DataFrame, as_of: date | datetime | str | None = None) -> pd.DataFrame:
    """The rows in force on ``as_of`` (default today); a list without the columns is whole."""
    day = as_of_iso(as_of)
    keep = pd.Series(True, index=frame.index)
    if "valid_from" in frame.columns:
        keep &= frame["valid_from"].isna() | (frame["valid_from"].astype(str) <= day)
    if "valid_to" in frame.columns:
        keep &= frame["valid_to"].isna() | (frame["valid_to"].astype(str) >= day)
    return frame[keep]


def in_force(frame: pl.DataFrame, as_of: date | datetime | str | None = None) -> pl.DataFrame:
    """``rows_in_force`` for a Polars frame."""
    day = as_of_iso(as_of)
    if "valid_from" in frame.columns:
        frame = frame.filter(pl.col("valid_from").is_null() | (pl.col("valid_from") <= day))
    if "valid_to" in frame.columns:
        frame = frame.filter(pl.col("valid_to").is_null() | (pl.col("valid_to") >= day))
    return frame

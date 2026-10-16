"""Service-date filtering of curated lists that carry valid_from / valid_to.

The EK-1A and EK-3O curated lists date the rows SGK added, amended or repealed after the
list's own date (scripts/sut/_common.py::_add_list_validity). Both columns hold
YYYY-MM-DD strings; null means open, so an undated row is in force on every date.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd


def as_of_iso(as_of: date | datetime | str | None) -> str:
    """The date a dated list is read on, as YYYY-MM-DD: the given date, or today."""
    if as_of is None:
        return date.today().isoformat()
    if isinstance(as_of, datetime):
        return as_of.date().isoformat()
    if isinstance(as_of, date):
        return as_of.isoformat()
    return str(as_of).strip()[:10]


def rows_in_force(frame: pd.DataFrame, as_of: date | datetime | str | None = None) -> pd.DataFrame:
    """The rows in force on ``as_of`` (default today); a list without the columns is whole."""
    day = as_of_iso(as_of)
    keep = pd.Series(True, index=frame.index)
    if "valid_from" in frame.columns:
        keep &= frame["valid_from"].isna() | (frame["valid_from"].astype(str) <= day)
    if "valid_to" in frame.columns:
        keep &= frame["valid_to"].isna() | (frame["valid_to"].astype(str) >= day)
    return frame[keep]

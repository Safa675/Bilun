"""
EK-4A version timeline from the raw list partitions.

SGK republishes EK-4A in every consolidated SUT package. A list's footer starts with
"RG-dd/mm/yyyy", the Official Gazette date from which it applies. When a newer list
replaces it, SGK keeps the old one as "MÜLGA ... (Yür. dd.mm.yyyy)", and that date is
the day it stopped applying, not a start date. The converter stores it as the raw
partition's effective_date. So a version is valid from its footer's RG date until the
next version's RG date, and a MÜLGA date must equal that next RG date. A MÜLGA date
before the next RG date is a gap: a version SGK no longer ships. One after it would be
an overlap, which is refused.

Marker rows inside a version ((*), (**), (***) footnotes) are not resolved here.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from scripts.sut._common import _data_cols, _safe_str

_RG_DATE = re.compile(r"RG-\s*(\d{2})[./](\d{2})[./](\d{4})")


@dataclass(frozen=True)
class Ek4aVersion:
    valid_from: dt.date
    valid_to: dt.date | None  # exclusive; None for the current list
    parquet_path: str  # relative to the raw parquet root
    footer: str


def ek4a_footer(df: pd.DataFrame) -> str:
    """The single "Yürürlük" footer cell of a raw EK-4A list, whitespace-normalized."""
    first = _data_cols(df)[0]
    footers = [" ".join(_safe_str(value).split()) for value in df[first] if "Yürürlük" in _safe_str(value)]
    if len(footers) != 1:
        raise ValueError(f"EK-4A list needs exactly one Yürürlük footer, found {len(footers)}")
    return footers[0]


def publication_date(footer: str) -> dt.date:
    match = _RG_DATE.search(footer)
    if match is None:
        raise ValueError("EK-4A footer has no RG publication date")
    day, month, year = (int(value) for value in match.groups())
    return dt.date(year, month, day)


def ek4a_timeline(raw_root: Path) -> tuple[list[Ek4aVersion], list[tuple[dt.date, dt.date]]]:
    """All EK-4A versions oldest first, plus the [start, end) gaps no version covers."""
    found = []
    for path in sorted(raw_root.glob("annex=EK-4A/effective_date=*/*.parquet")):
        partition = path.parent.name.split("=", 1)[1]
        replaced_on = None if partition == "unknown" else dt.date.fromisoformat(partition)
        footer = ek4a_footer(pd.read_parquet(path))
        found.append((publication_date(footer), replaced_on, path.relative_to(raw_root).as_posix(), footer))
    if not found:
        raise ValueError("No raw EK-4A partitions found")
    found.sort(key=lambda item: item[0])
    starts = [item[0] for item in found]
    if len(set(starts)) != len(starts):
        raise ValueError("Two EK-4A versions share an RG publication date")

    versions: list[Ek4aVersion] = []
    gaps: list[tuple[dt.date, dt.date]] = []
    for index, (valid_from, replaced_on, parquet_path, footer) in enumerate(found):
        if index == len(found) - 1:
            if replaced_on is not None:
                raise ValueError("The newest EK-4A version is MÜLGA; the current list is missing")
        elif replaced_on is None:
            raise ValueError(f"Only the newest EK-4A version may be current: {parquet_path}")
        else:
            next_from = found[index + 1][0]
            if not valid_from < replaced_on <= next_from:
                raise ValueError(
                    f"EK-4A {parquet_path} replaced on {replaced_on} does not fit between "
                    f"{valid_from} and the next version ({next_from})"
                )
            if replaced_on < next_from:
                gaps.append((replaced_on, next_from))
        versions.append(Ek4aVersion(valid_from, replaced_on, parquet_path, footer))
    return versions, gaps

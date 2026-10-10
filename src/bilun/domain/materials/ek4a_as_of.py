"""
src/bilun/domain/materials/ek4a_as_of.py
EK-4A as it applied on a service date.

Reads the curated history built by scripts/sut/catalogs/ek4a_history.py. The list version
whose window holds the service date gives the drugs. A date in a gap between versions gives
no drugs (coverage "gap"), and a date before the oldest version uses the oldest version
(coverage "before_history"; the synthetic demo cohort is dated 2023-2024). Each drug's
entry, activation and passivation dates are then evaluated on the service date itself:
  not_yet_listed  every entry date is after the service date
  passive         the latest activation/passivation event on or before it is a passivation
                  (a passivation wins a same-day tie)
  active          otherwise
  undated         a date cell holds text but no readable date
The history's span status ("ok", "duplicate_kamu_no", "unrecognized_marker",
"unknown_predecessor") is passed through; a row whose status is not "ok" is not a fact.
"""

from __future__ import annotations

import bisect
import datetime as dt
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

import polars as pl

from ..constants import EK4A_HISTORY_PATH, EK4A_WINDOWS_PATH
from ..utils import _safe_float, turkish_lower

Coverage = Literal["covered", "before_history", "gap", "unavailable"]

_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DMY_DATE = re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})[./](\d{4})")
_TEXT_FIELDS = (
    "kamu_no", "barcode", "drug_name", "equivalence_group", "therapeutic_group", "discount_status",
    "special_discount", "pharmacist_discount", "entry_date", "activation_date", "passivation_date",
)


def cell_dates(cell: str | None) -> list[dt.date] | None:
    """Dates in an EK-4A date cell: [] when empty, None when it has text but no readable date."""
    text = (cell or "").strip()
    if not text:
        return []
    parts = [(int(y), int(m), int(d)) for y, m, d in _ISO_DATE.findall(text)]
    parts += [(int(y), int(m), int(d)) for d, m, y in _DMY_DATE.findall(text)]
    try:
        dates = [dt.date(*part) for part in parts]
    except ValueError:
        return None
    return dates or None


def drug_state(entry: str | None, activation: str | None, passivation: str | None, on: dt.date) -> str:
    """Whether an EK-4A row is listed and active on a date, from its own date cells."""
    entries, activations, passivations = (cell_dates(cell) for cell in (entry, activation, passivation))
    if entries is None or activations is None or passivations is None:
        return "undated"
    if entries and min(entries) > on:
        return "not_yet_listed"
    # (day, 1) for a passivation sorts after (day, 0), so a passivation wins a same-day tie.
    events = [(day, 0) for day in activations if day <= on] + [(day, 1) for day in passivations if day <= on]
    return "passive" if events and max(events)[1] == 1 else "active"


@dataclass(frozen=True)
class _Slice:
    """Spans valid on one stretch of dates, with lookup indexes."""

    rows: tuple[dict[str, Any], ...]
    by_barcode: dict[str, tuple[int, ...]]
    by_kamu_no: dict[str, tuple[int, ...]]
    by_name: dict[str, tuple[int, ...]]


@dataclass(frozen=True)
class Ek4aAsOf:
    service_date: dt.date
    coverage: Coverage
    list_valid_from: dt.date | None
    _slice: _Slice | None

    def _records(self, indexes: tuple[int, ...] | range) -> list[dict[str, Any]]:
        if self._slice is None:
            return []
        records = []
        for index in indexes:
            row = self._slice.rows[index]
            state = drug_state(row["entry_date"], row["activation_date"], row["passivation_date"],
                               self.service_date)
            records.append(dict(row, state=state, coverage=self.coverage,
                                list_valid_from=self.list_valid_from.isoformat()))
        return records

    def drugs(self) -> list[dict[str, Any]]:
        return self._records(range(len(self._slice.rows))) if self._slice else []

    def by_barcode(self, barcode: str) -> list[dict[str, Any]]:
        """Rows whose current or old barcode matches."""
        return self._records(self._slice.by_barcode.get(barcode.strip(), ()) if self._slice else ())

    def by_kamu_no(self, kamu_no: str) -> list[dict[str, Any]]:
        return self._records(self._slice.by_kamu_no.get(kamu_no.strip(), ()) if self._slice else ())

    def by_name(self, name: str) -> list[dict[str, Any]]:
        """Rows whose Turkish-lowered name equals the query."""
        return self._records(self._slice.by_name.get(turkish_lower(name.strip()), ()) if self._slice else ())


@lru_cache(maxsize=1)
def _load() -> tuple[pl.DataFrame, tuple[tuple[str, dt.date, dt.date | None], ...], tuple[dt.date, ...]] | None:
    if not (EK4A_HISTORY_PATH.is_file() and EK4A_WINDOWS_PATH.is_file()):
        return None
    spans = pl.read_parquet(EK4A_HISTORY_PATH).with_columns(
        pl.col("valid_from").str.to_date(), pl.col("valid_until").str.to_date())
    windows = tuple(
        (row["kind"], dt.date.fromisoformat(row["valid_from"]),
         None if row["valid_until"] is None else dt.date.fromisoformat(row["valid_until"]))
        for row in pl.read_parquet(EK4A_WINDOWS_PATH).iter_rows(named=True))
    bounds = sorted({*spans["valid_from"].to_list(), *spans["valid_until"].drop_nulls().to_list(),
                     *(start for _, start, _ in windows), *(end for _, _, end in windows if end)})
    return spans, windows, tuple(bounds)


def _record(row: dict[str, Any]) -> dict[str, Any]:
    record = {field: str(row.get(field) or "").strip() for field in _TEXT_FIELDS}
    record["old_barcodes"] = [code.strip() for code in str(row.get("old_barcodes") or "").split("\n") if code.strip()]
    for tier in range(1, 5):
        record[f"discount_tier_{tier}"] = _safe_float(str(row.get(f"discount_tier_{tier}") or "").replace(",", "."))
    record["status"] = str(row.get("status") or "")
    return record


def _freeze(index: dict[str, list[int]]) -> dict[str, tuple[int, ...]]:
    return {key: tuple(value) for key, value in index.items()}


# A slice holds about 8,200 rows; few stretches are in use at once (demo dates share one).
@lru_cache(maxsize=4)
def _slice(start: dt.date) -> _Slice:
    """Spans valid from `start` until the next boundary; every date in that stretch shares them."""
    spans = _load()[0]
    valid = spans.filter((pl.col("valid_from") <= start)
                         & (pl.col("valid_until").is_null() | (pl.col("valid_until") > start)))
    rows = tuple(_record(row) for row in valid.iter_rows(named=True))
    by_barcode: dict[str, list[int]] = {}
    by_kamu_no: dict[str, list[int]] = {}
    by_name: dict[str, list[int]] = {}
    for index, row in enumerate(rows):
        for code in {row["barcode"], *row["old_barcodes"]} - {""}:
            by_barcode.setdefault(code, []).append(index)
        by_kamu_no.setdefault(row["kamu_no"], []).append(index)
        by_name.setdefault(turkish_lower(row["drug_name"]), []).append(index)
    return _Slice(rows, _freeze(by_barcode), _freeze(by_kamu_no), _freeze(by_name))


def ek4a_as_of(service_date: dt.date) -> Ek4aAsOf:
    """EK-4A on a service date; see the module docstring for coverage and drug states."""
    if type(service_date) is not dt.date:
        raise TypeError("service_date must be a datetime.date")
    loaded = _load()
    if loaded is None:
        return Ek4aAsOf(service_date, "unavailable", None, None)
    _, windows, bounds = loaded
    if any(kind == "gap" and start <= service_date < end for kind, start, end in windows):
        return Ek4aAsOf(service_date, "gap", None, None)
    versions = sorted((start, end) for kind, start, end in windows if kind == "version")
    on, coverage = service_date, "covered"
    if service_date < versions[0][0]:
        on, coverage = versions[0][0], "before_history"
    version = next(start for start, end in versions if start <= on and (end is None or on < end))
    stretch = bounds[bisect.bisect_right(bounds, on) - 1]
    return Ek4aAsOf(service_date, coverage, version, _slice(stretch))

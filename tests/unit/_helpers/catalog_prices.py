"""The list price of an EK-2B, EK-2C or EK-2Ç code on a date, read straight from the committed curated histories.

A test that bills a line "at list" or expects the engine to price a day, a package or a test at its list price
asks this module for the number instead of typing it, so a catalog change (a new list, #299's cut at the kuruş)
moves no test file. The oracle reads `data/gazette/curated/{ek2b,ek2c,ek2c_dental}_catalog_history.parquet` with
polars and never goes through the engine's loaders (`src.bilun.domain.loaders`, `lookup_procedure_code`), so a test
that compares the engine's price with the list still compares two independent readings of the same file.

- `list_price(code, on)`: `price_try` of the one row of `code` in force on `on` (`valid_from <= on <= valid_to`,
  an open `valid_to` is in force). EK-2C keys on `package_code` ("P610131"), EK-2B and EK-2Ç on `code`; the three
  lists share no code, so no annex is named.
- `list_puan(code, on)`: the puan of that row.
- `list_total(code, on, units)`: `units` × the list price, exact to the kuruş (Decimal), as a float.
- `list_text(code, on, units)`: the same amount as a two-decimal string, for a `Decimal(...)` billed amount.
"""

from __future__ import annotations

import functools
from datetime import date
from decimal import Decimal
from pathlib import Path

import polars as pl

_CURATED = Path(__file__).resolve().parents[3] / "data" / "gazette" / "curated"
_HISTORIES = (
    ("ek2b_catalog_history.parquet", "code"),
    ("ek2c_catalog_history.parquet", "package_code"),
    ("ek2c_dental_catalog_history.parquet", "code"),
)


@functools.cache
def _history() -> pl.DataFrame:
    return pl.concat(
        pl.read_parquet(_CURATED / name, columns=[key, "puan", "price_try", "valid_from", "valid_to"]).rename(
            {key: "code"}
        )
        for name, key in _HISTORIES
    )


@functools.cache
def _row(code: str, on: str) -> tuple[float, float]:
    rows = _history().filter(
        (pl.col("code") == code)
        & (pl.col("valid_from") <= on)
        & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= on))
    )
    if rows.height != 1:
        raise LookupError(f"{code} has {rows.height} rows in force on {on} in the curated catalog histories")
    puan, price = rows.row(0)[1:3]
    if price is None:
        raise LookupError(f"{code} has no list price on {on}")
    return puan, price


def _day(on: date | str) -> str:
    return on.isoformat() if isinstance(on, date) else on


def list_price(code: str, on: date | str) -> float:
    """The list price (`price_try`) of `code` in force on `on`."""
    return _row(code, _day(on))[1]


def list_puan(code: str, on: date | str) -> float:
    """The puan of the row of `code` in force on `on`."""
    return _row(code, _day(on))[0]


def list_total(code: str, on: date | str, units: int = 1) -> float:
    """`units` × the list price of `code` on `on`, exact to the kuruş."""
    return float(Decimal(str(list_price(code, on))) * units)


def list_text(code: str, on: date | str, units: int = 1) -> str:
    """`list_total` as a two-decimal string ("222.35"), the shape of a billed amount."""
    return f"{Decimal(str(list_price(code, on))) * units:.2f}"

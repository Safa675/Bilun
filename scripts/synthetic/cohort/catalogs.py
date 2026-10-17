"""Curated catalog lookups for composing synthetic SUT claims (Polars, lazy & cached)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from functools import cached_property
from pathlib import Path

import polars as pl

REPO = Path(__file__).resolve().parents[3]
EK3F1_FROM = "2025-12-13"
_ZERO = Decimal("0.00")


class CatalogError(ValueError):
    """Raised when a catalog lookup finds zero or multiple in-force rows, or an out-of-range date."""


@dataclass(frozen=True)
class CatalogRow:
    """Single in-force catalog entry returned by ``CohortCatalogs``."""

    code: str
    name: str
    price: Decimal
    source: str

    @property
    def price_try(self) -> Decimal:
        return self.price


def _iso_date(on: date | str, *, catalog: str, code: str) -> str:
    if isinstance(on, date) and not isinstance(on, datetime):
        return on.isoformat()
    if isinstance(on, str):
        try:
            return date.fromisoformat(on).isoformat()
        except ValueError as exc:
            raise CatalogError(f"{catalog} {code!r}: invalid ISO date {on!r}") from exc
    raise CatalogError(f"{catalog} {code!r}: invalid date {on!r}")


class CohortCatalogs:
    """Lazily loads EK-2B, EK-2C, EK-3/F-1 and EK-4A curated Parquet tables once with Polars."""

    def __init__(self, root: Path = REPO) -> None:
        self.root = Path(root)

    def _read_parquet(self, relative: str, columns: list[str]) -> pl.DataFrame:
        return pl.read_parquet(self.root / relative, columns=columns)

    @cached_property
    def ek2b(self) -> pl.DataFrame:
        return self._read_parquet(
            "data/gazette/curated/ek2b_catalog_history.parquet",
            ["code", "name", "puan", "price_try", "valid_from", "valid_to"],
        )

    @cached_property
    def ek2c(self) -> pl.DataFrame:
        return self._read_parquet(
            "data/gazette/curated/ek2c_catalog_history.parquet",
            ["package_code", "name", "group", "puan", "price_try", "valid_from", "valid_to"],
        )

    @cached_property
    def ek3f1(self) -> pl.DataFrame:
        return self._read_parquet(
            "data/gazette/curated/ek3f1_arthroplasty_materials.parquet",
            ["sut_code", "material_name", "description", "price_try"],
        )

    @cached_property
    def ek4a(self) -> pl.DataFrame:
        return self._read_parquet(
            "data/gazette/curated/ek4a_history.parquet",
            ["kamu_no", "barcode", "drug_name", "valid_from", "valid_until"],
        )

    def procedure_row(self, code: str, on: date | str) -> CatalogRow:
        """Return the EK-2C (for P-codes) or EK-2B row in force on ``on`` (inclusive ``valid_to``)."""
        is_pkg = code.startswith("P")
        catalog = "EK-2C" if is_pkg else "EK-2B"
        d = _iso_date(on, catalog=catalog, code=code)
        df = self.ek2c if is_pkg else self.ek2b
        code_col = "package_code" if is_pkg else "code"
        rows = df.filter(
            (pl.col(code_col) == code)
            & (pl.col("valid_from") <= d)
            & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= d))
        )
        if rows.height != 1:
            raise CatalogError(
                f"{catalog} {code!r} on {d}: expected 1 row in force, found {rows.height}"
            )
        r = rows.row(0, named=True)
        return CatalogRow(
            code=code,
            name=r["name"],
            price=Decimal(str(r["price_try"])),
            source=f"{catalog} valid_from {r['valid_from']}",
        )

    def material_row(self, code: str, on: date | str) -> CatalogRow:
        """Return the EK-3/F-1 row for ``code`` on ``on`` (in force from 2025-12-13)."""
        d = _iso_date(on, catalog="EK-3F-1", code=code)
        if d < EK3F1_FROM:
            raise CatalogError(
                f"EK-3F-1 {code!r} on {d}: curated list is in force from {EK3F1_FROM}"
            )
        rows = self.ek3f1.filter(pl.col("sut_code") == code)
        if rows.height != 1:
            raise CatalogError(f"EK-3F-1 {code!r} on {d}: expected 1 row, found {rows.height}")
        r = rows.row(0, named=True)
        name = " | ".join(part for part in (r["material_name"], r["description"]) if part)
        return CatalogRow(
            code=code,
            name=name,
            price=Decimal(str(r["price_try"])),
            source=f"EK-3F-1 from {EK3F1_FROM} (curated ek3f1_arthroplasty_materials)",
        )

    def drug_row(self, barcode: str, on: date | str) -> CatalogRow:
        """Return the EK-4A row for ``barcode`` in force on ``on`` (exclusive ``valid_until``)."""
        d = _iso_date(on, catalog="EK-4A", code=barcode)
        rows = self.ek4a.filter(
            (pl.col("barcode") == barcode)
            & (pl.col("valid_from") <= d)
            & (pl.col("valid_until").is_null() | (pl.col("valid_until") > d))
        )
        if rows.height != 1:
            raise CatalogError(
                f"EK-4A {barcode!r} on {d}: expected 1 row in force, found {rows.height}"
            )
        r = rows.row(0, named=True)
        return CatalogRow(
            code=barcode,
            name=r["drug_name"],
            price=_ZERO,
            source=f"EK-4A {r['kamu_no']} from {r['valid_from']}",
        )

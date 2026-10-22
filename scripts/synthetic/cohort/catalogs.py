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
# The curated EK-3/C-2 list (external orthoses and prostheses) is the raw partition annex=EK-3C-2/effective_date=
# 2026-01-24 (the list "Yür. 24.01.2026" of the 2026-10-02 SUT; scripts/sut/catalogs/hierarchical_materials.py).
EK3C2_FROM = "2026-01-24"
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
    """Lazily loads EK-2B, EK-2C, EK-3/F-1, EK-3/C-2 and EK-4A curated Parquet tables once with Polars."""

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
    def ek3c2(self) -> pl.DataFrame:
        return self._read_parquet(
            "data/gazette/curated/ek3c2_materials.parquet",
            ["sut_code", "material_name", "price_try"],
        )

    @cached_property
    def ek4a(self) -> pl.DataFrame:
        return self._read_parquet(
            "data/gazette/curated/ek4a_history.parquet",
            ["kamu_no", "barcode", "drug_name", "valid_from", "valid_until"],
        )

    @cached_property
    def icd10_tr(self) -> pl.DataFrame:
        return self._read_parquet(
            "data/synthetic/reference/icd10_tr.parquet",
            ["code", "name_tr"],
        )

    @cached_property
    def icd_names_map(self) -> dict[str, str]:
        df = self.icd10_tr
        return dict(zip(df["code"].to_list(), df["name_tr"].to_list(), strict=True))

    @cached_property
    def drug_crosswalk(self) -> pl.DataFrame:
        return self._read_parquet(
            "data/synthetic/reference/drug_crosswalk.parquet",
            ["barcode", "titck_product_name"],
        )

    @cached_property
    def titck_names_map(self) -> dict[str, str]:
        valid = self.drug_crosswalk.filter(pl.col("titck_product_name").is_not_null())
        return dict(
            zip(valid["barcode"].to_list(), valid["titck_product_name"].to_list(), strict=True)
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

    def material_row(self, code: str, on: date | str, annex: str = "EK-3F-1") -> CatalogRow:
        """Return the row for ``code`` on ``on`` of its EK-3 ``annex``: EK-3/F-1 (in force from 2025-12-13; the name is
        the site and the description joined) or EK-3/C-2 (in force from 2026-01-24; the name is the device's, the
        description being the report it needs)."""
        if annex not in ("EK-3F-1", "EK-3C-2"):
            raise CatalogError(f"{annex} {code!r}: not an EK-3 annex the cohort prices (EK-3F-1, EK-3C-2)")
        d = _iso_date(on, catalog=annex, code=code)
        start = EK3F1_FROM if annex == "EK-3F-1" else EK3C2_FROM
        if d < start:
            raise CatalogError(f"{annex} {code!r} on {d}: curated list is in force from {start}")
        frame = self.ek3f1 if annex == "EK-3F-1" else self.ek3c2
        rows = frame.filter(pl.col("sut_code") == code)
        if rows.height != 1:
            raise CatalogError(f"{annex} {code!r} on {d}: expected 1 row, found {rows.height}")
        r = rows.row(0, named=True)
        if annex == "EK-3F-1":
            name = " | ".join(part for part in (r["material_name"], r["description"]) if part)
            curated = "ek3f1_arthroplasty_materials"
        else:
            name, curated = r["material_name"], "ek3c2_materials"
        return CatalogRow(
            code=code,
            name=name,
            price=Decimal(str(r["price_try"])),
            source=f"{annex} from {start} (curated {curated})",
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

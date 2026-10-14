"""Shared loaders for the money / expected-outputs / MEDULA audit layer.

Read-only access to the synthetic cohort and the curated reference catalogs.
Never touches ilay_validation/ or raw data.
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

REPO = Path("/home/safa/Documents/Bilun")
CLAIMS = REPO / "data/synthetic/sut/claims"
CLEAN = REPO / "data/synthetic/sut/clean"
GAZ = REPO / "data/gazette/curated"
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

pl.Config.set_tbl_cols(40)
pl.Config.set_tbl_width_chars(220)
pl.Config.set_fmt_str_lengths(70)
pl.Config.set_tbl_rows(120)


def claims(name: str) -> pl.DataFrame:
    assert "ilay_validation" not in name
    return pl.read_parquet(CLAIMS / f"{name}.parquet")


def clean(name: str) -> pl.DataFrame:
    return pl.read_parquet(CLEAN / f"{name}.parquet")


def ek2b() -> pl.DataFrame:
    return pl.read_parquet(GAZ / "ek2b_catalog_history.parquet")


def ek2c() -> pl.DataFrame:
    return pl.read_parquet(GAZ / "ek2c_catalog_history.parquet")


def ek4a() -> pl.DataFrame:
    return pl.read_parquet(GAZ / "ek4a_history.parquet")


def catalog_versions() -> pl.DataFrame:
    """Union of EK-2B (6/7-char codes) and EK-2C (P-codes) price rows.

    Drops zero/negative-length windows (valid_to < valid_from), which are
    removal markers rather than price periods.
    """
    b = ek2b().select(
        pl.col("code"), "name", "price_try", "valid_from", "valid_to",
        pl.lit("EK-2B").alias("annex"),
    )
    c = ek2c().select(
        pl.col("package_code").alias("code"), "name", "price_try", "valid_from", "valid_to",
        pl.lit("EK-2C").alias("annex"),
    )
    u = pl.concat([b, c])
    u = u.filter(pl.col("valid_to").is_null() | (pl.col("valid_to") >= pl.col("valid_from")))
    return u


def asof_join(lines: pl.DataFrame, code_col: str, date_col: str) -> pl.DataFrame:
    """Attach the in-force catalog row (valid_from <= date <= valid_to) to each line.

    Returns lines with list_price_try / list_name / list_annex / n_asof_matches.
    Lines without a match keep nulls. Ambiguity (n_asof_matches>1) is reported.
    """
    cat = catalog_versions()
    j = (
        lines.with_row_index("_rid")
        .join(cat, left_on=code_col, right_on="code", how="left")
        .filter(
            pl.col("valid_from").is_null()
            | (
                (pl.col("valid_from") <= pl.col(date_col))
                & (pl.col("valid_to").is_null() | (pl.col(date_col) <= pl.col("valid_to")))
            )
        )
    )
    agg = j.group_by("_rid").agg(
        pl.col("price_try").first().alias("list_price_try"),
        pl.col("name").first().alias("list_name"),
        pl.col("annex").first().alias("list_annex"),
        pl.col("valid_from").first().alias("list_valid_from"),
        pl.col("price_try").n_unique().alias("n_distinct_asof_prices"),
        pl.col("price_try").drop_nulls().len().alias("n_asof_matches"),
    )
    return lines.with_row_index("_rid").join(agg, on="_rid", how="left").drop("_rid")

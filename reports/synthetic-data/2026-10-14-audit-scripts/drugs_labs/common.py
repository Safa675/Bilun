"""Shared loaders for the drugs/labs audit layer (read-only on the repo).

Only synthetic-cohort files and curated reference catalogs are read.
Nothing under claims/ilay_validation or "raw data/" is touched.
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

REPO = Path("/home/safa/Documents/Bilun")
SYN = REPO / "data/synthetic/sut"
CUR = REPO / "data/gazette/curated"
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

pl.Config.set_tbl_rows(60)
pl.Config.set_tbl_cols(30)
pl.Config.set_fmt_str_lengths(70)
pl.Config.set_tbl_width_chars(220)


def drugs() -> pl.DataFrame:
    return pl.read_parquet(SYN / "claims/drug_claim_lines.parquet").with_columns(
        pl.col("drug_claim_date").str.to_date().alias("d_date"),
        pl.col("drug_name").str.replace_all(r"\s+", " ").str.strip_chars().alias("drug_name_n"),
    )


def recete() -> pl.DataFrame:
    return pl.read_parquet(SYN / "clean/recete_clean.parquet").with_columns(
        pl.col("RECETE_TARIH").dt.date().alias("r_date"),
        pl.col("ilac_adi").str.replace_all(r"\s+", " ").str.strip_chars().alias("ilac_adi_n"),
    )


def labs() -> pl.DataFrame:
    return pl.read_parquet(SYN / "clean/lab_clean.parquet").with_columns(
        pl.col("tarih").dt.date().alias("l_date")
    )


def headers() -> pl.DataFrame:
    return pl.read_parquet(SYN / "claims/claim_headers.parquet").with_columns(
        pl.col("claim_start_date").str.to_date().alias("start"),
        pl.col("claim_end_date").str.to_date().alias("end"),
    )


def proc() -> pl.DataFrame:
    return pl.read_parquet(SYN / "claims/procedure_claim_lines.parquet").with_columns(
        pl.col("procedure_date").str.to_date().alias("p_date")
    )


def dx() -> pl.DataFrame:
    return pl.read_parquet(SYN / "claims/claim_diagnoses.parquet")


def anadata() -> pl.DataFrame:
    return pl.read_parquet(SYN / "clean/anadata_clean.parquet")


def ek4a() -> pl.DataFrame:
    return pl.read_parquet(CUR / "ek4a_history.parquet").with_columns(
        pl.col("valid_from").str.to_date().alias("vf"),
        pl.col("valid_until").str.to_date().alias("vu"),
        pl.col("drug_name").str.replace_all(r"\s+", " ").str.strip_chars().alias("ek_name_n"),
    )


def ek2b() -> pl.DataFrame:
    return pl.read_parquet(CUR / "ek2b_catalog_history.parquet").with_columns(
        pl.col("valid_from").str.to_date().alias("vf"),
        pl.col("valid_to").str.to_date().alias("vt"),
    )


def save(df: pl.DataFrame, name: str) -> None:
    df.write_csv(OUT / f"{name}.csv")


def hdr(title: str) -> None:
    print("\n" + "=" * 8 + " " + title + " " + "=" * 8)

"""Read-only catalog helpers for the showcase-story drafts."""
from __future__ import annotations
from pathlib import Path
import polars as pl
ROOT = Path(__file__).resolve().parents[3]
EK2B = pl.read_parquet(f"{ROOT}/data/gazette/curated/ek2b_catalog_history.parquet")
EK2C = pl.read_parquet(f"{ROOT}/data/gazette/curated/ek2c_catalog_history.parquet")
EK4A = pl.read_parquet(f"{ROOT}/data/gazette/curated/ek4a_history.parquet")

def _inforce(df: pl.DataFrame, d: str, until_col: str = "valid_to") -> pl.DataFrame:
    return df.filter((pl.col("valid_from") <= d) & (pl.col(until_col).is_null() | (pl.col(until_col) >= d)))

def ek2b(code: str, d: str) -> pl.DataFrame:
    return _inforce(EK2B.filter(pl.col("code") == code), d).select("code", "name", "puan", "price_try", "valid_from", "valid_to")

def ek2c(code: str, d: str) -> pl.DataFrame:
    return _inforce(EK2C.filter(pl.col("package_code") == code), d).select("package_code", "name", "group", "has_star", "prose_drg_locked", "puan", "price_try", "valid_from", "valid_to", "description")

def ek2b_hist(code: str) -> pl.DataFrame:
    return EK2B.filter(pl.col("code") == code).select("code", "name", "puan", "price_try", "valid_from", "valid_to").sort("valid_from")

def ek2c_hist(code: str) -> pl.DataFrame:
    return EK2C.filter(pl.col("package_code") == code).select("package_code", "name", "group", "puan", "price_try", "valid_from", "valid_to").sort("valid_from")

def ek2b_search(pattern: str, d: str) -> pl.DataFrame:
    return _inforce(EK2B.filter(pl.col("name").str.contains(pattern)), d).select("code", "name", "puan", "price_try", "valid_from", "valid_to")

def ek2c_search(pattern: str, d: str) -> pl.DataFrame:
    return _inforce(EK2C.filter(pl.col("name").str.contains(pattern)), d).select("package_code", "name", "group", "has_star", "puan", "price_try", "valid_from", "valid_to")

def ek4a_search(pattern: str, d: str) -> pl.DataFrame:
    return _inforce(EK4A.filter(pl.col("drug_name").str.contains(pattern)), d, "valid_until").select("kamu_no", "barcode", "drug_name", "equivalence_group", "therapeutic_group", "activation_date", "passivation_date", "valid_from", "valid_until", "status")

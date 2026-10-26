"""
src/bilun/domain/optimization/shared.py
Shared helper functions for optimization rules.
"""

from __future__ import annotations

import polars as pl

from ..icd10 import icd10_in_range as _icd10_in_range  # noqa: F401  (re-exported)


def collect_patient_diagnoses(
    ana_df: pl.DataFrame,
    *,
    id_col: str,
) -> dict[str, list[str]]:
    """Every ICD-10 code of each patient, the principal codes first.

    ``TANIKODU`` is the principal code of an episode and ``TUM_EPS_TANILAR`` all of the episode's
    codes, comma separated, principal included. Each patient's list starts with their principal
    codes (sorted), then the other episode codes (sorted); codes are stripped, never repeated, and
    empty tokens are dropped. A frame without ``TUM_EPS_TANILAR`` yields the principal codes only.
    """
    if ana_df.is_empty() or id_col not in ana_df.columns:
        return {}

    pid = pl.col(id_col).cast(pl.Utf8).alias("pid")
    parts: list[pl.DataFrame] = []
    if "TANIKODU" in ana_df.columns:
        parts.append(
            ana_df.select(
                pid,
                pl.col("TANIKODU").cast(pl.Utf8).str.strip_chars().alias("code"),
                pl.lit(0).alias("rank"),
            )
        )
    if "TUM_EPS_TANILAR" in ana_df.columns:
        parts.append(
            ana_df.select(
                pid,
                pl.col("TUM_EPS_TANILAR").cast(pl.Utf8).str.split(",").alias("code"),
                pl.lit(1).alias("rank"),
            )
            .explode("code")
            .with_columns(pl.col("code").str.strip_chars())
        )
    if not parts:
        return {}

    codes = (
        pl.concat(parts)
        .filter(pl.col("pid").is_not_null() & (pl.col("code").str.len_chars() > 0))
        .group_by("pid", "code")
        .agg(pl.col("rank").min())
        .sort("pid", "rank", "code")
        .group_by("pid", maintain_order=True)
        .agg(pl.col("code"))
    )
    return {str(row["pid"]): list(row["code"]) for row in codes.iter_rows(named=True)}


def _extract_diagnoses_bulk_pl(
    ana_df: pl.DataFrame,
    patient_ids: list[str],
) -> dict[str, list[str]]:
    """Every ICD-10 diagnosis per requested patient (``HASTA_ID`` frame), principal first."""
    if ana_df.is_empty() or "HASTA_ID" not in ana_df.columns:
        return {}
    return collect_patient_diagnoses(
        ana_df.filter(pl.col("HASTA_ID").is_in(patient_ids)),
        id_col="HASTA_ID",
    )


def _extract_patient_icd10_chapters(diagnoses: list[str]) -> set[str]:
    """Extract unique ICD-10 chapter letters from a list of diagnosis codes."""
    chapters: set[str] = set()
    for diag in diagnoses:
        if diag and diag[0].isalpha():
            chapters.add(diag[0].upper())
    return chapters
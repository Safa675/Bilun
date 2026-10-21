"""
src/bilun/domain/optimization/shared.py
Shared helper functions for optimization rules.
"""

from __future__ import annotations

import re

import polars as pl


def _icd10_in_range(code: str, start: str, end: str) -> bool:
    """Check if an ICD-10 code falls within a gazette exemption range.

    Matching logic:
      Range "A15-A19" matches "A16", "A16.2", "A17", etc.
      Single "C34" matches "C34", "C34.1", "C34.9", etc.
      Sub-code "C49.5" matches only "C49.5" exactly.
    """
    if not code or not start:
        return False

    code = code.strip().upper()
    start = start.strip().upper()
    end = end.strip().upper()

    if not code or not code[0].isalpha():
        return False

    code_letter = code[0]
    start_letter = start[0] if start else ""
    end_letter = end[0] if end else start_letter

    if code_letter != start_letter:
        return False

    if "." in start and start == end:
        return code == start or code.startswith(start + ".")

    if "." in start:
        return code.startswith(start.split(".")[0])

    m_code = re.match(r"[A-Z](\d{2,3})", code)
    m_start = re.match(r"[A-Z](\d{2,3})", start)
    m_end = re.match(r"[A-Z](\d{2,3})", end)

    if not m_code or not m_start or not m_end:
        return False

    code_num = int(m_code.group(1))
    start_num = int(m_start.group(1))
    end_num = int(m_end.group(1))

    return start_num <= code_num <= end_num


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
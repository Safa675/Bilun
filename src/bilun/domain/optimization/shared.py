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


def _extract_diagnoses_bulk_pl(
    ana_df: pl.DataFrame,
    patient_ids: list[str],
) -> dict[str, list[str]]:
    """Extract unique ICD-10 diagnoses per patient using Polars group_by."""
    if ana_df.is_empty() or "TANIKODU" not in ana_df.columns:
        return {}

    sub = (
        ana_df.filter(
            pl.col("HASTA_ID").is_in(patient_ids) & pl.col("TANIKODU").is_not_null()
        )
        .with_columns(pl.col("TANIKODU").cast(pl.Utf8).str.strip_chars().alias("_diag"))
        .filter(pl.col("_diag").str.len_chars() > 0)
    )

    if sub.is_empty():
        return {}

    agg = sub.group_by("HASTA_ID").agg(pl.col("_diag").unique().alias("diagnoses"))

    result: dict[str, list[str]] = {}
    for row in agg.iter_rows(named=True):
        result[row["HASTA_ID"]] = row["diagnoses"]
    return result


def _extract_patient_icd10_chapters(diagnoses: list[str]) -> set[str]:
    """Extract unique ICD-10 chapter letters from a list of diagnosis codes."""
    chapters: set[str] = set()
    for diag in diagnoses:
        if diag and diag[0].isalpha():
            chapters.add(diag[0].upper())
    return chapters
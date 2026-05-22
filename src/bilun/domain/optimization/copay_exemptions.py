"""
src/bilun/domain/optimization/copay_exemptions.py
Feature 1: Copayment exemption checker (EK-1A).
"""

from __future__ import annotations

import logging
from typing import Any

from ..catalog import get_ek1a_exemptions
from ..labels import normalize_sut_display_text
from .shared import _icd10_in_range

logger = logging.getLogger("bilun.domain.optimization")

_ek1a_by_letter: dict[str, list[tuple[str, str, str]]] | None = None


def _get_ek1a_by_letter() -> dict[str, list[tuple[str, str, str]]]:
    """Build EK-1A index grouped by ICD-10 chapter letter for O(1) access."""
    global _ek1a_by_letter
    if _ek1a_by_letter is not None:
        return _ek1a_by_letter

    ek1a = get_ek1a_exemptions()
    index: dict[str, list[tuple[str, str, str]]] = {}
    if not ek1a.empty:
        for _, row in ek1a.iterrows():
            start = str(row["icd10_start"]).strip().upper()
            end = str(row["icd10_end"]).strip().upper()
            disease = normalize_sut_display_text(str(row["disease_name_tr"]))
            if start and start[0].isalpha():
                letter = start[0]
                index.setdefault(letter, []).append((start, end, disease))
    _ek1a_by_letter = index
    return _ek1a_by_letter


def _precompute_exemption_map(
    all_diagnoses: set[str],
) -> dict[str, tuple[str, str]]:
    """Pre-check every unique ICD-10 code against EK-1A ranges once."""
    ek1a_idx = _get_ek1a_by_letter()
    if not ek1a_idx:
        return {}

    result: dict[str, tuple[str, str]] = {}
    for diag_raw in all_diagnoses:
        diag = diag_raw.strip().upper()
        if not diag or not diag[0].isalpha():
            continue
        letter = diag[0]
        ranges = ek1a_idx.get(letter, [])
        for start, end, disease in ranges:
            if _icd10_in_range(diag, start, end):
                range_str = f"{start}-{end}" if start != end else start
                result[diag_raw] = (disease, range_str)
                break
    return result


def check_copay_exemptions(patient_diagnoses: list[str]) -> dict[str, Any]:
    """Check patient ICD-10 codes against EK-1A chronic disease exemptions.

    Args:
        patient_diagnoses: List of ICD-10 codes from the patient's records.

    Returns:
        {
            "exempt": bool,
            "n_qualifying": int,
            "qualifying_diagnoses": [{"icd10": str, "disease": str, "range": str}]
        }
    """
    ek1a_idx = _get_ek1a_by_letter()
    if not ek1a_idx or not patient_diagnoses:
        return {"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []}

    qualifying: list[dict[str, str]] = []
    seen_diseases: set[str] = set()

    for diag in patient_diagnoses:
        if not diag or not isinstance(diag, str):
            continue
        diag = diag.strip().upper()
        if not diag or not diag[0].isalpha():
            continue

        letter = diag[0]
        ranges = ek1a_idx.get(letter, [])
        if not ranges:
            continue

        for start, end, disease in ranges:
            if _icd10_in_range(diag, start, end):
                if disease not in seen_diseases:
                    seen_diseases.add(disease)
                    range_str = f"{start}-{end}" if start != end else start
                    qualifying.append(
                        {"icd10": diag, "disease": disease, "range": range_str}
                    )
                break

    return {
        "exempt": len(qualifying) > 0,
        "n_qualifying": len(qualifying),
        "qualifying_diagnoses": qualifying,
    }

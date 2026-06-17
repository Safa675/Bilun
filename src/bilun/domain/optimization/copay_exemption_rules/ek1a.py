"""EK-1A chronic disease copay exemption (ICD-10)."""

from __future__ import annotations

import logging
from typing import Any

from ...catalog import get_ek1a_exemptions
from ...labels import normalize_sut_display_text
from ..shared import _icd10_in_range

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
        for start, end, disease in ek1a_idx.get(letter, []):
            if _icd10_in_range(diag, start, end):
                range_str = f"{start}-{end}" if start != end else start
                result[diag_raw] = (disease, range_str)
                break
    return result


def evaluate_ek1a_exemption(
    diagnoses: list[str],
    *,
    has_health_report: bool | None = None,
) -> dict[str, Any] | None:
    """Return an exemption source dict if any diagnosis matches EK-1/A."""
    ek1a_idx = _get_ek1a_by_letter()
    if not ek1a_idx or not diagnoses:
        return None

    qualifying: list[dict[str, str]] = []
    seen_diseases: set[str] = set()

    for diag in diagnoses:
        if not diag or not isinstance(diag, str):
            continue
        normalized = diag.strip().upper()
        if not normalized or not normalized[0].isalpha():
            continue

        letter = normalized[0]
        for start, end, disease in ek1a_idx.get(letter, []):
            if _icd10_in_range(normalized, start, end):
                if disease not in seen_diseases:
                    seen_diseases.add(disease)
                    range_str = f"{start}-{end}" if start != end else start
                    qualifying.append(
                        {
                            "icd10": normalized,
                            "disease": disease,
                            "range": range_str,
                        }
                    )
                break

    if not qualifying:
        return None

    counts_toward_exempt = has_health_report is True
    source: dict[str, Any] = {
        "category": "ek1a_chronic",
        "rule_source": "SUT §1.8.5(7) + EK-1/A chronic disease copay exemptions",
        "counts_toward_exempt": counts_toward_exempt,
        "waives_sections": ("1.8.1",),
        "evidence": {"qualifying_diagnoses": qualifying},
    }
    if has_health_report is False:
        source["exemption_strength"] = "partial"
        source["missing_requirements"] = ["chronic_health_report"]
    elif has_health_report is None:
        source["exemption_strength"] = "partial"
        source["missing_requirements"] = ["chronic_health_report"]
    return source

"""
src/bilun/domain/optimization/aggregator.py
Cohort-level aggregation: compute_optimization_summary.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from typing import Any

import polars as pl

from .shared import _extract_diagnoses_bulk_pl, _extract_patient_icd10_chapters
from .copay_exemptions import _get_ek1a_by_letter, _precompute_exemption_map
from .temporal import audit_temporal_prices
from .drugs import validate_drug_discount_tiers
from .exactness import (
    COPAY_RATE_REQUIRED_INPUTS,
    COPAY_RATE_UNAVAILABLE_REASON,
    EXACTNESS_STATUS_MISSING_INPUTS,
    SURCHARGE_REQUIRED_INPUTS,
    SURCHARGE_UNAVAILABLE_REASON,
    unavailable_cohort_drg_unbundling,
)

logger = logging.getLogger("bilun.domain.optimization")


def compute_optimization_summary(
    ana_df: pl.DataFrame,
    patient_ids: list[str],
    *,
    diagnoses_by_pid: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Compute cohort-level optimization findings for all 6 Features.

    Args:
        ana_df: The main visit/diagnosis DataFrame (pandas or Polars).
        patient_ids: List of patient IDs to analyze.
        diagnoses_by_pid: Optional pre-extracted diagnoses dict.

    Returns:
        {
            "copay_exemptions": {...},
            "surcharge_exposure": {...},
            "copay_rate_exposure": {...},
            "temporal_price_validation": {...},
            "drg_unbundling": {...},
            "drug_discount_validation": {...},
        }
    """
    t0 = time.perf_counter()

    if diagnoses_by_pid is None:
        diagnoses_by_pid = _extract_diagnoses_bulk_pl(ana_df, patient_ids)

    _get_ek1a_by_letter()

    all_unique_codes: set[str] = set()
    for diags in diagnoses_by_pid.values():
        all_unique_codes.update(diags)
    exemption_map = _precompute_exemption_map(all_unique_codes)

    n_exempt = 0
    all_diseases: list[str] = []
    for pid in patient_ids:
        diagnoses = diagnoses_by_pid.get(pid, [])

        if not diagnoses:
            continue

        seen_diseases: set[str] = set()
        patient_qualifying: list[dict[str, str]] = []
        for diag in diagnoses:
            match = exemption_map.get(diag)
            if match is not None:
                disease, range_str = match
                if disease not in seen_diseases:
                    seen_diseases.add(disease)
                    patient_qualifying.append(
                        {"icd10": diag, "disease": disease, "range": range_str}
                    )
        if patient_qualifying:
            n_exempt += 1
            for q in patient_qualifying:
                all_diseases.append(q["disease"])

    n_total = len(patient_ids)

    disease_counts = Counter(all_diseases)
    top_diseases = [
        {"disease": d, "count": c} for d, c in disease_counts.most_common(10)
    ]

    temporal = audit_temporal_prices()
    drug_discount = validate_drug_discount_tiers()

    elapsed = time.perf_counter() - t0
    logger.info(
        "Optimization summary computed in %.1fs (single pass, %d patients)",
        elapsed,
        n_total,
    )

    return {
        "copay_exemptions": {
            "n_exempt_patients": n_exempt,
            "n_total_patients": n_total,
            "exemption_rate": round(n_exempt / n_total, 4) if n_total else 0.0,
            "top_diseases": top_diseases,
            "methodology": (
                "Cross-references patient ICD-10 diagnosis codes against 98 "
                "chronic disease exemption ranges from gazette annex EK-1A. "
                "Patients with qualifying diagnoses are exempt from outpatient "
                "copayment (katılım payı) under SUT 1.8.1. "
                "100% real gazette data."
            ),
        },
        "surcharge_exposure": {
            "exactness_status": EXACTNESS_STATUS_MISSING_INPUTS,
            "unavailable_reason": SURCHARGE_UNAVAILABLE_REASON,
            "required_inputs_missing": list(SURCHARGE_REQUIRED_INPUTS),
            "n_total_ek2g": None,
            "mean_applicable_per_patient": None,
            "max_applicable": None,
            "cohort_coverage_rate": None,
            "methodology": (
                "Surcharge compliance is unavailable in active runtime surfaces "
                "until exact billed procedure codes and procedure dates are "
                "present in the SUT claim inputs."
            ),
        },
        "copay_rate_exposure": {
            "exactness_status": EXACTNESS_STATUS_MISSING_INPUTS,
            "unavailable_reason": COPAY_RATE_UNAVAILABLE_REASON,
            "required_inputs_missing": list(COPAY_RATE_REQUIRED_INPUTS),
            "n_total_ek2c1": None,
            "mean_applicable_per_patient": None,
            "cohort_mean_rate": None,
            "rate_distribution": {},
            "methodology": (
                "Copay rate compliance is unavailable in active runtime "
                "surfaces until exact billed procedure codes and claim dates "
                "are present in the SUT claim inputs."
            ),
        },
        "temporal_price_validation": temporal,
        "drg_unbundling": unavailable_cohort_drg_unbundling(n_total_patients=n_total),
        "drug_discount_validation": drug_discount,
    }

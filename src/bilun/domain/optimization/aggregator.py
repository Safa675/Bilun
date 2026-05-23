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

from src.bilun.domain.claims.patient_context import build_cohort_claim_context
from src.bilun.domain.claims.loader import SUTClaimDataset

from .shared import _extract_diagnoses_bulk_pl, _extract_patient_icd10_chapters
from .copay_exemptions import _get_ek1a_by_letter, _precompute_exemption_map
from .temporal import audit_temporal_prices
from .drugs import validate_drug_discount_tiers
from .unbundling import (
    detect_drg_unbundling,
    unavailable_cohort_drg_unbundling_with_context,
)
from .exactness import (
    EXACTNESS_STATUS_MISSING_INPUTS,
    COPAY_RATE_REQUIRED_INPUTS,
    COPAY_RATE_UNAVAILABLE_REASON,
    SURCHARGE_REQUIRED_INPUTS,
    SURCHARGE_UNAVAILABLE_REASON,
    is_exact_output,
    unavailable_cohort_drg_unbundling,
)
from .claim_context import (
    build_copay_rate_claim_context,
    build_surcharge_claim_context,
)
from .runtime_claim_context import ClaimContextManager
from .surcharge import analyze_surcharge_exposure
from .copay_rates import analyze_copay_rate_exposure

logger = logging.getLogger("bilun.domain.optimization")


def _aggregate_surcharge_exposure(
    patient_ids: list[str],
    claim_dataset: SUTClaimDataset | None,
) -> dict[str, Any]:
    if claim_dataset is None:
        return {
            "exactness_status": EXACTNESS_STATUS_MISSING_INPUTS,
            "unavailable_reason": SURCHARGE_UNAVAILABLE_REASON,
            "required_inputs_missing": list(SURCHARGE_REQUIRED_INPUTS),
            "n_total_ek2g": None,
            "mean_applicable_per_patient": None,
            "max_applicable": None,
            "cohort_coverage_rate": None,
            "methodology": SURCHARGE_UNAVAILABLE_REASON,
        }

    total_applicable = 0
    total_procedures = 0
    max_applicable = 0
    patients_with_flags = 0

    for patient_id in patient_ids:
        procedures = claim_dataset.procedure_lines_by_patient.get(patient_id, ())
        context = build_surcharge_claim_context(patient_id, procedures)
        chapters = set()
        with ClaimContextManager(surcharge=context):
            exposure = analyze_surcharge_exposure(chapters)
        if not is_exact_output(exposure):
            continue
        n_app = int(exposure.get("n_applicable_procedures") or 0)
        n_total = int(exposure.get("n_total_ek2g") or 0)
        total_applicable += n_app
        total_procedures += n_total
        max_applicable = max(max_applicable, n_app)
        if n_app > 0:
            patients_with_flags += 1

    n_patients = len(patient_ids) or 1
    return {
        "exactness_status": "exact",
        "n_total_ek2g": total_procedures,
        "mean_applicable_per_patient": round(total_applicable / n_patients, 2),
        "max_applicable": max_applicable,
        "cohort_coverage_rate": round(patients_with_flags / n_patients, 4),
        "n_patients_with_surcharge_flags": patients_with_flags,
        "methodology": (
            "Aggregated exact surcharge_applicable procedure flags from claim lines "
            "across the active cohort."
        ),
    }


def _aggregate_copay_rate_exposure(
    patient_ids: list[str],
    claim_dataset: SUTClaimDataset | None,
) -> dict[str, Any]:
    if claim_dataset is None:
        return {
            "exactness_status": EXACTNESS_STATUS_MISSING_INPUTS,
            "unavailable_reason": COPAY_RATE_UNAVAILABLE_REASON,
            "required_inputs_missing": list(COPAY_RATE_REQUIRED_INPUTS),
            "n_total_ek2c1": None,
            "mean_applicable_per_patient": None,
            "cohort_mean_rate": None,
            "rate_distribution": {},
            "methodology": COPAY_RATE_UNAVAILABLE_REASON,
        }

    total_applicable = 0
    total_procedures = 0
    rate_counter: Counter[str] = Counter()
    rate_sum = 0.0
    rate_count = 0
    patients_with_flags = 0

    for patient_id in patient_ids:
        procedures = claim_dataset.procedure_lines_by_patient.get(patient_id, ())
        context = build_copay_rate_claim_context(patient_id, procedures)
        chapters = set()
        with ClaimContextManager(copay_rate=context):
            exposure = analyze_copay_rate_exposure(chapters)
        if not is_exact_output(exposure):
            continue
        n_app = int(exposure.get("n_applicable_procedures") or 0)
        n_total = int(exposure.get("n_total_ek2c1") or 0)
        total_applicable += n_app
        total_procedures += n_total
        if n_app > 0:
            patients_with_flags += 1
        for procedure in exposure.get("procedures_with_rates", []):
            rate_key = f"{procedure.get('rate_pct')}%"
            rate_counter[rate_key] += 1
            rate_sum += float(procedure.get("rate_pct") or 0.0)
            rate_count += 1

    n_patients = len(patient_ids) or 1
    return {
        "exactness_status": "exact",
        "n_total_ek2c1": total_procedures,
        "mean_applicable_per_patient": round(total_applicable / n_patients, 2),
        "cohort_mean_rate": round(rate_sum / rate_count, 2) if rate_count else 0.0,
        "rate_distribution": dict(rate_counter),
        "n_patients_with_copay_rate_flags": patients_with_flags,
        "methodology": (
            "Aggregated exact copay_rate_applicable procedure flags from claim lines "
            "across the active cohort."
        ),
    }


def _aggregate_drg_unbundling(
    patient_ids: list[str],
    claim_dataset: SUTClaimDataset | None,
) -> dict[str, Any]:
    if claim_dataset is None:
        return unavailable_cohort_drg_unbundling(n_total_patients=len(patient_ids))

    cohort_ctx = build_cohort_claim_context(claim_dataset)
    if cohort_ctx is None:
        return unavailable_cohort_drg_unbundling(n_total_patients=len(patient_ids))

    n_with_risk = 0
    total_savings = 0.0
    chapter_counter: Counter[str] = Counter()

    for patient_id in patient_ids:
        ctx = cohort_ctx.patient_contexts.get(patient_id)
        if ctx is None:
            continue
        chapters = _extract_patient_icd10_chapters(
            [diag.icd10_code for diag in ctx.diagnoses]
        )
        finding = detect_drg_unbundling(set(chapters), ctx)
        if finding.get("has_unbundling_risk"):
            n_with_risk += 1
            total_savings += float(finding.get("total_potential_savings") or 0.0)
            for entry in finding.get("chapter_analysis", []):
                chapter_counter[entry.get("chapter", "?")] += 1

    top_chapters = [
        {"chapter": chapter, "count": count}
        for chapter, count in chapter_counter.most_common(10)
    ]

    return unavailable_cohort_drg_unbundling_with_context(
        n_total_patients=len(patient_ids),
        n_patients_with_risk=n_with_risk,
        total_potential_savings=total_savings,
        top_risky_chapters=top_chapters,
    )


def compute_optimization_summary(
    ana_df: pl.DataFrame,
    patient_ids: list[str],
    *,
    diagnoses_by_pid: dict[str, list[str]] | None = None,
    claim_dataset: SUTClaimDataset | None = None,
) -> dict[str, Any]:
    """Compute cohort-level optimization findings for all 6 Features."""

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
    cohort_ctx = build_cohort_claim_context(claim_dataset)
    drug_lines = cohort_ctx.all_drug_lines if cohort_ctx is not None else None
    drug_discount = validate_drug_discount_tiers(drug_lines)

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
        "surcharge_exposure": _aggregate_surcharge_exposure(patient_ids, claim_dataset),
        "copay_rate_exposure": _aggregate_copay_rate_exposure(patient_ids, claim_dataset),
        "temporal_price_validation": temporal,
        "drg_unbundling": _aggregate_drg_unbundling(patient_ids, claim_dataset),
        "drug_discount_validation": drug_discount,
    }

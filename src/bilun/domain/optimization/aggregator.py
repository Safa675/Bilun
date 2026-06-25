"""
src/bilun/domain/optimization/aggregator.py
Cohort-level aggregation: compute_optimization_summary.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from decimal import Decimal
from typing import Any

import polars as pl

from src.bilun.domain.claims.patient_context import build_cohort_claim_context
from src.bilun.domain.claims.loader import SUTClaimDataset

from .shared import _extract_diagnoses_bulk_pl, _extract_patient_icd10_chapters
from .copay_exemption_context import (
    build_copay_exemption_input,
    build_copay_inputs_by_patient,
)
from .copay_exemption_types import CopayExemptionInput
from .copay_exemption_rules.ek1a import _get_ek1a_by_letter
from .copay_exemptions import evaluate_copay_exemption
from .temporal import audit_temporal_prices
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
from .drug_discounts import validate_drug_discount_tiers

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
        n_violations = int(exposure.get("n_violations") or 0)
        n_total = int(exposure.get("n_total_ek2c1") or 0)
        total_applicable += n_violations
        total_procedures += n_total
        if n_violations > 0:
            patients_with_flags += 1
        for procedure in exposure.get("procedures_with_rates", []):
            if procedure.get("catalog_validated") is False:
                continue
            # B-H3: only codes with an actual EK-2C-1 mandated rate belong
            # in the cohort rate mean/distribution. copay_rate_matches_catalog
            # returns True for codes ABSENT from EK-2C-1 (mandated is None),
            # so catalog_validated alone never filters them out — they
            # polluted cohort_mean_rate and rate_distribution with codes that
            # have no mandated copay rate. Gate on mandated_rate_pct is not None.
            if procedure.get("mandated_rate_pct") is None:
                continue
            # B-H4: rate key must match exactness.py's quantized format so
            # per-patient and cohort distributions merge correctly. The
            # rate_pct is a float; format to 2dp to match
            # f"{rate.quantize(Decimal('0.01'))}%" from exactness.py.
            rate_val = procedure.get("rate_pct")
            rate_key = f"{Decimal(str(rate_val)).quantize(Decimal('0.01'))}%"
            rate_counter[rate_key] += 1
            rate_sum += float(rate_val or 0.0)
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
            "Aggregated EK-2C-1 catalog violations (flag or implied-rate mismatch) "
            "from exact claim lines across the active cohort."
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


def _aggregate_drug_discount_validation(
    patient_ids: list[str],
    claim_dataset: SUTClaimDataset | None,
) -> dict[str, Any]:
    drug_lines = (
        getattr(claim_dataset, "drug_lines", {}).values()
        if claim_dataset is not None
        else None
    )
    return validate_drug_discount_tiers(
        drug_lines,
        n_total_patients=len(patient_ids),
    )


def _aggregate_copay_exemptions_by_bill(
    patient_ids: list[str],
    copay_inputs: dict[str, CopayExemptionInput],
    claim_dataset: SUTClaimDataset | None,
) -> dict[str, Any] | None:
    """Return bill-scoped copay exemption counts when claim data is available."""
    if claim_dataset is None:
        return None

    claims_by_patient = getattr(claim_dataset, "claims_by_patient", {}) or {}
    procedure_lines_by_patient = (
        getattr(claim_dataset, "procedure_lines_by_patient", {}) or {}
    )

    n_total_bills = 0
    n_exempt_bills = 0
    n_exempt_ek1a = 0
    n_exempt_status_only = 0
    n_exempt_both = 0
    category_counts: Counter[str] = Counter()

    for pid in patient_ids:
        patient_input = copay_inputs.get(pid)
        if patient_input is None:
            continue
        claims = claims_by_patient.get(pid, ())
        if not claims:
            continue

        codes_by_claim: dict[str, list[str]] = {}
        for line in procedure_lines_by_patient.get(pid, ()):
            cid = getattr(line, "claim_id", None)
            if not cid:
                continue
            code = str(getattr(line, "procedure_code", "") or "").strip()
            if code:
                codes_by_claim.setdefault(cid, []).append(code)

        for claim in claims:
            cid = getattr(claim, "claim_id", None)
            if not cid:
                continue
            n_total_bills += 1
            bill_input = build_copay_exemption_input(
                diagnoses=list(patient_input.diagnoses),
                patient_profile=patient_input.patient_profile,
                patient_claims=(claim,),
                claim_procedure_codes=tuple(codes_by_claim.get(cid, [])),
                age_at_latest_claim=None,
                has_chronic_health_report=patient_input.has_chronic_health_report,
            )
            result = evaluate_copay_exemption(bill_input)
            if not result.get("exempt"):
                continue
            n_exempt_bills += 1
            categories = {
                str(source.get("category") or "")
                for source in result.get("exemption_sources", [])
            }
            has_ek1a = "ek1a_chronic" in categories
            has_status = bool(categories - {"ek1a_chronic"})
            if has_ek1a:
                n_exempt_ek1a += 1
            if has_status and not has_ek1a:
                n_exempt_status_only += 1
            if has_ek1a and has_status:
                n_exempt_both += 1
            for source in result.get("exemption_sources", []):
                category_counts[str(source.get("category") or "unknown")] += 1

    if n_total_bills == 0:
        return None

    return {
        "n_total_bills": n_total_bills,
        "n_exempt_bills": n_exempt_bills,
        "n_exempt_ek1a_bills": n_exempt_ek1a,
        "n_exempt_status_only_bills": n_exempt_status_only,
        "n_exempt_ek1a_and_status_bills": n_exempt_both,
        "exemption_rate_bills": (
            round(n_exempt_bills / n_total_bills, 4) if n_total_bills else 0.0
        ),
        "exemption_by_category_bills": [
            {"category": category, "count": count}
            for category, count in category_counts.most_common()
        ],
    }


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

    claims_by_patient = (
        getattr(claim_dataset, "claims_by_patient", {}) if claim_dataset is not None else {}
    )
    profiles_by_patient = (
        getattr(claim_dataset, "copay_profiles_by_patient", {})
        if claim_dataset is not None
        else {}
    )
    procedure_lines_by_patient = (
        getattr(claim_dataset, "procedure_lines_by_patient", {})
        if claim_dataset is not None
        else {}
    )
    copay_inputs = build_copay_inputs_by_patient(
        patient_ids,
        diagnoses_by_pid,
        claims_by_patient=claims_by_patient,
        copay_profiles_by_patient=profiles_by_patient,
        procedure_lines_by_patient=procedure_lines_by_patient,
    )

    n_exempt = 0
    n_exempt_ek1a = 0
    n_exempt_status_only = 0
    n_exempt_both = 0
    category_counts: Counter[str] = Counter()
    all_diseases: list[str] = []

    for pid in patient_ids:
        result = evaluate_copay_exemption(copay_inputs[pid])
        if not result.get("exempt"):
            continue
        n_exempt += 1
        categories = {
            str(source.get("category") or "")
            for source in result.get("exemption_sources", [])
        }
        has_ek1a = "ek1a_chronic" in categories
        has_status = bool(categories - {"ek1a_chronic"})
        if has_ek1a:
            n_exempt_ek1a += 1
        if has_status and not has_ek1a:
            n_exempt_status_only += 1
        if has_ek1a and has_status:
            n_exempt_both += 1
        for source in result.get("exemption_sources", []):
            category_counts[str(source.get("category") or "unknown")] += 1
        for diag in result.get("qualifying_diagnoses", []):
            disease = str(diag.get("disease") or "")
            if disease:
                all_diseases.append(disease)

    n_total = len(patient_ids)

    disease_counts = Counter(all_diseases)
    top_diseases = [
        {"disease": d, "count": c} for d, c in disease_counts.most_common(10)
    ]

    temporal = audit_temporal_prices()
    bill_level = _aggregate_copay_exemptions_by_bill(
        patient_ids, copay_inputs, claim_dataset
    )
    elapsed = time.perf_counter() - t0
    logger.info(
        "Optimization summary computed in %.1fs (single pass, %d patients)",
        elapsed,
        n_total,
    )

    copay_exemptions: dict[str, Any] = {
        "n_exempt_patients": n_exempt,
        "n_exempt_ek1a_patients": n_exempt_ek1a,
        "n_exempt_status_only_patients": n_exempt_status_only,
        "n_exempt_ek1a_and_status_patients": n_exempt_both,
        "n_total_patients": n_total,
        "exemption_rate": round(n_exempt / n_total, 4) if n_total else 0.0,
        "exemption_by_category": [
            {"category": category, "count": count}
            for category, count in category_counts.most_common()
        ],
        "top_diseases": top_diseases,
        "methodology": (
            "Composable copay exemption: EK-1A chronic ICD-10 ranges plus "
            "status/visit rules when patient profiles and claim visit types "
            "are available. EK-2C-1 copay rate ceilings are evaluated separately."
        ),
        "rule_source": (
            "EK-1A, visit type (acil/koruyucu), SGK status, occupational context"
        ),
    }
    if bill_level is not None:
        copay_exemptions.update(bill_level)

    return {
        "copay_exemptions": copay_exemptions,
        "surcharge_exposure": _aggregate_surcharge_exposure(patient_ids, claim_dataset),
        "copay_rate_exposure": _aggregate_copay_rate_exposure(patient_ids, claim_dataset),
        "temporal_price_validation": temporal,
        "drg_unbundling": _aggregate_drg_unbundling(patient_ids, claim_dataset),
        "drug_discount_validation": _aggregate_drug_discount_validation(
            patient_ids,
            claim_dataset,
        ),
        "rule_source": "EK-1A (copay), EK-2G (surcharge), EK-2C-1 (copay rates), EK-2B/2C (pricing/DRG)",
    }

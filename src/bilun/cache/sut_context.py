"""SUT assembly helpers for analytics cache context."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import polars as pl

from src.bilun.domain.claims import load_sut_claim_dataset
from src.bilun.domain.optimization.exactness import (
    EXACTNESS_STATUS_EXACT,
    is_exact_output,
)
from src.bilun.domain.optimization.claim_context import (
    build_copay_rate_claim_context,
    build_surcharge_claim_context,
)
from src.bilun.domain.optimization.copay_exemption_context import build_copay_inputs_by_patient
from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput
from src.bilun.domain.optimization.runtime_claim_context import ClaimContextManager

logger = logging.getLogger("bilun.cache.sut_context")


def _copay_exemption_action(result: dict[str, Any]) -> str | None:
    if not result.get("exempt"):
        return None
    category = result.get("primary_exemption_category")
    if category == "ek1a_chronic":
        return "Waive outpatient copay (EK-1A)"
    if category:
        return f"Waive outpatient copay ({category})"
    return "Waive outpatient copay"


def _format_copay_exemption_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "exempt": bool(result.get("exempt")),
        "n_qualifying": int(result.get("n_qualifying") or 0),
        "qualifying_diagnoses": list(result.get("qualifying_diagnoses", [])),
        "exemption_sources": list(result.get("exemption_sources", [])),
        "categories_not_evaluated": list(result.get("categories_not_evaluated", [])),
        "primary_exemption_category": result.get("primary_exemption_category"),
        "action": _copay_exemption_action(result),
    }


def _extract_icd10_chapters(diagnoses: list[str]) -> list[str]:
    chapters = {
        str(code).strip()[0].upper()
        for code in diagnoses
        if str(code).strip() and str(code).strip()[0].isalpha()
    }
    return sorted(chapters)


def build_sut_patient_alerts_cache(
    patient_ids: list[str],
    diagnoses_by_pid: dict[str, list[str]],
    *,
    evaluate_copay_exemption_fn,
    analyze_surcharge_exposure_fn,
    analyze_copay_rate_exposure_fn,
    procedure_lines_by_patient: dict[str, Any] | None = None,
    copay_inputs_by_pid: dict[str, CopayExemptionInput] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    n_exempt_patients = 0
    n_patients_with_surcharge_flags = 0
    n_patients_with_copay_rate_flags = 0
    n_patients_with_surcharge_unavailable = 0
    n_patients_with_copay_rate_unavailable = 0
    total_surcharge_flags = 0
    total_copay_rate_flags = 0
    surcharge_probe = analyze_surcharge_exposure_fn(set())
    copay_rate_probe = analyze_copay_rate_exposure_fn(set())
    procedure_lines_by_patient = procedure_lines_by_patient or {}
    copay_inputs_by_pid = copay_inputs_by_pid or {}

    for patient_id in patient_ids:
        diagnoses = diagnoses_by_pid.get(patient_id, [])
        chapters = _extract_icd10_chapters(diagnoses)
        chapter_set = set(chapters)

        procedure_lines = procedure_lines_by_patient.get(patient_id, ())
        surcharge_context = build_surcharge_claim_context(patient_id, procedure_lines)
        copay_rate_context = build_copay_rate_claim_context(patient_id, procedure_lines)

        with ClaimContextManager(
            surcharge=surcharge_context,
            copay_rate=copay_rate_context,
        ):
            copay_input = copay_inputs_by_pid.get(
                patient_id,
                CopayExemptionInput(diagnoses=diagnoses),
            )
            copay_exemption = evaluate_copay_exemption_fn(copay_input)
            surcharge_exposure = analyze_surcharge_exposure_fn(chapter_set)
            copay_rate_exposure = analyze_copay_rate_exposure_fn(chapter_set)

        surcharge_count = (
            int(surcharge_exposure.get("n_applicable_procedures") or 0)
            if is_exact_output(surcharge_exposure)
            else 0
        )
        copay_rate_count = (
            int(copay_rate_exposure.get("n_applicable_procedures") or 0)
            if is_exact_output(copay_rate_exposure)
            else 0
        )
        is_exempt = bool(copay_exemption.get("exempt"))

        n_exempt_patients += int(is_exempt)
        if is_exact_output(surcharge_exposure):
            n_patients_with_surcharge_flags += int(surcharge_count > 0)
        else:
            n_patients_with_surcharge_unavailable += 1
        if is_exact_output(copay_rate_exposure):
            n_patients_with_copay_rate_flags += int(copay_rate_count > 0)
        else:
            n_patients_with_copay_rate_unavailable += 1
        total_surcharge_flags += surcharge_count
        total_copay_rate_flags += copay_rate_count

        top_procedures = sorted(
            list(copay_rate_exposure.get("procedures_with_rates", [])),
            key=lambda procedure: (
                -float(procedure.get("rate_pct") or 0.0),
                str(procedure.get("code") or ""),
            ),
        )[:3]

        rows.append(
            {
                "patient_id": patient_id,
                "n_diagnoses": len(diagnoses),
                "icd10_chapters": chapters,
                "copay_exemption": _format_copay_exemption_payload(copay_exemption),
                "surcharge_exposure": {
                    **(
                        {"exactness_status": EXACTNESS_STATUS_EXACT}
                        if is_exact_output(surcharge_exposure)
                        else {}
                    ),
                    "n_applicable": (
                        surcharge_count if is_exact_output(surcharge_exposure) else None
                    ),
                    "exposure_rate": (
                        float(surcharge_exposure.get("exposure_rate") or 0.0)
                        if is_exact_output(surcharge_exposure)
                        else None
                    ),
                    "top_rules": (
                        list(surcharge_exposure.get("applicable_rules", []))[:3]
                        if is_exact_output(surcharge_exposure)
                        else []
                    ),
                    "action": (
                        "Do not charge surcharge"
                        if is_exact_output(surcharge_exposure) and surcharge_count > 0
                        else None
                    ),
                    **(
                        {}
                        if is_exact_output(surcharge_exposure)
                        else {
                            "exactness_status": surcharge_exposure.get("exactness_status"),
                            "unavailable_reason": surcharge_exposure.get(
                                "unavailable_reason"
                            ),
                            "required_inputs_missing": list(
                                surcharge_exposure.get("required_inputs_missing", [])
                            ),
                        }
                    ),
                },
                "copay_rate_exposure": {
                    **(
                        {"exactness_status": EXACTNESS_STATUS_EXACT}
                        if is_exact_output(copay_rate_exposure)
                        else {}
                    ),
                    "n_applicable": (
                        copay_rate_count if is_exact_output(copay_rate_exposure) else None
                    ),
                    "mean_rate": (
                        float(copay_rate_exposure.get("mean_rate") or 0.0)
                        if is_exact_output(copay_rate_exposure)
                        else None
                    ),
                    "top_procedures": (
                        top_procedures if is_exact_output(copay_rate_exposure) else []
                    ),
                    "action": (
                        "Apply capped copay rate"
                        if is_exact_output(copay_rate_exposure) and copay_rate_count > 0
                        else None
                    ),
                    **(
                        {}
                        if is_exact_output(copay_rate_exposure)
                        else {
                            "exactness_status": copay_rate_exposure.get(
                                "exactness_status"
                            ),
                            "unavailable_reason": copay_rate_exposure.get(
                                "unavailable_reason"
                            ),
                            "required_inputs_missing": list(
                                copay_rate_exposure.get("required_inputs_missing", [])
                            ),
                        }
                    ),
                },
            }
        )

    n_total_patients = len(patient_ids)
    summary: dict[str, Any] = {
        "n_total_patients": n_total_patients,
        "n_exempt_patients": n_exempt_patients,
        "exemption_rate": round(n_exempt_patients / max(n_total_patients, 1), 4),
        "n_patients_with_surcharge_flags": n_patients_with_surcharge_flags,
        "n_patients_with_copay_rate_flags": n_patients_with_copay_rate_flags,
        "total_surcharge_flags": total_surcharge_flags,
        "total_copay_rate_flags": total_copay_rate_flags,
        "n_patients_with_surcharge_unavailable": n_patients_with_surcharge_unavailable,
        "n_patients_with_copay_rate_unavailable": n_patients_with_copay_rate_unavailable,
    }
    if n_patients_with_surcharge_unavailable == 0:
        summary["surcharge_exactness_status"] = EXACTNESS_STATUS_EXACT
        summary["surcharge_unavailable_reason"] = None
        summary["surcharge_required_inputs_missing"] = []
    else:
        summary.update(
            {
                "n_patients_with_surcharge_flags": None,
                "total_surcharge_flags": None,
                "surcharge_exactness_status": surcharge_probe.get("exactness_status"),
                "surcharge_unavailable_reason": surcharge_probe.get(
                    "unavailable_reason"
                ),
                "surcharge_required_inputs_missing": list(
                    surcharge_probe.get("required_inputs_missing", [])
                ),
            }
        )
    if n_patients_with_copay_rate_unavailable == 0:
        summary["copay_rate_exactness_status"] = EXACTNESS_STATUS_EXACT
        summary["copay_rate_unavailable_reason"] = None
        summary["copay_rate_required_inputs_missing"] = []
    else:
        summary.update(
            {
                "n_patients_with_copay_rate_flags": None,
                "total_copay_rate_flags": None,
                "copay_rate_exactness_status": copay_rate_probe.get(
                    "exactness_status"
                ),
                "copay_rate_unavailable_reason": copay_rate_probe.get(
                    "unavailable_reason"
                ),
                "copay_rate_required_inputs_missing": list(
                    copay_rate_probe.get("required_inputs_missing", [])
                ),
            }
        )
    return {
        "patients": rows,
        "summary": summary,
    }


def _money_payload(value: Decimal | int | float | str) -> float:
    return float(value)


def _exact_claim_total_payload(total: Any) -> dict[str, Any]:
    return {
        "patient_id": str(total.patient_id),
        "total_billed_try": _money_payload(total.total_billed_try),
        "total_expected_payable_try": _money_payload(total.total_expected_payable_try),
        "claim_count": int(total.claim_count),
        "procedure_line_count": int(total.procedure_line_count),
        "material_line_count": int(total.material_line_count),
        "drug_line_count": int(total.drug_line_count),
        "lab_billed_line_count": int(total.lab_billed_line_count),
        "exactness_status": "exact",
        "source": "claim_lines",
    }


def _unavailable_claim_total_payload(
    patient_id: str,
    *,
    unavailable_reason: str,
    required_inputs_missing: list[str],
    error_type: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "patient_id": patient_id,
        "total_billed_try": None,
        "total_expected_payable_try": None,
        "claim_count": 0,
        "procedure_line_count": 0,
        "material_line_count": 0,
        "drug_line_count": 0,
        "lab_billed_line_count": 0,
        "exactness_status": "missing_exact_inputs",
        "unavailable_reason": unavailable_reason,
        "required_inputs_missing": required_inputs_missing,
        "source": "claim_lines",
    }
    if error_type:
        payload["error_type"] = error_type
    return payload


def build_exact_sut_patient_totals(
    patient_ids: list[str],
    *,
    load_sut_claim_dataset_fn=None,
) -> dict[str, dict[str, Any]]:
    loader = load_sut_claim_dataset_fn or load_sut_claim_dataset
    try:
        dataset = loader()
    except Exception as exc:
        return {
            patient_id: _unavailable_claim_total_payload(
                patient_id,
                unavailable_reason="exact_claim_dataset_unavailable",
                required_inputs_missing=["claim_lines"],
                error_type=type(exc).__name__,
            )
            for patient_id in patient_ids
        }

    patient_totals = getattr(dataset, "patient_totals", {})
    totals_by_pid: dict[str, dict[str, Any]] = {}
    for patient_id in patient_ids:
        total = patient_totals.get(patient_id)
        if total is None:
            totals_by_pid[patient_id] = _unavailable_claim_total_payload(
                patient_id,
                unavailable_reason="exact_claim_patient_totals_missing",
                required_inputs_missing=["claim_lines.patient_id"],
            )
        else:
            totals_by_pid[patient_id] = _exact_claim_total_payload(total)
    return totals_by_pid


def build_sut_claim_line_indexes(dataset: Any | None) -> dict[str, Any]:
    """Expose exact claim-line indexes for SUT runtime/cache consumers."""

    if dataset is None:
        return {
            "claims_by_patient": {},
            "procedure_lines_by_patient": {},
            "material_lines_by_patient": {},
            "drug_lines_by_patient": {},
            "diagnoses_by_patient": {},
        }
    return {
        "claims_by_patient": getattr(dataset, "claims_by_patient", {}),
        "procedure_lines_by_patient": getattr(dataset, "procedure_lines_by_patient", {}),
        "material_lines_by_patient": getattr(dataset, "material_lines_by_patient", {}),
        "drug_lines_by_patient": getattr(dataset, "drug_lines_by_patient", {}),
        "diagnoses_by_patient": getattr(dataset, "diagnoses_by_patient", {}),
    }


def assemble_sut_context(
    *,
    lab_df: pl.DataFrame,
    ana_df: pl.DataFrame,
    rec_df: pl.DataFrame,
    patient_ids: list[str],
    diagnoses_by_pid: dict[str, list[str]],
    compute_optimization_summary_fn,
    evaluate_copay_exemption_fn,
    analyze_surcharge_exposure_fn,
    analyze_copay_rate_exposure_fn,
    load_sut_claim_dataset_fn=None,
) -> dict[str, Any]:
    loader = load_sut_claim_dataset_fn or load_sut_claim_dataset
    claim_dataset = None
    claim_dataset_error: Exception | None = None
    try:
        claim_dataset = loader()
    except Exception as exc:
        claim_dataset_error = exc
        logger.warning(
            "SUT claim dataset unavailable for cache build: %s",
            exc,
            exc_info=True,
        )

    def _load_cached_claim_dataset():
        if claim_dataset_error is not None:
            raise claim_dataset_error
        return claim_dataset

    sut_by_pid = build_exact_sut_patient_totals(
        patient_ids,
        load_sut_claim_dataset_fn=_load_cached_claim_dataset,
    )
    optimization_summary = compute_optimization_summary_fn(
        ana_df,
        patient_ids,
        diagnoses_by_pid=diagnoses_by_pid,
        claim_dataset=claim_dataset,
    )
    copay_inputs_by_pid = build_copay_inputs_by_patient(
        patient_ids,
        diagnoses_by_pid,
        claims_by_patient=getattr(claim_dataset, "claims_by_patient", {}),
        copay_profiles_by_patient=getattr(
            claim_dataset, "copay_profiles_by_patient", {}
        ),
        procedure_lines_by_patient=getattr(
            claim_dataset, "procedure_lines_by_patient", {}
        ),
    )
    patient_alerts_cache = build_sut_patient_alerts_cache(
        patient_ids,
        diagnoses_by_pid,
        evaluate_copay_exemption_fn=evaluate_copay_exemption_fn,
        analyze_surcharge_exposure_fn=analyze_surcharge_exposure_fn,
        analyze_copay_rate_exposure_fn=analyze_copay_rate_exposure_fn,
        procedure_lines_by_patient=getattr(claim_dataset, "procedure_lines_by_patient", {}),
        copay_inputs_by_pid=copay_inputs_by_pid,
    )
    claim_line_indexes = build_sut_claim_line_indexes(claim_dataset)
    return {
        "sut_by_pid": sut_by_pid,
        "sut_claim_dataset": claim_dataset,
        **claim_line_indexes,
        "optimization_summary": optimization_summary,
        "patient_alerts_cache": patient_alerts_cache,
    }

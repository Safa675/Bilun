"""BILUN optimization endpoints — cohort summary, per-patient findings,
and revenue recovery."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from src.bilun.shared.exceptions import PatientNotFound, ServiceUnavailableError
from src.bilun.api.schemas import (
    PatientOptimizationResponse,
    BilunCachePayloadResponse,
)
from src.bilun.shared.state import (
    _get_active_build_id_or_none,
    _get_cache_reader,
    get_pipeline_mode,
)
from src.bilun.db import (
    read_json_payload as read_cache_json_payload,
    read_json_payload_rows as read_cache_json_payload_rows,
    read_patient_diagnoses as read_cache_patient_diagnoses,
)
from src.bilun.domain.billing.orchestrator import (
    patient_recovery_summary_from_payload,
)
from src.bilun.domain.optimization import (
    _extract_patient_icd10_chapters,
    analyze_copay_rate_exposure,
    analyze_surcharge_exposure,
    detect_drg_unbundling,
    evaluate_copay_exemption,
)
from src.bilun.domain.optimization.copay_exemption_context import (
    build_copay_exemption_input,
)
from src.bilun.domain.claims import load_sut_claim_dataset
from src.bilun.domain.claims.patient_context import build_patient_claim_context
from src.bilun.domain.claims.config import SUTDataSourceConfigError
from src.bilun.domain.claims.errors import ClaimValidationError
from src.bilun.domain.optimization.claim_context import (
    build_copay_rate_claim_context,
    build_surcharge_claim_context,
)
from src.bilun.domain.optimization.exactness import is_exact_output
from src.bilun.domain.optimization.runtime_claim_context import ClaimContextManager

from .provenance import attach_bilun_data_source, read_active_bilun_data_source

router = APIRouter()
PIPELINE_MODE: str | None = None
logger = logging.getLogger("bilun.api.optimization")


def _sanitize_optimization_summary(payload: dict) -> dict:
    """Attach provenance without overwriting claim-backed exactness fields."""
    return attach_bilun_data_source(payload)


def _pipeline_mode() -> str:
    override = PIPELINE_MODE
    if isinstance(override, str):
        return override.strip().lower()
    return get_pipeline_mode()


def _get_active_bilun_build_id(reader) -> str | None:
    return _get_active_build_id_or_none(reader, scope="bilun")


@router.get("/optimization-summary", response_model=BilunCachePayloadResponse)
def get_optimization_summary():
    """
    Cohort-level BILUN Optimization intelligence summary.

    Returns pre-computed findings from 5 gazette-based rule engines:
      1. Copayment Exemption Checker (EK-1A): chronic disease exemptions
      2. Surcharge Exposure Analyzer (EK-2G): unavailable without exact claim lines
      3. Copayment Rate Exposure (EK-2C-1): unavailable without exact claim lines
      4. Temporal Price Validation (EK-2B/2C): price changes across gazette dates
      5. DRG Package Unbundling (EK-2C): unavailable without exact itemized claims
    """
    mode = _pipeline_mode()
    if mode in {"hybrid", "persistent"}:
        reader = _get_cache_reader()
        active_build = _get_active_bilun_build_id(reader)
        if active_build is not None:
            payload = read_cache_json_payload(
                reader, "cohort_optimization_summary", active_build
            )
            if payload is not None:
                return _sanitize_optimization_summary(payload)
        if mode == "persistent":
            raise ServiceUnavailableError(
                "No active BILUN build. Run scripts/bilun/build_cache.py --activate"
            )

    # Legacy fallback removed - requires active build
    raise ServiceUnavailableError(
        "Optimization summary requires an active analytics build."
    )


@router.get("/patient/{patient_id}/optimization", response_model=PatientOptimizationResponse)
def get_patient_optimization(patient_id: str):
    """
    Per-patient BILUN Optimization findings.

    Runs optimization rule engines for a single patient on-demand:
      1. Copay exemptions: checks patient diagnoses against EK-1A
      2. Surcharge exposure: unavailable without exact billed procedure lines
      3. Copay rate exposure: unavailable without exact billed procedure lines
      5. DRG unbundling risk: unavailable without exact itemized claim lines

      Feature 4 (temporal) is system-level only — use /api/optimization-summary.
    """
    mode = _pipeline_mode()
    if mode in {"hybrid", "persistent"}:
        reader = _get_cache_reader()
        active_build = _get_active_bilun_build_id(reader)
        if active_build is not None:
            cached_diagnoses = read_cache_patient_diagnoses(
                reader, active_build, patient_id
            )
            if cached_diagnoses is not None:
                chapters = _extract_patient_icd10_chapters(cached_diagnoses)
                data_source = read_active_bilun_data_source(reader, active_build)
                surcharge_context = None
                copay_rate_context = None
                try:
                    claim_dataset = load_sut_claim_dataset()
                except (
                    ClaimValidationError,
                    FileNotFoundError,
                    OSError,
                    SUTDataSourceConfigError,
                    ValueError,
                ) as exc:
                    logger.warning(
                        "Exact BILUN claim context unavailable for patient %s: %s",
                        patient_id,
                        exc,
                    )
                    claim_dataset = None
                if claim_dataset is not None:
                    procedure_lines = claim_dataset.procedure_lines_by_patient.get(
                        patient_id,
                        (),
                    )
                    surcharge_context = build_surcharge_claim_context(
                        patient_id,
                        procedure_lines,
                    )
                    copay_rate_context = build_copay_rate_claim_context(
                        patient_id,
                        procedure_lines,
                    )
                with ClaimContextManager(
                    surcharge=surcharge_context,
                    copay_rate=copay_rate_context,
                ):
                    surcharge_exposure = analyze_surcharge_exposure(chapters)
                    copay_rate_exposure = analyze_copay_rate_exposure(chapters)

                patient_claim_context = None
                if claim_dataset is not None:
                    patient_claim_context = build_patient_claim_context(
                        patient_id,
                        claim_dataset,
                    )
                drg_unbundling = detect_drg_unbundling(
                    chapters,
                    patient_claim_context,
                )
                patient_claims = ()
                patient_profile = None
                if claim_dataset is not None:
                    patient_claims = claim_dataset.claims_by_patient.get(
                        patient_id,
                        (),
                    )
                    patient_profile = claim_dataset.copay_profiles_by_patient.get(
                        patient_id
                    )
                copay_input = build_copay_exemption_input(
                    diagnoses=cached_diagnoses,
                    patient_profile=patient_profile,
                    patient_claims=patient_claims,
                )
                return {
                    "patient_id": patient_id,
                    "n_diagnoses": len(cached_diagnoses),
                    "diagnoses": cached_diagnoses,
                    "icd10_chapters": sorted(chapters),
                    "copay_exemptions": evaluate_copay_exemption(copay_input),
                    "surcharge_exposure": surcharge_exposure,
                    "copay_rate_exposure": copay_rate_exposure,
                    "drg_unbundling": drg_unbundling,
                    "data_source": data_source,
                }
            # Patient not in cache — could be unknown patient
            if mode == "persistent":
                raise PatientNotFound(
                    f"Patient {patient_id} not found in canonical cache"
                )
        if mode == "persistent":
            raise ServiceUnavailableError(
                "No active BILUN build. Run scripts/bilun/build_cache.py --activate"
            )

    # Legacy fallback removed - requires active build
    raise ServiceUnavailableError(
        "Patient optimization requires an active analytics build."
    )


@router.get("/revenue-recovery", response_model=BilunCachePayloadResponse)
def get_revenue_recovery():
    """
    Cohort-level revenue recovery dashboard.

    Returns aggregated savings across all patients from the 5 normative
    billing algorithms: total recoverable TRY by category (lab, drug,
    copay, billing strategy), top-10 highest-impact patients, per-patient
    summaries for cohort tables, and priority distribution.
    """
    mode = _pipeline_mode()
    if mode in {"hybrid", "persistent"}:
        reader = _get_cache_reader()
        active_build = _get_active_bilun_build_id(reader)
        if active_build is not None:
            payload = read_cache_json_payload(
                reader, "cohort_recovery_summary", active_build
            )
            if payload is not None:
                if not payload.get("patient_summaries"):
                    billing_rows = read_cache_json_payload_rows(
                        reader, "patient_billing_report_rows", active_build
                    )
                    if billing_rows:
                        summaries = [
                            patient_recovery_summary_from_payload(report)
                            for _, report in billing_rows
                        ]
                        summaries.sort(
                            key=lambda row: row["total_recoverable_try"],
                            reverse=True,
                        )
                        payload = {**payload, "patient_summaries": summaries}
                return attach_bilun_data_source(payload)
        if mode == "persistent":
            raise ServiceUnavailableError(
                "No active BILUN build. Run scripts/bilun/build_cache.py --activate"
            )

    # Legacy fallback removed - requires active build
    raise ServiceUnavailableError(
        "Revenue recovery requires an active analytics build."
    )

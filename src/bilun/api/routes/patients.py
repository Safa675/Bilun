"""BILUN patient listing, search, and outcome endpoints."""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Query

from src.bilun.shared.pipeline import normalize_cached_drg_summary_payload
from src.bilun.shared.exceptions import PatientNotFound, ServiceUnavailableError
from src.bilun.api.schemas import PatientSearchResponse
from src.bilun.api.schemas import (
    BILUNPatientsListResponse,
    BilunPatientOutcomeResponse,
    PatientClaimDetailResponse,
    PatientClaimsListResponse,
    PatientClaimSummary,
    ClaimProcedureLine,
    ClaimMaterialLine,
    ClaimDrugLine,
)
from src.bilun.shared.state import (
    _get_active_build_id_or_none,
    _get_cache_reader,
    get_pipeline_mode,
)
from src.bilun.db import (
    has_json_payload_rows as cache_json_payload_rows_exist,
    read_all_patient_ids as read_cache_all_patient_ids,
    read_patient_meta as read_cache_patient_meta,
    read_patient_meta_by_ids as read_cache_patient_meta_by_ids,
    read_patient_outcome_base,
    read_patient_outcome_expensive,
    search_patient_ids as search_cache_patient_ids,
)
from src.bilun.domain.claims import load_sut_claim_dataset
from src.bilun.domain.claims.config import SUTDataSourceConfigError
from src.bilun.domain.claims.errors import ClaimValidationError
from src.bilun.domain.claims.models import ClaimHeader

from .provenance import attach_bilun_data_source, read_active_bilun_data_source

router = APIRouter()
PIPELINE_MODE: str | None = None
logger = logging.getLogger("bilun.api.patients")


def _money(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _serialize_claim_summary(
    header: ClaimHeader,
    *,
    rollup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = {
        "claim_id": header.claim_id,
        "episode_id": header.episode_id,
        "claim_type": header.claim_type,
        "admission_date": header.admission_date,
        "discharge_date": header.discharge_date,
        "claim_start_date": header.claim_start_date,
        "claim_end_date": header.claim_end_date,
        "primary_icd10": header.primary_icd10,
        "expected_total_billed_try": _money(header.expected_total_billed_try),
        "expected_total_payable_try": _money(header.expected_total_payable_try),
        "expected_denial_reason": header.expected_denial_reason,
        "scenario_tag": header.scenario_tag,
    }
    if rollup is not None:
        summary["recoverable_try"] = float(rollup.get("total_recoverable_try", 0.0))
        summary["priority"] = rollup.get("priority", "low")
    else:
        summary["recoverable_try"] = None
        summary["priority"] = None
    return summary


def _load_bill_report_rollups(patient_id: str) -> dict[str, dict[str, Any]]:
    """Load per-bill recoverable/priority rollups from the analytics cache.

    Returns ``claim_id -> {total_recoverable_try, priority}``. Empty when no
    active build or the per-bill table has not been populated yet.
    """
    mode = _pipeline_mode()
    if mode not in {"hybrid", "persistent"}:
        return {}

    try:
        reader = _get_cache_reader()
        active_build = _get_active_build_id_or_none(reader, scope="bilun")
        if active_build is None:
            return {}
        if not cache_json_payload_rows_exist(
            reader, "patient_bill_billing_report_rows", active_build
        ):
            return {}

        prefix = f"{patient_id}::"
        rows = reader.execute(
            """
            SELECT patient_id, payload_json
            FROM patient_bill_billing_report_rows
            WHERE build_id = ? AND patient_id LIKE ?
            """,
            [active_build, f"{prefix}%"],
        ).fetchall()
    except Exception as exc:
        logger.debug(
            "Per-bill billing rollups unavailable for %s: %s", patient_id, exc
        )
        return {}

    rollups: dict[str, dict[str, Any]] = {}
    for row_key, payload_json in rows:
        if not payload_json:
            continue
        claim_id = str(row_key)[len(prefix) :]
        if not claim_id:
            continue
        try:
            payload = json.loads(payload_json)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict):
            rollups[claim_id] = payload
    return rollups


def _load_claim_dataset() -> Any | None:
    try:
        return load_sut_claim_dataset()
    except (
        ClaimValidationError,
        FileNotFoundError,
        OSError,
        SUTDataSourceConfigError,
        ValueError,
    ) as exc:
        logger.warning("Exact BILUN claim dataset unavailable: %s", exc)
        return None


def _pipeline_mode() -> str:
    override = PIPELINE_MODE
    if isinstance(override, str):
        return override.strip().lower()
    return get_pipeline_mode()


def _active_bilun_build_or_503(reader) -> str:
    active_build = _get_active_build_id_or_none(reader, scope="bilun")
    if active_build is None:
        raise ServiceUnavailableError(
            "No active BILUN analytics build. "
            "Run scripts/bilun/build_cache.py --activate"
        )
    return active_build


@router.get("/patients", response_model=BILUNPatientsListResponse)
def get_bilun_patients():
    """Return BILUN patient count and initial patient metadata."""
    mode = _pipeline_mode()
    if mode not in {"hybrid", "persistent"}:
        raise ServiceUnavailableError(
            "BILUN patient listing requires an active analytics build. "
            "Run scripts/bilun/build_cache.py --activate"
        )

    reader = _get_cache_reader()
    active_build = _active_bilun_build_or_503(reader)
    meta_list = read_cache_patient_meta(reader, active_build)
    all_ids = [m["patient_id"] for m in meta_list]
    return {
        "patients": all_ids,
        "total": len(all_ids),
        "patient_meta": meta_list,
        "cache_mode": "bilun_canonical",
        "data_source": read_active_bilun_data_source(reader, active_build),
    }


@router.get("/patients/search", response_model=PatientSearchResponse)
def search_bilun_patients(
    q: str = Query("", description="Prefix to match against patient_id"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
):
    """Fast BILUN prefix search on patient IDs."""
    mode = _pipeline_mode()
    if mode not in {"hybrid", "persistent"}:
        raise ServiceUnavailableError(
            "BILUN patient search requires an active analytics build. "
            "Run scripts/bilun/build_cache.py --activate"
        )

    reader = _get_cache_reader()
    active_build = _active_bilun_build_or_503(reader)
    query = q.strip()
    if not query:
        matched_ids = read_cache_all_patient_ids(reader, active_build)[:limit]
    else:
        matched_ids = search_cache_patient_ids(reader, active_build, query, limit)

    matched_meta = read_cache_patient_meta_by_ids(reader, active_build, matched_ids)
    meta_lookup = {m["patient_id"]: m for m in matched_meta}
    results = []
    for pid in matched_ids:
        meta = meta_lookup.get(pid, {})
        results.append(
            {
                "patient_id": pid,
                "age": meta.get("age"),
                "sex": meta.get("sex"),
                "sex_raw": meta.get("sex_raw"),
                "weight_kg": meta.get("weight_kg"),
                "doctor_code": meta.get("doctor_code"),
                "comorbidity_conditions": meta.get("comorbidity_conditions", []),
            }
        )
    return {"results": results, "total_matched": len(results)}


@router.get("/patient/{patient_id}/outcome", response_model=BilunPatientOutcomeResponse)
def get_bilun_patient_outcome(
    patient_id: str,
    include_expensive: bool = Query(
        True, description="Include expensive DRG pricing analytics"
    ),
):
    """BILUN patient outcome data without requiring an active IHP build."""
    mode = _pipeline_mode()
    if mode not in {"hybrid", "persistent"}:
        raise ServiceUnavailableError(
            "BILUN patient outcome data requires an active analytics build. "
            "Run scripts/bilun/build_cache.py --activate"
        )

    reader = _get_cache_reader()
    active_build = _active_bilun_build_or_503(reader)
    base = read_patient_outcome_base(reader, active_build, patient_id)

    expensive = None
    expensive_state = "skipped"
    if include_expensive:
        expensive = read_patient_outcome_expensive(reader, active_build, patient_id)
        expensive_state = "ready" if expensive is not None else "missing"

    if base is None and expensive is None:
        raise PatientNotFound(f"No BILUN outcome profile for patient {patient_id}")

    base_payload = base or {}
    expensive = expensive or {}
    return attach_bilun_data_source(
        {
            **base_payload,
            "patient_id": patient_id,
            "eci": None,
            "narrative": "",
            "feature_bar": [],
            "cohort_ranking": [],
            "patient_percentile": None,
            "cohort_total": 0,
            "feature_correlations": [],
            "drg_summary": normalize_cached_drg_summary_payload(
                expensive.get("drg_summary")
            ),
            "consistency_warnings": expensive.get("consistency_warnings") or [],
            "expensive_analytics": {
                "state": expensive_state,
                "included": include_expensive,
            },
        },
        read_active_bilun_data_source(reader, active_build),
    )


@router.get("/patients/{patient_id}/claims", response_model=PatientClaimsListResponse)
def get_patient_claims(patient_id: str):
    """List all exact SUT claims for a single patient."""
    dataset = _load_claim_dataset()
    if dataset is None:
        raise ServiceUnavailableError(
            "Exact claim dataset is unavailable. "
            "Run scripts/bilun/build_sut_claims.py to generate it."
        )

    claims = dataset.claims_by_patient.get(patient_id, ())
    if not claims:
        raise PatientNotFound(f"No claims found for patient {patient_id}")

    rollups = _load_bill_report_rollups(patient_id)

    return attach_bilun_data_source(
        {
            "patient_id": patient_id,
            "claims": [
                _serialize_claim_summary(c, rollup=rollups.get(c.claim_id))
                for c in claims
            ],
            "total": len(claims),
        },
    )


@router.get(
    "/patients/{patient_id}/claims/{claim_id}",
    response_model=PatientClaimDetailResponse,
)
def get_patient_claim_detail(patient_id: str, claim_id: str):
    """Return one claim with its procedure, material and drug lines."""
    dataset = _load_claim_dataset()
    if dataset is None:
        raise ServiceUnavailableError(
            "Exact claim dataset is unavailable. "
            "Run scripts/bilun/build_sut_claims.py to generate it."
        )

    claims = dataset.claims_by_patient.get(patient_id, ())
    header = next((c for c in claims if c.claim_id == claim_id), None)
    if header is None:
        raise PatientNotFound(
            f"Claim {claim_id} not found for patient {patient_id}"
        )

    procedures = dataset.procedure_lines_by_claim.get(claim_id, ())
    materials = dataset.material_lines_by_claim.get(claim_id, ())
    drugs = dataset.drug_lines_by_claim.get(claim_id, ())

    return attach_bilun_data_source(
        {
            "claim_id": header.claim_id,
            "patient_id": header.patient_id,
            "episode_id": header.episode_id,
            "claim_type": header.claim_type,
            "facility_tier": header.facility_tier,
            "provider_type": header.provider_type,
            "department": header.department,
            "admission_date": header.admission_date,
            "discharge_date": header.discharge_date,
            "claim_start_date": header.claim_start_date,
            "claim_end_date": header.claim_end_date,
            "primary_icd10": header.primary_icd10,
            "package_candidate": header.package_candidate,
            "expected_total_billed_try": _money(header.expected_total_billed_try),
            "expected_total_payable_try": _money(header.expected_total_payable_try),
            "expected_denial_reason": header.expected_denial_reason,
            "scenario_tag": header.scenario_tag,
            "occupational_context": header.occupational_context,
            "procedures": [
                {
                    "procedure_line_id": p.procedure_line_id,
                    "procedure_date": p.procedure_date,
                    "procedure_code": p.procedure_code,
                    "procedure_name": p.procedure_name,
                    "procedure_category": p.procedure_category,
                    "quantity": p.quantity,
                    "unit_price_try": _money(p.unit_price_try),
                    "billed_amount_try": _money(p.billed_amount_try),
                    "expected_payable_try": _money(p.expected_payable_try),
                    "is_package_included": p.is_package_included,
                    "package_code": p.package_code,
                    "denial_reason_expected": p.denial_reason_expected,
                    "rule_trace_expected": p.rule_trace_expected,
                }
                for p in procedures
            ],
            "materials": [
                {
                    "material_line_id": m.material_line_id,
                    "material_date": m.material_date,
                    "material_code": m.material_code,
                    "material_name": m.material_name,
                    "material_type": m.material_type,
                    "specialty_category": m.specialty_category,
                    "quantity": m.quantity,
                    "unit_price_try": _money(m.unit_price_try),
                    "billed_amount_try": _money(m.billed_amount_try),
                    "expected_payable_try": _money(m.expected_payable_try),
                    "is_bundled": m.is_bundled,
                    "requires_pre_auth": m.requires_pre_auth,
                    "denial_reason_expected": m.denial_reason_expected,
                    "rule_trace_expected": m.rule_trace_expected,
                }
                for m in materials
            ],
            "drugs": [
                {
                    "drug_claim_line_id": d.drug_claim_line_id,
                    "prescription_id": d.prescription_id,
                    "drug_claim_date": d.drug_claim_date,
                    "drug_name": d.drug_name,
                    "drug_code": d.drug_code,
                    "barkod": d.barkod,
                    "equivalence_group": d.equivalence_group,
                    "quantity": d.quantity,
                    "unit_price_try": _money(d.unit_price_try),
                    "billed_amount_try": _money(d.billed_amount_try),
                    "expected_payable_try": _money(d.expected_payable_try),
                    "discount_tier_expected": _money(d.discount_tier_expected),
                    "denial_reason_expected": d.denial_reason_expected,
                    "rule_trace_expected": d.rule_trace_expected,
                }
                for d in drugs
            ],
        },
    )

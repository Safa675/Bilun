"""BILUN patient listing, search, and outcome endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.bilun.shared.pipeline import normalize_cached_drg_summary_payload
from src.bilun.shared.exceptions import PatientNotFound, ServiceUnavailableError
from src.bilun.api.schemas import PatientSearchResponse
from src.bilun.api.schemas import BILUNPatientsListResponse, BilunPatientOutcomeResponse
from src.bilun.shared.state import (
    _get_active_build_id_or_none,
    _get_cache_reader,
    get_pipeline_mode,
)
from src.bilun.db import (
    read_all_patient_ids as read_cache_all_patient_ids,
    read_patient_meta as read_cache_patient_meta,
    read_patient_meta_by_ids as read_cache_patient_meta_by_ids,
    read_patient_outcome_base,
    read_patient_outcome_expensive,
    search_patient_ids as search_cache_patient_ids,
)

from .provenance import attach_bilun_data_source, read_active_bilun_data_source

router = APIRouter()
PIPELINE_MODE: str | None = None


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

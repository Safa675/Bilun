"""Cohort compliance index — live finding families for the Compliance tab."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.bilun.api.schemas import BilunCachePayloadResponse
from src.bilun.db import read_json_payload as read_cache_json_payload
from src.bilun.db import read_json_payload_rows as read_cache_json_payload_rows
from src.bilun.domain.billing.cohort_compliance import (
    INDEX_SURFACES,
    build_cohort_compliance_index,
    empty_cohort_compliance_index,
    slice_compliance_index,
)
from src.bilun.domain.billing.wavea_evidence import (
    original_five_report_payload,
)
from src.bilun.shared.exceptions import ServiceUnavailableError, ValidationError
from src.bilun.shared.state import (
    _get_active_build_id_or_none,
    _get_cache_reader,
    get_pipeline_mode,
)

from .provenance import attach_bilun_data_source, read_active_bilun_data_source
from .wavea_gate import complete_build_evidence_available, declared_patient_report_count

router = APIRouter(tags=["compliance"])

_DEFAULT_LIMIT = 500
_MAX_LIMIT = 5000


class ComplianceIndexRequest(BaseModel):
    surface: str | None = None
    patient_id: list[str] | None = None
    limit: int = _DEFAULT_LIMIT
    offset: int = 0


def _pipeline_mode() -> str:
    return get_pipeline_mode()


def _get_active_bilun_build_id(reader) -> str | None:
    return _get_active_build_id_or_none(reader, scope="bilun")


def _parse_patient_ids(patient_id: list[str] | None) -> frozenset[str] | None:
    if not patient_id:
        return None
    parsed: set[str] = set()
    for raw in patient_id:
        for part in str(raw).split(","):
            value = part.strip()
            if value:
                parsed.add(value)
    return frozenset(parsed) if parsed else None


def _compliance_index_response(
    surface: str | None = None,
    patient_id: list[str] | None = None,
    limit: int = _DEFAULT_LIMIT,
    offset: int = 0,
):
    normalized_surface = (surface or "").strip() or None
    if normalized_surface is not None and normalized_surface not in INDEX_SURFACES:
        raise ValidationError(
            "Invalid compliance index surface. "
            f"Expected one of: {', '.join(INDEX_SURFACES)}.",
            surface=normalized_surface,
        )
    if limit <= 0 or limit > _MAX_LIMIT:
        raise ValidationError(
            f"limit must be between 1 and {_MAX_LIMIT}.",
            limit=limit,
        )
    if offset < 0:
        raise ValidationError("offset must be greater than or equal to 0.")

    mode = _pipeline_mode()
    if mode not in {"hybrid", "persistent"}:
        raise ServiceUnavailableError(
            "Compliance index requires an active analytics build."
        )

    reader = _get_cache_reader()
    active_build = _get_active_bilun_build_id(reader)
    if active_build is None:
        if mode == "persistent":
            raise ServiceUnavailableError(
                "No active BILUN build. Run scripts/bilun/build_cache.py --activate"
            )
        raise ServiceUnavailableError(
            "Compliance index requires an active analytics build."
        )

    payload: dict[str, Any] | None
    try:
        payload = read_cache_json_payload(
            reader, "cohort_compliance_index", active_build
        )
    except Exception:
        payload = None

    data_source = read_active_bilun_data_source(reader, active_build)
    if payload is None:
        unavailable = empty_cohort_compliance_index(artifacts_available=False)
        unavailable["pagination"] = {
            "total_matching": 0,
            "limit": limit,
            "offset": offset,
            "has_more": False,
        }
        unavailable["query"] = {
            "surface": normalized_surface,
            "limit": limit,
            "offset": offset,
        }
        return attach_bilun_data_source(unavailable, data_source)

    try:
        wavea_index = read_cache_json_payload(
            reader, "wavea_evidence_index", active_build
        )
    except Exception:
        wavea_index = None
    if not complete_build_evidence_available(reader, wavea_index, active_build):
        # Cached aggregate counts have no rule IDs. Rebuild from the stored
        # patient rows so a draft or unmarked old cache cannot leak Wave A
        # statuses through a count even when its finding rows are empty.
        try:
            expected = declared_patient_report_count(reader, active_build)
            reports = read_cache_json_payload_rows(
                reader, "patient_billing_report_rows", active_build
            )
            if (
                len(reports) != expected
                or payload.get("n_patients") != expected
                or any(
                    report.get("patient_id") != patient_id
                    or not isinstance(report.get("claim_compliance"), dict)
                    or not all(
                        isinstance(report["claim_compliance"].get(field), list)
                        for field in ("findings", "evaluations")
                    )
                    for patient_id, report in reports
                )
            ):
                raise ValueError("Draft build patient reports disagree with build metadata")
            payload = build_cohort_compliance_index(
                {
                    patient_id: original_five_report_payload(report)
                    for patient_id, report in reports
                }
            )
        except Exception:
            unavailable = empty_cohort_compliance_index(artifacts_available=False)
            unavailable["pagination"] = {
                "total_matching": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False,
            }
            return attach_bilun_data_source(unavailable, data_source)

    sliced = slice_compliance_index(
        payload,
        surface=normalized_surface,
        patient_ids=_parse_patient_ids(patient_id),
        limit=limit,
        offset=offset,
    )
    return attach_bilun_data_source(sliced, data_source)


@router.get("/compliance-index", response_model=BilunCachePayloadResponse)
def get_compliance_index(
    surface: str | None = None,
    patient_id: Annotated[list[str] | None, Query()] = None,
    limit: int = _DEFAULT_LIMIT,
    offset: int = 0,
):
    """Cohort rollup of cached compliance ``recommended_actions``.

    Built at cache time into ``cohort_compliance_index``. Old caches that
    predate this table return ``artifacts_available: false`` with null
    counts — never invented zeros.
    """
    return _compliance_index_response(surface, patient_id, limit, offset)


@router.post("/compliance-index", response_model=BilunCachePayloadResponse)
def post_compliance_index(request: ComplianceIndexRequest):
    """Body-based equivalent for cohorts too large for a safe GET request line."""
    return _compliance_index_response(
        request.surface,
        request.patient_id,
        request.limit,
        request.offset,
    )

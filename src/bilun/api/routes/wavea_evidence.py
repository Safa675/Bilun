"""Build-scoped Wave A evidence drill-down, hidden until full capability activation."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.bilun.api.schemas import BilunCachePayloadResponse
from src.bilun.db import read_json_payload, read_json_payload_row
from src.bilun.domain.billing.wavea_full_evidence import (
    FULL_EVIDENCE_SCHEMA_VERSION,
    validate_full_wavea_evidence_detail,
)
from src.bilun.shared.exceptions import PatientNotFound, ServiceUnavailableError, ValidationError
from src.bilun.shared.state import (
    _get_active_build_id_or_none,
    _get_cache_reader,
    get_pipeline_mode,
)

from .provenance import attach_bilun_data_source, read_active_bilun_data_source
from .wavea_gate import complete_build_evidence_available

router = APIRouter(tags=["wavea_evidence"])
_MAX_LIMIT = 500
_DEFAULT_LIMIT = 20
_STATUSES = ("evaluated", "missing_inputs", "unavailable")
_KINDS = ("evaluations", "reviews", "advisories", "financial_rows")
_COHORT_ROW_KINDS = ("reviews", "advisories", "financial_rows")


class WaveAEvidenceIndexRequest(BaseModel):
    patient_id: list[str] | None = None
    rule_id: str | None = None
    limit: int = _DEFAULT_LIMIT
    offset: int = 0


class WaveAEvidenceRowsRequest(BaseModel):
    kind: str = "reviews"
    patient_id: list[str] | None = None
    claim_id: str | None = None
    rule_id: str | None = None
    limit: int = _DEFAULT_LIMIT
    offset: int = 0


def _validate_page(limit: int, offset: int) -> None:
    if not 1 <= limit <= _MAX_LIMIT or offset < 0:
        raise ValidationError(f"limit must be 1..{_MAX_LIMIT} and offset nonnegative")


def _selected_patient_ids(values: list[str] | None) -> set[str] | None:
    if values is None:
        return None
    selected = {part.strip() for value in values for part in str(value).split(",") if part.strip()}
    return selected


def _status_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError("Malformed Wave A status counters")
    result = {}
    for status in _STATUSES:
        count = value.get(status)
        if type(count) is not int or count < 0:
            raise ValueError("Malformed Wave A status count")
        result[status] = count
    return result


def _compact_patient_row(patient_id: str, summary: Any, rule_id: str | None) -> dict[str, Any]:
    if not isinstance(summary, dict):
        raise ValueError("Malformed Wave A patient summary")
    if not summary.get("available"):
        return {
            "patient_id": patient_id,
            "available": False,
            "unavailable_reason": summary.get("unavailable_reason") or "wavea_capability_unavailable",
            "counts": None,
        }
    counts = summary.get("counts")
    if not isinstance(counts, dict) or not isinstance(counts.get("by_group"), dict):
        raise ValueError("Malformed Wave A patient counters")
    for statuses in counts["by_group"].values():
        _status_counts(statuses)
    row_counts = {
        "by_group": counts["by_group"],
        "evaluation_count": counts["evaluation_count"],
        "review_count": counts["review_count"],
        "advisory_count": counts["advisory_count"],
        "financial_count": counts["financial_count"],
    }
    if rule_id is not None:
        by_rule = counts.get("by_rule")
        if not isinstance(by_rule, dict):
            raise ValueError("Malformed Wave A rule counters")
        row_counts["by_rule"] = {rule_id: _status_counts(by_rule[rule_id])} if rule_id in by_rule else {}
    return {"patient_id": patient_id, "available": True, "unavailable_reason": None, "counts": row_counts}


def _active_index() -> tuple[Any, str, dict[str, Any] | None]:
    if get_pipeline_mode() not in {"hybrid", "persistent"}:
        raise ServiceUnavailableError("Wave A evidence requires an active analytics build")
    reader = _get_cache_reader()
    build_id = _get_active_build_id_or_none(reader, scope="bilun")
    if build_id is None:
        raise ServiceUnavailableError("Wave A evidence requires an active BILUN build")
    try:
        index = read_json_payload(reader, "wavea_evidence_index", build_id)
    except Exception:
        index = None
    return reader, build_id, index


def _ready(reader: Any, index: dict[str, Any] | None, build_id: str) -> bool:
    return complete_build_evidence_available(reader, index, build_id)


def _unavailable(
    reader: Any,
    build_id: str,
    limit: int,
    offset: int,
    reason: str = "wavea_capability_unavailable",
) -> dict[str, Any]:
    return attach_bilun_data_source(
        {
            "available": False,
            "unavailable_reason": reason,
            "counts": None,
            "rows": [],
            "pagination": {
                "total_matching": None,
                "limit": limit,
                "offset": offset,
                "has_more": None,
            },
        },
        read_active_bilun_data_source(reader, build_id),
    )


def _bill_report_matches_detail(report: Any, detail: dict[str, Any], patient_id: str, claim_id: str) -> bool:
    """A bill preview must describe its own exhaustive bill-scope evidence."""
    if not isinstance(report, dict) or report.get("patient_id") != patient_id or (
        report.get("claim_id") not in (None, claim_id)
        or report.get("scope") not in (None, "bill")
    ):
        return False
    counts = detail["counts"]
    expected_coverage = {
        "schema_version": detail["schema_version"],
        "available": detail["available"],
        "unavailable_reason": detail["unavailable_reason"],
        "tracked_rule_count": len(counts["by_rule"]),
        "evaluation_count": counts["evaluation_count"],
        "by_group": counts["by_group"],
    }
    if report.get("wavea_coverage") != expected_coverage:
        return False
    for report_key, detail_key in (
        ("claim_reviews", "reviews"),
        ("claim_advisories", "advisories"),
        ("financial_findings", "financial_rows"),
    ):
        block = report.get(report_key)
        source = detail[detail_key]
        if not isinstance(block, dict) or not isinstance(block.get("rows"), list) or (
            block.get("available") is not detail["available"]
            or block.get("unavailable_reason") != detail["unavailable_reason"]
            or block.get("total_rows") != len(source)
            or block["rows"] != source[: len(block["rows"])]
            or block.get("has_more") is not (len(block["rows"]) < len(source))
        ):
            return False
    return True


@router.get("/wavea-evidence-index", response_model=BilunCachePayloadResponse)
def get_wavea_evidence_index(
    patient_id: Annotated[list[str] | None, Query()] = None,
    rule_id: str | None = None,
    limit: int = _DEFAULT_LIMIT,
    offset: int = 0,
):
    """Return compact exact cohort counters with bounded patient summaries."""
    return _wavea_evidence_index_response(patient_id, rule_id, limit, offset)


@router.post("/wavea-evidence-index", response_model=BilunCachePayloadResponse)
def post_wavea_evidence_index(request: WaveAEvidenceIndexRequest):
    """Body-based equivalent for large selected patient sets."""
    return _wavea_evidence_index_response(
        request.patient_id, request.rule_id, request.limit, request.offset
    )


def _wavea_evidence_index_response(
    patient_id: list[str] | None,
    rule_id: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    _validate_page(limit, offset)
    reader, build_id, index = _active_index()
    if not _ready(reader, index, build_id):
        return _unavailable(reader, build_id, limit, offset)
    assert index is not None
    patients = index.get("patients")
    if not isinstance(patients, dict):
        return _unavailable(reader, build_id, limit, offset)
    rule_id = rule_id.strip() if rule_id is not None else None
    if rule_id == "":
        raise ValidationError("rule_id must not be blank")
    selected = _selected_patient_ids(patient_id)
    if selected is not None and not selected <= patients.keys():
        return _unavailable(reader, build_id, limit, offset, "requested_patient_not_in_build")
    patient_ids = sorted(pid for pid in patients if selected is None or pid in selected)
    try:
        unavailable_count = sum(not patients[pid]["available"] for pid in patient_ids)
        by_rule: dict[str, dict[str, int]] = {}
        by_group: dict[str, dict[str, int]] = {}
        evaluation_count = review_count = advisory_count = financial_count = 0
        for pid in patient_ids:
            patient_counts = patients[pid]["counts"]
            if not isinstance(patient_counts, dict):
                raise ValueError("Malformed Wave A patient counters")
            for key in (
                "evaluation_count", "review_count", "advisory_count", "financial_count"
            ):
                value = patient_counts.get(key)
                if type(value) is not int or value < 0:
                    raise ValueError("Malformed Wave A evidence count")
            evaluation_count += patient_counts["evaluation_count"]
            review_count += patient_counts["review_count"]
            advisory_count += patient_counts["advisory_count"]
            financial_count += patient_counts["financial_count"]
            for source_key, target in (("by_group", by_group), ("by_rule", by_rule)):
                source = patient_counts.get(source_key)
                if not isinstance(source, dict):
                    raise ValueError("Malformed Wave A counters")
                identities = (rule_id,) if source_key == "by_rule" and rule_id is not None else (
                    () if source_key == "by_rule" else source.keys()
                )
                for identity in identities:
                    if identity not in source:
                        continue
                    statuses = _status_counts(source[identity])
                    total = target.setdefault(identity, {status: 0 for status in _STATUSES})
                    for status in _STATUSES:
                        total[status] += statuses[status]
        counts: dict[str, Any] = {
            "by_group": by_group,
            "evaluation_count": evaluation_count,
            "review_count": review_count,
            "advisory_count": advisory_count,
            "financial_count": financial_count,
        }
        if rule_id is not None:
            counts["by_rule"] = by_rule
        page_ids = patient_ids[offset : offset + limit]
        rows = [_compact_patient_row(pid, patients[pid], rule_id) for pid in page_ids]
    except (KeyError, TypeError, ValueError):
        return _unavailable(reader, build_id, limit, offset)
    return attach_bilun_data_source(
        {
            "available": True,
            "unavailable_reason": "some_patients_unavailable" if unavailable_count else None,
            "patient_coverage": {
                "selected": len(patient_ids),
                "available": len(patient_ids) - unavailable_count,
                "unavailable": unavailable_count,
            },
            "counts": counts,
            "rows": rows,
            "pagination": {
                "total_matching": len(patient_ids),
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < len(patient_ids),
            },
        },
        read_active_bilun_data_source(reader, build_id),
    )


@router.get("/wavea-evidence/{patient_id}", response_model=BilunCachePayloadResponse)
def get_wavea_evidence_detail(
    patient_id: str,
    scope: str = "patient",
    kind: str = "evaluations",
    claim_id: str | None = None,
    rule_id: str | None = None,
    evidence_id: str | None = None,
    limit: int = _DEFAULT_LIMIT,
    offset: int = 0,
):
    """Page stored patient or bill evidence; no evaluator runs on API requests."""
    _validate_page(limit, offset)
    if scope not in ("patient", "bill"):
        raise ValidationError("scope must be patient or bill")
    if scope == "bill" and (claim_id is None or not claim_id.strip()):
        raise ValidationError("bill scope requires a nonblank claim_id")
    if kind not in _KINDS:
        raise ValidationError(f"kind must be one of: {', '.join(_KINDS)}")
    if evidence_id is not None:
        prefix = {
            "reviews": "wavea_review:",
            "advisories": "wavea_advisory:",
            "financial_rows": "wavea_financial:",
        }.get(kind)
        if prefix is None or not evidence_id.startswith(prefix) or len(evidence_id) <= len(prefix):
            raise ValidationError("evidence_id does not match the selected evidence kind")
    reader, build_id, index = _active_index()
    if not _ready(reader, index, build_id):
        return _unavailable(reader, build_id, limit, offset)
    assert index is not None
    patients = index.get("patients")
    if not isinstance(patients, dict) or patient_id not in patients:
        raise PatientNotFound(f"Patient {patient_id} not found in Wave A evidence")
    bill_key = f"{patient_id}::{claim_id}" if scope == "bill" else None
    table_name = "wavea_bill_evidence_detail" if scope == "bill" else "wavea_evidence_detail"
    try:
        detail = read_json_payload_row(reader, table_name, build_id, bill_key or patient_id)
    except Exception:
        detail = None
    if (
        not isinstance(detail, dict)
        or detail.get("build_id") != build_id
        or detail.get("patient_id") != patient_id
        or detail.get("schema_version") != FULL_EVIDENCE_SCHEMA_VERSION
        or not isinstance(detail.get("counts"), dict)
    ):
        return _unavailable(reader, build_id, limit, offset)
    try:
        validate_full_wavea_evidence_detail(detail, patient_id)
    except ValueError:
        return _unavailable(reader, build_id, limit, offset)
    if scope == "bill":
        inventory = detail["claim_scope_inventory"]
        if inventory["context_state"] != "available" or [
            row["claim_id"] for row in inventory["claims"]
        ] != [claim_id]:
            return _unavailable(reader, build_id, limit, offset)
        try:
            report = read_json_payload_row(reader, "patient_bill_billing_report_rows", build_id, bill_key)
        except Exception:
            report = None
        if not _bill_report_matches_detail(report, detail, patient_id, claim_id):
            return _unavailable(reader, build_id, limit, offset)
    else:
        summary = patients[patient_id]
        fields = (
            "by_rule", "by_group", "evaluation_count", "review_count", "advisory_count",
            "financial_count",
        )
        if (
            not isinstance(summary, dict)
            or summary.get("available") is not detail.get("available")
            or not isinstance(summary.get("counts"), dict)
            or summary["counts"] != {field: detail["counts"][field] for field in fields}
        ):
            return _unavailable(reader, build_id, limit, offset)
    source = detail.get(kind)
    if not isinstance(source, list):
        return _unavailable(reader, build_id, limit, offset)
    rows = [
        row
        for row in source
        if isinstance(row, dict)
        and (claim_id is None or row.get("claim_id") == claim_id)
        and (rule_id is None or row.get("rule_id") == rule_id)
        and (evidence_id is None or row.get("evidence_id") == evidence_id)
    ]
    return attach_bilun_data_source(
        {
            "available": detail["available"],
            "unavailable_reason": detail.get("unavailable_reason"),
            "patient_id": patient_id,
            "scope": scope,
            "claim_id": claim_id if scope == "bill" else None,
            "kind": kind,
            "patient_counts": detail.get("counts"),
            "rows": rows[offset : offset + limit],
            "pagination": {
                "total_matching": len(rows),
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < len(rows),
            },
        },
        read_active_bilun_data_source(reader, build_id),
    )


@router.get("/wavea-evidence-rows", response_model=BilunCachePayloadResponse)
def get_wavea_evidence_rows(
    kind: str = "reviews",
    patient_id: Annotated[list[str] | None, Query()] = None,
    claim_id: str | None = None,
    rule_id: str | None = None,
    limit: int = _DEFAULT_LIMIT,
    offset: int = 0,
):
    """Page sparse cohort review/advisory/financial evidence from the build index."""
    return _wavea_evidence_rows_response(kind, patient_id, claim_id, rule_id, limit, offset)


@router.post("/wavea-evidence-rows", response_model=BilunCachePayloadResponse)
def post_wavea_evidence_rows(request: WaveAEvidenceRowsRequest):
    """Body-based equivalent for large selected patient sets."""
    return _wavea_evidence_rows_response(
        request.kind,
        request.patient_id,
        request.claim_id,
        request.rule_id,
        request.limit,
        request.offset,
    )


def _wavea_evidence_rows_response(
    kind: str,
    patient_id: list[str] | None,
    claim_id: str | None,
    rule_id: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    _validate_page(limit, offset)
    if kind not in _COHORT_ROW_KINDS:
        raise ValidationError(f"kind must be one of: {', '.join(_COHORT_ROW_KINDS)}")
    for label, value in (("claim_id", claim_id), ("rule_id", rule_id)):
        if value is not None and not value.strip():
            raise ValidationError(f"{label} must not be blank")
    reader, build_id, index = _active_index()
    if not _ready(reader, index, build_id):
        return _unavailable(reader, build_id, limit, offset)
    assert index is not None
    patients = index["patients"]
    selected = _selected_patient_ids(patient_id)
    if selected is not None and not selected <= patients.keys():
        return _unavailable(reader, build_id, limit, offset, "requested_patient_not_in_build")
    selected_ids = set(patients) if selected is None else selected
    unavailable_count = sum(patients[pid]["available"] is not True for pid in selected_ids)
    prefix = {
        "reviews": "wavea_review:",
        "advisories": "wavea_advisory:",
        "financial_rows": "wavea_financial:",
    }[kind]
    rows = [
        row
        for row in index["evidence_rows"]
        if row["evidence_id"].startswith(prefix)
        and row["patient_id"] in selected_ids
        and (claim_id is None or row["claim_id"] == claim_id)
        and (rule_id is None or row["rule_id"] == rule_id)
    ]
    return attach_bilun_data_source(
        {
            "available": True,
            "unavailable_reason": "some_patients_unavailable" if unavailable_count else None,
            "patient_coverage": {
                "selected": len(selected_ids),
                "available": len(selected_ids) - unavailable_count,
                "unavailable": unavailable_count,
            },
            "kind": kind,
            "counts": {"matching_rows": len(rows)},
            "rows": rows[offset : offset + limit],
            "pagination": {
                "total_matching": len(rows),
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < len(rows),
            },
        },
        read_active_bilun_data_source(reader, build_id),
    )

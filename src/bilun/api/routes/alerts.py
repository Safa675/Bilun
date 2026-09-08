"""BILUN patient alerts endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from src.bilun.shared.exceptions import ServiceUnavailableError, ValidationError
from src.bilun.api.schemas import PatientAlertsResponse
from src.bilun.shared.state import (
    _get_active_build_id_or_none,
    _get_cache_reader,
    get_pipeline_mode,
)
from src.bilun.db import (
    has_patient_alert_tables,
    read_patient_alert_rows_page,
    read_patient_alerts_summary,
)
from src.bilun.domain.optimization.exactness import (
    EXACTNESS_STATUS_EXACT,
    is_exact_output,
    unavailable_patient_alert_copay_rate,
    unavailable_patient_alert_surcharge,
)

router = APIRouter()
PIPELINE_MODE: str | None = None


def _pipeline_mode() -> str:
    override = PIPELINE_MODE
    if isinstance(override, str):
        return override.strip().lower()
    return get_pipeline_mode()


def _get_active_bilun_build_id(reader) -> str | None:
    return _get_active_build_id_or_none(reader, scope="bilun")

_ALERT_STATUS_OPTIONS: dict[str, set[str]] = {
    "exemptions": {"all", "exempt", "not_exempt"},
    "surcharge": {"all", "flagged", "clear"},
    "copay_rates": {"all", "flagged", "clear"},
}
_MAX_PATIENT_ALERT_LIMIT = 100


def _sanitize_patient_alert_summary(summary: dict[str, object]) -> dict[str, object]:
    total_patients = int(summary.get("n_total_patients") or 0)
    sanitized = dict(summary)
    surcharge_status = str(summary.get("surcharge_exactness_status") or "").strip()
    if not surcharge_status:
        surcharge = unavailable_patient_alert_surcharge()
        sanitized.update(
            {
                "n_patients_with_surcharge_flags": None,
                "total_surcharge_flags": None,
                "n_patients_with_surcharge_unavailable": total_patients,
                "surcharge_exactness_status": surcharge["exactness_status"],
                "surcharge_unavailable_reason": surcharge["unavailable_reason"],
                "surcharge_required_inputs_missing": surcharge[
                    "required_inputs_missing"
                ],
            }
        )
    elif surcharge_status == "partial_exact":
        surcharge = unavailable_patient_alert_surcharge()
        sanitized.setdefault(
            "surcharge_unavailable_reason",
            surcharge["unavailable_reason"],
        )
        sanitized.setdefault(
            "surcharge_required_inputs_missing",
            surcharge["required_inputs_missing"],
        )
    copay_rate_status = str(summary.get("copay_rate_exactness_status") or "").strip()
    if not copay_rate_status:
        copay_rate = unavailable_patient_alert_copay_rate()
        sanitized.update(
            {
                "n_patients_with_copay_rate_flags": None,
                "total_copay_rate_flags": None,
                "n_patients_with_copay_rate_unavailable": total_patients,
                "copay_rate_exactness_status": copay_rate["exactness_status"],
                "copay_rate_unavailable_reason": copay_rate["unavailable_reason"],
                "copay_rate_required_inputs_missing": copay_rate[
                    "required_inputs_missing"
                ],
            }
        )
    elif copay_rate_status == "partial_exact":
        copay_rate = unavailable_patient_alert_copay_rate()
        sanitized.setdefault(
            "copay_rate_unavailable_reason",
            copay_rate["unavailable_reason"],
        )
        sanitized.setdefault(
            "copay_rate_required_inputs_missing",
            copay_rate["required_inputs_missing"],
        )
    return sanitized


def _patient_alert_summary_exact(summary: dict[str, object], category: str) -> bool:
    if category == "surcharge":
        return is_exact_output(
            {"exactness_status": summary.get("surcharge_exactness_status")}
        )
    if category == "copay_rates":
        return is_exact_output(
            {"exactness_status": summary.get("copay_rate_exactness_status")}
        )
    return True


def _attach_exactness_or_unavailable(
    payload: dict[str, object],
    unavailable: dict[str, object],
    *,
    assume_exact: bool,
) -> dict[str, object]:
    status = str(payload.get("exactness_status") or "").strip()
    if status == EXACTNESS_STATUS_EXACT:
        return payload
    if not status and assume_exact:
        return {**payload, "exactness_status": EXACTNESS_STATUS_EXACT}
    return unavailable


def _attach_patient_alert_exactness(
    category: str,
    patients: list[dict[str, object]],
    summary: dict[str, object],
) -> list[dict[str, object]]:
    if category == "surcharge":
        assume_exact = _patient_alert_summary_exact(summary, category)
        unavailable = unavailable_patient_alert_surcharge()
        return [
            {
                **patient,
                "surcharge_exposure": _attach_exactness_or_unavailable(
                    dict(patient.get("surcharge_exposure") or {}),
                    unavailable,
                    assume_exact=assume_exact,
                ),
            }
            for patient in patients
        ]
    if category == "copay_rates":
        assume_exact = _patient_alert_summary_exact(summary, category)
        unavailable = unavailable_patient_alert_copay_rate()
        return [
            {
                **patient,
                "copay_rate_exposure": _attach_exactness_or_unavailable(
                    dict(patient.get("copay_rate_exposure") or {}),
                    unavailable,
                    assume_exact=assume_exact,
                ),
            }
            for patient in patients
        ]
    return patients


def _validate_patient_alert_params(
    *,
    category: str,
    status: str,
    search: str | None,
    limit: int,
    offset: int,
) -> tuple[str, str, str]:
    normalized_category = (category or "exemptions").strip().lower()
    normalized_status = (status or "all").strip().lower()
    normalized_search = (search or "").strip()

    if normalized_category not in _ALERT_STATUS_OPTIONS:
        raise ValidationError(
            "Invalid patient alerts category. "
            "Expected one of: exemptions, surcharge, copay_rates."
        )
    if normalized_status not in _ALERT_STATUS_OPTIONS[normalized_category]:
        raise ValidationError(
            f"Invalid status '{normalized_status}' for category "
            f"'{normalized_category}'."
        )
    if limit <= 0 or limit > _MAX_PATIENT_ALERT_LIMIT:
        raise ValidationError(
            f"limit must be between 1 and {_MAX_PATIENT_ALERT_LIMIT}."
        )
    if offset < 0:
        raise ValidationError("offset must be greater than or equal to 0.")
    return normalized_category, normalized_status, normalized_search


@router.get("/patient-alerts", response_model=PatientAlertsResponse)
def get_patient_alerts(
    category: str = "exemptions",
    status: str = "all",
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    Per-patient optimization alerts for the entire cohort.

    Returns pre-computed alert rows from the 3 actionable rule engines
    (copay exemptions, surcharge compliance, copay rate exposure).
    Each row contains the patient's flags and recommended actions.

    This powers the BILUN Optimization tab's patient-level alert tables.
    Pre-computed at pipeline startup to avoid per-request iteration over
    the full cohort.
    """
    category, status, search = _validate_patient_alert_params(
        category=category,
        status=status,
        search=search,
        limit=limit,
        offset=offset,
    )

    mode = _pipeline_mode()
    if mode in {"hybrid", "persistent"}:
        reader = _get_cache_reader()
        active_build = _get_active_bilun_build_id(reader)
        if active_build is not None:
            # Read-only existence check (B-C6): the write-backfill in
            # ensure_patient_alert_tables must NOT run on the shared reader
            # cursor — it issues DELETE+INSERT inside a transaction on the
            # process-singleton connection, which (a) is visible to and
            # blocks concurrent readers, and (b) collides with DuckDB's
            # single-writer model. The alerts tables are populated by the
            # build lifecycle; if they are absent here, surface "unavailable"
            # rather than corrupting concurrent reads.
            if not has_patient_alert_tables(reader, active_build):
                raise ServiceUnavailableError(
                    "Patient alerts cache is unavailable for the active build. "
                    "Run the patient-alerts backfill or rebuild the analytics cache."
                )
            summary = read_patient_alerts_summary(reader, active_build)
            if summary is None:
                raise ServiceUnavailableError(
                    "Patient alerts summary is unavailable for the active build. "
                    "Run the patient-alerts backfill or rebuild the analytics cache."
                )
            sanitized_summary = _sanitize_patient_alert_summary(summary)
            patients, total_matching = read_patient_alert_rows_page(
                reader,
                active_build,
                category=category,
                status=status,
                search=search,
                limit=limit,
                offset=offset,
            )
            patients = _attach_patient_alert_exactness(
                category,
                patients,
                sanitized_summary,
            )
            return {
                "patients": patients,
                "summary": sanitized_summary,
                "pagination": {
                    "total_matching": total_matching,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(patients) < total_matching,
                },
                "query": {
                    "category": category,
                    "status": status,
                    "search": search,
                },
            }
        if mode == "persistent":
            raise ServiceUnavailableError(
                "No active BILUN build. Run scripts/bilun/build_cache.py --activate"
            )

    # Legacy fallback removed - requires active build
    raise ServiceUnavailableError(
        "Patient alerts require an active analytics build."
    )

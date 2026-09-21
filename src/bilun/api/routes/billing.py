"""Per-patient billing report, drug catalog, and materials-by-specialty
browser endpoints."""

from __future__ import annotations

import dataclasses
from typing import Any

from fastapi import APIRouter

from src.bilun.shared.exceptions import PatientNotFound, ServiceUnavailableError
from src.bilun.api.schemas import (
    BillingReportResponse,
    DrugCatalogResponse,
    MaterialsBySpecialtyResponse,
)
from src.bilun.shared.state import (
    _get_active_build_id_or_none,
    _get_cache_reader,
    get_pipeline_mode,
)
from src.bilun.db import (
    has_json_payload as cache_json_payload_exists,
    has_json_payload_rows as cache_json_payload_rows_exist,
    read_json_payload_entry as read_cache_json_payload_entry,
    read_json_payload_row as read_cache_json_payload_row,
)
from src.bilun.domain.billing import BillingActionReport
from src.bilun.domain.billing.drug_indication_findings import (
    normalize_drug_indication_payload,
)
from src.bilun.domain.materials import get_all_specialty_materials
from src.bilun.domain.utils import turkish_lower

from .provenance import attach_bilun_data_source, read_active_bilun_data_source

router = APIRouter()
PIPELINE_MODE: str | None = None


def _pipeline_mode() -> str:
    override = PIPELINE_MODE
    if isinstance(override, str):
        return override.strip().lower()
    return get_pipeline_mode()


def _get_active_bilun_build_id(reader) -> str | None:
    return _get_active_build_id_or_none(reader, scope="bilun")


def _serialize_billing_report(report: BillingActionReport | dict[str, Any]) -> dict[str, Any]:
    """Serialize a BillingActionReport to a JSON-safe dict."""
    if dataclasses.is_dataclass(report):
        payload = dataclasses.asdict(report)
        strategy = payload.get("billing_strategy")
        if isinstance(strategy, dict):
            strategy["uplift_savings_try"] = report.billing_strategy.uplift_savings_try
            strategy["optional_override_uplift_try"] = (
                report.billing_strategy.optional_override_uplift_try
            )
        session = payload.get("session_uplift")
        if isinstance(session, dict):
            session["total_uplift_try"] = report.session_uplift.total_uplift_try
            session["confirmed_uplift_try"] = report.session_uplift.confirmed_uplift_try
            session["review_uplift_try"] = report.session_uplift.review_uplift_try
            session["review_opportunity_count"] = (
                report.session_uplift.review_opportunity_count
            )
        gazette = payload.get("gazette_repricing")
        if isinstance(gazette, dict):
            gazette["total_repricing_try"] = report.gazette_repricing.total_repricing_try
            gazette["confirmed_repricing_try"] = (
                report.gazette_repricing.confirmed_repricing_try
            )
            gazette["review_repricing_try"] = report.gazette_repricing.review_repricing_try
        drg = payload.get("drg_uplift")
        if isinstance(drg, dict):
            drg["total_uplift_try"] = report.drg_uplift.total_uplift_try
            drg["confirmed_uplift_try"] = report.drg_uplift.confirmed_uplift_try
        blood = payload.get("blood_uplift")
        if isinstance(blood, dict):
            blood["total_uplift_try"] = report.blood_uplift.total_uplift_try
            blood["confirmed_uplift_try"] = report.blood_uplift.confirmed_uplift_try
        material = payload.get("material_uplift")
        if isinstance(material, dict):
            material["total_uplift_try"] = report.material_uplift.total_uplift_try
            material["confirmed_uplift_try"] = report.material_uplift.confirmed_uplift_try
        procedure_addon = payload.get("procedure_addon_uplift")
        if isinstance(procedure_addon, dict):
            procedure_addon["total_uplift_try"] = (
                report.procedure_addon_uplift.total_uplift_try
            )
            procedure_addon["confirmed_uplift_try"] = (
                report.procedure_addon_uplift.confirmed_uplift_try
            )
        care_setting = payload.get("care_setting_review")
        if isinstance(care_setting, dict):
            care_setting["total_uplift_try"] = report.care_setting_review.total_uplift_try
            care_setting["confirmed_uplift_try"] = (
                report.care_setting_review.confirmed_uplift_try
            )
            care_setting["review_uplift_try"] = (
                report.care_setting_review.review_uplift_try
            )
            care_setting["review_opportunity_count"] = (
                report.care_setting_review.review_opportunity_count
            )
        drug_indication = payload.get("drug_indication")
        if isinstance(drug_indication, dict):
            drug_indication["findings"] = [
                finding.to_dict() for finding in report.drug_indication.findings
            ]
            drug_indication["evaluations"] = [
                evaluation.to_dict()
                for evaluation in report.drug_indication.evaluations
            ]
            normalized_drug_indication = normalize_drug_indication_payload(
                drug_indication
            )
            payload["drug_indication"] = normalized_drug_indication
            payload["drug_indication_violation_count"] = normalized_drug_indication.get(
                "violation_count", 0
            )
        return payload
    if isinstance(report, dict):
        payload = dict(report)
        drug_indication = payload.get("drug_indication")
        if isinstance(drug_indication, dict):
            normalized_drug_indication = normalize_drug_indication_payload(
                drug_indication
            )
            payload["drug_indication"] = normalized_drug_indication
            payload["drug_indication_violation_count"] = normalized_drug_indication.get(
                "violation_count", 0
            )
        return payload
    raise TypeError(f"Unsupported billing report payload type: {type(report)!r}")


@router.get("/billing-report/{patient_id}", response_model=BillingReportResponse)
def get_patient_billing_report(patient_id: str):
    """
    Per-patient billing action report with specific TRY-denominated
    savings recommendations from 5 normative billing algorithms.

    Returns actionable recommendations for lab billing optimization,
    drug cost optimization, copay savings, billing strategy, and
    material reimbursability pre-checks.
    """
    mode = _pipeline_mode()
    if mode in {"hybrid", "persistent"}:
        reader = _get_cache_reader()
        active_build = _get_active_bilun_build_id(reader)
        if active_build is not None:
            report = read_cache_json_payload_row(
                reader,
                "patient_billing_report_rows",
                active_build,
                patient_id,
            )
            if report is not None:
                return attach_bilun_data_source(
                    _serialize_billing_report(report),
                    read_active_bilun_data_source(reader, active_build),
                )
            if (
                mode == "persistent"
                and cache_json_payload_rows_exist(
                    reader, "patient_billing_report_rows", active_build
                )
            ):
                raise PatientNotFound(
                    f"Patient {patient_id} not found in canonical cache"
                )

            report = read_cache_json_payload_entry(
                reader,
                "patient_billing_reports",
                active_build,
                patient_id,
            )
            if report is not None:
                return attach_bilun_data_source(
                    _serialize_billing_report(report),
                    read_active_bilun_data_source(reader, active_build),
                )
            if (
                mode == "persistent"
                and cache_json_payload_exists(
                    reader, "patient_billing_reports", active_build
                )
            ):
                raise PatientNotFound(
                    f"Patient {patient_id} not found in canonical cache"
                )
        if mode == "persistent":
            raise ServiceUnavailableError(
                "No active BILUN build. Run scripts/bilun/build_cache.py --activate"
            )

    # Legacy fallback removed - requires active build
    raise ServiceUnavailableError(
        "Billing report requires an active analytics build."
    )


@router.get(
    "/billing-report/{patient_id}/bills/{claim_id}",
    response_model=BillingReportResponse,
)
def get_bill_billing_report(patient_id: str, claim_id: str):
    """Claim-scoped billing action report for a single bill (``claim_id``).

    Same algorithm family as the per-patient report, but every section reflects
    only the selected bill. Served from the precomputed
    ``patient_bill_billing_report_rows`` table (key ``{patient_id}::{claim_id}``).
    """
    mode = _pipeline_mode()
    if mode in {"hybrid", "persistent"}:
        reader = _get_cache_reader()
        active_build = _get_active_bilun_build_id(reader)
        if active_build is not None:
            report = read_cache_json_payload_row(
                reader,
                "patient_bill_billing_report_rows",
                active_build,
                f"{patient_id}::{claim_id}",
            )
            if report is not None:
                payload = _serialize_billing_report(report)
                payload["patient_id"] = patient_id
                payload["claim_id"] = claim_id
                payload["scope"] = "bill"
                return attach_bilun_data_source(
                    payload,
                    read_active_bilun_data_source(reader, active_build),
                )
            if mode == "persistent" and cache_json_payload_rows_exist(
                reader, "patient_bill_billing_report_rows", active_build
            ):
                raise PatientNotFound(
                    f"Bill {claim_id} for patient {patient_id} not found in canonical cache"
                )
        if mode == "persistent":
            raise ServiceUnavailableError(
                "No active BILUN build. Run scripts/bilun/build_cache.py --activate"
            )

    raise ServiceUnavailableError(
        "Per-bill billing report requires an active analytics build."
    )


@router.get("/drugs", response_model=DrugCatalogResponse)
def get_drug_catalog(q: str = "", page: int = 1, per_page: int = 50):
    """Browse or search the EK-4A drug reimbursement list."""
    from src.bilun.domain.materials import get_ek4a_drugs, lookup_drug

    per_page = max(1, min(per_page, 200))
    q = q.strip()

    if q:
        # Single drug search
        match = lookup_drug(q)
        if match:
            return {"drugs": [match], "total": 1, "page": 1, "total_pages": 1}
        # Fallback: substring filter
        all_drugs = get_ek4a_drugs()
        q_lower = turkish_lower(q)
        filtered = [
            d for d in all_drugs
            if q_lower in turkish_lower(d.get("drug_name", ""))
        ]
    else:
        filtered = get_ek4a_drugs()

    total = len(filtered)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    return {
        "drugs": filtered[start:start + per_page],
        "total": total,
        "page": page,
        "total_pages": total_pages,
    }


@router.get("/materials/by-specialty", response_model=MaterialsBySpecialtyResponse)
def get_materials_by_specialty(specialty: str = ""):
    """Filter EK-3 materials by specialty annex (e.g. EK-3H, EK-3G)."""
    from src.bilun.domain.constants import _EK3_SPECIALTY_CATALOGS

    all_mats = get_all_specialty_materials()
    available = sorted(
        [{"label": k, "name": v[1]} for k, v in _EK3_SPECIALTY_CATALOGS.items()],
        key=lambda x: x["label"],
    )

    if specialty:
        spec_upper = specialty.strip().upper()
        filtered = [m for m in all_mats if (m.get("source", "").upper() == spec_upper)]
    else:
        filtered = all_mats

    return {
        "materials": filtered[:500],
        "total": len(filtered),
        "truncated": len(filtered) > 500,
        "specialties": available,
    }

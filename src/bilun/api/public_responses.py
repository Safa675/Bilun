"""Frozen, nested public response contracts, shared by HTTP and chatbot tools.

``public_contracts.json`` records the reviewed officer-facing DTO fields. It is
not generated at runtime from permissive cache models or client input: adding a
backend/frontend field does not make it public. Named records, list members and
map values all undergo projection. ``True`` means a JSON scalar, never an opaque
object. Private source metadata cannot hide inside an allowed scalar field.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.bilun.domain.sut.source_authority_schema import bounded_source_authority

_DEFINITIONS = json.loads(Path(__file__).with_name("public_contracts.json").read_text())
_DROP = object()


def _fields(*names: str) -> dict[str, bool]:
    return dict.fromkeys(names, True)


def _ref(name: str) -> dict[str, str]:
    return {"$ref": name}


_PATIENT_META = {
    **_fields("patient_id", "age", "sex", "sex_raw", "weight_kg", "doctor_code", "priority", "total_recoverable_try"),
    "comorbidity_conditions": {"$list": True},
}
_PUBLIC_CLAUSE = _ref("RuleClause")
_CLAUSE_SEARCH_ROW = {
    **_fields("clause_id", "clause_key", "clause_coordinate", "section_id", "section_title", "section_path", "clause_type", "text_tr", "source_effective_date"),
    "annex_refs": {"$list": True}, "procedure_codes": {"$list": True},
    "amendment_refs": {"$list": True},
}
_MEDULA_PLAYBOOK_ROW = {
    **_fields("playbook_key", "sonuc_kodu", "medula_stage", "title_tr", "title_en", "description_tr", "description_en", "sut_anchor", "rebill_permitted", "regulatory_basis", "stage", "code", "name", "summary", "problem_summary_tr", "rebill_stage"),
    "corrective_steps_tr": {"$list": True}, "corrective_steps_en": {"$list": True},
    "required_documents": {"$list": True}, "sources": {"$list": _CLAUSE_SEARCH_ROW},
}

PUBLIC_SURFACES: dict[str, Any] = {
    "/api/patients": {
        "patients": {"$list": True}, "total": True,
        "patient_meta": {"$list": _PATIENT_META},
    },
    "/api/patients/search": {"results": {"$list": _PATIENT_META}, "total_matched": True},
    "/api/patient/{patient_id}/outcome": _ref("SutPatientOutcomeData"),
    "/api/patients/{patient_id}/claims": _ref("PatientClaimsListResponse"),
    "/api/patients/{patient_id}/claims/{claim_id}": _ref("PatientClaimDetail"),
    "/api/billing-report/{patient_id}": _ref("BillingActionReport"),
    "/api/billing-report/{patient_id}/bills/{claim_id}": _ref("BillingActionReport"),
    "/api/patient/{patient_id}/optimization": _ref("PatientOptimization"),
    "/api/patient/{patient_id}/bills/{claim_id}/optimization": _ref("PatientOptimization"),
    "/api/optimization-summary": _ref("OptimizationSummary"),
    "/api/revenue-recovery": _ref("CohortRecoverySummary"),
    "/api/patient-alerts": _ref("PatientAlertsResponse"),
    "/api/compliance-index": _ref("ComplianceIndexResponse"),
    "/api/medula-rejections/ingest-status": {"ingest_available": True},
    "/api/medula-rejections/queue": _ref("MedulaRejectionQueueResponse"),
    "/api/procedure/{code}": _ref("SutProcedureInfo"),
    "/api/material/{code}/pricing": _ref("SutMaterialPricingResult"),
    "/api/visit-pricing": _ref("VisitPricingResponse"),
    "/api/price-history/{code}": {
        "code": True, "name": True,
        "history": {"$list": _fields("effective_date", "price_try", "puan")},
    },
    "/api/lab-prices": {"tests": {"$list": _ref("LabPriceEntry")}, "total": True},
    "/api/drugs": {
        "drugs": {"$list": _ref("DrugEntry")},
        **_fields("total", "page", "total_pages"),
    },
    "/api/materials/by-specialty": _ref("MaterialsBySpecialtyResponse"),
    "/api/bundled-consumables": _ref("SutBundledConsumablesResult"),
    "/api/rules/clauses/{clause_id}": _PUBLIC_CLAUSE,
    "/api/validate-claim": _ref("SutValidationResult"),
    "/api/wavea-evidence-index": _ref("WaveAEvidenceIndexPage"),
    "/api/wavea-evidence/{patient_id}": _ref("WaveAEvidencePage"),
    "/api/wavea-evidence-rows": _ref("WaveACohortEvidencePage"),
    "search_sut_clauses": {"query": True, "clauses": {"$list": _CLAUSE_SEARCH_ROW}},
    "search_medula_playbook": {"$list": _MEDULA_PLAYBOOK_ROW},
    "medula_queue_count": _fields("ingest_available", "total"),
    "search_medula": {
        "known_codes": {"$list": _fields("code", "meaning_tr", "meaning_en", "action", "is_error")},
        "rejection_categories": {"$list": {
            **_fields("stage", "stage_en", "category", "problem", "resolution"),
            "causes": {"$anyOf": [True, {"$list": True}]},
        }},
        "workflow_stage": _fields("name_tr", "name_en", "description_tr", "description_en"),
        "playbook_entries": {"$list": _MEDULA_PLAYBOOK_ROW},
    },
}

_ALIASES = {
    "get_billing_report": "/api/billing-report/{patient_id}",
    "get_bill_billing_report": "/api/billing-report/{patient_id}/bills/{claim_id}",
    "get_revenue_recovery": "/api/revenue-recovery",
    "get_patient_optimization": "/api/patient/{patient_id}/optimization",
    "get_optimization_summary": "/api/optimization-summary",
    "get_patient_outcome": "/api/patient/{patient_id}/outcome",
    "search_patients": "/api/patients/search", "list_patients": "/api/patients",
    "search_drugs": "/api/drugs", "get_patient_alerts": "/api/patient-alerts",
    "validate_claim": "/api/validate-claim",
}


def _project(value: Any, schema: Any) -> Any:
    if value is None:
        return None
    if schema is True:
        return value if isinstance(value, (str, int, float, bool)) else _DROP
    if "$ref" in schema:
        if schema["$ref"] == "ClinicalSourceAuthorityEvidence":
            # Validate before selecting fields: stripping arbitrary fields first
            # could turn an untrusted cached claim into apparently valid proof.
            authority = bounded_source_authority(value)
            return authority if authority is not None else _DROP
        return _project(value, _DEFINITIONS[schema["$ref"]])
    if "$statusCountsSummary" in schema:
        if not isinstance(value, dict):
            return _DROP
        statuses = ("evaluated", "missing_inputs", "unavailable")
        totals = dict.fromkeys(statuses, 0)
        found = False
        for counts in value.values():
            if isinstance(counts, dict) and all(type(counts.get(key)) is int and counts[key] >= 0 for key in statuses):
                found = True
                for key in statuses:
                    totals[key] += counts[key]
        # Detector function names are an implementation inventory. Officers
        # retain the evaluation/uncertainty totals and individual evidence.
        return {"claim_checks": totals} if found else {}
    if "$anyOf" in schema:
        results = [_project(value, choice) for choice in schema["$anyOf"]]
        results = [result for result in results if result is not _DROP]
        if isinstance(value, dict):
            return {key: item for result in results if isinstance(result, dict) for key, item in result.items()}
        return next(iter(results), _DROP)
    if "$list" in schema:
        if not isinstance(value, list):
            return _DROP
        return [item for raw in value if (item := _project(raw, schema["$list"])) is not _DROP]
    if not isinstance(value, dict):
        return _DROP
    output = {}
    for key, raw in value.items():
        field_schema = schema.get(key, schema.get("$map"))
        if field_schema is not None:
            item = _project(raw, field_schema)
            if key not in schema and "$map" in schema and item == {} and raw:
                continue
            if item is not _DROP:
                output[key] = item
    return output


def project_public_response(payload: Any, surface: str) -> Any:
    """Project one documented business surface; unknown surfaces fail closed."""
    surface = _ALIASES.get(surface, surface)
    if surface not in PUBLIC_SURFACES:
        raise ValueError("No public response contract for this surface")
    projected = _project(payload, PUBLIC_SURFACES[surface])
    if projected is _DROP:
        raise ValueError("Unexpected public response shape")
    if isinstance(payload, dict) and isinstance(projected, dict) and "data_source" in payload:
        provenance = _project(payload["data_source"], _ref("SUTDataSourceMetadata"))
        if provenance is _DROP:
            raise ValueError("Unexpected public provenance shape")
        projected["data_source"] = provenance
    return projected


def public_error(status_code: int) -> dict[str, str]:
    """Never reflect internal exception context, filesystem paths or request bodies."""
    messages = {
        400: "The request is invalid.", 401: "Authentication required.",
        403: "Developer access required.", 404: "The requested resource was not found.",
        405: "Method not allowed.", 409: "Reload the page or upgrade your client.",
        413: "The request is too large.", 422: "The request contains invalid values.",
        429: "Too many requests. Please try again later.",
    }
    return {"detail": messages.get(status_code, "The service is temporarily unavailable.")}

"""Payload builders for BILUN analytics cache tables."""

from __future__ import annotations

import json
from typing import Any

import polars as pl

from src.bilun.cache.patient_slice import _build_diagnoses_by_pid
from src.bilun.domain.claims.provenance import attach_bilun_data_source_metadata


def build_patient_diagnoses_df(ctx: dict[str, Any]) -> pl.DataFrame:
    diagnoses_by_pid = _build_diagnoses_by_pid(ctx["ana_df_pl"])
    if not diagnoses_by_pid:
        return pl.DataFrame()
    return pl.DataFrame(
        [
            {
                "patient_id": patient_id,
                "diagnoses_json": json.dumps(diagnoses, ensure_ascii=False),
            }
            for patient_id, diagnoses in diagnoses_by_pid.items()
        ]
    )


def build_sut_patient_detail_payload(
    patient_id: str,
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    """Build a SUT-only overlay payload for patient detail composition."""
    return {"summary": {"patient_id": patient_id}}


def _money(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _date(value: Any) -> str | None:
    if value is None:
        return None
    isoformat = getattr(value, "isoformat", None)
    return isoformat() if callable(isoformat) else str(value)


def _build_claim_line_summary(patient_id: str, ctx: dict[str, Any]) -> dict[str, Any]:
    claims = list(ctx.get("claims_by_patient", {}).get(patient_id, ()))
    procedures = list(ctx.get("procedure_lines_by_patient", {}).get(patient_id, ()))
    materials = list(ctx.get("material_lines_by_patient", {}).get(patient_id, ()))
    drugs = list(ctx.get("drug_lines_by_patient", {}).get(patient_id, ()))
    diagnoses = list(ctx.get("claim_diagnoses_by_patient", {}).get(patient_id, ()))
    if not any((claims, procedures, materials, drugs, diagnoses)):
        return {
            "exactness_status": "missing_exact_inputs",
            "unavailable_reason": "exact_claim_lines_missing_for_patient",
            "required_inputs_missing": ["claim_lines.patient_id"],
            "source": "claim_lines",
            "claim_count": 0,
            "procedure_line_count": 0,
            "material_line_count": 0,
            "drug_line_count": 0,
            "diagnosis_count": 0,
            "claims": [],
            "top_procedures": [],
            "drug_claims": [],
            "material_claims": [],
        }

    def _claim_total(claim_id: str) -> float:
        return sum(
            _money(line.billed_amount_try) or 0.0
            for line in [*procedures, *materials, *drugs]
            if line.claim_id == claim_id
        )

    return {
        "exactness_status": "exact",
        "source": "claim_lines",
        "claim_count": len(claims),
        "procedure_line_count": len(procedures),
        "material_line_count": len(materials),
        "drug_line_count": len(drugs),
        "diagnosis_count": len(diagnoses),
        "claims": [
            {
                "claim_id": claim.claim_id,
                "episode_id": claim.episode_id,
                "claim_type": claim.claim_type,
                "department": claim.department,
                "admission_date": _date(claim.admission_date),
                "claim_start_date": _date(claim.claim_start_date),
                "claim_end_date": _date(claim.claim_end_date),
                "primary_icd10": claim.primary_icd10,
                "total_billed_try": round(_claim_total(claim.claim_id), 2),
            }
            for claim in claims[:10]
        ],
        "top_procedures": [
            {
                "procedure_line_id": line.procedure_line_id,
                "claim_id": line.claim_id,
                "episode_id": line.episode_id,
                "procedure_date": _date(line.procedure_date),
                "procedure_code": line.procedure_code,
                "procedure_name": line.procedure_name,
                "procedure_category": line.procedure_category,
                "billed_amount_try": _money(line.billed_amount_try),
                "expected_payable_try": _money(line.expected_payable_try),
                "surcharge_applicable": bool(line.surcharge_applicable),
                "copay_rate_applicable": bool(line.copay_rate_applicable),
            }
            for line in sorted(
                procedures,
                key=lambda item: _money(item.billed_amount_try) or 0.0,
                reverse=True,
            )[:10]
        ],
        "drug_claims": [
            {
                "drug_claim_line_id": line.drug_claim_line_id,
                "claim_id": line.claim_id,
                "drug_claim_date": _date(line.drug_claim_date),
                "drug_name": line.drug_name,
                "drug_code": line.drug_code,
                "billed_amount_try": _money(line.billed_amount_try),
                "expected_payable_try": _money(line.expected_payable_try),
            }
            for line in drugs[:10]
        ],
        "material_claims": [
            {
                "material_line_id": line.material_line_id,
                "claim_id": line.claim_id,
                "material_date": _date(line.material_date),
                "material_code": line.material_code,
                "material_name": line.material_name,
                "billed_amount_try": _money(line.billed_amount_try),
                "expected_payable_try": _money(line.expected_payable_try),
            }
            for line in materials[:10]
        ],
    }


def build_sut_patient_outcome_payload(
    patient_id: str,
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    """Build a SUT-only overlay payload for patient outcome composition."""
    sut_claim_totals = ctx.get("sut_by_pid", {}).get(patient_id)
    if sut_claim_totals is None:
        sut_claim_totals = {
            "patient_id": patient_id,
            "total_billed_try": None,
            "total_expected_payable_try": None,
            "claim_count": 0,
            "procedure_line_count": 0,
            "material_line_count": 0,
            "drug_line_count": 0,
            "lab_billed_line_count": 0,
            "exactness_status": "missing_exact_inputs",
            "unavailable_reason": "exact_claim_patient_totals_missing",
            "required_inputs_missing": ["claim_lines.patient_id"],
            "source": "claim_lines",
        }
    return attach_bilun_data_source_metadata(
        {
            "sut_claim_totals": sut_claim_totals,
            "sut_claim_summary": _build_claim_line_summary(patient_id, ctx),
        },
        ctx.get("data_source") or ctx.get("sut_data_source"),
    )

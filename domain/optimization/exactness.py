"""Shared exactness helpers for SUT optimization outputs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .claim_context import (
    CopayRateClaimContext,
    SurchargeClaimContext,
    procedure_rate_pct,
)

EXACTNESS_STATUS_EXACT = "exact"
EXACTNESS_STATUS_MISSING_INPUTS = "missing_exact_inputs"

SURCHARGE_REQUIRED_INPUTS = (
    "billed_procedure_codes",
    "procedure_dates",
)
SURCHARGE_UNAVAILABLE_REASON = (
    "Surcharge compliance requires exact billed procedure codes and procedure "
    "dates, which are not available in the active SUT runtime inputs."
)

COPAY_RATE_REQUIRED_INPUTS = (
    "billed_procedure_codes",
    "procedure_dates",
)
COPAY_RATE_UNAVAILABLE_REASON = (
    "Copay rate compliance requires exact billed procedure codes and claim "
    "dates, which are not available in the active SUT runtime inputs."
)

DRG_UNBUNDLING_REQUIRED_INPUTS = (
    "itemized_billed_procedure_lines",
    "episode_package_eligibility_context",
    "admission_dates",
)
DRG_UNBUNDLING_UNAVAILABLE_REASON = (
    "DRG unbundling risk requires exact billed procedure lines, package "
    "eligibility context, and dated package pricing, which are not available "
    "in the active SUT runtime inputs."
)

DRUG_DISCOUNT_REQUIRED_INPUTS = (
    "dispensed_drug_claim_lines",
    "drug_claim_dates",
    "billed_drug_amounts",
)
DRUG_DISCOUNT_UNAVAILABLE_REASON = (
    "Drug discount validation requires exact dispensed drug claim lines and "
    "billed drug amounts, which are not available in the active SUT runtime "
    "inputs."
)


def is_exact_output(payload: Mapping[str, Any] | None) -> bool:
    if payload is None:
        return False
    status = str(payload.get("exactness_status") or "").strip().lower()
    return status == EXACTNESS_STATUS_EXACT


def build_missing_exact_inputs_block(
    *,
    unavailable_reason: str,
    required_inputs_missing: Iterable[str],
    null_fields: Iterable[str] = (),
    empty_list_fields: Iterable[str] = (),
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "exactness_status": EXACTNESS_STATUS_MISSING_INPUTS,
        "unavailable_reason": unavailable_reason,
        "required_inputs_missing": list(required_inputs_missing),
    }
    for field in null_fields:
        payload[field] = None
    for field in empty_list_fields:
        payload[field] = []
    if extra:
        payload.update(dict(extra))
    return payload


def unavailable_surcharge_exposure() -> dict[str, Any]:
    return build_missing_exact_inputs_block(
        unavailable_reason=SURCHARGE_UNAVAILABLE_REASON,
        required_inputs_missing=SURCHARGE_REQUIRED_INPUTS,
        null_fields=("n_applicable_procedures", "n_total_ek2g", "exposure_rate"),
        empty_list_fields=("applicable_rules",),
    )


def build_exact_surcharge_exposure(context: SurchargeClaimContext) -> dict[str, Any]:
    applicable = [line for line in context.procedures if line.surcharge_applicable]
    total_procedures = len(context.procedures)
    exposure_rate = len(applicable) / total_procedures if total_procedures else 0.0
    rules = [
        {
            "code": line.procedure_code,
            "name": line.procedure_name or line.procedure_code,
            "procedure_date": line.procedure_date.isoformat(),
            "billed_amount_try": float(line.billed_amount_try),
            "expected_payable_try": float(line.expected_payable_try),
            "rule_trace": line.rule_trace_expected,
            "matched_chapters": [],
        }
        for line in applicable
    ]
    return {
        "exactness_status": EXACTNESS_STATUS_EXACT,
        "n_applicable_procedures": len(applicable),
        "n_total_ek2g": total_procedures,
        "exposure_rate": round(exposure_rate, 4),
        "applicable_rules": rules,
        "methodology": (
            "Uses exact dated procedure claim lines and their explicit "
            "surcharge_applicable rule flags; unavailable if those claim lines "
            "are absent."
        ),
    }


def unavailable_patient_alert_surcharge() -> dict[str, Any]:
    return build_missing_exact_inputs_block(
        unavailable_reason=SURCHARGE_UNAVAILABLE_REASON,
        required_inputs_missing=SURCHARGE_REQUIRED_INPUTS,
        null_fields=("n_applicable", "exposure_rate"),
        empty_list_fields=("top_rules",),
        extra={"action": None},
    )


def unavailable_copay_rate_exposure() -> dict[str, Any]:
    return build_missing_exact_inputs_block(
        unavailable_reason=COPAY_RATE_UNAVAILABLE_REASON,
        required_inputs_missing=COPAY_RATE_REQUIRED_INPUTS,
        null_fields=("n_applicable_procedures", "n_total_ek2c1", "mean_rate"),
        empty_list_fields=("procedures_with_rates",),
        extra={"rate_distribution": {}},
    )


def build_exact_copay_rate_exposure(context: CopayRateClaimContext) -> dict[str, Any]:
    applicable = [line for line in context.procedures if line.copay_rate_applicable]
    rates = [procedure_rate_pct(line) for line in applicable]
    mean_rate = (
        (sum(rates, Decimal("0.00")) / Decimal(len(rates))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if rates
        else Decimal("0.00")
    )
    distribution: dict[str, int] = {}
    procedures = []
    for line, rate in zip(applicable, rates, strict=True):
        rate_key = f"{rate.normalize()}%"
        distribution[rate_key] = distribution.get(rate_key, 0) + 1
        procedures.append(
            {
                "code": line.procedure_code,
                "name": line.procedure_name or line.procedure_code,
                "procedure_date": line.procedure_date.isoformat(),
                "rate_pct": float(rate),
                "billed_amount_try": float(line.billed_amount_try),
                "expected_payable_try": float(line.expected_payable_try),
                "rule_trace": line.rule_trace_expected,
                "matched_chapters": [],
            }
        )
    return {
        "exactness_status": EXACTNESS_STATUS_EXACT,
        "n_applicable_procedures": len(applicable),
        "n_total_ek2c1": len(context.procedures),
        "mean_rate": float(mean_rate),
        "procedures_with_rates": procedures,
        "rate_distribution": distribution,
        "methodology": (
            "Uses exact dated procedure claim lines, explicit "
            "copay_rate_applicable flags, and billed/payable amounts encoded "
            "on the claim lines; unavailable if those inputs are absent."
        ),
    }


def unavailable_patient_alert_copay_rate() -> dict[str, Any]:
    return build_missing_exact_inputs_block(
        unavailable_reason=COPAY_RATE_UNAVAILABLE_REASON,
        required_inputs_missing=COPAY_RATE_REQUIRED_INPUTS,
        null_fields=("n_applicable", "mean_rate"),
        empty_list_fields=("top_procedures",),
        extra={"action": None},
    )


def unavailable_patient_drg_unbundling() -> dict[str, Any]:
    return build_missing_exact_inputs_block(
        unavailable_reason=DRG_UNBUNDLING_UNAVAILABLE_REASON,
        required_inputs_missing=DRG_UNBUNDLING_REQUIRED_INPUTS,
        null_fields=(
            "has_unbundling_risk",
            "n_chapters_analyzed",
            "total_potential_savings",
        ),
        empty_list_fields=("chapter_analysis",),
    )


def unavailable_cohort_drg_unbundling(*, n_total_patients: int) -> dict[str, Any]:
    return build_missing_exact_inputs_block(
        unavailable_reason=DRG_UNBUNDLING_UNAVAILABLE_REASON,
        required_inputs_missing=DRG_UNBUNDLING_REQUIRED_INPUTS,
        null_fields=("n_patients_with_risk", "risk_rate", "total_potential_savings"),
        empty_list_fields=("top_risky_chapters",),
        extra={"n_patients_checked": n_total_patients},
    )


def unavailable_drug_discount_validation() -> dict[str, Any]:
    return build_missing_exact_inputs_block(
        unavailable_reason=DRUG_DISCOUNT_UNAVAILABLE_REASON,
        required_inputs_missing=DRUG_DISCOUNT_REQUIRED_INPUTS,
        null_fields=("n_drugs_total", "n_active_drugs", "mean_discount_tier_1"),
        empty_list_fields=("sample_drugs",),
        extra={
            "tier_distribution": {},
            "discount_status_distribution": {},
            "methodology": (
                "EK-4A remains a gazette catalog reference, but patient-specific "
                "discount validation is unavailable until exact dispensed drug "
                "claim lines are present in the active SUT runtime inputs."
            ),
        },
    )

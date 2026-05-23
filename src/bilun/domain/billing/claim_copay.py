"""Copay billing optimization from exact claim lines."""

from __future__ import annotations

from decimal import Decimal

from src.bilun.domain.claims.patient_context import PatientClaimContext

from .types import EXACTNESS_STATUS_EXACT, CopayOptimization


def _copay_component(billed: Decimal, payable: Decimal) -> Decimal:
    """Estimate copay/katilim portion embedded in billed vs payable amounts."""

    if billed <= payable:
        return Decimal("0")
    return billed - payable


def optimize_copay_from_claims(
    ctx: PatientClaimContext,
    copay_exemption: dict,
) -> CopayOptimization:
    """Compute copay savings from exact procedure and drug claim lines."""

    result = CopayOptimization()
    is_exempt = bool(copay_exemption.get("exempt"))
    result.is_exempt = is_exempt

    if is_exempt:
        qualifying = copay_exemption.get("qualifying_diagnoses", [])
        if qualifying:
            result.exemption_disease = qualifying[0].get("disease", "")
            result.exemption_range = qualifying[0].get("range", "")

    if not ctx.procedure_lines and not ctx.drug_lines:
        return result

    visit_savings = Decimal("0")
    rx_savings = Decimal("0")

    for line in ctx.procedure_lines:
        if not line.copay_rate_applicable:
            continue
        component = _copay_component(line.billed_amount_try, line.expected_payable_try)
        if is_exempt and component > 0:
            visit_savings += component
            result.rate_corrections.append(
                {
                    "code": line.procedure_code,
                    "name": line.procedure_name,
                    "billed_try": float(line.billed_amount_try),
                    "payable_try": float(line.expected_payable_try),
                    "copay_component_try": float(component),
                    "detail": "EK-1A exemption may waive this copay component",
                }
            )

    for line in ctx.drug_lines:
        component = _copay_component(line.billed_amount_try, line.expected_payable_try)
        if is_exempt and component > 0:
            rx_savings += component

    result.visit_copay_savings_try = round(float(visit_savings), 2)
    result.rx_copay_savings_try = round(float(rx_savings), 2)
    result.total_copay_savings_try = round(float(visit_savings + rx_savings), 2)
    result.exactness_status = EXACTNESS_STATUS_EXACT
    result.unavailable_reason = None
    result.required_inputs_missing = []
    return result

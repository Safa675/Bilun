"""Copay billing optimization from exact claim lines."""

from __future__ import annotations

from decimal import Decimal

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.drugs.ek4d_exempt import match_ek4d_copay_exempt_drug
from src.bilun.domain.prose_rules.copay_general import (
    resolve_drug_copay_rate,
    resolve_material_copay_rate,
)

from .types import (
    COPAY_GAP_KIND_EXEMPTION_CORRECTION,
    COPAY_SAVINGS_BENEFICIARY_PATIENT_AND_SGK,
    EXACTNESS_STATUS_EXACT,
    CopayOptimization,
)

_COPAY_RULE_SOURCE = (
    "SUT §1.8.5(7)+EK-1/A exemptions; §1.8.2(3)+EK-4/D drug exemptions; "
    "§1.8.2/§1.8.3 prose (copay_general_1_8)"
)


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
    partial_exempt = bool(copay_exemption.get("partial_exempt"))
    has_health_report = copay_exemption.get("has_chronic_health_report")
    result.is_exempt = is_exempt

    diagnosis_codes: list[str] = []
    for diag in getattr(ctx, "diagnoses", ()) or ():
        code = getattr(diag, "icd10_code", "")
        if code:
            diagnosis_codes.append(str(code))
    for claim in getattr(ctx, "claims", ()) or ():
        primary = getattr(claim, "primary_icd10", "")
        if primary:
            diagnosis_codes.append(str(primary))

    if is_exempt:
        qualifying = copay_exemption.get("qualifying_diagnoses", [])
        if qualifying:
            result.exemption_disease = qualifying[0].get("disease", "")
            result.exemption_range = qualifying[0].get("range", "")
    elif partial_exempt:
        qualifying = copay_exemption.get("qualifying_diagnoses", [])
        if qualifying:
            result.exemption_disease = qualifying[0].get("disease", "")
            result.exemption_range = qualifying[0].get("range", "")
            result.rate_corrections.append(
                {
                    "detail": (
                        "EK-1/A ICD match without chronic health report — "
                        "§1.8.5(7) savings not asserted"
                    ),
                    "sut_section": "1.8.5(7)",
                }
            )

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
                    "detail": "Copay exemption may waive this copay component",
                }
            )

    for line in ctx.drug_lines:
        component = _copay_component(line.billed_amount_try, line.expected_payable_try)
        if is_exempt and component > 0:
            rx_savings += component
            continue

        ek4d = match_ek4d_copay_exempt_drug(
            diagnosis_codes,
            drug_name=str(getattr(line, "drug_name", "") or ""),
            drug_code=str(getattr(line, "drug_code", "") or ""),
            barkod=str(getattr(line, "barkod", "") or ""),
            has_health_report=has_health_report,
        )
        if ek4d is None:
            continue
        if ek4d.get("partial_without_report"):
            result.rate_corrections.append(
                {
                    "code": line.drug_code,
                    "name": line.drug_name,
                    "detail": (
                        "EK-4/D drug match without health report — "
                        "§1.8.2(3) savings not asserted"
                    ),
                    "sut_section": "1.8.2.(3)",
                    "section_title": ek4d["evidence"].get("section_title"),
                }
            )
            continue
        if ek4d.get("counts_toward_exempt") and component > 0:
            rx_savings += component
            result.rate_corrections.append(
                {
                    "code": line.drug_code,
                    "name": line.drug_name,
                    "billed_try": float(line.billed_amount_try),
                    "payable_try": float(line.expected_payable_try),
                    "copay_component_try": float(component),
                    "detail": (
                        f"EK-4/D exempt drug ({ek4d['evidence'].get('drug_name_tr')}) "
                        f"for {ek4d['evidence'].get('section_title', 'listed disease')}"
                    ),
                    "sut_section": "1.8.2.(3)",
                }
            )

    visit_waived = round(float(visit_savings), 2)
    rx_waived = round(float(rx_savings), 2)
    result.savings_beneficiary = COPAY_SAVINGS_BENEFICIARY_PATIENT_AND_SGK
    result.gap_kind = COPAY_GAP_KIND_EXEMPTION_CORRECTION
    result.visit_copay_savings_try = visit_waived
    result.rx_copay_savings_try = rx_waived
    result.total_copay_savings_try = visit_waived  # legacy: procedure/visit only
    result.patient_copay_waived_total_try = round(visit_waived + rx_waived, 2)
    result.exactness_status = EXACTNESS_STATUS_EXACT
    result.unavailable_reason = None
    result.required_inputs_missing = []
    result.rule_source = _COPAY_RULE_SOURCE

    expected_rx_rate = resolve_drug_copay_rate("other")
    if ctx.drug_lines and not is_exempt:
        result.rate_corrections.append(
            {
                "detail": (
                    f"SUT §1.8.2 mandates {expected_rx_rate:.0%} drug copay for "
                    "non-income-recipient patients when EK-1/A exemption does not apply."
                ),
                "expected_copay_rate_pct": round(expected_rx_rate * 100, 1),
                "sut_section": "1.8.2.(1)",
            }
        )

    if getattr(ctx, "material_lines", ()):
        material_rate = resolve_material_copay_rate("other")
        result.rate_corrections.append(
            {
                "detail": (
                    f"SUT §1.8.3(2) material copay reference rate: {material_rate:.0%}"
                ),
                "expected_copay_rate_pct": round(material_rate * 100, 1),
                "sut_section": "1.8.3.(2)",
            }
        )

    return result

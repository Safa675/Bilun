"""Copay billing optimization from exact claim lines."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from src.bilun.domain.claims.models import ClaimHeader
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.copay_general import (
    resolve_drug_copay_rate,
    resolve_material_copay_rate,
)

from .copay_line_waivers import (
    WaiverResult,
    find_ek1a_source,
    waiver_composite_drug,
    waiver_composite_procedure,
    waiver_ek1a_muayene,
    waiver_ek4d_drug,
    waiver_inpatient_drug,
)
from .line_decomposition import (
    aggregate_decomposition_status,
    decompose_drug_line,
    decompose_procedure_line,
)
from .types import (
    COPAY_GAP_KIND_EXEMPTION_CORRECTION,
    COPAY_SAVINGS_BENEFICIARY_PATIENT_AND_SGK,
    EXACTNESS_STATUS_EXACT,
    CopayOptimization,
)

_COPAY_RULE_SOURCE = (
    "SUT §1.8.5(7)+EK-1/A exemptions; §1.8.5(8) inpatient/day-case drugs; "
    "§1.8.2(3)+EK-4/D drug exemptions; §1.8.2/§1.8.3 prose (copay_general_1_8)"
)


def _build_claim_procedure_codes(
    ctx: PatientClaimContext,
) -> dict[str, set[str]]:
    codes_by_claim: dict[str, set[str]] = defaultdict(set)
    for line in ctx.procedure_lines:
        code = str(line.procedure_code or "").strip()
        if code:
            codes_by_claim[line.claim_id].add(code)
    return codes_by_claim


def _collect_diagnosis_codes(ctx: PatientClaimContext) -> list[str]:
    diagnosis_codes: list[str] = []
    for diag in getattr(ctx, "diagnoses", ()) or ():
        code = getattr(diag, "icd10_code", "")
        if code:
            diagnosis_codes.append(str(code))
    for claim in getattr(ctx, "claims", ()) or ():
        primary = getattr(claim, "primary_icd10", "")
        if primary:
            diagnosis_codes.append(str(primary))
    return diagnosis_codes


def _resolve_exemption_sources(copay_exemption: dict) -> list[dict]:
    sources = list(copay_exemption.get("exemption_sources") or [])
    if sources:
        return sources

    if not copay_exemption.get("exempt"):
        return []

    qualifying = list(copay_exemption.get("qualifying_diagnoses") or [])
    if not qualifying:
        return []

    return [
        {
            "category": "ek1a_chronic",
            "rule_source": "SUT §1.8.5(7) + EK-1/A chronic disease copay exemptions",
            "counts_toward_exempt": copay_exemption.get("has_chronic_health_report")
            is not False,
            "waives_sections": ("1.8.1",),
            "evidence": {"qualifying_diagnoses": qualifying},
        }
    ]


def _apply_procedure_waiver(
    waiver: WaiverResult | None,
    *,
    visit_savings: Decimal,
    result: CopayOptimization,
) -> Decimal:
    if waiver is None:
        return visit_savings
    result.rate_corrections.append(waiver.to_rate_correction())
    if waiver.component_try > 0:
        visit_savings += waiver.component_try
    return visit_savings


def _apply_drug_waiver(
    waiver: WaiverResult | None,
    *,
    rx_savings: Decimal,
    rx_by_ground: dict[str, Decimal],
    result: CopayOptimization,
) -> Decimal:
    if waiver is None:
        return rx_savings
    result.rate_corrections.append(waiver.to_rate_correction())
    if waiver.component_try > 0:
        rx_savings += waiver.component_try
        rx_by_ground[waiver.exemption_ground] += waiver.component_try
    return rx_savings


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

    exemption_sources = _resolve_exemption_sources(copay_exemption)
    ek1a_source = find_ek1a_source(exemption_sources)

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

    claim_by_id: dict[str, ClaimHeader] = {claim.claim_id: claim for claim in ctx.claims}
    claim_procedure_codes = _build_claim_procedure_codes(ctx)
    diagnosis_codes = _collect_diagnosis_codes(ctx)

    visit_savings = Decimal("0")
    rx_savings = Decimal("0")
    rx_by_ground: dict[str, Decimal] = defaultdict(Decimal)
    patient_copay_total = Decimal("0")
    ilave_total = Decimal("0")
    decomposition_statuses: list[str] = []

    for line in ctx.procedure_lines:
        if line.billed_amount_try > line.expected_payable_try:
            decomp = decompose_procedure_line(line)
            patient_copay_total += decomp.patient_copay_try
            ilave_total += decomp.ilave_ucret_try
            decomposition_statuses.append(decomp.status)

        claim = claim_by_id.get(line.claim_id)
        if claim is None:
            continue

        waiver = waiver_composite_procedure(
            line,
            claim,
            exemption_sources,
            claim_procedure_codes,
        )
        if waiver is None or waiver.component_try <= 0:
            waiver = waiver_ek1a_muayene(
                line,
                claim,
                ek1a_source,
                has_health_report=has_health_report,
            )
        visit_savings = _apply_procedure_waiver(
            waiver,
            visit_savings=visit_savings,
            result=result,
        )

    for line in ctx.drug_lines:
        if line.billed_amount_try > line.expected_payable_try:
            decomp = decompose_drug_line(line)
            patient_copay_total += decomp.patient_copay_try
            ilave_total += decomp.ilave_ucret_try
            decomposition_statuses.append(decomp.status)

        claim = claim_by_id.get(line.claim_id)
        if claim is None:
            continue

        drug_waiver: WaiverResult | None = None

        composite = waiver_composite_drug(
            line,
            claim,
            exemption_sources,
            claim_procedure_codes,
        )
        if composite is not None and composite.component_try > 0:
            drug_waiver = composite

        if drug_waiver is None:
            inpatient = waiver_inpatient_drug(line, claim)
            if inpatient is not None and inpatient.component_try > 0:
                drug_waiver = inpatient

        ek4d = waiver_ek4d_drug(
            line,
            diagnosis_codes,
            has_health_report=has_health_report,
            savings_already_applied=drug_waiver is not None,
        )
        if ek4d is not None:
            if ek4d.component_try > 0 and drug_waiver is None:
                drug_waiver = ek4d
            elif ek4d.insight_only or ek4d.component_try <= 0:
                result.rate_corrections.append(ek4d.to_rate_correction())

        rx_savings = _apply_drug_waiver(
            drug_waiver,
            rx_savings=rx_savings,
            rx_by_ground=rx_by_ground,
            result=result,
        )

    visit_waived = round(float(visit_savings), 2)
    rx_waived = round(float(rx_savings), 2)
    result.savings_beneficiary = COPAY_SAVINGS_BENEFICIARY_PATIENT_AND_SGK
    result.gap_kind = COPAY_GAP_KIND_EXEMPTION_CORRECTION
    result.visit_copay_savings_try = visit_waived
    result.rx_copay_savings_try = rx_waived
    result.total_copay_savings_try = visit_waived
    result.patient_copay_waived_total_try = round(visit_waived + rx_waived, 2)
    result.patient_copay_try = round(float(patient_copay_total), 2)
    result.ilave_ucret_total_try = round(float(ilave_total), 2)
    result.line_decomposition_status = aggregate_decomposition_status(decomposition_statuses)
    result.rx_copay_savings_by_ground = {
        ground: round(float(amount), 2) for ground, amount in rx_by_ground.items() if amount > 0
    }
    result.exemption_sources = exemption_sources
    result.primary_exemption_category = copay_exemption.get("primary_exemption_category")
    result.categories_not_evaluated = list(
        copay_exemption.get("categories_not_evaluated") or []
    )
    if is_exempt:
        result.copay_primary_outcome = "exempt"
    elif partial_exempt:
        result.copay_primary_outcome = "partial_exempt"
    else:
        result.copay_primary_outcome = "none"

    result.exactness_status = EXACTNESS_STATUS_EXACT
    result.unavailable_reason = None
    result.required_inputs_missing = []
    result.rule_source = _COPAY_RULE_SOURCE

    expected_rx_rate = resolve_drug_copay_rate("other")
    if ctx.drug_lines and rx_waived == 0 and not is_exempt:
        result.rate_corrections.append(
            {
                "detail": (
                    f"SUT §1.8.2 mandates {expected_rx_rate:.0%} drug copay for "
                    "non-income-recipient patients when no line-level waiver applies."
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

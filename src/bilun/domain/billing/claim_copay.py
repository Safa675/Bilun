"""Copay billing optimization from exact claim lines."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from functools import lru_cache

from src.bilun.domain.claims.models import ClaimHeader
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.copay_general import (
    resolve_drug_copay_rate,
    resolve_material_copay_rate,
)
from src.bilun.domain.sut.clause_reference import (
    RULE_TYPE_COPAY_RATE,
    RULE_TYPE_COPAY_WAIVER,
    SutClauseReference,
    sut_clause_reference,
)

from .copay_line_waivers import (
    _EMERGENCY_TYPES,
    _normalize_token,
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
    cancer_surcharge_exemption_clause,
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


# Drug-derived exemption grounds; their rate-correction rows already carry
# ilave_ucret_status="drug_prohibited" and never receive the cancer upgrade.
_DRUG_EXEMPTION_GROUNDS = frozenset(
    {"inpatient_drug_1_8_5_8", "ek4d_drug", "ek4d_partial"}
)


def _has_malignant_qualifying_diagnosis(sources: list[dict]) -> bool:
    """True when any qualifying diagnosis ICD-10 code is in the C00-C97 range.

    Consumes structured exemption output only: a code qualifies when it
    uppercased starts with 'C' followed by two digits (e.g. "C50", "C83.1").
    """
    for source in sources:
        evidence = source.get("evidence") or {}
        for diagnosis in evidence.get("qualifying_diagnoses") or []:
            code = str(diagnosis.get("icd10") or "").strip().upper()
            if len(code) >= 3 and code[0] == "C" and code[1:3].isdigit():
                return True
    return False


def _emergency_claim_ids(
    claims: tuple[ClaimHeader, ...],
    sources: list[dict],
) -> frozenset[str]:
    """Claim ids whose type is an emergency type, when an acil source exists."""
    if not any(source.get("category") == "acil_servis" for source in sources):
        return frozenset()
    return frozenset(
        claim.claim_id
        for claim in claims
        if _normalize_token(claim.claim_type) in _EMERGENCY_TYPES
    )


def _annotate_cancer_exempt(
    row: dict,
    *,
    exemption_ground: str,
    cancer_exempt: bool,
) -> None:
    """Upgrade an unset/'none' procedure-derived row to cancer_exempt."""
    if not cancer_exempt:
        return
    if exemption_ground in _DRUG_EXEMPTION_GROUNDS:
        return
    if row.get("ilave_ucret_status") not in (None, "none"):
        return
    row["ilave_ucret_status"] = "cancer_exempt"
    row["ilave_clause_ref"] = cancer_surcharge_exemption_clause().to_dict()


@lru_cache(maxsize=1)
def _ek1a_partial_clause_ref() -> SutClauseReference:
    return sut_clause_reference(
        "1.8.5.(7)", rule_type=RULE_TYPE_COPAY_WAIVER, annex="EK-1/A"
    )


@lru_cache(maxsize=1)
def _drug_copay_mandate_clause_ref() -> SutClauseReference:
    return sut_clause_reference("1.8.2.(1)", rule_type=RULE_TYPE_COPAY_RATE)


@lru_cache(maxsize=1)
def _material_copay_clause_ref() -> SutClauseReference:
    return sut_clause_reference("1.8.3.(2)", rule_type=RULE_TYPE_COPAY_RATE)


def _apply_procedure_waiver(
    waiver: WaiverResult | None,
    *,
    visit_savings: Decimal,
    result: CopayOptimization,
    cancer_exempt: bool = False,
) -> Decimal:
    if waiver is None:
        return visit_savings
    row = waiver.to_rate_correction()
    _annotate_cancer_exempt(
        row, exemption_ground=waiver.exemption_ground, cancer_exempt=cancer_exempt
    )
    result.rate_corrections.append(row)
    if waiver.component_try > 0:
        visit_savings += waiver.component_try
    return visit_savings


def _apply_drug_waiver(
    waiver: WaiverResult | None,
    *,
    rx_savings: Decimal,
    rx_by_ground: dict[str, Decimal],
    result: CopayOptimization,
    cancer_exempt: bool = False,
) -> Decimal:
    if waiver is None:
        return rx_savings
    row = waiver.to_rate_correction()
    _annotate_cancer_exempt(
        row, exemption_ground=waiver.exemption_ground, cancer_exempt=cancer_exempt
    )
    result.rate_corrections.append(row)
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
    cancer_exempt = _has_malignant_qualifying_diagnosis(exemption_sources)
    emergency_claim_ids = _emergency_claim_ids(ctx.claims, exemption_sources)

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
            # The report is not on file (False) or not known (None): no waiver is claimed.
            report_missing = has_health_report is False
            result.rate_corrections.append(
                {
                    "detail": (
                        "EK-1/A diagnosis matched; no chronic health report on file, "
                        "so the §1.8.5(7) waiver is not claimed."
                        if report_missing
                        else "EK-1/A diagnosis matched; chronic health report status unknown, "
                        "so the §1.8.5(7) waiver is not claimed."
                    ),
                    "sut_section": "1.8.5(7)",
                    "rule_id": "copay_exemption_ek1a",
                    "clause_ref": _ek1a_partial_clause_ref().to_dict(),
                    "message_code": (
                        "ek1a_report_missing" if report_missing else "ek1a_report_unknown"
                    ),
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
            decomp = decompose_procedure_line(
                line,
                cancer_exempt=cancer_exempt,
                emergency_exempt=line.claim_id in emergency_claim_ids,
            )
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
            cancer_exempt=cancer_exempt,
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
            cancer_exempt=cancer_exempt,
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
                "clause_ref": _drug_copay_mandate_clause_ref().to_dict(),
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
                "clause_ref": _material_copay_clause_ref().to_dict(),
                "message_code": "material_copay_rate",
                "message_params": {"rate_pct": int(round(material_rate * 100))},
            }
        )

    return result

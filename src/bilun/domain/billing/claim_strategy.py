"""Package vs itemized billing strategy from exact claim lines."""

from __future__ import annotations

from datetime import date

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.pricing import get_drg_package_price_for_date
from src.bilun.domain.prose_rules import (
    check_payment_method_compliance,
    resolve_payment_method,
)
from src.bilun.domain.prose_rules.catalog_membership import get_ek2c_entry
from src.bilun.domain.prose_rules.claim_utils import infer_care_setting
from src.bilun.domain.prose_rules.session_pricing import (
    compute_session_adjusted_itemized_total,
)
from src.bilun.domain.prose_rules.types import PaymentMethodKind, PaymentMethodResult

from .types import EXACTNESS_STATUS_EXACT, BillingStrategyRecommendation

_PROSE_RULE_SOURCE = (
    "SUT §2.2 prose rules (payment_method_2_2) + EK-2B/EK-2C catalog membership"
)


def _money(value) -> float:
    return round(float(value), 2)


def _claim_for_line(
    line: ProcedureClaimLine,
    claims: tuple[ClaimHeader, ...],
) -> ClaimHeader | None:
    for claim in claims:
        if claim.claim_id == line.claim_id:
            return claim
    return None


def _line_as_of_date(
    line: ProcedureClaimLine,
    claim: ClaimHeader | None,
) -> date | None:
    if line.procedure_date is not None:
        return line.procedure_date
    if claim is None:
        return None
    return claim.admission_date or claim.claim_start_date


def _resolve_line_payment_method(
    line: ProcedureClaimLine,
    claim: ClaimHeader | None,
    *,
    care_setting: str,
) -> PaymentMethodResult:
    facility_tier = claim.facility_tier if claim is not None else None
    provider_type = claim.provider_type if claim is not None else None
    return resolve_payment_method(
        line.procedure_code,
        care_setting=care_setting,  # type: ignore[arg-type]
        facility_tier=facility_tier,
        provider_type=provider_type,
        as_of_date=_line_as_of_date(line, claim),
    )


def _infer_current_billing(claim_procs: list[ProcedureClaimLine]) -> str:
    billed_package = any(
        line.procedure_category == "paket" and float(line.billed_amount_try) > 0
        for line in claim_procs
    )
    return "package" if billed_package else "itemized"


def _aggregate_claim_kind(line_results: list[PaymentMethodResult]) -> PaymentMethodKind | None:
    kinds = {result.kind for result in line_results if result.kind != "NOT_IN_SUT"}
    if not kinds:
        return None
    if kinds == {"ITEMIZED"}:
        return "ITEMIZED"
    if "DRG_MANDATORY" in kinds:
        return "DRG_MANDATORY"
    if "DRG_OVERRIDABLE" in kinds:
        return "DRG_OVERRIDABLE"
    return next(iter(sorted(kinds)))


def _primary_line_result(
    line_results: list[PaymentMethodResult],
    claim_kind: PaymentMethodKind,
) -> PaymentMethodResult:
    for result in line_results:
        if result.kind == claim_kind:
            return result
    return line_results[0]


def _compute_claim_savings(
    *,
    claim_kind: PaymentMethodKind,
    recommendation: str,
    current_billing: str,
    package_total: float,
    itemized_total: float,
) -> float:
    if claim_kind == "DRG_OVERRIDABLE":
        return _money(abs(package_total - itemized_total))

    if recommendation == "package":
        if current_billing == "package":
            return 0.0
        return _money(max(0.0, itemized_total - package_total))

    if current_billing == "itemized":
        return 0.0
    return _money(max(0.0, package_total - itemized_total))


def _claim_recommendation_detail(
    *,
    claim_id: str,
    claim_kind: PaymentMethodKind,
    recommendation: str,
    recommendation_kind: str,
    package_total: float,
    itemized_total: float,
    current_billing: str,
) -> str:
    if claim_kind == "DRG_MANDATORY":
        if current_billing == "package":
            return (
                f"Claim {claim_id} is billed correctly as package per SUT §2.2.2(1). "
                f"Package total {package_total:.2f} TRY."
            )
        return (
            f"SUT §2.2 mandates package billing for claim {claim_id} "
            f"(EK-2/C procedure present). Package total {package_total:.2f} TRY vs "
            f"itemized {itemized_total:.2f} TRY."
        )

    if claim_kind == "ITEMIZED":
        if current_billing == "itemized":
            return (
                f"Claim {claim_id} is billed correctly as itemized per SUT §2.2. "
                f"Itemized total {itemized_total:.2f} TRY."
            )
        return (
            f"SUT §2.2 mandates itemized billing for claim {claim_id}. "
            f"Itemized total {itemized_total:.2f} TRY vs package "
            f"{package_total:.2f} TRY."
        )

    if recommendation == "package":
        return (
            f"Claim {claim_id}: optional §2.2.2(2) override — package billing "
            f"({package_total:.2f} TRY) is the higher legal option vs itemized "
            f"({itemized_total:.2f} TRY)."
        )
    return (
        f"Claim {claim_id}: optional §2.2.2(2) override — itemized billing "
        f"({itemized_total:.2f} TRY) is the higher legal option vs package "
        f"({package_total:.2f} TRY)."
    )


def recommend_billing_strategy_from_claims(
    ctx: PatientClaimContext,
) -> BillingStrategyRecommendation:
    """Recommend package vs itemized billing per SUT §2.2 prose rules."""

    recommendations: list[dict] = []

    for line in ctx.procedure_lines:
        claim = _claim_for_line(line, ctx.claims)
        care_setting = infer_care_setting(claim) if claim is not None else "inpatient"
        billed_as_package = line.procedure_category == "paket"

        as_of = _line_as_of_date(line, claim)
        compliance = check_payment_method_compliance(
            line.procedure_code,
            billed_as_package=billed_as_package,
            care_setting=care_setting,  # type: ignore[arg-type]
            facility_tier=claim.facility_tier if claim is not None else None,
            provider_type=claim.provider_type if claim is not None else None,
            as_of_date=as_of,
        )
        if not compliance.is_compliant and compliance.mandated_method != "unknown":
            recommendations.append(
                {
                    "type": "compliance_violation",
                    "claim_id": line.claim_id,
                    "procedure_code": line.procedure_code,
                    "procedure_name": line.procedure_name,
                    "mandated_method": compliance.mandated_method,
                    "payment_method_kind": compliance.kind,
                    "billed_as_package": billed_as_package,
                    "sut_section_id": compliance.trace.sut_section,
                    "rule_id": compliance.trace.rule_id,
                    "detail": compliance.detail,
                }
            )

        mandated = _resolve_line_payment_method(
            line,
            claim,
            care_setting=care_setting,
        )
        if mandated.payment_method != "unknown":
            recommendations.append(
                {
                    "claim_id": line.claim_id,
                    "procedure_code": line.procedure_code,
                    "mandated_method": mandated.payment_method,
                    "payment_method_kind": mandated.kind,
                    "sut_section_id": mandated.trace.sut_section,
                    "rule_id": mandated.trace.rule_id,
                    "detail": mandated.trace.detail,
                }
            )

    for claim in ctx.claims:
        if not claim.package_candidate:
            continue

        claim_procs = [
            line for line in ctx.procedure_lines if line.claim_id == claim.claim_id
        ]
        if not claim_procs:
            continue

        care_setting = infer_care_setting(claim)
        line_results = [
            _resolve_line_payment_method(line, claim, care_setting=care_setting)
            for line in claim_procs
        ]
        claim_kind = _aggregate_claim_kind(line_results)
        if claim_kind is None:
            continue

        itemized_raw = sum(
            float(line.expected_payable_try)
            for line in claim_procs
            if line.procedure_category != "paket" and not line.is_package_included
        )
        itemized_total, itemized_meta = compute_session_adjusted_itemized_total(
            claim_procs,
            same_incision=True,
            cross_specialty=False,
        )
        itemized_price_methodology = str(
            itemized_meta.get("methodology") or "claim_lines"
        )

        package_lines = [
            line for line in claim_procs if line.procedure_category == "paket"
        ]
        package_total = sum(float(line.expected_payable_try) for line in package_lines)
        package_price_methodology = "claim_lines"

        if package_total <= 0 and package_lines:
            for line in package_lines:
                as_of = _line_as_of_date(line, claim)
                entry = get_ek2c_entry(line.procedure_code, as_of_date=as_of)
                price_try = entry.get("price_try") if entry else None
                if price_try is not None and float(price_try) > 0:
                    package_total = float(price_try)
                    package_price_methodology = "ek2c_code"
                    break

        if package_total <= 0 and claim.admission_date is not None:
            chapter = (claim.primary_icd10 or "R69")[:1].upper()
            drg_price = get_drg_package_price_for_date(
                chapter,
                claim.admission_date,
                icd10_code=claim.primary_icd10,
            )
            if drg_price is not None:
                package_total = float(drg_price)
                package_price_methodology = "chapter_median_heuristic"

        if package_total <= 0 and itemized_total <= 0:
            continue

        primary = _primary_line_result(line_results, claim_kind)
        current_billing = _infer_current_billing(claim_procs)

        if claim_kind == "DRG_MANDATORY":
            recommendation = "package"
            recommendation_kind = "mandatory_compliance"
        elif claim_kind == "ITEMIZED":
            recommendation = "itemized"
            recommendation_kind = "mandatory_compliance"
        else:
            recommendation = (
                "package" if package_total >= itemized_total else "itemized"
            )
            recommendation_kind = "optional_override"

        savings = _compute_claim_savings(
            claim_kind=claim_kind,
            recommendation=recommendation,
            current_billing=current_billing,
            package_total=package_total,
            itemized_total=itemized_total,
        )
        detail = _claim_recommendation_detail(
            claim_id=claim.claim_id,
            claim_kind=claim_kind,
            recommendation=recommendation,
            recommendation_kind=recommendation_kind,
            package_total=package_total,
            itemized_total=itemized_total,
            current_billing=current_billing,
        )

        catalog_dates = sorted(
            {
                d.isoformat()
                for d in (_line_as_of_date(line, claim) for line in claim_procs)
                if d is not None
            }
        )
        if package_price_methodology == "chapter_median_heuristic":
            savings_basis = "heuristic"
        elif recommendation_kind == "optional_override":
            savings_basis = "optional_override"
        else:
            savings_basis = "claim_line"

        recommendations.append(
            {
                "claim_id": claim.claim_id,
                "recommendation": recommendation,
                "recommendation_kind": recommendation_kind,
                "payment_method_kind": claim_kind,
                "sut_section_id": primary.trace.sut_section,
                "rule_id": primary.trace.rule_id,
                "package_total_try": _money(package_total),
                "itemized_total_try": _money(itemized_total),
                "savings_try": savings,
                "savings_basis": savings_basis,
                "current_billing": current_billing,
                "detail": detail,
                "catalog_as_of_date": catalog_dates[-1] if catalog_dates else None,
                "package_price_methodology": package_price_methodology,
                "itemized_price_methodology": itemized_price_methodology,
                "itemized_raw_try": _money(itemized_raw),
                "mandated_methods": sorted(
                    {
                        result.payment_method
                        for result in line_results
                        if result.payment_method != "unknown"
                    }
                ),
            }
        )

    if not recommendations:
        return BillingStrategyRecommendation(
            recommendations=[],
            exactness_status=EXACTNESS_STATUS_EXACT,
            unavailable_reason=None,
            required_inputs_missing=[],
            rule_source=_PROSE_RULE_SOURCE,
        )

    return BillingStrategyRecommendation(
        recommendations=recommendations,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
    )

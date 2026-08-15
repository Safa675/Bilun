"""Package vs itemized billing strategy from exact claim lines."""

from __future__ import annotations

from datetime import date
from typing import Any

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules import (
    check_payment_method_compliance,
    resolve_payment_method,
)
from src.bilun.domain.prose_rules.catalog_membership import get_ek2c_entry
from src.bilun.domain.prose_rules.care_setting_review import _pick_claim_kind
from src.bilun.domain.prose_rules.claim_utils import infer_care_setting
from src.bilun.domain.prose_rules.session_pricing import (
    _line_itemized_payable,
    compute_session_adjusted_itemized_total,
)
from src.bilun.domain.prose_rules.facility_tier import FACILITY_TIER_MISSING_INPUT
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_OPTIONAL_OVERRIDE,
    SAVINGS_CATEGORY_COMPLIANCE,
    SAVINGS_CATEGORY_SGK_UPLIFT,
    PaymentMethodCompliance,
    PaymentMethodKind,
    PaymentMethodResult,
)
from src.bilun.domain.sut.clause_reference import sut_clause_reference

from .demo_vignette_lookup import (
    hypothetical_itemized_total_try,
    hypothetical_package_total_try,
    recommended_package_code_for_claim,
)
from .types import EXACTNESS_STATUS_EXACT, EXACTNESS_STATUS_MISSING_INPUTS, BillingStrategyRecommendation

_PROSE_RULE_SOURCE = (
    "SUT §2.2 prose rules (payment_method_2_2) + EK-2B/EK-2C catalog membership"
)


# _money is imported from src.bilun.domain.money (money_round_half_up).
# Previously a local `round(float(value), 2)` — banker's rounding, no SUT
# citation. Now ROUND_HALF_UP, float return type preserved.


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


def resolve_package_total_try(
    claim: ClaimHeader,
    claim_procs: list[ProcedureClaimLine],
) -> tuple[float, str]:
    """Resolve package total using claim-line payables, then EK-2C code lookup."""
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

    if package_total <= 0:
        package_codes = sorted(
            {
                str(line.package_code).strip()
                for line in claim_procs
                if str(line.package_code or "").strip()
            }
        )
        for package_code in package_codes:
            as_of = _line_as_of_date(claim_procs[0], claim)
            entry = get_ek2c_entry(package_code, as_of_date=as_of)
            price_try = entry.get("price_try") if entry else None
            if price_try is not None and float(price_try) > 0:
                package_total = float(price_try)
                package_price_methodology = "ek2c_candidate_code"
                break

    return _money(package_total), package_price_methodology


def lines_for_legal_itemized_alternative(
    lines: list[ProcedureClaimLine],
    claim: ClaimHeader,
    *,
    care_setting: str | None = None,
) -> list[ProcedureClaimLine]:
    """Procedure lines that may count toward a legal itemized payment alternative."""
    if care_setting is None:
        care_setting = infer_care_setting(claim)
    eligible: list[ProcedureClaimLine] = []

    for line in lines:
        if line.procedure_category == "paket":
            continue
        if line.is_package_included:
            continue
        if _line_itemized_payable(line) <= 0:
            continue

        billed_as_package = line.procedure_category == "paket"
        compliance = check_payment_method_compliance(
            line.procedure_code,
            billed_as_package=billed_as_package,
            care_setting=care_setting,  # type: ignore[arg-type]
            facility_tier=claim.facility_tier,
            provider_type=claim.provider_type,
            as_of_date=_line_as_of_date(line, claim),
        )
        if not compliance.is_compliant:
            continue
        eligible.append(line)

    return eligible


def _itemized_exclusion_metadata(
    lines: list[ProcedureClaimLine],
    claim: ClaimHeader,
    *,
    eligible_lines: list[ProcedureClaimLine] | None = None,
) -> tuple[int, list[str]]:
    # Reuse the caller's eligible-lines computation when available to avoid a
    # second call to lines_for_legal_itemized_alternative (which iterates the
    # full claim + does session/cross-specialty gating each time).
    resolved_eligible = (
        eligible_lines
        if eligible_lines is not None
        else lines_for_legal_itemized_alternative(lines, claim)
    )
    eligible_ids = {
        line.procedure_line_id
        for line in resolved_eligible
    }
    excluded_codes = sorted(
        {
            line.procedure_code
            for line in lines
            if line.procedure_line_id not in eligible_ids
            and line.procedure_category != "paket"
            and not line.is_package_included
            and _line_itemized_payable(line) > 0
        }
    )
    return len(excluded_codes), excluded_codes


def _infer_current_billing(claim_procs: list[ProcedureClaimLine]) -> str:
    billed_package = any(
        line.procedure_category == "paket" and float(line.billed_amount_try) > 0
        for line in claim_procs
    )
    return "package" if billed_package else "itemized"


def _aggregate_claim_kind(line_results: list[PaymentMethodResult]) -> PaymentMethodKind | None:
    if any(result.kind == "MISSING_INPUTS" for result in line_results):
        return None
    return _pick_claim_kind({result.kind for result in line_results})


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
        if current_billing == recommendation:
            return 0.0
        return _money(abs(package_total - itemized_total))

    if recommendation == "package":
        if current_billing == "package":
            return 0.0
        return _money(max(0.0, itemized_total - package_total))

    if current_billing == "itemized":
        return 0.0
    return _money(max(0.0, package_total - itemized_total))


def _claim_recommendation_message(
    *,
    claim_id: str,
    claim_kind: PaymentMethodKind,
    recommendation: str,
    recommendation_kind: str,
    package_total: float,
    itemized_total: float,
    current_billing: str,
) -> dict[str, Any]:
    """Claim-level detail plus the §2.2 structured message contract.

    The English ``detail`` stays byte-identical (fallback / ``text_en``);
    ``message_code`` + ``message_params`` let the frontend render the same
    sentence from i18n templates without regex-parsing. Amount params carry
    the exact two-decimal text embedded in ``detail`` so rendering output is
    unchanged.
    """
    package_amount = f"{package_total:.2f}"
    itemized_amount = f"{itemized_total:.2f}"

    if claim_kind == "DRG_MANDATORY":
        if current_billing == "package":
            return {
                "detail": (
                    f"Claim {claim_id} is billed correctly as package per SUT §2.2.2(1). "
                    f"Package total {package_amount} TRY."
                ),
                "message_code": "claim_package_ok",
                "message_params": {
                    "claim_id": claim_id,
                    "amount_try": package_amount,
                },
            }
        return {
            "detail": (
                f"SUT §2.2 mandates package billing for claim {claim_id} "
                f"(EK-2/C procedure present). Package total {package_amount} TRY vs "
                f"itemized {itemized_amount} TRY."
            ),
            "message_code": "claim_mandate_package",
            "message_params": {
                "claim_id": claim_id,
                "package_total_try": package_amount,
                "itemized_total_try": itemized_amount,
            },
        }

    if claim_kind == "ITEMIZED":
        if current_billing == "itemized":
            return {
                "detail": (
                    f"Claim {claim_id} is billed correctly as itemized per SUT §2.2. "
                    f"Itemized total {itemized_amount} TRY."
                ),
                "message_code": "claim_itemized_ok",
                "message_params": {
                    "claim_id": claim_id,
                    "amount_try": itemized_amount,
                },
            }
        return {
            "detail": (
                f"SUT §2.2 mandates itemized billing for claim {claim_id}. "
                f"Itemized total {itemized_amount} TRY vs package "
                f"{package_amount} TRY."
            ),
            "message_code": "claim_mandate_itemized",
            "message_params": {
                "claim_id": claim_id,
                "itemized_total_try": itemized_amount,
                "package_total_try": package_amount,
            },
        }

    if recommendation == "package":
        return {
            "detail": (
                f"Claim {claim_id}: optional §2.2.2(2) override — package billing "
                f"({package_amount} TRY) is the higher legal option vs itemized "
                f"({itemized_amount} TRY)."
            ),
            "message_code": "claim_optional_package_higher",
            "message_params": {
                "claim_id": claim_id,
                "package_total_try": package_amount,
                "itemized_total_try": itemized_amount,
            },
        }
    return {
        "detail": (
            f"Claim {claim_id}: optional §2.2.2(2) override — itemized billing "
            f"({itemized_amount} TRY) is the higher legal option vs package "
            f"({package_amount} TRY)."
        ),
        "message_code": "claim_optional_itemized_higher",
        "message_params": {
            "claim_id": claim_id,
            "itemized_total_try": itemized_amount,
            "package_total_try": package_amount,
        },
    }


def _compliance_violation_message(
    compliance: PaymentMethodCompliance,
    payment_method_tr: str,
) -> dict[str, Any]:
    """Structured message fields for §2.2 "must use" compliance-violation rows.

    Only called for non-compliant rows with a known mandated method, i.e. the
    two detail shapes built by ``check_payment_method_compliance``.
    """
    message_code = (
        "procedure_must_package"
        if compliance.mandated_method == "package"
        else "procedure_must_itemized"
    )
    return {
        "message_code": message_code,
        "message_params": {
            "procedure_code": compliance.procedure_code,
            "method": payment_method_tr,
            "section": compliance.trace.sut_section,
        },
    }


def recommend_billing_strategy_from_claims(
    ctx: PatientClaimContext,
) -> BillingStrategyRecommendation:
    """Recommend package vs itemized billing per SUT §2.2 prose rules."""

    recommendations: list[dict] = []
    tier_inputs_missing = False

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
        mandated = _resolve_line_payment_method(
            line,
            claim,
            care_setting=care_setting,
        )
        emitted_violation = False
        if not compliance.is_compliant and compliance.mandated_method != "unknown":
            violation_row: dict[str, Any] = {
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
            violation_row.update(
                _compliance_violation_message(compliance, mandated.payment_method_tr)
            )
            if compliance.trace.sut_section:
                violation_row["clause_ref"] = sut_clause_reference(
                    compliance.trace.sut_section
                ).to_dict()
            recommendations.append(violation_row)
            emitted_violation = True
        if mandated.kind == "MISSING_INPUTS":
            tier_inputs_missing = True
        # Only emit the informational mandated-method line when we did NOT
        # already emit a compliance_violation for the same procedure line.
        # Emitting both produced a duplicate that inflated action_count while
        # being invisible in the UI (no type/recommendation_kind to match the
        # frontend predicates). Tag informational rows with an explicit type
        # so downstream counters/filters can exclude them from action totals.
        if mandated.payment_method != "unknown" and not emitted_violation:
            recommendations.append(
                {
                    "type": "informational",
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

        eligible_lines = lines_for_legal_itemized_alternative(claim_procs, claim)
        excluded_count, excluded_codes = _itemized_exclusion_metadata(
            claim_procs, claim, eligible_lines=eligible_lines
        )
        itemized_raw = sum(float(line.expected_payable_try) for line in eligible_lines)
        itemized_total, itemized_meta = compute_session_adjusted_itemized_total(
            eligible_lines,
            same_incision=True,
            cross_specialty=None,
            claim=claim,
        )
        itemized_price_methodology = str(
            itemized_meta.get("methodology") or "claim_lines"
        )

        package_total, package_price_methodology = resolve_package_total_try(
            claim,
            claim_procs,
        )
        hypothetical_package = hypothetical_package_total_try(
            claim,
            claim_procs,
            resolved_package_total=package_total,
        )
        if hypothetical_package is not None:
            package_total = max(package_total, hypothetical_package)
            if package_total == hypothetical_package:
                package_price_methodology = "demo_vignette_hypothesis"

        hypothetical_itemized = hypothetical_itemized_total_try(
            claim,
            claim_procs,
            resolved_itemized_total=itemized_total,
        )
        if hypothetical_itemized is not None:
            itemized_total = max(itemized_total, hypothetical_itemized)
            if itemized_total == hypothetical_itemized:
                itemized_price_methodology = "demo_vignette_hypothesis"

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
        message = _claim_recommendation_message(
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
        if recommendation_kind == "optional_override":
            savings_basis = SAVINGS_BASIS_OPTIONAL_OVERRIDE
        else:
            savings_basis = "claim_line"

        savings_category = (
            SAVINGS_CATEGORY_SGK_UPLIFT
            if recommendation_kind == "optional_override" and savings > 0
            else SAVINGS_CATEGORY_COMPLIANCE
            if recommendation_kind == "mandatory_compliance" and savings > 0
            else None
        )

        recommended_package_code = (
            recommended_package_code_for_claim(claim, claim_procs)
            if recommendation == "package"
            else None
        )

        claim_row: dict[str, Any] = {
            "claim_id": claim.claim_id,
            "recommendation": recommendation,
            "recommendation_kind": recommendation_kind,
            "payment_method_kind": claim_kind,
            "recommended_package_code": recommended_package_code,
            "sut_section_id": primary.trace.sut_section,
            "rule_id": primary.trace.rule_id,
            "package_total_try": _money(package_total),
            "itemized_total_try": _money(itemized_total),
            "savings_try": savings,
            "recoverable_uplift_try": savings,
            "savings_basis": savings_basis,
            "savings_category": savings_category,
            "included_in_sgk_total": bool(savings_category),
            "current_billing": current_billing,
            "detail": message["detail"],
            "message_code": message["message_code"],
            "message_params": message["message_params"],
            "catalog_as_of_date": catalog_dates[-1] if catalog_dates else None,
            "package_price_methodology": package_price_methodology,
            "itemized_price_methodology": itemized_price_methodology,
            "itemized_raw_try": _money(itemized_raw),
            "itemized_excluded_violation_count": excluded_count,
            "itemized_excluded_procedure_codes": excluded_codes[:10],
            "mandated_methods": sorted(
                {
                    result.payment_method
                    for result in line_results
                    if result.payment_method != "unknown"
                }
            ),
        }
        # Natural coordinate already carried by the row (sut_section_id) —
        # attach the resolved clause cite; never invent one.
        if primary.trace.sut_section:
            claim_row["clause_ref"] = sut_clause_reference(
                primary.trace.sut_section
            ).to_dict()
        recommendations.append(claim_row)

    required_inputs_missing = (
        [FACILITY_TIER_MISSING_INPUT] if tier_inputs_missing else []
    )
    exactness_status = (
        EXACTNESS_STATUS_MISSING_INPUTS
        if tier_inputs_missing
        else EXACTNESS_STATUS_EXACT
    )
    unavailable_reason = (
        "facility_tier required for §2.2.2(2) optional override eligibility"
        if tier_inputs_missing
        else None
    )

    if not recommendations:
        return BillingStrategyRecommendation(
            recommendations=[],
            exactness_status=exactness_status,
            unavailable_reason=unavailable_reason,
            required_inputs_missing=required_inputs_missing,
            rule_source=_PROSE_RULE_SOURCE,
        )

    return BillingStrategyRecommendation(
        recommendations=recommendations,
        exactness_status=exactness_status,
        unavailable_reason=unavailable_reason,
        required_inputs_missing=required_inputs_missing,
        rule_source=_PROSE_RULE_SOURCE,
    )

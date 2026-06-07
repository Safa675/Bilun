"""Advisory care-setting review — inpatient vs outpatient ambiguity (SUT §2.2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.bilun.domain.prose_rules.claim_utils import detect_care_setting_ambiguity
from src.bilun.domain.prose_rules.facility_tier import normalize_facility_tier
from src.bilun.domain.prose_rules.payment_method import resolve_payment_method
from src.bilun.domain.prose_rules.session_pricing import (
    compute_session_adjusted_itemized_total,
)
from src.bilun.domain.prose_rules.types import (
    SAVINGS_CATEGORY_SGK_UPLIFT,
    CareSetting,
    PaymentMethodKind,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_RULE_SET_ID = "care_setting_review_2_2"


@dataclass(frozen=True)
class CareSettingLegalTotals:
    best_try: float
    kind: PaymentMethodKind | None
    package_total_try: float
    itemized_total_try: float


def _money(value: float) -> float:
    return round(float(value), 2)


def _line_as_of_date(
    line: ProcedureClaimLine,
    claim: ClaimHeader,
):
    if line.procedure_date is not None:
        return line.procedure_date
    return claim.admission_date or claim.claim_start_date


def _aggregate_claim_kind(
    line_kinds: list[PaymentMethodKind],
) -> PaymentMethodKind | None:
    kinds = {kind for kind in line_kinds if kind != "NOT_IN_SUT"}
    if not kinds:
        return None
    if kinds == {"ITEMIZED"}:
        return "ITEMIZED"
    if "DRG_MANDATORY" in kinds:
        return "DRG_MANDATORY"
    if "DRG_OVERRIDABLE" in kinds:
        return "DRG_OVERRIDABLE"
    return next(iter(sorted(kinds)))


def _resolve_claim_kind(
    claim: ClaimHeader,
    claim_procs: list[ProcedureClaimLine],
    *,
    care_setting: CareSetting,
) -> PaymentMethodKind | None:
    kinds: list[PaymentMethodKind] = []
    for line in claim_procs:
        result = resolve_payment_method(
            line.procedure_code,
            care_setting=care_setting,
            facility_tier=claim.facility_tier,
            provider_type=claim.provider_type,
            as_of_date=_line_as_of_date(line, claim),
        )
        kinds.append(result.kind)
    return _aggregate_claim_kind(kinds)


def _best_legal_recoverable_try(
    claim: ClaimHeader,
    claim_procs: list[ProcedureClaimLine],
    *,
    care_setting: CareSetting,
) -> CareSettingLegalTotals:
    claim_kind = _resolve_claim_kind(claim, claim_procs, care_setting=care_setting)
    if claim_kind is None:
        return CareSettingLegalTotals(0.0, None, 0.0, 0.0)

    itemized_total, _ = compute_session_adjusted_itemized_total(
        claim_procs,
        same_incision=True,
        cross_specialty=None,
        claim=claim,
    )
    from src.bilun.domain.billing.claim_strategy import resolve_package_total_try

    package_total, _ = resolve_package_total_try(claim, claim_procs)

    if package_total <= 0 and itemized_total <= 0:
        return CareSettingLegalTotals(
            0.0,
            claim_kind,
            _money(package_total),
            _money(itemized_total),
        )

    if claim_kind == "DRG_OVERRIDABLE":
        best = max(package_total, itemized_total)
    elif claim_kind == "DRG_MANDATORY":
        best = package_total
    elif claim_kind == "ITEMIZED":
        best = itemized_total
    else:
        best = 0.0

    return CareSettingLegalTotals(
        _money(best),
        claim_kind,
        _money(package_total),
        _money(itemized_total),
    )


def detect_care_setting_review_opportunities(
    claim: ClaimHeader,
    claim_procs: list[ProcedureClaimLine],
) -> list[dict]:
    """Flag coding-review uplift when alternate care setting is legally higher."""
    if not claim_procs:
        return []

    ambiguity = detect_care_setting_ambiguity(claim)
    if ambiguity is None:
        return []

    tier = normalize_facility_tier(
        claim.facility_tier,
        provider_type=claim.provider_type,
    )
    if not tier.is_third_tier:
        return []

    primary_totals = _best_legal_recoverable_try(
        claim,
        claim_procs,
        care_setting=ambiguity.primary_setting,
    )
    alternate_totals = _best_legal_recoverable_try(
        claim,
        claim_procs,
        care_setting=ambiguity.alternate_setting,
    )

    if alternate_totals.kind is None or primary_totals.kind is None:
        return []

    # Meaningful only when alternate unlocks DRG optional override or a higher legal ceiling.
    if alternate_totals.kind != "DRG_OVERRIDABLE" and alternate_totals.best_try <= primary_totals.best_try:
        return []

    delta = _money(alternate_totals.best_try - primary_totals.best_try)
    if delta <= 0:
        return []

    sut_section = (
        "2.2.2"
        if ambiguity.alternate_setting == "inpatient"
        else "2.2.1.B"
    )

    return [
        {
            "claim_id": claim.claim_id,
            "claim_type": claim.claim_type,
            "ambiguity_reason": ambiguity.reason,
            "actual_care_setting": ambiguity.primary_setting,
            "alternate_care_setting": ambiguity.alternate_setting,
            "actual_best_try": primary_totals.best_try,
            "alternate_best_try": alternate_totals.best_try,
            "actual_payment_method_kind": primary_totals.kind,
            "alternate_payment_method_kind": alternate_totals.kind,
            "package_total_try": alternate_totals.package_total_try,
            "itemized_total_try": alternate_totals.itemized_total_try,
            "recoverable_uplift_try": delta,
            "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
            "recommendation_kind": "coding_review",
            "review_kind": "needs_clinical_review",
            "included_in_sgk_total": False,
            "sut_section_id": sut_section,
            "rule_id": f"care_setting_review.{ambiguity.reason}",
            "rule_set_id": _RULE_SET_ID,
            "detail": (
                f"Claim {claim.claim_id} ({claim.claim_type}) is ambiguous between "
                f"{ambiguity.primary_setting} and {ambiguity.alternate_setting} "
                f"({ambiguity.detail}). Under the alternate setting the best legal "
                f"recoverable total is {alternate_totals.best_try:.2f} TRY vs "
                f"{primary_totals.best_try:.2f} TRY at the current inference — "
                f"verify episode coding before changing Y/G classification."
            ),
        }
    ]

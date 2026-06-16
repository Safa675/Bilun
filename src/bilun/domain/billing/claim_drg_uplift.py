"""DRG itemized-vs-package uplift from exact claim lines (billing report)."""

from __future__ import annotations

from typing import Any

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.session_pricing import compute_session_adjusted_itemized_total
from src.bilun.domain.prose_rules.types import SAVINGS_BASIS_SOURCED, SAVINGS_CATEGORY_SGK_UPLIFT

from .claim_strategy import (
    _aggregate_claim_kind,
    _infer_current_billing,
    _resolve_line_payment_method,
    resolve_package_total_try,
)
from .types import (
    DRG_UPLIFT_REQUIRED_INPUTS,
    DRG_UPLIFT_UNAVAILABLE_REASON,
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    DrgUpliftRecommendation,
)
from src.bilun.domain.prose_rules.claim_utils import infer_care_setting

_PROSE_RULE_SOURCE = (
    "SUT §2.2.2 itemized vs package comparison (drg_unbundling) — uplift-only subset"
)


def _money(value: float | int) -> float:
    return round(float(value), 2)


def _strategy_uplift_by_claim(recommendations: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for recommendation in recommendations:
        if recommendation.get("type") == "compliance_violation":
            continue
        if not recommendation.get("recommendation_kind"):
            continue
        savings = recommendation.get("savings_try")
        if savings is None:
            continue
        amount = float(savings)
        if amount <= 0:
            continue
        claim_id = recommendation.get("claim_id")
        if not claim_id:
            continue
        totals[str(claim_id)] = totals.get(str(claim_id), 0.0) + amount
    return totals


def _session_confirmed_by_claim(opportunities: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in opportunities:
        if not row.get("included_in_sgk_total", True):
            continue
        claim_id = row.get("claim_id")
        if not claim_id:
            continue
        totals[str(claim_id)] = totals.get(str(claim_id), 0.0) + float(
            row.get("recoverable_uplift_try") or 0.0
        )
    return totals


def _claim_allows_itemized_uplift(claim_kind: str | None, current_billing: str) -> bool:
    if current_billing != "package":
        return False
    if claim_kind == "DRG_MANDATORY":
        return False
    return claim_kind in {"DRG_OVERRIDABLE", "ITEMIZED"}


def recommend_drg_uplift_from_claims(
    ctx: PatientClaimContext,
    *,
    session_opportunities: list[dict[str, Any]] | None = None,
    strategy_recommendations: list[dict[str, Any]] | None = None,
) -> DrgUpliftRecommendation:
    """Extract legal itemized-vs-package uplift; de-dupe strategy and session totals."""
    if not ctx.procedure_lines:
        return DrgUpliftRecommendation(
            exactness_status=EXACTNESS_STATUS_MISSING_INPUTS,
            unavailable_reason=DRG_UPLIFT_UNAVAILABLE_REASON,
            required_inputs_missing=list(DRG_UPLIFT_REQUIRED_INPUTS),
            rule_source=_PROSE_RULE_SOURCE,
        )

    session_by_claim = _session_confirmed_by_claim(session_opportunities or [])
    strategy_by_claim = _strategy_uplift_by_claim(strategy_recommendations or [])
    opportunities: list[dict[str, Any]] = []

    for claim in ctx.claims:
        claim_procs = [
            line for line in ctx.procedure_lines if line.claim_id == claim.claim_id
        ]
        if not claim_procs:
            continue

        if strategy_by_claim.get(claim.claim_id, 0.0) > 0:
            continue

        care_setting = infer_care_setting(claim)
        line_results = [
            _resolve_line_payment_method(line, claim, care_setting=care_setting)
            for line in claim_procs
        ]
        claim_kind = _aggregate_claim_kind(line_results)
        current_billing = _infer_current_billing(claim_procs)
        if not _claim_allows_itemized_uplift(claim_kind, current_billing):
            continue

        mandated_methods = {
            result.payment_method
            for result in line_results
            if result.payment_method != "unknown"
        }
        if mandated_methods == {"package"}:
            continue

        itemized_raw = _money(
            sum(
                float(line.expected_payable_try)
                for line in claim_procs
                if line.procedure_category != "paket" and not line.is_package_included
            )
        )
        itemized_adj, itemized_meta = compute_session_adjusted_itemized_total(
            claim_procs,
            same_incision=True,
            cross_specialty=None,
            claim=claim,
        )
        package_total, package_methodology = resolve_package_total_try(claim, claim_procs)
        if package_total <= 0 or itemized_adj <= package_total:
            continue

        gross_uplift = _money(max(0.0, itemized_adj - package_total))
        if gross_uplift <= 0:
            continue

        session_overlap = _money(session_by_claim.get(claim.claim_id, 0.0))
        recoverable = _money(max(0.0, gross_uplift - session_overlap))
        if recoverable <= 0:
            continue

        if claim_kind not in {"DRG_OVERRIDABLE", "ITEMIZED"}:
            continue

        savings_basis = (
            "optional_override"
            if claim_kind == "DRG_OVERRIDABLE"
            else SAVINGS_BASIS_SOURCED
        )

        opportunities.append(
            {
                "type": "itemized_package_uplift",
                "claim_id": claim.claim_id,
                "payment_method_kind": claim_kind,
                "current_billing": current_billing,
                "itemized_total_try": itemized_adj,
                "itemized_raw_try": itemized_raw,
                "package_total_try": package_total,
                "package_price_methodology": package_methodology,
                "itemized_heuristic_uplift_try": 0.0,
                "gross_uplift_try": gross_uplift,
                "deduped_session_try": min(session_overlap, gross_uplift),
                "recoverable_uplift_try": recoverable,
                "included_in_sgk_total": True,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": savings_basis,
                "itemized_price_methodology": str(
                    itemized_meta.get("methodology") or "session_adjusted"
                ),
                "sut_section_id": "2.2.2",
                "detail": (
                    f"Claim {claim.claim_id}: session-adjusted itemized total "
                    f"{itemized_adj:.2f} TRY exceeds package {package_total:.2f} TRY; "
                    f"switching from package billing may increase Kurum ödemesi."
                ),
            }
        )

    return DrgUpliftRecommendation(
        opportunities=opportunities,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
    )

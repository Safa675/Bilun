"""EK-2/C package code adequacy — under-coded package coding review (§2.2)."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from src.bilun.domain.constants import _PROSE_RULES_DIR
from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.pricing.temporal import get_ek2c_price_for_date
from src.bilun.domain.prose_rules.catalog_membership import (
    get_ek2c_entry,
    normalize_procedure_code,
)
from src.bilun.domain.prose_rules.session_scope import line_billed_as_package

from .types import SAVINGS_BASIS_SOURCED, SAVINGS_CATEGORY_PACKAGE_ADEQUACY

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
    from src.bilun.domain.claims.patient_context import PatientClaimContext

_RULES_PATH = _PROSE_RULES_DIR / "drg_package_adequacy_prose.json"
_RULE_SET_ID = "drg_package_adequacy"
_OPPORTUNITY_TYPE = "under_coded_package"
_BILLING_TOLERANCE = 0.02



@lru_cache(maxsize=1)
def load_drg_package_adequacy_rules() -> dict[str, Any]:
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _rules_by_package() -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for rule in load_drg_package_adequacy_rules().get("rules", []):
        code = normalize_procedure_code(str(rule.get("package_code") or ""))
        if code:
            index[code] = rule
    return index


def _clinical_procedure_codes(claim_procs: list[ProcedureClaimLine]) -> set[str]:
    codes: set[str] = set()
    for line in claim_procs:
        if line_billed_as_package(line) or line.is_package_included:
            continue
        if float(line.billed_amount_try) <= _BILLING_TOLERANCE:
            continue
        code = normalize_procedure_code(line.procedure_code)
        if code:
            codes.add(code)
    return codes


def _billed_package_code(claim_procs: list[ProcedureClaimLine]) -> str | None:
    for line in claim_procs:
        if not line_billed_as_package(line):
            continue
        if float(line.billed_amount_try) <= _BILLING_TOLERANCE:
            continue
        code = normalize_procedure_code(line.procedure_code)
        if code:
            return code
    return None


def _footprint_codes(rule: dict[str, Any] | None) -> frozenset[str]:
    if not rule:
        return frozenset()
    return frozenset(
        normalize_procedure_code(str(code))
        for code in rule.get("required_procedure_codes", [])
        if normalize_procedure_code(str(code))
    )


def _package_price_try(
    package_code: str,
    claim: ClaimHeader,
    claim_procs: list[ProcedureClaimLine],
) -> tuple[float | None, str]:
    as_of = claim.admission_date or claim.claim_start_date
    for line in claim_procs:
        if not line_billed_as_package(line):
            continue
        if normalize_procedure_code(line.procedure_code) != package_code:
            continue
        payable = float(line.expected_payable_try)
        if payable > _BILLING_TOLERANCE:
            return _money(payable), "claim_line_payable"

    catalog = get_ek2c_price_for_date(package_code, as_of)
    if catalog is not None and catalog > _BILLING_TOLERANCE:
        return _money(catalog), "ek2c_list_price"
    entry = get_ek2c_entry(package_code, as_of_date=as_of)
    price = entry.get("price_try") if entry else None
    if price is not None and float(price) > _BILLING_TOLERANCE:
        return _money(float(price)), "ek2c_catalog_entry"
    return None, ""


def _chapter_allowed(rule: dict[str, Any], primary_icd10: str) -> bool:
    prefixes = rule.get("icd10_chapter_prefixes")
    if not prefixes:
        return True
    chapter = (primary_icd10 or "").strip().upper()[:1]
    return chapter in {str(p).strip().upper()[:1] for p in prefixes}


def detect_drg_package_adequacy_opportunities(
    claim: ClaimHeader,
    claim_procs: list[ProcedureClaimLine],
) -> list[dict[str, Any]]:
    """Flag under-coded EK-2/C packages when clinical procedures support a larger footprint.

    The claim is a package claim by its codes: a line billed as a package (``line_billed_as_package``, #294).
    """
    if not claim_procs:
        return []

    clinical = _clinical_procedure_codes(claim_procs)
    if not clinical:
        return []

    current_package = _billed_package_code(claim_procs)
    if not current_package:
        return []

    rules_by_package = _rules_by_package()
    current_rule = rules_by_package.get(current_package)
    if current_rule is None:
        return []

    current_footprint = _footprint_codes(current_rule)

    if current_footprint and not current_footprint.issubset(clinical):
        return []

    current_price, current_methodology = _package_price_try(
        current_package, claim, claim_procs
    )

    opportunities: list[dict[str, Any]] = []
    seen_candidates: set[str] = set()

    for rule in load_drg_package_adequacy_rules().get("rules", []):
        candidate_code = normalize_procedure_code(str(rule.get("package_code") or ""))
        if not candidate_code or candidate_code == current_package:
            continue
        if candidate_code in seen_candidates:
            continue
        if not _chapter_allowed(rule, claim.primary_icd10):
            continue

        candidate_footprint = _footprint_codes(rule)
        if not candidate_footprint or not candidate_footprint.issubset(clinical):
            continue
        if not candidate_footprint > current_footprint:
            continue

        group = str(rule.get("ek2c_group") or "").strip()
        if group:
            as_of = claim.admission_date or claim.claim_start_date
            entry = get_ek2c_entry(candidate_code, as_of_date=as_of)
            entry_group = str(entry.get("group") or "") if entry else ""
            if entry_group and entry_group != group:
                continue

        candidate_price, candidate_methodology = _package_price_try(
            candidate_code, claim, claim_procs
        )
        if candidate_price is None:
            catalog = get_ek2c_price_for_date(
                candidate_code, claim.admission_date or claim.claim_start_date
            )
            if catalog is not None and catalog > _BILLING_TOLERANCE:
                candidate_price = _money(catalog)
                candidate_methodology = "ek2c_list_price"

        review_delta = 0.0
        if (
            candidate_price is not None
            and current_price is not None
            and candidate_price > current_price
        ):
            review_delta = _money(candidate_price - current_price)
        if review_delta <= 0:
            continue

        message = str(rule.get("message_tr") or "").strip()
        detail = message or (
            f"Clinical procedures {sorted(clinical)} support package "
            f"{candidate_code} (footprint {sorted(candidate_footprint)}), but claim "
            f"bills lower package {current_package} "
            f"(footprint {sorted(current_footprint)}). Verify coding with ICD-10 "
            f"{claim.primary_icd10} evidence — no auto-switch."
        )

        seen_candidates.add(candidate_code)
        opportunities.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim.claim_id,
                "primary_icd10": claim.primary_icd10,
                "clinical_procedure_codes": sorted(clinical),
                "current_package_code": current_package,
                "current_package_footprint": sorted(current_footprint),
                "candidate_package_code": candidate_code,
                "candidate_package_footprint": sorted(candidate_footprint),
                "current_package_price_try": current_price,
                "candidate_package_price_try": candidate_price,
                "current_price_methodology": current_methodology or None,
                "candidate_price_methodology": candidate_methodology or None,
                "recoverable_uplift_try": review_delta,
                "savings_category": SAVINGS_CATEGORY_PACKAGE_ADEQUACY,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "recommendation_kind": "documentation_review",
                "review_kind": "needs_coding_review",
                "included_in_sgk_total": False,
                "sut_section_id": "2.2.1.B",
                "rule_id": str(rule.get("rule_id") or f"adequacy.{candidate_code}"),
                "rule_set_id": _RULE_SET_ID,
                "detail": detail,
            }
        )

    return opportunities


def check_drg_package_adequacy_for_context(
    ctx: PatientClaimContext,
) -> list[dict[str, Any]]:
    """Run §2.2 EK-2/C package adequacy on a PatientClaimContext.

    Procedure-driven check: returns immediately when ``ctx.procedure_lines`` is
    empty (no clinical footprint to evaluate). Mirrors the per-claim loop in
    ``recommend_drg_package_adequacy_from_claims`` (the orchestrator entrypoint)
    but projects the optimization-shaped opportunity dicts the detector returns
    into the violation-dict shape the unified ``analyze_claim`` core /
    Phase 2.4 adapter consume: ``rule``, ``severity``, ``material_name``,
    ``message``, ``savings_try``, ``risk_amount``, ``material_outcome``, plus
    the full opportunity preserved in ``details``.

    Severity is ``review`` (documentation review — no auto-switch) and
    ``material_outcome`` is ``documentation_review`` so the adapter classifies
    the finding as savings-bearing rather than a no-pay risk.
    """
    if not ctx.procedure_lines:
        return []

    violations: list[dict[str, Any]] = []
    for claim in ctx.claims:
        claim_procs = [
            line for line in ctx.procedure_lines if line.claim_id == claim.claim_id
        ]
        if not claim_procs:
            continue
        for opportunity in detect_drg_package_adequacy_opportunities(claim, claim_procs):
            candidate = str(opportunity.get("candidate_package_code") or "")
            material_name = f"Package {candidate} (under-coded review)"
            violations.append(
                {
                    "rule": _RULE_SET_ID,
                    "severity": "review",
                    "material_name": material_name,
                    "material_code": candidate,
                    "message": str(opportunity.get("detail") or ""),
                    "savings_try": float(opportunity.get("recoverable_uplift_try") or 0.0),
                    "risk_amount": 0.0,
                    "material_outcome": "documentation_review",
                    "claim_id": opportunity.get("claim_id"),
                    "primary_icd10": opportunity.get("primary_icd10"),
                    "sut_section": opportunity.get("sut_section_id", "2.2.1.B"),
                    "rule_id": opportunity.get("rule_id"),
                    "rule_set_id": opportunity.get("rule_set_id", _RULE_SET_ID),
                    "details": opportunity,
                }
            )

    return violations

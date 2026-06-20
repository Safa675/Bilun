"""SUT §2.2.2 missing same-session procedure add-on detector."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from src.bilun.domain.constants import _PROSE_RULES_DIR
from src.bilun.domain.pricing.temporal import get_ek2b_price_for_date
from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code
from src.bilun.domain.prose_rules.claim_utils import group_procedure_lines_by_session
from src.bilun.domain.prose_rules.session_pricing import compute_session_point_factors
from src.bilun.domain.prose_rules.session_specialty import detect_cross_specialty_session

from .types import SAVINGS_BASIS_SOURCED, SAVINGS_CATEGORY_SGK_UPLIFT

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

from src.bilun.domain.money import money_round_half_up as _money
_RULES_PATH = _PROSE_RULES_DIR / "procedure_pairing_prose.json"
_OPPORTUNITY_TYPE = "missing_add_on_procedure"
_RULE_SET_ID = "procedure_pairing_addon"
_BILLING_TOLERANCE = 0.02



@lru_cache(maxsize=1)
def load_procedure_pairing_rules() -> dict[str, Any]:
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _rules_by_trigger() -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for rule in load_procedure_pairing_rules().get("rules", []):
        for code in rule.get("trigger_procedure_codes", []):
            normalized = normalize_procedure_code(str(code))
            if not normalized:
                continue
            index.setdefault(normalized, []).append(rule)
    return index


def _line_billed(line: ProcedureClaimLine) -> float:
    return float(line.billed_amount_try)


def _procedure_name(code: str) -> str:
    try:
        from src.bilun.domain.catalog import lookup_procedure_code

        lookup = lookup_procedure_code(code)
        entry = lookup.get("entry") if lookup else None
        if entry is not None and entry.get("name"):
            return str(entry["name"])
    except Exception:
        pass
    return code


def _addon_lines_on_session(
    session_lines: list[ProcedureClaimLine],
    addon_codes: set[str],
) -> list[ProcedureClaimLine]:
    return [
        line
        for line in session_lines
        if normalize_procedure_code(line.procedure_code) in addon_codes
    ]


def _addon_billed_on_session(
    session_lines: list[ProcedureClaimLine],
    addon_codes: set[str],
) -> float:
    lines = _addon_lines_on_session(session_lines, addon_codes)
    if not lines:
        return 0.0
    return max(_line_billed(line) for line in lines)


def _session_uplift_codes(
    session_uplift_opportunities: list[dict[str, Any]] | None,
    *,
    claim_id: str,
    session_date: str,
) -> set[str]:
    if not session_uplift_opportunities:
        return set()
    codes: set[str] = set()
    for row in session_uplift_opportunities:
        if row.get("claim_id") != claim_id:
            continue
        if str(row.get("session_date") or "") != session_date:
            continue
        code = normalize_procedure_code(str(row.get("procedure_code") or ""))
        if code:
            codes.add(code)
    return codes


def _resolve_addon_factor(
    *,
    trigger_code: str,
    addon_code: str,
    session_lines: list[ProcedureClaimLine],
    claim: ClaimHeader,
    rule: dict[str, Any],
) -> float:
    """Match §2.2.2.B / §2.2.2.A(5) session point factors for the add-on code."""
    same_incision = bool(rule.get("same_incision", True))
    billable = [
        line
        for line in session_lines
        if line.procedure_category != "paket"
        and not line.is_package_included
        and _line_billed(line) > 0
    ]
    codes = list(
        dict.fromkeys(
            [normalize_procedure_code(line.procedure_code) for line in billable]
            + [trigger_code, addon_code]
        )
    )
    cross_specialty = detect_cross_specialty_session(billable, claim)
    session = compute_session_point_factors(
        codes,
        same_incision=same_incision,
        cross_specialty=cross_specialty,
    )
    factors = {
        normalize_procedure_code(f.procedure_code): f for f in session.factors
    }
    addon_factor = factors.get(addon_code)
    if addon_factor is not None and not addon_factor.is_primary:
        return float(addon_factor.point_factor)
    return float(rule.get("addon_factor") or 0.0)


def detect_missing_procedure_addon_opportunities(
    claim: ClaimHeader,
    claim_procs: list[ProcedureClaimLine],
    *,
    session_uplift_opportunities: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Flag expected add-on procedures missing from a billed trigger session."""
    if not claim_procs:
        return []

    rules_by_trigger = _rules_by_trigger()
    if not rules_by_trigger:
        return []

    opportunities: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for session_date, session_lines in group_procedure_lines_by_session(claim_procs).items():
        session_date_str = str(session_date)
        uplift_codes = _session_uplift_codes(
            session_uplift_opportunities,
            claim_id=claim.claim_id,
            session_date=session_date_str,
        )

        triggers = [
            line
            for line in session_lines
            if line.procedure_category != "paket"
            and not line.is_package_included
            and _line_billed(line) > 0
            and normalize_procedure_code(line.procedure_code) in rules_by_trigger
        ]
        if not triggers:
            continue

        for trigger_line in triggers:
            trigger_code = normalize_procedure_code(trigger_line.procedure_code)
            trigger_billed = _line_billed(trigger_line)
            for rule in rules_by_trigger.get(trigger_code, []):
                addon_codes = {
                    normalize_procedure_code(str(code))
                    for code in rule.get("expected_addon_procedure_codes", [])
                    if normalize_procedure_code(str(code))
                }
                if not addon_codes:
                    continue

                for addon_code in sorted(addon_codes):
                    dedupe_key = (claim.claim_id, session_date_str, addon_code)
                    if dedupe_key in seen:
                        continue

                    if addon_code in uplift_codes:
                        continue

                    addon_lines = _addon_lines_on_session(session_lines, {addon_code})
                    if addon_lines:
                        continue

                    actual_billed = _addon_billed_on_session(session_lines, {addon_code})
                    if actual_billed > _BILLING_TOLERANCE:
                        continue

                    factor = _resolve_addon_factor(
                        trigger_code=trigger_code,
                        addon_code=addon_code,
                        session_lines=session_lines,
                        claim=claim,
                        rule=rule,
                    )
                    if factor <= 0:
                        continue

                    as_of = trigger_line.procedure_date or claim.claim_start_date
                    reference_ek2b = get_ek2b_price_for_date(addon_code, as_of)
                    # B-H1: the recoverable uplift must be priced off the
                    # ADDON's own EK-2/B list price (the procedure that is
                    # actually missing from the bill), not the trigger's
                    # billed amount. The trigger and addon usually have very
                    # different list prices; using the trigger's billed
                    # amount mis-prices the SGK-uplift headline by their
                    # ratio. Fall back to trigger_billed only when the addon
                    # list price is unavailable.
                    price_basis = (
                        reference_ek2b
                        if reference_ek2b is not None
                        else trigger_billed
                    )
                    recoverable = _money(price_basis * factor)
                    if recoverable <= _BILLING_TOLERANCE:
                        continue

                    seen.add(dedupe_key)
                    sut_section = str(rule.get("sut_section") or "2.2.2.A.(5)")
                    rule_id = str(rule.get("rule_id") or "procedure_pairing_addon")
                    message = str(rule.get("message_tr") or "").strip()
                    detail = message or (
                        f"Trigger {trigger_code} billed {trigger_billed:.2f} TRY on "
                        f"{session_date_str}; expected add-on {addon_code} at "
                        f"{factor:.0%} of its list price is missing."
                    )

                    opportunities.append(
                        {
                            "type": _OPPORTUNITY_TYPE,
                            "claim_id": claim.claim_id,
                            "trigger_procedure_line_id": trigger_line.procedure_line_id,
                            "trigger_procedure_code": trigger_code,
                            "trigger_procedure_name": trigger_line.procedure_name
                            or _procedure_name(trigger_code),
                            "expected_addon_procedure_code": addon_code,
                            "expected_addon_procedure_name": _procedure_name(addon_code),
                            "session_date": session_date_str,
                            "addon_factor": factor,
                            "trigger_billed_try": _money(trigger_billed),
                            "list_price_try": _money(reference_ek2b)
                            if reference_ek2b is not None
                            else None,
                            "actual_billed_try": _money(actual_billed),
                            "recoverable_uplift_try": recoverable,
                            "price_methodology": (
                                "addon_list_price_x_session_factor"
                                if reference_ek2b is not None
                                else "primary_billed_x_session_factor_fallback"
                            ),
                            "same_incision": bool(rule.get("same_incision", True)),
                            "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                            "savings_basis": SAVINGS_BASIS_SOURCED,
                            "included_in_sgk_total": True,
                            "sut_section_id": sut_section,
                            "rule_id": rule_id,
                            "rule_set_id": _RULE_SET_ID,
                            "detail": detail,
                        }
                    )

    return opportunities

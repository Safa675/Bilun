"""SUT §2.2.2.B same-session multi-procedure point factors."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from ..constants import _PROSE_RULES_DIR
from ..money import money_round_half_up as _money
from .catalog_membership import (
    get_ek2c_entry,
    normalize_procedure_code,
    procedure_annex_membership,
)
from .claim_utils import group_procedure_lines_by_session
from .session_specialty import detect_cross_specialty_session
from .types import ProseRuleTrace, SessionPricingResult, SessionProcedureFactor

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_RULE_SET_ID = "session_pricing_2_2_2_B"
_RULES_PATH = _PROSE_RULES_DIR / "session_pricing_2_2_2_B.json"
_ITEMIZED_RULE_ID = "2.2.2.A.(5)"


@lru_cache(maxsize=1)
def _load_session_rules() -> dict:
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_session_pricing_rules() -> list[dict[str, Any]]:
    """Load the 4 §2.2.2.B rules from ``session_pricing_2_2_2_B.json`` (cached).

    The JSON is the SINGLE SOURCE OF TRUTH for the factor values applied by
    ``compute_session_point_factors``. Returns the list of rule dicts under the
    top-level ``rules`` key. Returns an empty list if the file is absent or
    malformed so callers can fall back to the original hardcoded literals.
    """
    try:
        payload = _load_session_rules()
    except (OSError, ValueError):
        return []
    rules = payload.get("rules") if isinstance(payload, dict) else None
    return list(rules) if isinstance(rules, list) else []


# Original hardcoded factor values — used ONLY as a backward-compat fallback
# when the JSON is missing, fails to load, or no rule matches. Mirrors the
# pre-refactor literals so behaviour is identical when the JSON is absent.
_FALLBACK_OTHER_FACTOR_SAME_INCISION = 0.25
_FALLBACK_OTHER_FACTOR_DIFFERENT_INCISION = 0.5
_FALLBACK_EK2B_FACTOR_SAME_INCISION = 0.3
_FALLBACK_EK2B_FACTOR_DIFFERENT_INCISION = 0.5


def _match_session_pricing_rule(
    *,
    same_incision: bool,
    all_in_ek2c: bool,
    mixed_ek2c_ek2b: bool,
) -> dict[str, Any] | None:
    """Find the JSON rule whose condition matches the computed flags.

    Match precedence mirrors the existing if/elif order in
    ``compute_session_point_factors``: the ``mixed_ek2c_ek2b`` rules
    (``.c``/``.ç``) are checked before the ``all_in_ek2c`` rules
    (``.a``/``.b``) — even though the JSON lists them in ``.a/.b/.c/.ç``
    order. Returns the matched rule dict, or ``None`` if no rule matches
    (caller then falls back to the hardcoded literals).
    """
    rules = load_session_pricing_rules()
    # First pass: mixed rules (.c/.ç) take precedence. Second pass:
    # all_in_ek2c rules (.a/.b). Order-independent of the on-disk listing.
    if mixed_ek2c_ek2b:
        for rule in rules:
            condition = rule.get("condition") or {}
            if condition.get("mixed_ek2c_ek2b") and bool(
                condition.get("same_incision")
            ) == same_incision:
                return rule
    if all_in_ek2c:
        for rule in rules:
            condition = rule.get("condition") or {}
            if condition.get("all_in_ek2c") and bool(
                condition.get("same_incision")
            ) == same_incision:
                return rule
    return None


def _factor_with_uplift(base: float, cross_specialty: bool) -> float:
    """Apply the +0.25 cross-specialty uplift (capped at 1.0).

    ``base`` is sourced from the matched JSON rule's ``action``. Replaces the
    inline ``min(1.0, base + 0.25)`` pattern.
    """
    if cross_specialty:
        return min(1.0, base + 0.25)
    return base


def _procedure_point_score(code: str) -> float:
    """EK-2/C puan from catalog; EK-2/B-only via lookup; fallback for unknown codes."""
    normalized = normalize_procedure_code(code)
    if not normalized:
        return 0.0

    ek2c_entry = get_ek2c_entry(normalized)
    if ek2c_entry is not None and ek2c_entry.get("puan") is not None:
        return float(ek2c_entry["puan"])

    try:
        from ..catalog import lookup_procedure_code

        lookup = lookup_procedure_code(normalized)
        entry = lookup.get("entry") if lookup else None
        if entry is not None and entry.get("puan") is not None:
            return float(entry["puan"])
    except Exception:
        pass

    _, in_ek2c = procedure_annex_membership(normalized)
    return 2.0 if in_ek2c else 1.0


def _primary_index_by_points(codes: list[str]) -> int:
    """Index of highest EK puan procedure; ties → first occurrence (SUT §2.2.2.B)."""
    best_idx = 0
    best_points = -1.0
    for idx, code in enumerate(codes):
        points = _procedure_point_score(code)
        if points > best_points:
            best_points = points
            best_idx = idx
    return best_idx


def _itemized_secondary_factor(*, same_incision: bool, cross_specialty: bool) -> float:
    """§2.2.2.A(5) secondary procedure percentage (30% / 50%; +25pp if cross-specialty)."""
    base = 0.30 if same_incision else 0.50
    if cross_specialty:
        return min(1.0, base + 0.25)
    return base


def _build_itemized_session_factors(
    normalized: list[str],
    *,
    same_incision: bool,
    cross_specialty: bool,
    primary_idx: int,
    rule_id: str = _ITEMIZED_RULE_ID,
    detail_prefix: str = "§2.2.2.A(5) itemized session",
) -> SessionPricingResult:
    secondary = _itemized_secondary_factor(
        same_incision=same_incision, cross_specialty=cross_specialty
    )
    factors: list[SessionProcedureFactor] = []
    for idx, code in enumerate(normalized):
        is_primary = idx == primary_idx
        factor = 1.0 if is_primary else secondary
        factors.append(
            SessionProcedureFactor(
                procedure_code=code,
                point_factor=factor,
                is_primary=is_primary,
                trace=ProseRuleTrace(
                    rule_id=rule_id,
                    sut_section=rule_id,
                    rule_set_id=_RULE_SET_ID,
                    detail=(
                        f"{detail_prefix}: highest-point procedure at 100%; "
                        f"others at {factor:.0%}."
                        + (" Cross-specialty +25pp applied." if cross_specialty else "")
                    ),
                ),
            )
        )
    return SessionPricingResult(
        factors=tuple(factors),
        rule_id=rule_id,
        sut_section=rule_id,
        metadata={"cross_specialty": cross_specialty},
    )


def compute_session_point_factors(
    procedure_codes: list[str],
    *,
    same_incision: bool,
    cross_specialty: bool = False,
) -> SessionPricingResult:
    """Apply §2.2.2.B / §2.2.2.A(5) point factors for procedures in the same session."""
    normalized = [normalize_procedure_code(code) for code in procedure_codes if code]
    normalized = [code for code in normalized if code]
    if not normalized:
        return SessionPricingResult(factors=(), rule_id="", sut_section="")

    memberships = [procedure_annex_membership(code) for code in normalized]
    all_in_ek2c = all(in_ek2c for _, in_ek2c in memberships)
    any_in_ek2c = any(in_ek2c for _, in_ek2c in memberships)
    any_ek2b_only = any(in_ek2b and not in_ek2c for in_ek2b, in_ek2c in memberships)
    mixed = any_in_ek2c and any_ek2b_only

    primary_idx = _primary_index_by_points(normalized)
    _, primary_in_ek2c = memberships[primary_idx]

    if len(normalized) == 1:
        code = normalized[0]
        return SessionPricingResult(
            factors=(
                SessionProcedureFactor(
                    procedure_code=code,
                    point_factor=1.0,
                    is_primary=True,
                    trace=ProseRuleTrace(
                        rule_id="single_procedure",
                        sut_section="2.2.2.B",
                        rule_set_id=_RULE_SET_ID,
                        detail="Single procedure session — full points.",
                    ),
                ),
            ),
            rule_id="single_procedure",
            sut_section="2.2.2.B",
        )

    if mixed and not primary_in_ek2c:
        return _build_itemized_session_factors(
            normalized,
            same_incision=same_incision,
            cross_specialty=cross_specialty,
            primary_idx=primary_idx,
            detail_prefix="Mixed session — EK-2/B highest puan; fallback",
        )

    if mixed:
        matched_rule = _match_session_pricing_rule(
            same_incision=same_incision,
            all_in_ek2c=all_in_ek2c,
            mixed_ek2c_ek2b=True,
        )
        if matched_rule is not None:
            rule_id = matched_rule.get("rule_id", "2.2.2.B.c" if same_incision else "2.2.2.B.ç")
            action = matched_rule.get("action") or {}
            ek2b_factor = float(action.get("ek2b_procedure_factor", _FALLBACK_EK2B_FACTOR_SAME_INCISION if same_incision else _FALLBACK_EK2B_FACTOR_DIFFERENT_INCISION))
        else:
            rule_id = "2.2.2.B.c" if same_incision else "2.2.2.B.ç"
            ek2b_factor = _FALLBACK_EK2B_FACTOR_SAME_INCISION if same_incision else _FALLBACK_EK2B_FACTOR_DIFFERENT_INCISION
        ek2b_factor = _factor_with_uplift(ek2b_factor, cross_specialty)
        factors: list[SessionProcedureFactor] = []
        for idx, code in enumerate(normalized):
            _, in_ek2c = memberships[idx]
            if in_ek2c:
                factor = 1.0
            else:
                factor = ek2b_factor
            factors.append(
                SessionProcedureFactor(
                    procedure_code=code,
                    point_factor=factor,
                    is_primary=idx == primary_idx,
                    trace=ProseRuleTrace(
                        rule_id=rule_id,
                        sut_section=rule_id,
                        rule_set_id=_RULE_SET_ID,
                        detail=(
                            f"Mixed EK-2/C + EK-2/B session: EK-2/C at 100%, "
                            f"EK-2/B at {factor:.0%}."
                        ),
                    ),
                )
            )
        return SessionPricingResult(
            factors=tuple(factors),
            rule_id=rule_id,
            sut_section=rule_id,
            metadata={"mixed_ek2c_ek2b": True, "cross_specialty": cross_specialty},
        )

    if all_in_ek2c:
        matched_rule = _match_session_pricing_rule(
            same_incision=same_incision,
            all_in_ek2c=all_in_ek2c,
            mixed_ek2c_ek2b=False,
        )
        if matched_rule is not None:
            rule_id = matched_rule.get("rule_id", "2.2.2.B.a" if same_incision else "2.2.2.B.b")
            action = matched_rule.get("action") or {}
            other_factor = float(action.get("other_procedure_factor", _FALLBACK_OTHER_FACTOR_SAME_INCISION if same_incision else _FALLBACK_OTHER_FACTOR_DIFFERENT_INCISION))
        else:
            rule_id = "2.2.2.B.a" if same_incision else "2.2.2.B.b"
            other_factor = _FALLBACK_OTHER_FACTOR_SAME_INCISION if same_incision else _FALLBACK_OTHER_FACTOR_DIFFERENT_INCISION
        other_factor = _factor_with_uplift(other_factor, cross_specialty)
        factors = []
        for idx, code in enumerate(normalized):
            is_primary = idx == primary_idx
            factors.append(
                SessionProcedureFactor(
                    procedure_code=code,
                    point_factor=1.0 if is_primary else other_factor,
                    is_primary=is_primary,
                    trace=ProseRuleTrace(
                        rule_id=rule_id,
                        sut_section=rule_id,
                        rule_set_id=_RULE_SET_ID,
                        detail=(
                            "Highest-point procedure at 100%; others at "
                            f"{other_factor:.0%}."
                        ),
                    ),
                )
            )
        return SessionPricingResult(
            factors=tuple(factors),
            rule_id=rule_id,
            sut_section=rule_id,
            metadata={"cross_specialty": cross_specialty},
        )

    return _build_itemized_session_factors(
        normalized,
        same_incision=same_incision,
        cross_specialty=cross_specialty,
        primary_idx=primary_idx,
        detail_prefix="EK-2/B-only multi-procedure session",
    )



def line_gazette_list_billed_try(line: ProcedureClaimLine) -> float:
    """Gazette list-line amount (unit × qty) used for §2.2.2 session factor math."""
    qty = max(int(line.quantity), 1)
    unit = float(line.unit_price_try)
    if unit > 0:
        return _money(unit * qty)

    billed = float(line.billed_amount_try)
    if billed > 0:
        return billed

    normalized = normalize_procedure_code(line.procedure_code)
    if not normalized:
        return 0.0

    try:
        from ..catalog import lookup_procedure_code

        lookup = lookup_procedure_code(normalized)
        entry = lookup.get("entry") if lookup else None
        if entry is not None:
            price = float(entry.get("price_try") or 0)
            if price > 0:
                return _money(price * qty)
    except Exception:
        pass

    return 0.0


def expected_session_billed_try(
    line: ProcedureClaimLine,
    *,
    point_factor: float,
) -> float:
    """Expected billed TRY for a line at its §2.2.2 session point factor (list × factor)."""
    return _money(line_gazette_list_billed_try(line) * point_factor)


def _line_itemized_payable(line: ProcedureClaimLine) -> float:
    payable = float(line.expected_payable_try)
    if payable > 0:
        return payable
    return float(line.billed_amount_try)


def _session_adjusted_line_payable(
    line: ProcedureClaimLine,
    *,
    point_factor: float,
    apply_blood_fraction: bool,
) -> float:
    # Payables already contain the whole-line quantity. Each procedure's
    # percentage applies to its own amount, not the primary procedure's price.
    base = _line_itemized_payable(line)
    amount = base * point_factor

    if apply_blood_fraction:
        fraction = blood_component_billable_fraction(line.procedure_code)
        if fraction is not None:
            amount = min(amount, base * fraction)
    return amount


def compute_session_adjusted_itemized_total(
    lines: list[ProcedureClaimLine],
    *,
    same_incision: bool = True,
    cross_specialty: bool | None = None,
    claim: ClaimHeader | None = None,
    apply_blood_fraction: bool = True,
) -> tuple[float, dict[str, Any]]:
    """Sum itemized payables with §2.2.2.B / §2.2.2.A(5) session point factors applied.

    When ``cross_specialty`` is ``None``, each session auto-detects different
    specialties from line ``procedure_specialty_code`` and EK-2/C (or EK-2/B) ``group``.
    """
    total = 0.0
    sessions_with_adjustment = 0
    lines_in_scope = 0
    sessions_cross_specialty = 0

    for _session_date, session_lines in group_procedure_lines_by_session(lines).items():
        billable = [
            line
            for line in session_lines
            if line.procedure_category != "paket"
            and not line.is_package_included
            and _line_itemized_payable(line) > 0
        ]
        if not billable:
            continue

        lines_in_scope += len(billable)
        if len(billable) == 1:
            line = billable[0]
            total += _session_adjusted_line_payable(
                line,
                point_factor=1.0,
                apply_blood_fraction=apply_blood_fraction,
            )
            continue

        codes = [line.procedure_code for line in billable]
        session_cross = (
            detect_cross_specialty_session(billable, claim)
            if cross_specialty is None
            else cross_specialty
        )
        if session_cross:
            sessions_cross_specialty += 1
        session = compute_session_point_factors(
            codes,
            same_incision=same_incision,
            cross_specialty=session_cross,
        )
        if session.rule_id != "single_procedure":
            sessions_with_adjustment += 1

        # Factors preserve input occurrence order, excluding empty normalized
        # codes. A code-keyed map would discard the primary factor when two
        # distinct lines normalize to the same code.
        factors = iter(session.factors)
        for line in billable:
            factor = next(factors) if normalize_procedure_code(line.procedure_code) else None
            point_factor = factor.point_factor if factor is not None else 1.0
            total += _session_adjusted_line_payable(
                line,
                point_factor=point_factor,
                apply_blood_fraction=apply_blood_fraction,
            )

    methodology = (
        "session_adjusted"
        if sessions_with_adjustment > 0
        else "claim_lines"
    )
    return _money(total), {
        "methodology": methodology,
        "sessions_with_adjustment": sessions_with_adjustment,
        "sessions_cross_specialty": sessions_cross_specialty,
        "itemized_lines": lines_in_scope,
        "same_incision": same_incision,
        "cross_specialty": cross_specialty,
        "cross_specialty_mode": "auto" if cross_specialty is None else "fixed",
    }


def blood_component_billable_fraction(procedure_code: str) -> float | None:
    """Return separately billable point fraction for special blood component codes.

    Reads the authoritative per-code ``fractions`` map first
    (``special_codes.blood_component_partial_bill.fractions`` — the SUT §4.6
    EK-2/C partial-billing tiers), then falls back to the legacy ``codes[]`` +
    ``billable_point_fraction`` pair so configs without the map keep the old
    behaviour.
    """
    normalized = normalize_procedure_code(procedure_code)
    if not normalized:
        return None
    rules = _load_session_rules()
    special = rules.get("special_codes", {}).get("blood_component_partial_bill", {})
    fractions = special.get("fractions") or {}
    for raw_code, fraction in fractions.items():
        if normalize_procedure_code(raw_code) == normalized:
            return float(fraction)
    if normalized in {normalize_procedure_code(c) for c in special.get("codes", [])}:
        return float(special.get("billable_point_fraction", 0.36))
    return None

"""SUT §2.2.2.B same-session multi-procedure point factors."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from datetime import date
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
from .session_scope import (
    is_session_operation_code,
    line_billed_as_package,
    session_operation_lines,
)
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


def _package_secondary_factor(*, same_incision: bool, cross_specialty: bool) -> tuple[str, float]:
    """Rule id and factor of a tanıya dayalı işlem after the session's highest one.

    §2.2.2.B(3)(a)/(b) (C000670 / C000671): 25 % / 50 % of its own package puan,
    +25 points across specialties (C000674).
    """
    rule_id = "2.2.2.B.a" if same_incision else "2.2.2.B.b"
    factor = (
        _FALLBACK_OTHER_FACTOR_SAME_INCISION
        if same_incision
        else _FALLBACK_OTHER_FACTOR_DIFFERENT_INCISION
    )
    matched_rule = _match_session_pricing_rule(
        same_incision=same_incision, all_in_ek2c=True, mixed_ek2c_ek2b=False,
    )
    if matched_rule is not None:
        rule_id = matched_rule.get("rule_id", rule_id)
        factor = float((matched_rule.get("action") or {}).get("other_procedure_factor", factor))
    return rule_id, _factor_with_uplift(factor, cross_specialty)


def _ek2c_puan(normalized: str, *, as_of_date: date | str | None) -> float | None:
    ek2c_entry = get_ek2c_entry(normalized, as_of_date=as_of_date)
    if ek2c_entry is not None and ek2c_entry.get("puan") is not None:
        return float(ek2c_entry["puan"])
    return None


def _ek2b_puan(normalized: str, *, as_of_date: date | str | None) -> float | None:
    try:
        from ..catalog import lookup_procedure_code

        lookup = lookup_procedure_code(normalized, visit_date=as_of_date)
        entry = (
            lookup.get("entry")
            if lookup and lookup.get("match_type") in {"exact", "package_prefix"}
            else None
        )
        # The general catalog may return its oldest row before history starts.
        # Session ranking must not treat that future amendment as dated evidence.
        effective = str(entry.get("effective_date") or "") if entry else ""
        effective_on_date = as_of_date is None or not effective or effective <= str(as_of_date)
        if effective_on_date and entry is not None and entry.get("puan") is not None:
            return float(entry["puan"])
    except Exception:
        pass
    return None


def _procedure_point_score(
    code: str,
    *,
    as_of_date: date | str | None = None,
    billed_as_package: bool | None = None,
) -> float:
    """EK-2/C puan from catalog; EK-2/B-only via lookup; fallback for unknown codes.

    A line billed hizmet başı (``billed_as_package`` False) ranks by its EK-2/B
    puan first, since that is the işlem puanı §2.2.2.A(5) compares.
    """
    normalized = normalize_procedure_code(code)
    if not normalized:
        return 0.0

    lookups = (_ek2c_puan, _ek2b_puan) if billed_as_package is not False else (_ek2b_puan, _ek2c_puan)
    for lookup in lookups:
        points = lookup(normalized, as_of_date=as_of_date)
        if points is not None:
            return points

    _, in_ek2c = procedure_annex_membership(normalized, as_of_date=as_of_date)
    return 2.0 if in_ek2c else 1.0


def _primary_index_by_points(
    codes: list[str],
    *,
    as_of_date: date | str | None = None,
    billed_as_package: list[bool] | None = None,
) -> int:
    """Index of highest EK puan procedure; ties → first occurrence (SUT §2.2.2.B)."""
    best_idx = 0
    best_points = -1.0
    for idx, code in enumerate(codes):
        points = _procedure_point_score(
            code,
            as_of_date=as_of_date,
            billed_as_package=None if billed_as_package is None else billed_as_package[idx],
        )
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
    as_of_date: date | str | None = None,
    billed_as_package: Sequence[bool] | None = None,
) -> SessionPricingResult:
    """Apply §2.2.2.B / §2.2.2.A(5) point factors for procedures in the same session.

    ``billed_as_package`` (one flag per code) prices each line by how it was
    billed: a package line as EK-2/C (§2.2.2.B(3)(a)/(b), 25 % / 50 %), a hizmet
    başı line as EK-2/B (§2.2.2.A(5), 30 % / 50 %), both kinds together by
    §2.2.2.B(3)(c)/(ç). Most §6 codes are in both lists, so catalog membership
    alone, used when the flags are omitted, cannot tell the two apart.
    """
    if billed_as_package is not None and len(billed_as_package) != len(procedure_codes):
        raise ValueError("billed_as_package needs one flag per procedure code")
    flags = list(billed_as_package) if billed_as_package is not None else [None] * len(procedure_codes)
    kept = [
        (normalize_procedure_code(code), flag)
        for code, flag in zip(procedure_codes, flags, strict=True)
        if code
    ]
    kept = [(code, flag) for code, flag in kept if code]
    normalized = [code for code, _ in kept]
    if not normalized:
        return SessionPricingResult(factors=(), rule_id="", sut_section="")
    package_flags = None if billed_as_package is None else [bool(flag) for _, flag in kept]

    memberships = [procedure_annex_membership(code, as_of_date=as_of_date) for code in normalized]
    if as_of_date is not None and not any(in_b or in_c for in_b, in_c in memberships):
        # No annex evidence at the requested date. Preserve the line amounts;
        # arbitrary unknown-code ordering cannot establish a payable discount.
        return SessionPricingResult(
            factors=tuple(
                SessionProcedureFactor(
                    procedure_code=code, point_factor=1.0, is_primary=idx == 0,
                    trace=ProseRuleTrace(
                        rule_id="session_tariff_unavailable", sut_section="",
                        rule_set_id=_RULE_SET_ID,
                        detail="No historical annex membership available for this session date.",
                    ),
                ) for idx, code in enumerate(normalized)
            ),
            rule_id="session_tariff_unavailable", sut_section="",
            metadata={"historical_catalog_unavailable": True, "as_of_date": str(as_of_date)},
        )
    if package_flags is not None:
        # Price by billing method: package lines as EK-2/C, hizmet başı as EK-2/B.
        memberships = [(not flag, flag) for flag in package_flags]
    all_in_ek2c = all(in_ek2c for _, in_ek2c in memberships)
    any_in_ek2c = any(in_ek2c for _, in_ek2c in memberships)
    any_ek2b_only = any(in_ek2b and not in_ek2c for in_ek2b, in_ek2c in memberships)
    mixed = any_in_ek2c and any_ek2b_only

    primary_idx = _primary_index_by_points(
        normalized, as_of_date=as_of_date, billed_as_package=package_flags,
    )
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
        # C000672 / C000673: a procedure outside EK-2/C takes 30 % / 50 % of its
        # EK-2/B puan. The tanıya dayalı işlemler among themselves keep
        # §2.2.2.B(3)(a)/(b) (C000670 / C000671): the highest in full, the others
        # at 25 % / 50 %. C000674 adds 25 points to each percentage.
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
        package_rule_id, package_factor = _package_secondary_factor(
            same_incision=same_incision, cross_specialty=cross_specialty,
        )
        factors: list[SessionProcedureFactor] = []
        for idx, code in enumerate(normalized):
            _, in_ek2c = memberships[idx]
            if idx == primary_idx:
                factor, line_rule, detail = 1.0, rule_id, "highest-point EK-2/C procedure at 100%"
            elif in_ek2c:
                factor, line_rule = package_factor, package_rule_id
                detail = f"another EK-2/C procedure at {package_factor:.0%}"
            else:
                factor, line_rule = ek2b_factor, rule_id
                detail = f"EK-2/B procedure at {ek2b_factor:.0%}"
            factors.append(
                SessionProcedureFactor(
                    procedure_code=code,
                    point_factor=factor,
                    is_primary=idx == primary_idx,
                    trace=ProseRuleTrace(
                        rule_id=line_rule,
                        sut_section=line_rule,
                        rule_set_id=_RULE_SET_ID,
                        detail=f"Mixed EK-2/C + EK-2/B session: {detail}.",
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
        rule_id, other_factor = _package_secondary_factor(
            same_incision=same_incision, cross_specialty=cross_specialty,
        )
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



def line_gazette_list_billed_try(line: ProcedureClaimLine) -> float | None:
    """Gazette list-line amount (unit × qty) used for §2.2.2 session factor math.

    The bill's unit price when it states one; otherwise the catalog list price
    on the procedure date: EK-2/C for a line billed as a package, EK-2/B for the
    rest. Never the billed amount, which is what the factor checks: a secondary
    correctly billed at 30 % would read as its own 100 %. ``None`` when neither
    is known, so the line cannot be assessed.
    """
    qty = max(int(line.quantity), 1)
    unit = float(line.unit_price_try)
    if unit > 0:
        return _money(unit * qty)

    normalized = normalize_procedure_code(line.procedure_code)
    if not normalized:
        return None

    if line_billed_as_package(line):
        entry = get_ek2c_entry(line.procedure_code, as_of_date=line.procedure_date) or {}
        price = float(entry.get("price_try") or 0)
        return _money(price * qty) if price > 0 else None

    try:
        from ..catalog import lookup_procedure_code

        lookup = lookup_procedure_code(normalized, visit_date=line.procedure_date)
        entry = (
            lookup.get("entry")
            if lookup and lookup.get("match_type") in {"exact", "package_prefix"}
            else None
        )
        effective = str(entry.get("effective_date") or "") if entry else ""
        if entry is not None and (not effective or effective <= str(line.procedure_date)):
            price = float(entry.get("price_try") or 0)
            if price > 0:
                return _money(price * qty)
    except Exception:
        pass

    return None


def expected_session_billed_try(
    line: ProcedureClaimLine,
    *,
    point_factor: float,
) -> float | None:
    """Expected billed TRY at the line's §2.2.2 session point factor (list × factor).

    ``None`` when the line's list price is unknown.
    """
    listed = line_gazette_list_billed_try(line)
    return None if listed is None else _money(listed * point_factor)


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

    Factors apply to the operations of each session only (``session_scope``).
    When ``cross_specialty`` is ``None``, each session auto-detects different
    specialties from the lines' ``procedure_specialty_code`` (branch codes).
    """
    # Hypothetical itemized alternatives omit package rows and must retain
    # full itemized blood prices. Candidate flags/codes are not billed packages.
    package_scopes = billed_package_scopes(lines)
    total = 0.0
    sessions_with_adjustment = 0
    lines_in_scope = 0
    sessions_cross_specialty = 0

    for session_date, session_lines in group_procedure_lines_by_session(lines).items():
        billable = [
            line
            for line in session_lines
            if not line_billed_as_package(line)
            and not line.is_package_included
            and _line_itemized_payable(line) > 0
        ]
        if not billable:
            continue

        lines_in_scope += len(billable)
        # Only operations form a session (#261); beds, visits, labs, anaesthesia
        # and the other lines keep their own payable at 100 %.
        operations = session_operation_lines(billable)
        factors: Iterator[SessionProcedureFactor] | None = None
        if len(operations) >= 2:
            session_cross = (
                detect_cross_specialty_session(operations, claim)
                if cross_specialty is None
                else cross_specialty
            )
            if session_cross:
                sessions_cross_specialty += 1
            session = compute_session_point_factors(
                [line.procedure_code for line in operations],
                same_incision=same_incision,
                cross_specialty=session_cross,
                as_of_date=session_date,
                billed_as_package=[line_billed_as_package(line) for line in operations],
            )
            if any(f.point_factor != 1.0 for f in session.factors):
                sessions_with_adjustment += 1
            factors = iter(session.factors)

        # Factors preserve the operations' occurrence order (their codes are
        # never empty). A code-keyed map would discard the primary factor when
        # two distinct lines normalize to the same code.
        for line in billable:
            point_factor = (
                next(factors).point_factor
                if factors is not None and is_session_operation_code(line.procedure_code)
                else 1.0
            )
            total += _session_adjusted_line_payable(
                line,
                point_factor=point_factor,
                apply_blood_fraction=(
                    apply_blood_fraction
                    and (line.patient_id, line.claim_id, line.episode_id) in package_scopes
                ),
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


def billed_package_scopes(
    lines: list[ProcedureClaimLine],
) -> frozenset[tuple[str, str, str]]:
    """Actual package billing in a patient/claim/episode, not a candidate code.

    §4.6(3)/(4) distinguishes itemized treatment from package treatment. Blood
    can be used on another day in the same treatment, so no same-day gate applies.
    """
    return frozenset(
        (line.patient_id, line.claim_id, line.episode_id) for line in lines
        if line_billed_as_package(line) and float(line.billed_amount_try) > 0
    )


def blood_component_max_billable_try(
    line: ProcedureClaimLine, *, package_context: bool = False,
) -> float | None:
    """Package-only blood ceiling on the whole-line payable (billed fallback)."""
    if not package_context:
        return None
    fraction = blood_component_billable_fraction(line.procedure_code)
    if fraction is None:
        return None
    return _line_itemized_payable(line) * fraction

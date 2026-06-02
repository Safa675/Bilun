"""SUT §2.2.2.B same-session multi-procedure point factors."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from ..constants import _PROSE_RULES_DIR
from .catalog_membership import (
    get_ek2c_entry,
    normalize_procedure_code,
    procedure_annex_membership,
)
from .claim_utils import group_procedure_lines_by_session
from .types import ProseRuleTrace, SessionPricingResult, SessionProcedureFactor

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ProcedureClaimLine

_RULE_SET_ID = "session_pricing_2_2_2_B"
_RULES_PATH = _PROSE_RULES_DIR / "session_pricing_2_2_2_B.json"
_ITEMIZED_RULE_ID = "2.2.2.A.(5)"


@lru_cache(maxsize=1)
def _load_session_rules() -> dict:
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


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
        rule_id = "2.2.2.B.c" if same_incision else "2.2.2.B.ç"
        ek2b_factor = 0.3 if same_incision else 0.5
        if cross_specialty:
            ek2b_factor = min(1.0, ek2b_factor + 0.25)
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
        rule_id = "2.2.2.B.a" if same_incision else "2.2.2.B.b"
        other_factor = 0.25 if same_incision else 0.5
        if cross_specialty:
            other_factor = min(1.0, other_factor + 0.25)
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


def _money(value: float | int) -> float:
    return round(float(value), 2)


def _line_itemized_payable(line: ProcedureClaimLine) -> float:
    payable = float(line.expected_payable_try)
    if payable > 0:
        return payable
    return float(line.billed_amount_try)


def _session_adjusted_line_payable(
    line: ProcedureClaimLine,
    *,
    primary_line: ProcedureClaimLine,
    primary_payable: float,
    point_factor: float,
    primary_factor: float,
    apply_blood_fraction: bool,
) -> float:
    if line.procedure_line_id == primary_line.procedure_line_id:
        amount = primary_payable
    elif primary_factor > 0:
        amount = primary_payable * (point_factor / primary_factor)
    else:
        amount = 0.0

    if apply_blood_fraction:
        fraction = blood_component_billable_fraction(line.procedure_code)
        if fraction is not None:
            base = _line_itemized_payable(line)
            amount = min(amount, base * fraction)
    return amount


def compute_session_adjusted_itemized_total(
    lines: list[ProcedureClaimLine],
    *,
    same_incision: bool = True,
    cross_specialty: bool = False,
    apply_blood_fraction: bool = True,
) -> tuple[float, dict[str, Any]]:
    """Sum itemized payables with §2.2.2.B / §2.2.2.A(5) session point factors applied."""
    total = 0.0
    sessions_with_adjustment = 0
    lines_in_scope = 0

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
                primary_line=line,
                primary_payable=_line_itemized_payable(line),
                point_factor=1.0,
                primary_factor=1.0,
                apply_blood_fraction=apply_blood_fraction,
            )
            continue

        codes = [line.procedure_code for line in billable]
        session = compute_session_point_factors(
            codes,
            same_incision=same_incision,
            cross_specialty=cross_specialty,
        )
        if session.rule_id != "single_procedure":
            sessions_with_adjustment += 1

        factors = {
            normalize_procedure_code(f.procedure_code): f for f in session.factors
        }
        primary_line = billable[0]
        primary_factor = 1.0
        for line in billable:
            factor = factors.get(normalize_procedure_code(line.procedure_code))
            if factor is not None and factor.is_primary:
                primary_line = line
                primary_factor = factor.point_factor
                break

        primary_payable = _line_itemized_payable(primary_line)
        for line in billable:
            factor = factors.get(normalize_procedure_code(line.procedure_code))
            point_factor = factor.point_factor if factor is not None else 1.0
            total += _session_adjusted_line_payable(
                line,
                primary_line=primary_line,
                primary_payable=primary_payable,
                point_factor=point_factor,
                primary_factor=primary_factor,
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
        "itemized_lines": lines_in_scope,
        "same_incision": same_incision,
        "cross_specialty": cross_specialty,
    }


def blood_component_billable_fraction(procedure_code: str) -> float | None:
    """Return separately billable point fraction for special blood component codes."""
    normalized = normalize_procedure_code(procedure_code)
    rules = _load_session_rules()
    special = rules.get("special_codes", {}).get("blood_component_partial_bill", {})
    if normalized in {normalize_procedure_code(c) for c in special.get("codes", [])}:
        return float(special.get("billable_point_fraction", 0.36))
    return None

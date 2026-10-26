"""
src/bilun/domain/prose_rules/lab_capture_gap.py
Detect clinical lab tests that have result rows but no matching billed claim line.

Given the claim, a test whose every result row falls inside its EK-2/C package window (an işlem grubu package,
billed or mandated, on a yatarak claim) is inside the package (SUT §2.2.2.B-1(1)(ğ), (3); ``package_window_tests``,
#290) and is no gap. A row is dated by the feed's ``date`` column; an undated row is inside only when the whole stay
lies in the window.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import polars as pl

from src.bilun.domain.catalog import lookup_procedure_code
from src.bilun.domain.prose_rules.package_window_tests import package_test_window
from src.bilun.domain.sut.clause_reference import SOURCE_REHBER, non_sut_reference

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader

SAVINGS_CATEGORY_CAPTURE_GAP = "capture_gap"
SAVINGS_BASIS_SOURCED = "sourced"
_RULE_SET_ID = "lab_capture_gap"
_OPPORTUNITY_TYPE = "lab_performed_not_submitted"
_BILLING_TOLERANCE = 0.02

# Provenance (Phase 2): lab capture completeness is a review guideline
# (rehber) rule, not a SUT clause — honest non-SUT reference (empty
# clause_key). Resolved once at module load; shared by every finding.
_SOURCE_TYPE = SOURCE_REHBER
_CLAUSE_REF = non_sut_reference(
    "Lab capture completeness review", source_type=SOURCE_REHBER
).to_dict()


def _resolve_lab_list_price(code: str, service_date: Any | None = None) -> tuple[float | None, str]:
    """Return (list_price_try, price_methodology) for an exact lab SUT code."""
    lookup = lookup_procedure_code(code, visit_date=service_date)
    entry = lookup.get("entry") if lookup and lookup.get("match_type") == "exact" else None
    if entry is not None:
        price = entry.get("price_try")
        if price:
            return float(price), "ek2b_list_price"

    return None, ""


def _result_day(value: Any) -> date | None:
    """The date of a lab result row (``date`` column: a datetime, a date or an ISO text); None when absent or unreadable."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def detect_lab_capture_gaps(
    lab_df_pl: pl.DataFrame,
    procedure_claim_lines: list[Any],
    episode_id: str,
    service_date: Any | None = None,
    *,
    claim: ClaimHeader | None = None,
) -> list[dict[str, Any]]:
    """Flag clinical lab tests performed on ``episode_id`` but missing from claim lines.

    ``lab_df_pl`` is the normalized clinical lab feed (``patient_id``, ``visit_id``,
    ``test_name``, ...). Multiple result rows for the same test code on the same visit
    are deduplicated into a single performed test.

    ``procedure_claim_lines`` should be filtered to the same claim/episode. A lab is
    considered captured if any claim line with ``procedure_category == "laboratuvar``
    and the same SUT code has ``billed_amount_try > 0.02``.

    With ``claim`` (the claim of ``procedure_claim_lines``), a test whose every result
    row lies inside the claim's EK-2/C package window is inside the package (module
    docstring) and is no gap.
    """
    if lab_df_pl.is_empty() or "patient_id" not in lab_df_pl.columns:
        return []

    if "visit_id" in lab_df_pl.columns:
        scoped = lab_df_pl.filter(pl.col("visit_id") == episode_id)
    else:
        scoped = lab_df_pl

    if scoped.is_empty():
        return []

    # Collect performed lab SUT codes (deduplicated per code per visit) and the days of their results.
    performed_days: dict[str, set[date | None]] = {}
    if "test_name" in scoped.columns:
        days = scoped["date"].to_list() if "date" in scoped.columns else [None] * scoped.height
        for name, day in zip(scoped["test_name"].to_list(), days, strict=True):
            code = str(name).strip().upper()
            if code.startswith("L") and len(code) >= 4:
                performed_days.setdefault(code, set()).add(_result_day(day))
    performed_codes = set(performed_days)

    if not performed_codes:
        return []

    # Collect billed lab SUT codes for this episode.
    billed_codes: set[str] = set()
    for line in procedure_claim_lines:
        if line.procedure_category != "laboratuvar":
            continue
        if float(line.billed_amount_try or 0) <= _BILLING_TOLERANCE:
            continue
        code = str(line.procedure_code or "").strip().upper()
        if code:
            billed_codes.add(code)

    gap_codes = performed_codes - billed_codes
    window = package_test_window(claim, list(procedure_claim_lines)) if claim is not None else None
    if window is not None:
        gap_codes = {
            code
            for code in gap_codes
            if not all(window.covers(code, day) for day in performed_days[code])
        }
    if not gap_codes:
        return []

    opportunities: list[dict[str, Any]] = []
    seen: set[str] = set()
    for code in sorted(gap_codes):
        if code in seen:
            continue
        seen.add(code)
        list_price, methodology = _resolve_lab_list_price(code, service_date)
        if list_price is None or list_price <= _BILLING_TOLERANCE:
            continue

        opportunities.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": "",
                "procedure_code": code,
                "procedure_name": code,
                "service_date": str(service_date) if service_date else "",
                "source": "lab",
                "actual_billed_try": 0.0,
                "list_price_try": round(list_price, 2),
                "recoverable_gap_try": round(list_price, 2),
                "price_methodology": methodology,
                "savings_category": SAVINGS_CATEGORY_CAPTURE_GAP,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "included_in_sgk_total": False,
                "sut_section_id": "clinical lab capture completeness",
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "rule_id": "lab_performed_not_submitted",
                "rule_set_id": _RULE_SET_ID,
                "detail": (
                    f"Clinical lab feed shows {code} performed on {episode_id} "
                    f"but no matching lab claim line was submitted."
                ),
            }
        )

    return opportunities

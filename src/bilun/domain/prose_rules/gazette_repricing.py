"""Prospective gazette repricing — stale EK-2B/EK-2C price after tebliğ amendment."""

from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Literal

from src.bilun.domain.constants import _PROSE_RULES_DIR
from src.bilun.domain.pricing.temporal import (
    get_ek2b_price_for_date,
    get_ek2c_price_for_date,
    get_price_history,
)
from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code

from .types import SAVINGS_BASIS_SOURCED, SAVINGS_CATEGORY_GAZETTE_REPRICING

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_RULES_PATH = _PROSE_RULES_DIR / "gazette_repricing_prose.json"
_RULE_SET_ID = "gazette_repricing"
_OPPORTUNITY_TYPE = "stale_gazette_price"
_PRICE_TOLERANCE = 0.02
_PAYABLE_TOLERANCE = 0.05


def _money(value: float | int) -> float:
    return round(float(value), 2)


@lru_cache(maxsize=1)
def load_gazette_repricing_rules() -> dict[str, Any]:
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _parse_date(value: date | datetime | str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _catalog_for_line(line: ProcedureClaimLine) -> Literal["ek2b", "ek2c"]:
    if line.procedure_category == "paket":
        return "ek2c"
    return "ek2b"


def _history_code(line: ProcedureClaimLine) -> str:
    normalized = normalize_procedure_code(line.procedure_code)
    if line.procedure_category == "paket" and normalized and not normalized.startswith("P"):
        return f"P{normalized}"
    return normalized


def _price_for_service(
    line: ProcedureClaimLine,
    service_date: date,
) -> float | None:
    code = normalize_procedure_code(line.procedure_code)
    if not code:
        return None
    if line.procedure_category == "paket":
        return get_ek2c_price_for_date(code, service_date)
    return get_ek2b_price_for_date(code, service_date)


def _latest_increase_after_service(
    line: ProcedureClaimLine,
    service_date: date,
    max_days: int | None = None,
) -> dict[str, Any] | None:
    catalog = _catalog_for_line(line)
    code = _history_code(line)
    if not code:
        return None

    price_at_service = _price_for_service(line, service_date)
    if price_at_service is None or price_at_service <= _PRICE_TOLERANCE:
        return None

    try:
        history = get_price_history(code, catalog=catalog)
    except Exception:
        return None
    if history.is_empty():
        return None

    service_key = service_date.isoformat()
    best: dict[str, Any] | None = None

    for row in history.iter_rows(named=True):
        amendment_raw = row.get("effective_date")
        if amendment_raw is None:
            continue
        amendment_date = str(amendment_raw)[:10]
        if amendment_date <= service_key:
            continue
        if max_days is not None:
            try:
                delta = (_parse_date(amendment_date) - service_date).days
            except Exception:
                continue
            if delta > max_days or delta < 0:
                continue
        new_price = float(row.get("price_try") or 0.0)
        if new_price <= price_at_service + _PRICE_TOLERANCE:
            continue
        if best is None or amendment_date > str(best["amendment_date"]):
            best = {
                "amendment_date": amendment_date,
                "old_price_try": _money(price_at_service),
                "new_price_try": _money(new_price),
                "catalog": catalog,
            }
    return best


def _line_payable_per_unit(line: ProcedureClaimLine) -> float:
    qty = max(int(line.quantity or 1), 1)
    payable = float(line.expected_payable_try)
    if payable > _PRICE_TOLERANCE:
        return payable / qty
    billed = float(line.billed_amount_try)
    if billed > _PRICE_TOLERANCE:
        return billed / qty
    return float(line.unit_price_try)


def _rebill_permitted(rules: dict[str, Any]) -> bool:
    return bool(rules.get("rebill_permitted_default", True))


def _max_days_after_service(rules: dict[str, Any]) -> int | None:
    value = rules.get("max_days_after_service")
    if value is None:
        return None
    try:
        days = int(value)
    except (TypeError, ValueError):
        return None
    return days if days > 0 else None


def _category_excluded(line: ProcedureClaimLine, rules: dict[str, Any]) -> bool:
    excluded = {
        str(category)
        for category in rules.get("excluded_procedure_categories", [])
        if str(category).strip()
    }
    return line.procedure_category in excluded


def detect_gazette_repricing_opportunities(
    claim: ClaimHeader,
    claim_procs: list[ProcedureClaimLine],
) -> list[dict[str, Any]]:
    """Flag lines still priced at pre-amendment gazette rates after a tebliğ increase."""
    rules = load_gazette_repricing_rules()
    if not _rebill_permitted(rules):
        return []

    max_days = _max_days_after_service(rules)
    opportunities: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for line in claim_procs:
        if line.is_package_included:
            continue
        if _category_excluded(line, rules):
            continue
        if float(line.billed_amount_try) <= _PRICE_TOLERANCE:
            continue

        service_date = line.procedure_date or claim.claim_start_date
        if service_date is None:
            continue

        increase = _latest_increase_after_service(
            line, _parse_date(service_date), max_days=max_days
        )
        if increase is None:
            continue

        code = normalize_procedure_code(line.procedure_code)
        qty = max(int(line.quantity or 1), 1)
        payable_per_unit = _line_payable_per_unit(line)
        old_price = float(increase["old_price_try"])
        new_price = float(increase["new_price_try"])

        if payable_per_unit > old_price * (1 + _PAYABLE_TOLERANCE):
            continue

        recoverable = _money((new_price - old_price) * qty)
        if recoverable <= _PRICE_TOLERANCE:
            continue

        dedupe_key = (claim.claim_id, line.procedure_line_id, str(increase["amendment_date"]))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        message = str(rules.get("message_tr") or "").strip()
        detail = message or (
            f"Procedure {code} on {service_date} was priced at {old_price:.2f} TRY/unit "
            f"but tebliğ {increase['amendment_date']} raised the gazette list to "
            f"{new_price:.2f} TRY/unit. Prospective repricing review only."
        )

        opportunities.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim.claim_id,
                "procedure_line_id": line.procedure_line_id,
                "procedure_code": code,
                "procedure_name": line.procedure_name,
                "procedure_category": line.procedure_category,
                "service_date": str(service_date),
                "amendment_effective_date": increase["amendment_date"],
                "catalog": increase["catalog"],
                "quantity": qty,
                "price_at_service_try": old_price,
                "amended_list_price_try": new_price,
                "actual_payable_per_unit_try": _money(payable_per_unit),
                "recoverable_repricing_try": recoverable,
                "price_methodology": "gazette_amendment_delta_x_qty",
                "savings_category": SAVINGS_CATEGORY_GAZETTE_REPRICING,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "recommendation_kind": "prospective_repricing",
                "review_kind": "needs_billing_review",
                "included_in_sgk_total": False,
                "sut_section_id": "2.2",
                "rule_id": f"gazette_repricing.{code}",
                "rule_set_id": _RULE_SET_ID,
                "detail": detail,
            }
        )

    return opportunities

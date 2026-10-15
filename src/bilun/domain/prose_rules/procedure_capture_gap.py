"""EMR/OR performed procedure vs claim submission gap detector."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.bilun.domain.pricing.temporal import get_ek2b_price_for_date, get_ek2c_price_for_date
from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code

from .types import SAVINGS_BASIS_SOURCED, SAVINGS_CATEGORY_CAPTURE_GAP

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import (
        ClaimHeader,
        PerformedProcedureLine,
        ProcedureClaimLine,
    )

from src.bilun.domain.money import money_round_half_up as _money
_OPPORTUNITY_TYPE = "performed_not_submitted"
_RULE_SET_ID = "procedure_capture_completeness"
_BILLING_TOLERANCE = 0.02



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


def _submitted_amount_by_code_date(
    claim_procs: list[ProcedureClaimLine],
) -> dict[tuple[str, str], float]:
    """Map (service_date, procedure_code) → max billed amount on the claim.

    Itemized lines only; ``paket`` lines are matched by ``_package_billed_by_code``.
    """
    submitted: dict[tuple[str, str], float] = {}
    for line in claim_procs:
        if line.procedure_category == "paket" or line.is_package_included:
            continue
        code = normalize_procedure_code(line.procedure_code)
        if not code:
            continue
        key = (str(line.procedure_date), code)
        billed = float(line.billed_amount_try)
        submitted[key] = max(submitted.get(key, 0.0), billed)
    return submitted


def _package_billed_by_code(
    claim_procs: list[ProcedureClaimLine],
) -> dict[str, float]:
    """Map EK-2C package code → max billed amount of its ``paket`` lines (#266).

    ``normalize_procedure_code`` drops the ``P`` prefix, so a log row with
    ``P609235`` or the EK-2B ``609235`` hits the ``P609235`` package. A
    package bills its operation once per claim, so the line date is ignored.
    """
    packages: dict[str, float] = {}
    for line in claim_procs:
        if line.procedure_category != "paket":
            continue
        code = normalize_procedure_code(line.procedure_code)
        if not code:
            continue
        packages[code] = max(packages.get(code, 0.0), float(line.billed_amount_try))
    return packages


def _resolve_catalog_price(
    code: str, service_date, *, claim_has_package: bool = False
) -> tuple[float | None, str]:
    """Return (price_try, price_methodology) from EK-2B or EK-2C.

    When the claim carries the EK-2C package for ``code``, only EK-2C prices
    the gap: an EK-2B line would unbundle the package (#266).
    """
    if not claim_has_package:
        ek2b = get_ek2b_price_for_date(code, service_date)
        if ek2b is not None and ek2b > 0:
            return _money(ek2b), "ek2b_list_price"
    ek2c = get_ek2c_price_for_date(code, service_date)
    if ek2c is not None and ek2c > 0:
        return _money(ek2c), "ek2c_package_price"
    return None, ""


def detect_procedure_capture_gaps(
    claim: ClaimHeader,
    performed_lines: list[PerformedProcedureLine],
    claim_procs: list[ProcedureClaimLine],
) -> list[dict[str, Any]]:
    """Flag performed procedures missing from claim submission with catalog pricing."""
    if not performed_lines:
        return []

    submitted = _submitted_amount_by_code_date(claim_procs)
    packages = _package_billed_by_code(claim_procs)
    opportunities: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for performed in performed_lines:
        if performed.claim_id != claim.claim_id:
            continue

        code = normalize_procedure_code(performed.procedure_code)
        if not code:
            continue

        service_date_str = str(performed.service_date)
        dedupe_key = (claim.claim_id, service_date_str, code)
        if dedupe_key in seen:
            continue

        billed = max(
            submitted.get((service_date_str, code), 0.0), packages.get(code, 0.0)
        )
        if billed > _BILLING_TOLERANCE:
            continue

        list_price, methodology = _resolve_catalog_price(
            code, performed.service_date, claim_has_package=code in packages
        )
        if list_price is None or list_price <= _BILLING_TOLERANCE:
            continue

        seen.add(dedupe_key)
        name = performed.procedure_name or _procedure_name(code)
        source = performed.source or "emr"
        detail = (
            f"EMR log shows {code} performed on {service_date_str} "
            f"({source}) but claim submission has "
            f"{billed:.2f} TRY billed."
        )

        opportunities.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim.claim_id,
                "performed_line_id": performed.performed_line_id,
                "procedure_code": code,
                "procedure_name": name,
                "service_date": service_date_str,
                "source": source,
                "actual_billed_try": _money(billed),
                "list_price_try": list_price,
                "recoverable_gap_try": list_price,
                "price_methodology": methodology,
                "savings_category": SAVINGS_CATEGORY_CAPTURE_GAP,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "included_in_sgk_total": False,
                "sut_section_id": "EMR capture completeness",
                "rule_id": "performed_not_submitted",
                "rule_set_id": _RULE_SET_ID,
                "detail": detail,
            }
        )

    return opportunities

"""Runtime EK-2G / EK-2C-1 catalog joins for optimization exactness paths (L2.3, L2.4)."""

from __future__ import annotations

from decimal import Decimal

from src.bilun.domain.catalog import get_ek2c1_copay_rates, get_ek2g_no_surcharge
from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code

_ek2g_normalized: set[str] | None = None
_ek2c1_normalized: dict[str, dict] | None = None

_RATE_TOLERANCE_PCT = Decimal("0.5")


def _load_ek2g_codes() -> set[str]:
    global _ek2g_normalized
    if _ek2g_normalized is None:
        _ek2g_normalized = {
            normalize_procedure_code(code)
            for code in get_ek2g_no_surcharge()
            if normalize_procedure_code(code)
        }
    return _ek2g_normalized


def _load_ek2c1() -> dict[str, dict]:
    global _ek2c1_normalized
    if _ek2c1_normalized is None:
        rows = get_ek2c1_copay_rates()
        _ek2c1_normalized = {
            normalize_procedure_code(code): row
            for code, row in rows.items()
            if normalize_procedure_code(code)
        }
    return _ek2c1_normalized


def is_ek2g_surcharge_prohibited(procedure_code: str) -> bool:
    """True when §1.9.3 / EK-2/G prohibits ilave ücret on this procedure."""
    norm = normalize_procedure_code(procedure_code)
    if not norm:
        return False
    return norm in _load_ek2g_codes()


def catalog_surcharge_eligible(procedure_code: str) -> bool:
    """True when surcharge may apply (procedure not on EK-2/G list)."""
    return not is_ek2g_surcharge_prohibited(procedure_code)


def get_ek2c1_mandated_copay_rate_pct(procedure_code: str) -> float | None:
    """Mandated copay rate % from EK-2C-1, or None if not listed."""
    norm = normalize_procedure_code(procedure_code)
    if not norm:
        return None
    row = _load_ek2c1().get(norm)
    if row is None:
        return None
    return float(row.get("copay_rate_pct", 0))


def catalog_copay_rate_applicable(procedure_code: str) -> bool:
    return get_ek2c1_mandated_copay_rate_pct(procedure_code) is not None


def copay_rate_matches_catalog(
    implied_copay_rate_pct: Decimal,
    procedure_code: str,
) -> bool:
    """True when implied copay % (from payable/billed) matches EK-2C-1 catalog."""
    mandated = get_ek2c1_mandated_copay_rate_pct(procedure_code)
    if mandated is None:
        return True
    return abs(implied_copay_rate_pct - Decimal(str(mandated))) <= _RATE_TOLERANCE_PCT

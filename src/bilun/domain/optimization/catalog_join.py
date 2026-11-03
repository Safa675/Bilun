"""Runtime EK-2G / EK-2C-1 catalog joins for optimization exactness paths (L2.3, L2.4)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.bilun.domain.catalog import get_ek2c1_copay_rates, get_ek2g_no_surcharge
from src.bilun.domain.loaders.legacy import ek2c1_version_day, ek2g_version_day
from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code
from src.bilun.domain.prose_rules.icu_puani import ICU_PACKAGE_CODES

# The normalized codes of each list version, keyed by its first day: a row applies within
# its valid_from / valid_to, so every service date of one version shares one index.
_ek2g_normalized: dict[str, set[str]] = {}
_ek2c1_normalized: dict[str, dict[str, dict]] = {}

_RATE_TOLERANCE_PCT = Decimal("0.5")


def _load_ek2g_codes(as_of: date | str | None = None) -> set[str]:
    day = ek2g_version_day(as_of)
    if day not in _ek2g_normalized:
        _ek2g_normalized[day] = {
            normalize_procedure_code(code)
            for code in get_ek2g_no_surcharge(day)
            if normalize_procedure_code(code)
        }
    return _ek2g_normalized[day]


def _load_ek2c1(as_of: date | str | None = None) -> dict[str, dict]:
    day = ek2c1_version_day(as_of)
    if day not in _ek2c1_normalized:
        _ek2c1_normalized[day] = {
            normalize_procedure_code(code): row
            for code, row in get_ek2c1_copay_rates(day).items()
            if normalize_procedure_code(code)
        }
    return _ek2c1_normalized[day]


def is_ek2g_surcharge_prohibited(procedure_code: str, as_of: date | str | None = None) -> bool:
    """True when §1.9.3 / EK-2/G prohibits ilave ücret on this procedure on ``as_of`` (default today)."""
    norm = normalize_procedure_code(procedure_code)
    if not norm:
        return False
    return norm in _load_ek2g_codes(as_of)


def catalog_surcharge_eligible(procedure_code: str, as_of: date | str | None = None) -> bool:
    """True when surcharge may apply (procedure not on EK-2/G list on ``as_of``)."""
    return not is_ek2g_surcharge_prohibited(procedure_code, as_of)


def get_ek2c1_mandated_copay_rate_pct(procedure_code: str, as_of: date | str | None = None) -> float | None:
    """Mandated copay rate % from EK-2C-1 on ``as_of`` (default today), or None if not listed.

    The ICU day packages (P552001-3, P552006-8, ``icu_puani.ICU_PACKAGE_CODES``) read as not listed: EK-2C-1
    holds them at 100, and SUT 2.2.(20) (C000549) adds that rate to the procedure's points when a Sınıf-3
    facility performs it. The ICU motor applies it so (``icu_puani._resolve_ilave_oran``, the +100 % uplift
    of the package days); it is no patient copay rate.
    """
    norm = normalize_procedure_code(procedure_code)
    if not norm or norm in ICU_PACKAGE_CODES:
        return None
    row = _load_ek2c1(as_of).get(norm)
    if row is None:
        return None
    return float(row.get("copay_rate_pct", 0))


def catalog_copay_rate_applicable(procedure_code: str, as_of: date | str | None = None) -> bool:
    return get_ek2c1_mandated_copay_rate_pct(procedure_code, as_of) is not None


def copay_rate_matches_catalog(
    implied_copay_rate_pct: Decimal,
    procedure_code: str,
    as_of: date | str | None = None,
) -> bool:
    """True when implied copay % (from payable/billed) matches EK-2C-1 catalog on ``as_of``."""
    mandated = get_ek2c1_mandated_copay_rate_pct(procedure_code, as_of)
    if mandated is None:
        return True
    return abs(implied_copay_rate_pct - Decimal(str(mandated))) <= _RATE_TOLERANCE_PCT

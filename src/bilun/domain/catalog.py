"""
src/bilun/domain/catalog.py
Unified catalog loader and price lookup functions for the SUT engine.

Delegates data loading to .loaders and uses mappings from .constants.
This module owns the 3-tier fallback loading strategy and all public
price-lookup APIs.

Dependencies: .constants, .utils, .loaders
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from .constants import (
    BILUN_TO_SUT_CODE,
    _OLD_TO_NEW_CODE,
)
from .loaders import (
    _build_checkup_lab_index,
    _build_checkup_procedure_index,
    _load_checkup_json,
    _load_curated_ek2b_by_asof,
    _load_curated_ek2c_by_asof,
    _load_curated_ek2c_dental_by_asof,
    _load_ek1a_exemptions,
    _load_ek2g_no_surcharge,
    _load_ek2c1_copay_rates,
    get_cached_ek2a,
)
from .money import money_round_half_up as _money
from .utils import _safe_float, _safe_str

logger = logging.getLogger("ilay.sut_catalog")

# ═══════════════════════════════════════════════════════════════════════════
# Module-level cache
# ═══════════════════════════════════════════════════════════════════════════

_catalog_cache_by_asof: dict[str, dict[str, Any]] = {}


# ═══════════════════════════════════════════════════════════════════════════
# Code categorization
# ═══════════════════════════════════════════════════════════════════════════


def _categorize_code(code: str) -> str:
    """Categorize a SUT procedure code by its prefix or numeric range."""
    if code.startswith("L1"):
        return "lab_tests"
    if code.startswith("R1"):
        return "radiology_new"
    if code.startswith("G1"):
        return "genomics"
    try:
        code_int = int(code)
        if 510000 <= code_int < 520000:
            return "beds"
        if 520000 <= code_int < 530000:
            return "visits"
        if 530000 <= code_int < 550000:
            return "procedures"
        if 550000 <= code_int < 560000:
            return "anesthesia"
        if 600000 <= code_int < 619000:
            return "surgery"
        if 700000 <= code_int < 800000:
            return "imaging"
        if 800000 <= code_int < 900000:
            return "radiology"
        if 900000 <= code_int < 913000:
            return "lab_tests_legacy"
    except (ValueError, TypeError):
        pass
    return "other"


# ═══════════════════════════════════════════════════════════════════════════
# Date normalization
# ═══════════════════════════════════════════════════════════════════════════


def _normalize_asof_date(visit_date: Any | None) -> str:
    """Normalize input visit date to YYYY-MM-DD string for as-of selection."""
    if visit_date is None:
        return dt.date.today().isoformat()

    if isinstance(visit_date, dt.datetime):
        return visit_date.date().isoformat()

    if isinstance(visit_date, dt.date):
        return visit_date.isoformat()

    parsed = pd.to_datetime(visit_date, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Invalid visit_date: {visit_date}")
    return parsed.date().isoformat()


# ═══════════════════════════════════════════════════════════════════════════
# Unified catalog loader (curated temporal parquet)
# ═══════════════════════════════════════════════════════════════════════════


def load_sut_catalog(
    force_reload: bool = False,
    visit_date: Any | None = None,
) -> dict[str, Any]:
    """
    Load the SUT catalog from curated temporal parquets (as-of date filtered).

    Returns:
        Dict with keys "ek2b" and "ek2c", each containing parsed data
        with "procedures"/"packages", "by_code", and "stats".
        The "ek2b" by_code index supports BOTH old (9xxxxx) and new (L1xxxxx) codes.

    Raises:
        FileNotFoundError: When curated parquets are missing (run ETL first).
    """
    asof_date = _normalize_asof_date(visit_date)
    if not force_reload and asof_date in _catalog_cache_by_asof:
        return _catalog_cache_by_asof[asof_date]

    parquet_data = _load_curated_ek2b_by_asof(asof_date)

    # EK-2Ç dental procedures live in a separate annex (40xxxx codes) but use
    # the same puan→TRY pricing structure as EK-2B. Merge them into the unified
    # ``by_code`` index so ``lookup_procedure_code`` resolves dental codes
    # (e.g. 402010 amalgam filling) alongside EK-2B entries. Dental codes never
    # overlap EK-2B's code space (L1/R1/G1 prefixes, 5xxxxx-9xxxxx ranges), so
    # the merge is collision-free; we only add codes absent from EK-2B.
    dental_data = _load_curated_ek2c_dental_by_asof(asof_date)
    if dental_data:
        merged: dict[str, dict[str, Any]] = dict(parquet_data) if parquet_data else {}
        for dcode, dentry in dental_data.items():
            if dcode not in merged:
                merged[dcode] = dentry
        parquet_data = merged

    if parquet_data:
        procedures_by_code: dict[str, dict[str, Any]] = {}
        for entry in parquet_data.values():
            code = _safe_str(entry.get("code"))
            if code and code not in procedures_by_code:
                procedures_by_code[code] = entry
        procedures = list(procedures_by_code.values())
        prices = [p["price_try"] for p in procedures if p.get("price_try") is not None]

        categories: dict[str, int] = {}
        for proc in procedures:
            cat = _categorize_code(proc["code"])
            categories[cat] = categories.get(cat, 0) + 1

        stats = {
            "total_procedures": len(procedures),
            "categories": categories,
            "price_min": round(min(prices), 2) if prices else 0,
            "price_max": round(max(prices), 2) if prices else 0,
            "price_mean": round(sum(prices) / len(prices), 2) if prices else 0,
            "source": "temporal_parquet",
            "asof_date": asof_date,
            "dental_codes": len(dental_data),
        }

        ek2c_data = _load_curated_ek2c_by_asof(asof_date)

        catalog = {
            "ek2b": {
                "procedures": procedures,
                "by_code": parquet_data,
                "stats": stats,
            },
            "ek2c": ek2c_data,
            "ek2c_dental": {
                "by_code": dental_data,
            },
        }
        _catalog_cache_by_asof[asof_date] = catalog
        return catalog

    raise FileNotFoundError("Curated SUT parquets missing. Run the ETL pipeline (scripts/sut/build_curated_catalogs.py --overwrite) first.")


# ═══════════════════════════════════════════════════════════════════════════
# Price lookup functions (public API)
# ═══════════════════════════════════════════════════════════════════════════


def get_lab_price(test_name: str, visit_date: Any | None = None) -> float | None:
    """
    Get the SUT gazette price (TRY) for a BILUN lab test name.

    Args:
        test_name: BILUN test name (e.g., "ALT", "CRP", "Hemoglobin")
        visit_date: Optional date for temporal catalog selection.

    Returns:
        Price in TRY, or None if the test is not in the mapping or catalog.
    """
    sut_code = BILUN_TO_SUT_CODE.get(test_name)
    if sut_code is None:
        return None

    catalog = load_sut_catalog(visit_date=visit_date)
    entry = catalog["ek2b"]["by_code"].get(sut_code)
    if entry is not None:
        return entry["price_try"]

    return None


def get_all_lab_prices(visit_date: Any | None = None) -> dict[str, float]:
    """
    Get SUT gazette prices for all mapped BILUN lab test names.

    Returns:
        Dict mapping test_name -> price_try for all tests in BILUN_TO_SUT_CODE
        that have a valid price in the catalog.
    """
    catalog = load_sut_catalog(visit_date=visit_date)
    by_code = catalog["ek2b"]["by_code"]

    result: dict[str, float] = {}
    for test_name, sut_code in BILUN_TO_SUT_CODE.items():
        entry = by_code.get(sut_code)
        if entry is not None:
            result[test_name] = entry["price_try"]

    return result


def get_visit_prices(visit_date: Any | None = None) -> dict[str, float]:
    """
    Get SUT gazette prices for bed and visit codes.

    Returns:
        Dict mapping descriptive key -> price_try.
    """
    catalog = load_sut_catalog(visit_date=visit_date)
    by_code = catalog["ek2b"]["by_code"]

    visit_code_map = {
        "standard_bed": "510010",  # Standart yatak tarifesi
        "incubator": "510070",  # Kuvoz
        "icu": "510090",  # Yogun bakim
        "sterile_room": "510100",  # Steril oda
        "day_bed": "510120",  # Gunduz yatak tarifesi
        "consultation": "520010",  # Konsultasyon
        "emergency_visit": "520020",  # Acil poliklinik muayenesi
        "outpatient_visit": "520030",  # Normal poliklinik muayenesi
        "primary_care_visit": "520080",  # Birinci basamak poliklinik muayenesi
    }

    result: dict[str, float] = {}
    for key, code in visit_code_map.items():
        entry = by_code.get(code)
        if entry is not None:
            result[key] = entry["price_try"]

    return result


def get_checkup_procedure_prices() -> dict[str, dict[str, Any]]:
    """
    Get check-up-specific procedure prices from the compiled JSON.

    Returns:
        Dict mapping procedure key (e.g. "ekg", "mamografi", "batin_usg")
        to {"sut_kodu", "sut_adi", "puan", "tl"}.
    """
    data = _load_checkup_json()
    return data.get("islemler", {})


def get_copayment_info() -> dict[str, Any]:
    """
    Get co-payment (katilim payi) information from the compiled JSON.

    Returns:
        Dict with "muayene" and "ilac" co-payment tiers, or empty dict.
    """
    data = _load_checkup_json()
    return data.get("katilim_payi", {})


def get_katsayi() -> float:
    """
    Get the current SUT coefficient (katsayi) for puan -> TL conversion.

    Formula: Islem Bedeli (TL) = Puan x Katsayi

    Returns:
        Katsayi value (default 0.593 from RG-17/1/2026-33140).
    """
    data = _load_checkup_json()
    return data.get("meta", {}).get("katsayi", 0.593)


def get_ek2c_group_price_ranges(
    visit_date: Any | None = None,
) -> dict[str, tuple[float, float]]:
    """
    Get (min, max) price ranges per EK-2C procedure group.

    Returns:
        Dict mapping group name -> (min_price, max_price).
    """
    catalog = load_sut_catalog(visit_date=visit_date)
    group_stats = catalog["ek2c"].get("group_stats", {})

    result: dict[str, tuple[float, float]] = {}
    for grp, stats in group_stats.items():
        result[grp] = (stats["price_min"], stats["price_max"])

    return result


def get_ek2a_visit_prices() -> dict[str, Any]:
    """Get EK-2A outpatient visit pricing data (cached)."""
    return get_cached_ek2a()


def lookup_ek2a_visit_price_try(
    specialty_code: str,
    *,
    facility_tier: str | None = None,
    provider_type: str | None = None,
) -> tuple[float | None, str]:
    """Look up EK-2A visit price for specialty × facility tier.

    Returns (price_try, methodology) where methodology is
    ``ek2a_tier_row`` or ``unavailable``.
    """
    from src.bilun.domain.prose_rules.facility_tier import normalize_facility_tier

    data = get_ek2a_visit_prices()
    specialties = data.get("specialties", [])
    code = str(specialty_code or "").strip()
    if not code:
        return None, "unavailable"

    row = next((s for s in specialties if str(s.get("code", "")).strip() == code), None)
    if row is None:
        return None, "unavailable"

    tier_ctx = normalize_facility_tier(facility_tier, provider_type=provider_type)
    if not tier_ctx.resolved or tier_ctx.basamak is None:
        return None, "missing_facility_tier"
    column = "U1" if tier_ctx.basamak == 3 and tier_ctx.is_university_eah else (
        "A1" if tier_ctx.basamak == 3 else "B"
    )
    price = row.get("prices_try", {}).get(column)
    if price is None:
        prices = list(row.get("prices_try", {}).values())
        if not prices:
            return None, "unavailable"
        price = sum(prices) / len(prices)
        return _money(price), "ek2a_specialty_mean"
    return _money(price), "ek2a_tier_row"


# ═══════════════════════════════════════════════════════════════════════════
# Optimization annex accessors (EK-1A, EK-2G, EK-2C-1)
# ═══════════════════════════════════════════════════════════════════════════


def get_ek1a_exemptions() -> pd.DataFrame:
    """Return EK-1A chronic disease ICD-10 exemption ranges.

    DataFrame columns: icd10_start, icd10_end, disease_name_tr
    (98 rows — 32 ranges + 66 single codes covering chronic diseases
    that qualify for copayment exemption under SUT 1.8.1.)
    """
    return _load_ek1a_exemptions()


def get_ek2g_no_surcharge() -> dict[str, str]:
    """Return EK-2G procedures where additional fees are prohibited.

    Returns dict: {procedure_code: procedure_name}
    (213 procedures where surcharges are banned by the gazette.)
    """
    return _load_ek2g_no_surcharge()


def get_ek2c1_copay_rates() -> dict[str, dict[str, Any]]:
    """Return EK-2C-1 procedures with explicit copayment rate percentages.

    Returns dict: {procedure_code: {"procedure_name": str, "copay_rate_pct": float}}
    (465 procedures with gazette-mandated rates ranging from 20% to 100%.)
    """
    return _load_ek2c1_copay_rates()


# ═══════════════════════════════════════════════════════════════════════════
# Flexible procedure code lookup (exact → P-strip → prefix search)
# ═══════════════════════════════════════════════════════════════════════════

# Module-level sorted code list for binary search prefix matching
_sorted_codes: list[str] | None = None


def lookup_procedure_code(
    raw_code: str,
    visit_date: Any | None = None,
    max_candidates: int = 10,
) -> dict[str, Any]:
    """Look up a SUT procedure code with flexible matching.

    Three-tier fallback strategy:
      1. **Exact match** — normalised code looked up in EK-2B by_code index.
      2. **P-prefix stripped** — hospitals often prefix codes with "P" (MEDULA).
      3. **Prefix search** — if input ≥ 3 chars, return codes that start with
         the normalised string (capped at *max_candidates*).

    Args:
        raw_code: User-supplied procedure code string.
        visit_date: Optional date for temporal catalog selection.
        max_candidates: Maximum number of prefix-search results (default 10).

    Returns:
        Dict with keys:
          - ``match_type``: ``"exact"`` | ``"prefix_stripped"`` | ``"prefix_search"`` | ``"none"``
          - ``entry``: Single matched entry dict (or None).
          - ``candidates``: List of entries for prefix search (or []).
    """
    global _sorted_codes

    catalog = load_sut_catalog(visit_date=visit_date)
    by_code: dict[str, dict[str, Any]] = catalog.get("ek2b", {}).get("by_code", {})

    normalized = raw_code.strip().replace(".", "").replace(" ", "").replace("-", "")

    # ── Tier 1: Exact match ───────────────────────────────────────────────
    entry = by_code.get(normalized)
    if entry is not None:
        return {"match_type": "exact", "entry": entry, "candidates": []}

    # ── Tier 2: Strip leading P/p prefix ──────────────────────────────────
    if normalized and normalized[0] in ("P", "p"):
        stripped = normalized[1:]
        entry = by_code.get(stripped)
        if entry is not None:
            return {"match_type": "prefix_stripped", "entry": entry, "candidates": []}

    # ── Tier 3: Prefix search (min 3 chars) ───────────────────────────────
    search_key = normalized.lstrip("Pp")
    if len(search_key) >= 3:
        # Build sorted code list once (for efficient prefix scan)
        if _sorted_codes is None or len(_sorted_codes) != len(by_code):
            _sorted_codes = sorted(by_code.keys())

        import bisect

        lo = bisect.bisect_left(_sorted_codes, search_key)
        candidates: list[dict[str, Any]] = []
        for i in range(lo, min(lo + max_candidates * 3, len(_sorted_codes))):
            c = _sorted_codes[i]
            if not c.startswith(search_key):
                break
            e = by_code.get(c)
            if e is not None:
                candidates.append(e)
            if len(candidates) >= max_candidates:
                break

        if candidates:
            return {
                "match_type": "prefix_search",
                "entry": candidates[0],
                "candidates": candidates,
            }

    return {"match_type": "none", "entry": None, "candidates": []}


# ═══════════════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    """Load catalog and print summary."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    logger.info("=== SUT Catalog Loader ===")

    catalog = load_sut_catalog()
    ek2b = catalog["ek2b"]
    ek2c = catalog["ek2c"]

    print(f"\nEK-2B: {ek2b['stats']['total_procedures']} procedures")
    print(f"  Source: {ek2b['stats'].get('source', 'unknown')}")
    print(
        f"  Price range: {ek2b['stats']['price_min']}-{ek2b['stats']['price_max']} TRY"
    )
    if "categories" in ek2b["stats"]:
        print(f"  Categories: {ek2b['stats']['categories']}")

    print(f"\nEK-2C: {ek2c['stats'].get('total_packages', 0)} packages")
    if "unique_groups" in ek2c.get("stats", {}):
        print(f"  Groups: {ek2c['stats']['unique_groups']}")
    for grp, gs in sorted(ek2c.get("group_stats", {}).items()):
        print(f"    {grp}: {gs['count']} pkgs, {gs['price_min']}-{gs['price_max']} TRY")

    # Verify BILUN lab mappings
    print("\nBILUN Lab Price Mapping:")
    lab_prices = get_all_lab_prices()
    for name, price in sorted(lab_prices.items(), key=lambda x: x[1], reverse=True):
        code = BILUN_TO_SUT_CODE[name]
        print(f"  {name:20s} -> {price:>10.2f} TRY (SUT code {code})")

    print(f"\n{len(lab_prices)}/{len(BILUN_TO_SUT_CODE)} tests mapped successfully")

    # Print check-up procedure prices
    proc_prices = get_checkup_procedure_prices()
    if proc_prices:
        print(f"\nCheck-up Procedure Prices ({len(proc_prices)} items):")
        for key, entry in sorted(
            proc_prices.items(), key=lambda x: x[1].get("tl", 0), reverse=True
        ):
            print(
                f"  {key:30s} -> {entry.get('tl', 0):>10.2f} TRY "
                f"({entry.get('sut_kodu', '?')})"
            )

    print(f"\nKatsayi: {get_katsayi()}")


if __name__ == "__main__":
    main()

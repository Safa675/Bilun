"""
src/bilun/domain/materials/drugs.py
EK-4A drug reimbursement data and tier classification.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..constants import EK4A_PARQUET_PATH
from ..utils import _safe_float, turkish_lower

logger = logging.getLogger("ilay.sut_catalog")

_ek4a_cache: dict[str, Any] | None = None
_ek4a_name_index: dict[str, dict[str, Any]] | None = None
_prefix3_index: dict[str, dict[str, Any]] | None = None
_prefix2_index: dict[str, dict[str, Any]] | None = None


def _load_ek4a() -> list[dict[str, Any]]:
    """Load EK-4A drug list from curated parquet."""
    if not EK4A_PARQUET_PATH.exists():
        logger.warning("EK-4A curated parquet not found: %s", EK4A_PARQUET_PATH)
        return []
    try:
        df = pd.read_parquet(EK4A_PARQUET_PATH)
        records: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            drug_name = str(row.get("drug_name", "")).strip()
            if not drug_name:
                continue
            d1 = _safe_float(str(row.get("discount_tier_1", "")).replace(",", "."))
            d2 = _safe_float(str(row.get("discount_tier_2", "")).replace(",", "."))
            d3 = _safe_float(str(row.get("discount_tier_3", "")).replace(",", "."))
            d4 = _safe_float(str(row.get("discount_tier_4", "")).replace(",", "."))
            records.append(
                {
                    "kamu_no": str(row.get("kamu_no", "")).strip(),
                    "barcode": str(row.get("barcode", "")).strip(),
                    "drug_name": drug_name,
                    "equivalence_group": str(row.get("equivalence_group", "")).strip(),
                    "discount_status": str(row.get("discount_status", "")).strip(),
                    "discount_tier_1": d1,
                    "discount_tier_2": d2,
                    "discount_tier_3": d3,
                    "discount_tier_4": d4,
                    "passivation_date": str(row.get("passivation_date", "")).strip(),
                }
            )
        logger.info("EK-4A loaded: %d drugs", len(records))
        return records
    except Exception as e:
        logger.warning("Failed to load EK-4A: %s", e)
        return []


def get_ek4a_drugs() -> list[dict[str, Any]]:
    """Get the full EK-4A drug list (cached)."""
    global _ek4a_cache
    if _ek4a_cache is None:
        _ek4a_cache = {"drugs": _load_ek4a()}
    return _ek4a_cache["drugs"]


def _build_drug_name_index() -> dict[str, dict[str, Any]]:
    """Build a Turkish-lowered drug name index for fuzzy matching."""
    global _ek4a_name_index
    if _ek4a_name_index is not None:
        return _ek4a_name_index

    drugs = get_ek4a_drugs()
    index: dict[str, dict[str, Any]] = {}
    for d in drugs:
        if d["passivation_date"] and d["passivation_date"] not in ("", "nan", "None"):
            continue
        key = turkish_lower(d["drug_name"])
        index[key] = d
    _ek4a_name_index = index
    return _ek4a_name_index


def _build_prefix_indexes() -> tuple[
    dict[str, dict[str, Any]], dict[str, dict[str, Any]]
]:
    """Build prefix-keyed indexes for O(1) prefix matching."""
    global _prefix3_index, _prefix2_index
    if _prefix3_index is not None and _prefix2_index is not None:
        return _prefix3_index, _prefix2_index

    idx = _build_drug_name_index()
    p3: dict[str, dict[str, Any]] = {}
    p2: dict[str, dict[str, Any]] = {}

    for key, drug in idx.items():
        tokens = key.split()
        if len(tokens) >= 3:
            prefix3 = " ".join(tokens[:3])
            if prefix3 not in p3:
                p3[prefix3] = drug
        if len(tokens) >= 2:
            prefix2 = " ".join(tokens[:2])
            if prefix2 not in p2:
                p2[prefix2] = drug

    _prefix3_index = p3
    _prefix2_index = p2
    return _prefix3_index, _prefix2_index


def lookup_drug(rx_name: str) -> dict[str, Any] | None:
    """Look up a prescription drug name in EK-4A.

    Args:
        rx_name: Drug name from prescription data.

    Returns:
        EK-4A drug record dict if found, None otherwise.
    """
    idx = _build_drug_name_index()
    if not idx:
        return None

    needle = turkish_lower(rx_name.strip())

    if needle in idx:
        return idx[needle]

    normalized = needle.replace(".", ",")
    if normalized in idx:
        return idx[normalized]

    tokens = needle.split()
    if len(tokens) >= 3:
        prefix = " ".join(tokens[:3])
        for key, drug in idx.items():
            if key.startswith(prefix):
                return drug

    if len(tokens) >= 2:
        prefix2 = " ".join(tokens[:2])
        for key, drug in idx.items():
            if key.startswith(prefix2):
                return drug

    return None


def lookup_drug_bulk(drug_names: list[str]) -> dict[str, dict[str, Any] | None]:
    """Lookup multiple drug names at once with O(1) prefix matching.

    Args:
        drug_names: List of drug names.

    Returns:
        Dict mapping each unique drug name to its EK-4A record (or None).
    """
    idx = _build_drug_name_index()
    p3, p2 = _build_prefix_indexes()

    if not idx:
        return {name: None for name in drug_names}

    results: dict[str, dict[str, Any] | None] = {}
    for name in set(drug_names):
        needle = turkish_lower(name.strip())

        if needle in idx:
            results[name] = idx[needle]
            continue

        normalized = needle.replace(".", ",")
        if normalized in idx:
            results[name] = idx[normalized]
            continue

        tokens = needle.split()
        if len(tokens) >= 3:
            prefix = " ".join(tokens[:3])
            if prefix in p3:
                results[name] = p3[prefix]
                continue

        if len(tokens) >= 2:
            prefix2 = " ".join(tokens[:2])
            if prefix2 in p2:
                results[name] = p2[prefix2]
                continue

        results[name] = None

    return results


def classify_drug_tier(drug: dict[str, Any] | None) -> str:
    """Classify a drug into pricing tiers based on EK-4A metadata.

    Args:
        drug: EK-4A drug record, or None.

    Returns:
        One of "basic", "moderate", "specialty".
    """
    if drug is None:
        return "basic"

    status = drug.get("discount_status", "")

    if status in ("KAN ÜRÜNÜ", "RADYOFARMASÖTİK", "ENTERAL"):
        return "specialty"

    d1 = drug.get("discount_tier_1")
    if d1 is not None and d1 > 0.35:
        return "specialty"

    if status == "REFERANS":
        d2 = drug.get("discount_tier_2")
        if d2 is not None and d2 > 0.15:
            return "moderate"
        return "moderate"

    if status == "ESDEĞER":
        return "basic"

    if status == "FIYAT KORUMALI":
        d1_val = drug.get("discount_tier_1")
        if d1_val is not None and d1_val > 0.25:
            return "moderate"
        return "basic"

    return "basic"
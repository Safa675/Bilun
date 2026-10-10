"""
src/bilun/domain/materials/drugs.py
EK-4A drug reimbursement data and tier classification.

All reads go through ek4a_as_of(): records are the list in force on a service date, each
with its "state" (active, passive, not_yet_listed, undated) and history "status". Without
a service date (catalog browsing) the list in force today is used.
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache
from typing import Any

from ..utils import turkish_lower
from .ek4a_as_of import Ek4aAsOf, ek4a_as_of


def _snapshot(service_date: dt.date | None) -> Ek4aAsOf:
    return ek4a_as_of(service_date if service_date is not None else dt.date.today())


def get_ek4a_drugs(service_date: dt.date | None = None) -> list[dict[str, Any]]:
    """The EK-4A list in force on ``service_date`` (default: today), every row with its state."""
    return _snapshot(service_date).drugs()


@lru_cache(maxsize=8)
def _name_indexes(service_date: dt.date) -> tuple[
    dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]
]:
    """Turkish-lowered name, 3-token and 2-token prefix indexes of the drugs active on the date.

    Only active rows whose history status is "ok" are matchable: a passive or not yet listed
    drug, or a row SGK published ambiguously, must not be presented as reimbursable.
    """
    names: dict[str, dict[str, Any]] = {}
    prefix3: dict[str, dict[str, Any]] = {}
    prefix2: dict[str, dict[str, Any]] = {}
    for drug in ek4a_as_of(service_date).drugs():
        if drug["state"] != "active" or drug["status"] != "ok":
            continue
        key = turkish_lower(drug["drug_name"])
        names.setdefault(key, drug)
        tokens = key.split()
        if len(tokens) >= 3:
            prefix3.setdefault(" ".join(tokens[:3]), drug)
        if len(tokens) >= 2:
            prefix2.setdefault(" ".join(tokens[:2]), drug)
    return names, prefix3, prefix2


def _match(name: str, indexes: tuple[dict, dict, dict]) -> dict[str, Any] | None:
    names, prefix3, prefix2 = indexes
    needle = turkish_lower(name.strip())
    for key in (needle, needle.replace(".", ",")):
        if key in names:
            return names[key]
    tokens = needle.split()
    if len(tokens) >= 3 and " ".join(tokens[:3]) in prefix3:
        return prefix3[" ".join(tokens[:3])]
    if len(tokens) >= 2 and " ".join(tokens[:2]) in prefix2:
        return prefix2[" ".join(tokens[:2])]
    return None


def lookup_drug(rx_name: str, service_date: dt.date | None = None) -> dict[str, Any] | None:
    """Look up a prescription drug name in the EK-4A list in force on ``service_date``.

    Args:
        rx_name: Drug name from prescription data.
        service_date: Claim date; default today.

    Returns:
        EK-4A drug record dict if an active drug matches, None otherwise.
    """
    day = service_date if service_date is not None else dt.date.today()
    return _match(rx_name, _name_indexes(day))


def lookup_drug_bulk(
    drug_names: list[str], service_date: dt.date | None = None
) -> dict[str, dict[str, Any] | None]:
    """Lookup multiple drug names at once with O(1) prefix matching.

    Args:
        drug_names: List of drug names.
        service_date: Claim date; default today.

    Returns:
        Dict mapping each unique drug name to its EK-4A record (or None).
    """
    day = service_date if service_date is not None else dt.date.today()
    indexes = _name_indexes(day)
    return {name: _match(name, indexes) for name in set(drug_names)}


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

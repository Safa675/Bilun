"""Feature 6 gating: drug discount validation is unavailable without claims."""

from __future__ import annotations

from typing import Any

from .exactness import unavailable_drug_discount_validation

_drug_discount_cache: dict[str, Any] | None = None


def validate_drug_discount_tiers() -> dict[str, Any]:
    """Gate patient-facing drug discount validation until claim inputs exist."""
    global _drug_discount_cache
    if _drug_discount_cache is not None:
        return _drug_discount_cache

    result = unavailable_drug_discount_validation()
    _drug_discount_cache = result
    return result

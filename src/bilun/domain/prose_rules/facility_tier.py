"""Normalize claim facility tier strings for SUT §2.2 payment-method rules."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from ..claims.models import ClaimHeader

Basamak = Literal[2, 3]

FACILITY_TIER_MISSING_INPUT = "facility_tier"

_UNIVERSITY_PROVIDER_TYPES = frozenset(
    {
        "universite",
        "university",
        "egitim_arastirma",
        "tip_fakultesi",
        "tip_fakultesi_sam",
    }
)

_EXPLICIT_TIER_MAP: dict[str, tuple[Basamak, bool]] = {
    # Synthetic claim dataset
    "3_basamak": (3, False),
    "2_basamak_kamu": (2, False),
    "2_3_basamak_ozel": (2, False),
    "1_basamak": (2, False),
    # Frontend / copay simulator
    "2_basamak_resmi": (2, False),
    "3_basamak_resmi": (3, False),
    "egitim_arastirma": (3, True),
    "universite_devlet": (3, True),
    "universite_vakif": (3, True),
    # Bare numeric legacy values
    "1": (2, False),
    "2": (2, False),
    "3": (3, False),
}


def _canonicalize_tier(raw: str | None) -> str:
    text = str(raw or "").strip().lower()
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")
    return ascii_text


def _canonicalize_provider(raw: str | None) -> str:
    return _canonicalize_tier(raw)


def _unresolved_tier_context(raw: str) -> TierContext:
    return TierContext(
        raw_tier=raw,
        basamak=None,
        is_university_eah=False,
        used_default=True,
    )


@dataclass(frozen=True)
class TierContext:
    """Resolved hospital tier for prose-rule evaluation."""

    raw_tier: str
    basamak: Basamak | None
    is_university_eah: bool
    used_default: bool

    @property
    def resolved(self) -> bool:
        return not self.used_default and self.basamak is not None

    @property
    def is_third_tier(self) -> bool:
        return self.basamak == 3

    @property
    def allows_section_2_2_2_override(self) -> bool:
        """Whether §2.2.2(2) optional EK-2/B override may apply (tier gate only)."""
        return self.is_third_tier


def normalize_facility_tier(
    facility_tier: str | None,
    *,
    provider_type: str | None = None,
) -> TierContext:
    """Map a claim facility tier string to basamak + university flags.

    Empty or unmapped values are returned unresolved (``used_default=True``,
    ``basamak=None``) so callers can surface ``missing_inputs`` instead of
    silently assuming basamak 2.
    """
    raw = str(facility_tier or "").strip()
    canonical = _canonicalize_tier(raw)

    if canonical in _EXPLICIT_TIER_MAP:
        basamak, is_university = _EXPLICIT_TIER_MAP[canonical]
    elif canonical.startswith("3_") or canonical.endswith("_3_basamak"):
        basamak, is_university = 3, False
    elif "universite" in canonical or "egitim_arastirma" in canonical:
        basamak, is_university = 3, True
    elif canonical.startswith("2_") or canonical.startswith("1_"):
        basamak, is_university = 2, False
    elif not canonical:
        return _unresolved_tier_context(raw)
    else:
        return _unresolved_tier_context(raw)

    provider_canonical = _canonicalize_provider(provider_type)
    if not is_university and provider_canonical in _UNIVERSITY_PROVIDER_TYPES:
        if basamak == 3 or canonical == "3_basamak":
            is_university = True

    return TierContext(
        raw_tier=raw,
        basamak=basamak,
        is_university_eah=is_university,
        used_default=False,
    )


def tier_context_from_claim(claim: ClaimHeader) -> TierContext:
    """Resolve tier context from an existing claim header."""
    return normalize_facility_tier(
        claim.facility_tier,
        provider_type=claim.provider_type,
    )

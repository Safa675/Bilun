"""Blood component partial-bill fraction tiers (SUT §2.2.2.B-1.e / §4.6).

Covers the generalized ``blood_component_billable_fraction()``: the
authoritative per-code ``fractions`` map (8 codes × 4 tiers), the legacy
``codes[]`` + ``billable_point_fraction`` fallback for configs without the
map, fractions-map precedence, and procedure-code normalization (P-prefix).
"""

from __future__ import annotations

from unittest import mock

import pytest

from src.bilun.domain.prose_rules.session_pricing import (
    blood_component_billable_fraction,
)

pytestmark = pytest.mark.unit

# All 8 blood components across the 4 SUT §4.6 tiers.
_TIER_CASES: tuple[tuple[str, float], ...] = (
    ("705371", 0.36),
    ("705430", 0.36),
    ("705440", 0.36),
    ("705372", 0.24),
    ("705373", 0.24),
    ("705441", 0.20),
    ("705442", 0.28),
    ("705443", 0.28),
)

# The 3 legacy codes covered by the pre-tier `codes[]` + fraction pair.
_LEGACY_CODES = ("705371", "705430", "705440")


def _legacy_payload() -> dict:
    """Config shape before the tier map existed — no ``fractions`` key."""
    return {
        "special_codes": {
            "blood_component_partial_bill": {
                "codes": list(_LEGACY_CODES),
                "billable_point_fraction": 0.36,
            }
        }
    }


class TestBloodComponentFractionTiers:
    def test_all_eight_codes_return_tier_fraction(self) -> None:
        for code, expected in _TIER_CASES:
            assert (
                blood_component_billable_fraction(code) == pytest.approx(expected)
            ), f"{code} expected {expected}"

    def test_p_prefix_normalized(self) -> None:
        # P-prefix (MEDULA package prefix) must resolve to the same tier.
        assert blood_component_billable_fraction("P705441") == pytest.approx(0.20)
        assert blood_component_billable_fraction("p705443") == pytest.approx(0.28)

    def test_punctuated_code_normalized(self) -> None:
        assert blood_component_billable_fraction("705.442") == pytest.approx(0.28)
        assert blood_component_billable_fraction("705 371") == pytest.approx(0.36)

    def test_unknown_code_returns_none(self) -> None:
        assert blood_component_billable_fraction("999999") is None
        assert blood_component_billable_fraction("") is None

    def test_legacy_fallback_without_fractions_map(self) -> None:
        # Old configs (no 'fractions') must behave exactly as before: the 3
        # legacy codes resolve to the legacy fraction, the tier-only codes to
        # None.
        with mock.patch(
            "src.bilun.domain.prose_rules.session_pricing._load_session_rules",
            return_value=_legacy_payload(),
        ):
            for code in _LEGACY_CODES:
                assert blood_component_billable_fraction(code) == pytest.approx(0.36)
            assert blood_component_billable_fraction("705372") is None
            assert blood_component_billable_fraction("705441") is None
            assert blood_component_billable_fraction("705443") is None

    def test_fractions_map_takes_precedence_over_legacy(self) -> None:
        # When both exist, 'fractions' is authoritative.
        payload = {
            "special_codes": {
                "blood_component_partial_bill": {
                    "codes": ["705371"],
                    "billable_point_fraction": 0.36,
                    "fractions": {"705371": 0.24},
                }
            }
        }
        with mock.patch(
            "src.bilun.domain.prose_rules.session_pricing._load_session_rules",
            return_value=payload,
        ):
            assert blood_component_billable_fraction("705371") == pytest.approx(0.24)

"""Unit tests for facility tier normalization (Phase 2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit


class TestNormalizeFacilityTier:
    def test_synthetic_third_tier_maps_to_basamak_3(self) -> None:
        from src.bilun.domain.prose_rules.facility_tier import normalize_facility_tier

        ctx = normalize_facility_tier("3_basamak")
        assert ctx.basamak == 3
        assert ctx.is_third_tier is True
        assert ctx.is_university_eah is False
        assert ctx.used_default is False

    def test_synthetic_second_tier_values_map_to_basamak_2(self) -> None:
        from src.bilun.domain.prose_rules.facility_tier import normalize_facility_tier

        for tier in ("2_basamak_kamu", "2_3_basamak_ozel"):
            ctx = normalize_facility_tier(tier)
            assert ctx.basamak == 2
            assert ctx.allows_section_2_2_2_override is False

    def test_frontend_university_tiers(self) -> None:
        from src.bilun.domain.prose_rules.facility_tier import normalize_facility_tier

        for tier in ("egitim_arastirma", "universite_devlet", "universite_vakif"):
            ctx = normalize_facility_tier(tier)
            assert ctx.basamak == 3
            assert ctx.is_university_eah is True

    def test_frontend_public_resmi_tiers(self) -> None:
        from src.bilun.domain.prose_rules.facility_tier import normalize_facility_tier

        assert normalize_facility_tier("2_basamak_resmi").basamak == 2
        assert normalize_facility_tier("3_basamak_resmi").basamak == 3

    def test_unknown_defaults_conservatively_to_basamak_2(self) -> None:
        from src.bilun.domain.prose_rules.facility_tier import normalize_facility_tier

        ctx = normalize_facility_tier("")
        assert ctx.basamak == 2
        assert ctx.used_default is True
        assert ctx.allows_section_2_2_2_override is False

        ctx = normalize_facility_tier("devlet")
        assert ctx.basamak == 2
        assert ctx.used_default is True

    def test_legacy_numeric_tier(self) -> None:
        from src.bilun.domain.prose_rules.facility_tier import normalize_facility_tier

        assert normalize_facility_tier("3").basamak == 3
        assert normalize_facility_tier("2").basamak == 2

    def test_university_provider_upgrades_3_basamak(self) -> None:
        from src.bilun.domain.prose_rules.facility_tier import normalize_facility_tier

        ctx = normalize_facility_tier("3_basamak", provider_type="Universite")
        assert ctx.basamak == 3
        assert ctx.is_university_eah is True

    def test_tier_context_from_claim(self) -> None:
        from src.bilun.domain.claims.models import ClaimHeader
        from src.bilun.domain.prose_rules.facility_tier import tier_context_from_claim

        claim = ClaimHeader(
            claim_id="CLM1",
            patient_id="P1",
            episode_id="E1",
            claim_type="yatis",
            facility_tier="2_basamak_kamu",
            provider_type="Kamu",
            department="cardiology",
            admission_date=date(2026, 1, 10),
            discharge_date=date(2026, 1, 12),
            claim_start_date=date(2026, 1, 10),
            claim_end_date=date(2026, 1, 12),
            primary_icd10="I21.9",
            package_candidate=True,
            expected_total_billed_try=Decimal("5000"),
            expected_total_payable_try=Decimal("4000"),
            expected_denial_reason="",
            scenario_tag="test",
        )
        ctx = tier_context_from_claim(claim)
        assert ctx.basamak == 2
        assert ctx.raw_tier == "2_basamak_kamu"

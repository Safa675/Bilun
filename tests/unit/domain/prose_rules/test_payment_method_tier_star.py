"""Unit tests for tier- and star-aware payment method resolution (Phase 3)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

TIER_2 = "2_basamak_kamu"
TIER_3 = "egitim_arastirma"
NON_STAR_DUAL = "600150"
STAR_DUAL = "550970"
EK2C_DEFAULT = "610070"
PROSE_LOCKED_DUAL = "604250"


class TestPaymentMethodTierStar:
    def test_tier_2_ek2c_is_drg_mandatory(self) -> None:
        from src.bilun.domain.prose_rules import resolve_payment_method

        result = resolve_payment_method(
            EK2C_DEFAULT,
            care_setting="inpatient",
            facility_tier=TIER_2,
        )
        assert result.kind == "DRG_MANDATORY"
        assert result.payment_method == "package"
        assert result.trace.rule_id == "2.2.2.(1).package"

    def test_tier_3_non_star_dual_listed_is_overridable(self) -> None:
        from src.bilun.domain.prose_rules import resolve_payment_method

        result = resolve_payment_method(
            NON_STAR_DUAL,
            care_setting="inpatient",
            facility_tier=TIER_3,
        )
        assert result.kind == "DRG_OVERRIDABLE"
        assert result.payment_method == "overridable"
        assert result.in_ek2b is True
        assert result.in_ek2c is True
        assert result.has_star is False
        assert result.allowed_methods == ("package", "itemized")
        assert result.trace.rule_id == "2.2.2.(2).override"

    def test_tier_3_prose_locked_dual_listed_is_drg_mandatory(self) -> None:
        from src.bilun.domain.prose_rules import resolve_payment_method
        from src.bilun.domain.prose_rules.catalog_membership import (
            procedure_prose_drg_locked,
        )

        assert procedure_prose_drg_locked(PROSE_LOCKED_DUAL) is True
        result = resolve_payment_method(
            PROSE_LOCKED_DUAL,
            care_setting="inpatient",
            facility_tier=TIER_3,
        )
        assert result.kind == "DRG_MANDATORY"
        assert result.payment_method == "package"
        assert "Prose-mandated" in result.trace.detail

    def test_tier_3_starred_code_is_drg_mandatory(self) -> None:
        from src.bilun.domain.prose_rules import resolve_payment_method

        result = resolve_payment_method(
            STAR_DUAL,
            care_setting="inpatient",
            facility_tier=TIER_3,
        )
        assert result.kind == "DRG_MANDATORY"
        assert result.payment_method == "package"
        assert result.has_star is True
        assert "override not permitted" in result.trace.detail

    def test_outpatient_ek2c_skips_override_even_at_tier_3(self) -> None:
        from src.bilun.domain.prose_rules import resolve_payment_method

        result = resolve_payment_method(
            NON_STAR_DUAL,
            care_setting="outpatient",
            facility_tier=TIER_3,
        )
        assert result.kind == "DRG_MANDATORY"
        assert result.trace.rule_id == "2.2.1.B-1.a"

    def test_unknown_tier_defaults_conservative(self) -> None:
        from src.bilun.domain.prose_rules import resolve_payment_method

        result = resolve_payment_method(
            NON_STAR_DUAL,
            care_setting="inpatient",
            facility_tier="",
        )
        assert result.kind == "DRG_MANDATORY"

    def test_ek2b_only_is_itemized(self) -> None:
        from src.bilun.domain.prose_rules.catalog_membership import (
            get_ek2b_codes,
            get_ek2c_codes,
        )
        from src.bilun.domain.prose_rules import resolve_payment_method

        ek2b_only = next(iter(get_ek2b_codes() - get_ek2c_codes()), None)
        if ek2b_only is None:
            pytest.skip("No EK-2/B-only code in catalog")

        result = resolve_payment_method(
            ek2b_only,
            care_setting="inpatient",
            facility_tier=TIER_3,
        )
        assert result.kind == "ITEMIZED"
        assert result.payment_method == "itemized"


class TestPaymentMethodComplianceKind:
    def test_overridable_accepts_package_and_itemized(self) -> None:
        from src.bilun.domain.prose_rules import check_payment_method_compliance

        for billed_as_package in (True, False):
            result = check_payment_method_compliance(
                NON_STAR_DUAL,
                billed_as_package=billed_as_package,
                care_setting="inpatient",
                facility_tier=TIER_3,
            )
            assert result.kind == "DRG_OVERRIDABLE"
            assert result.is_compliant is True

    def test_mandatory_package_flags_itemized_billing(self) -> None:
        from src.bilun.domain.prose_rules import check_payment_method_compliance

        result = check_payment_method_compliance(
            EK2C_DEFAULT,
            billed_as_package=False,
            care_setting="inpatient",
            facility_tier=TIER_2,
        )
        assert result.kind == "DRG_MANDATORY"
        assert result.is_compliant is False
        assert "package billing" in result.detail

    def test_mandatory_package_accepts_package_billing(self) -> None:
        from src.bilun.domain.prose_rules import check_payment_method_compliance

        result = check_payment_method_compliance(
            STAR_DUAL,
            billed_as_package=True,
            care_setting="inpatient",
            facility_tier=TIER_3,
        )
        assert result.kind == "DRG_MANDATORY"
        assert result.is_compliant is True

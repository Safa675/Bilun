"""Unit tests for SUT prose rule evaluators (Phase 3)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestPaymentMethod:
    def test_ek2c_code_mandates_package(self) -> None:
        from src.bilun.domain.prose_rules import resolve_payment_method

        # facility_tier is now a required input after the §2.2.2(2) override batch.
        # At university tier the override applies → DRG_OVERRIDABLE (package preferred, itemized also permitted).
        result = resolve_payment_method(
            "610070", care_setting="inpatient", facility_tier="universite"
        )
        assert result.in_ek2c is True
        assert result.payment_method in {"package", "overridable"}
        assert result.kind == "DRG_OVERRIDABLE"
        assert result.trace.sut_section == "2.2.2.(2)"
        assert result.bill_materials_separately is True

    def test_ek2b_only_mandates_itemized(self) -> None:
        from src.bilun.domain.prose_rules.catalog_membership import (
            get_ek2b_codes,
            get_ek2c_codes,
        )
        from src.bilun.domain.prose_rules import resolve_payment_method

        ek2b_only = next(iter(get_ek2b_codes() - get_ek2c_codes()), None)
        if ek2b_only is None:
            pytest.skip("No EK-2/B-only code in catalog")

        result = resolve_payment_method(ek2b_only, care_setting="outpatient")
        assert result.payment_method == "itemized"
        assert result.kind == "ITEMIZED"
        assert result.visit_fee_annex == "EK-2/A"
        assert result.trace.rule_id == "2.2.1.B-1.b"

    def test_compliance_flags_wrong_billing_method(self) -> None:
        from src.bilun.domain.prose_rules import check_payment_method_compliance

        # With facility_tier resolved, §2.2.2(2) override makes itemized
        # billing compliant at university tier (package preferred, not mandatory).
        result = check_payment_method_compliance(
            "610070",
            billed_as_package=False,
            care_setting="inpatient",
            facility_tier="universite",
        )
        assert result.mandated_method in {"package", "overridable"}
        assert result.kind == "DRG_OVERRIDABLE"
        assert result.is_compliant is True  # itemized permitted under override


class TestSessionPricing:
    def test_same_incision_ek2c_session_factors(self) -> None:
        from src.bilun.domain.prose_rules import compute_session_point_factors

        result = compute_session_point_factors(
            ["610070", "609270"],
            same_incision=True,
        )
        assert result.rule_id == "2.2.2.B.a"
        factors = {f.procedure_code: (f.point_factor, f.is_primary) for f in result.factors}
        assert len(factors) == 2
        # 609270 has higher EK-2/C puan than 610070 — must be primary per §2.2.2.B.a
        assert factors["609270"] == (1.0, True)
        assert factors["610070"] == (0.25, False)

    def test_ek2b_only_multi_procedure_uses_itemized_a5(self, monkeypatch) -> None:
        from src.bilun.domain.prose_rules import compute_session_point_factors

        def _ek2b_only(_code: str) -> tuple[bool, bool]:
            return (True, False)

        monkeypatch.setattr(
            "src.bilun.domain.prose_rules.session_pricing.procedure_annex_membership",
            _ek2b_only,
        )
        monkeypatch.setattr(
            "src.bilun.domain.prose_rules.session_pricing._procedure_point_score",
            lambda _code: 10.0,
        )

        result = compute_session_point_factors(
            ["600150", "600151"],
            same_incision=True,
        )
        assert result.rule_id == "2.2.2.A.(5)"
        factors = {f.procedure_code: f.point_factor for f in result.factors}
        assert factors["600150"] == 1.0
        assert factors["600151"] == pytest.approx(0.30)

    def test_mixed_session_falls_back_to_a5_when_ek2b_primary(self, monkeypatch) -> None:
        from src.bilun.domain.prose_rules import compute_session_point_factors

        def _membership(code: str) -> tuple[bool, bool]:
            return (True, False) if code == "EK2BHI" else (True, True)

        def _points(code: str) -> float:
            return 100.0 if code == "EK2BHI" else 1.0

        monkeypatch.setattr(
            "src.bilun.domain.prose_rules.session_pricing.procedure_annex_membership",
            _membership,
        )
        monkeypatch.setattr(
            "src.bilun.domain.prose_rules.session_pricing._procedure_point_score",
            _points,
        )

        result = compute_session_point_factors(
            ["EK2CLO", "EK2BHI"],
            same_incision=True,
        )
        assert result.rule_id == "2.2.2.A.(5)"
        factors = {f.procedure_code: (f.point_factor, f.is_primary) for f in result.factors}
        assert factors["EK2BHI"][0] == 1.0
        assert factors["EK2BHI"][1] is True
        assert factors["EK2CLO"][0] == pytest.approx(0.30)

    def test_cross_specialty_increases_secondary_factor(self, monkeypatch) -> None:
        from src.bilun.domain.prose_rules import compute_session_point_factors

        monkeypatch.setattr(
            "src.bilun.domain.prose_rules.session_pricing.procedure_annex_membership",
            lambda _code: (True, False),
        )
        monkeypatch.setattr(
            "src.bilun.domain.prose_rules.session_pricing._procedure_point_score",
            lambda code: 10.0 if code == "B" else 5.0,
        )

        result = compute_session_point_factors(
            ["A", "B"],
            same_incision=True,
            cross_specialty=True,
        )
        secondary = [f.point_factor for f in result.factors if not f.is_primary][0]
        assert secondary == pytest.approx(0.55)

    def test_blood_component_special_fraction(self) -> None:
        from src.bilun.domain.prose_rules.session_pricing import (
            blood_component_billable_fraction,
        )

        assert blood_component_billable_fraction("705371") == 0.36
        assert blood_component_billable_fraction("999999") is None


class TestCopayGeneral:
    def test_drug_copay_rates(self) -> None:
        from src.bilun.domain.prose_rules import resolve_drug_copay_rate

        assert resolve_drug_copay_rate("sgk_income_recipient") == 0.1
        assert resolve_drug_copay_rate("other") == 0.2

    def test_prescription_flat_fee_2026(self) -> None:
        from src.bilun.domain.prose_rules import resolve_prescription_flat_fee_try

        assert resolve_prescription_flat_fee_try(2, as_of="2026-06-01") == 3.76
        assert resolve_prescription_flat_fee_try(5, as_of="2026-06-01") == pytest.approx(
            6.26
        )

    def test_ivf_treatment_copay_by_attempt(self) -> None:
        from src.bilun.domain.prose_rules import (
            resolve_ivf_drug_copay_rate,
            resolve_ivf_treatment_copay_rate,
        )

        assert resolve_ivf_treatment_copay_rate("sgk_income_recipient", attempt=1) == 0.3
        assert resolve_ivf_treatment_copay_rate("other", attempt=2) == 0.25
        assert resolve_ivf_treatment_copay_rate("other", attempt=3) == 0.2
        assert resolve_ivf_drug_copay_rate("other") == 0.3

    def test_material_copay_rate(self) -> None:
        from src.bilun.domain.prose_rules import resolve_material_copay_rate

        assert resolve_material_copay_rate("sgk_income_recipient") == 0.1
        assert resolve_material_copay_rate("other") == 0.2


class TestDecisionTables:
    def test_json_tables_load(self) -> None:
        from src.bilun.domain.prose_rules.copay_general import load_decision_table
        from src.bilun.domain.prose_rules.payment_method import load_decision_table as load_pm

        pm = load_pm()
        copay = load_decision_table()
        assert pm["rule_set_id"] == "payment_method_2_2"
        assert copay["rule_set_id"] == "copay_general_1_8"
        assert len(pm["rules"]) >= 5

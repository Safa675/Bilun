"""Execution tests for the newly-wired gap-closing + dental + definitions engines.

These confirm the engines actually evaluate rule conditions against claim
contexts and fire/suppress correctly — not just that the loaders exist.
The honesty guard (rules skip when condition data is absent) is also covered.
"""

from __future__ import annotations

from src.bilun.domain.prose_rules.gap_closing import (
    check_gap_closing_misc,
    check_gap_closing_treatment,
)
from src.bilun.domain.prose_rules.dental_2_4_1 import check_dental_2_4_1_prose
from src.bilun.domain.prose_rules.definitions_2_6 import load_definitions_2_6_rules
from src.bilun.domain.sut.rule_registry import RULE_BY_ID


class TestGapClosingMisc:
    def test_uncontracted_private_non_emergency_fires(self) -> None:
        ctx = {"facility_uncontracted_private": True, "is_emergency": False}
        hits = check_gap_closing_misc(ctx)
        rule_ids = {h["rule_id"] for h in hits}
        assert "1.5.1.(3).uncontracted_private_non_emergency_no_pay" in rule_ids
        fired = next(h for h in hits if h["rule_id"] == "1.5.1.(3).uncontracted_private_non_emergency_no_pay")
        assert fired["billable"] is False
        assert fired["material_outcome"] == "no_pay"

    def test_emergency_suppresses_uncontracted_rule(self) -> None:
        # Same provider but emergency → the no-pay rule must NOT fire.
        ctx = {"facility_uncontracted_private": True, "is_emergency": True}
        hits = check_gap_closing_misc(ctx)
        assert not any("uncontracted_private_non_emergency" in h["rule_id"] for h in hits)

    def test_honesty_guard_empty_context_fires_nothing(self) -> None:
        # No claim data surfaced → rules must not guess; zero violations.
        assert check_gap_closing_misc({}) == []


class TestGapClosingTreatment:
    def test_fee_for_service_payment_method_fires(self) -> None:
        ctx = {"payment_method": "fee_for_service", "not_in_drg_package": True}
        hits = check_gap_closing_treatment(ctx)
        assert any("non_diagnosis_fee_for_service" in h["rule_id"] for h in hits)

    def test_procedure_category_any_predicate(self) -> None:
        # Set-membership predicate: procedure_category in the rule's _any list.
        ctx = {"procedure_category": "inpatient_surgery"}
        hits = check_gap_closing_treatment(ctx)
        assert any("materials_supplied_by_provider" in h["rule_id"] for h in hits)

    def test_procedure_category_not_in_set_does_not_fire(self) -> None:
        ctx = {"procedure_category": "consultation"}
        hits = check_gap_closing_treatment(ctx)
        assert not any("materials_supplied_by_provider" in h["rule_id"] for h in hits)

    def test_honesty_guard_missing_scalar_skips(self) -> None:
        # payment_method absent → rules keyed on it must not fire.
        assert check_gap_closing_treatment({"not_in_drg_package": True}) == [] or all(
            "fee_for_service" not in h["rule_id"] for h in check_gap_closing_treatment({"not_in_drg_package": True})
        )


class TestDental241:
    def test_precious_metal_no_pay(self) -> None:
        mats = [
            {
                "name": "Bego gold EWL kron",
                "procedure_category": "dental_restoration",
                "material_contains_precious_metal": True,
            }
        ]
        hits = check_dental_2_4_1_prose(mats)
        assert any("precious_metal" in h["rule_id"] for h in hits)
        assert next(h for h in hits if "precious_metal" in h["rule_id"])["billable"] is False

    def test_non_precious_metal_does_not_fire(self) -> None:
        mats = [
            {
                "name": "çelik kron",
                "procedure_category": "dental_restoration",
                "material_contains_precious_metal": False,
            }
        ]
        hits = check_dental_2_4_1_prose(mats)
        assert not any("precious_metal" in h["rule_id"] for h in hits)

    def test_implant_without_board_report_no_pay(self) -> None:
        mats = [
            {
                "name": "dental implant",
                "procedure_category": "dental_implant",
                "medical_necessity_board_report": False,
            }
        ]
        hits = check_dental_2_4_1_prose(mats)
        assert any("bone_implant" in h["rule_id"] for h in hits)

    def test_turkish_normalization_in_keyword_match(self) -> None:
        # "altın" with Turkish dotless i / diacritics must match normalized.
        mats = [
            {
                "name": "altın kaplama",
                "procedure_category": "dental_restoration",
                "material_contains_precious_metal": True,
            }
        ]
        hits = check_dental_2_4_1_prose(mats)
        assert any("precious_metal" in h["rule_id"] for h in hits)


class TestDefinitions26NonAlgorithmic:
    def test_loader_returns_rule_set(self) -> None:
        ruleset = load_definitions_2_6_rules()
        assert ruleset["rule_set_id"] == "definitions_2_6"
        assert len(ruleset["rules"]) >= 50

    def test_registry_entry_is_non_algorithmic(self) -> None:
        entry = RULE_BY_ID["definitions_2_6"]
        assert entry.coverage_status == "non_algorithmic"
        assert any("definitions_2_6.py" in m for m in entry.domain_modules)


class TestWiredEnginesRegistered:
    """All four newly-wired engines must be in the registry with correct status."""

    def test_gap_closing_misc_registered_partial(self) -> None:
        e = RULE_BY_ID["gap_closing_misc"]
        assert e.coverage_status == "partial"
        assert "gap_closing.py" in e.domain_modules[0]

    def test_gap_closing_treatment_registered_partial(self) -> None:
        e = RULE_BY_ID["gap_closing_treatment_2"]
        assert e.coverage_status == "partial"

    def test_dental_registered_partial(self) -> None:
        e = RULE_BY_ID["dental_2_4_1"]
        assert e.coverage_status == "partial"

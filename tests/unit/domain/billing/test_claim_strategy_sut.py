"""Unit tests for SUT-compliant claim-level billing strategy (Phase 4)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.claim_strategy import recommend_billing_strategy_from_claims
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit


def _claim(**overrides) -> ClaimHeader:
    base = dict(
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
    base.update(overrides)
    return ClaimHeader(**base)


def _proc(**overrides) -> ProcedureClaimLine:
    base = dict(
        procedure_line_id="PL1",
        claim_id="CLM1",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 10),
        procedure_code="610070",
        procedure_name="Test procedure",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
        expected_payable_try=Decimal("800"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    base.update(overrides)
    return ProcedureClaimLine(**base)


def _ctx(claim: ClaimHeader, *lines: ProcedureClaimLine) -> PatientClaimContext:
    return PatientClaimContext(
        patient_id=claim.patient_id,
        claims=(claim,),
        procedure_lines=tuple(lines),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


class TestClaimStrategySut:
    @pytest.mark.parametrize(
        "package_amount, expected_recommendation, expected_savings",
        [("1100", "package", 0.0), ("1000", "itemized", 30.0)],
    )
    def test_secondary_own_payable_controls_optional_strategy(
        self,
        monkeypatch,
        package_amount,
        expected_recommendation,
        expected_savings,
    ) -> None:
        from src.bilun.domain.billing import claim_strategy
        from src.bilun.domain.prose_rules import payment_method, session_pricing
        from src.bilun.domain.prose_rules.types import PaymentMethodResult, ProseRuleTrace

        def optional_payment_method(code, **_kwargs):
            is_package = str(code).startswith("P")
            return PaymentMethodResult(
                procedure_code=code,
                payment_method="package" if is_package else "itemized",
                kind="DRG_OVERRIDABLE",
                in_ek2b=True,
                in_ek2c=is_package,
                has_star=False,
                bill_materials_separately=False,
                bill_drugs_separately=False,
                visit_fee_annex=None,
                trace=ProseRuleTrace(
                    rule_id="test",
                    sut_section="2.2.2.(2)",
                    rule_set_id="test",
                    detail="test optional itemized alternative",
                ),
            )

        monkeypatch.setattr(claim_strategy, "resolve_payment_method", optional_payment_method)
        monkeypatch.setattr(payment_method, "resolve_payment_method", optional_payment_method)
        monkeypatch.setattr(
            session_pricing,
            "procedure_annex_membership",
            lambda code, **kwargs: (True, False),
        )
        # #261: placeholder codes sit in EK-2/B §6, the only lines that form a session.
        monkeypatch.setattr(
            session_pricing,
            "_procedure_point_score",
            lambda code, **kwargs: {"611111": 20, "622222": 10}[code],
        )
        claim = _claim(facility_tier="egitim_arastirma", package_candidate=True)
        lines = [
            _proc(
                procedure_code="611111",
                procedure_specialty_code="same-specialty",
                expected_payable_try=Decimal("1000"),
                billed_amount_try=Decimal("1000"),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="622222",
                procedure_specialty_code="same-specialty",
                unit_price_try=Decimal("100"),
                expected_payable_try=Decimal("100"),
                billed_amount_try=Decimal("100"),
            ),
            _proc(
                procedure_line_id="PL3",
                procedure_code="P333333",
                procedure_category="paket",
                unit_price_try=Decimal(package_amount),
                expected_payable_try=Decimal(package_amount),
                billed_amount_try=Decimal(package_amount),
            ),
        ]

        result = recommend_billing_strategy_from_claims(_ctx(claim, *lines))
        claim_recs = [rec for rec in result.recommendations if "recommendation_kind" in rec]

        assert len(claim_recs) == 1
        rec = claim_recs[0]
        assert rec["recommendation"] == expected_recommendation
        assert rec["savings_try"] == expected_savings
        assert rec["recoverable_uplift_try"] == expected_savings
        assert rec["recommendation_kind"] == "optional_override"
        assert rec["payment_method_kind"] == "DRG_OVERRIDABLE"
        assert rec["current_billing"] == "package"
        assert rec["itemized_raw_try"] == 1100.0
        assert rec["itemized_total_try"] == 1030.0
        assert rec["package_total_try"] == float(package_amount)
        assert rec["itemized_price_methodology"] == "session_adjusted"
        assert rec["itemized_excluded_violation_count"] == 0
        assert rec["included_in_sgk_total"] is (expected_savings > 0)

    def test_tier_2_ek2c_mandatory_package_not_cheaper_itemized(self) -> None:
        claim = _claim(facility_tier="2_basamak_kamu")
        lines = [
            _proc(
                procedure_code="610070",
                procedure_category="islem",
                expected_payable_try=Decimal("5000"),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="520080",
                procedure_category="islem",
                expected_payable_try=Decimal("100"),
            ),
        ]
        result = recommend_billing_strategy_from_claims(_ctx(claim, *lines))
        claim_recs = [
            rec
            for rec in result.recommendations
            if rec.get("claim_id") == "CLM1" and "recommendation" in rec
        ]
        assert len(claim_recs) == 1
        rec = claim_recs[0]
        assert rec["recommendation"] == "package"
        assert rec["recommendation_kind"] == "mandatory_compliance"
        assert rec["payment_method_kind"] == "DRG_MANDATORY"
        assert "lower than" not in rec["detail"]
        assert "mandates package billing" in rec["detail"]
        # Structured message contract: params rebuild the detail byte-for-byte.
        assert rec["message_code"] == "claim_mandate_package"
        params = rec["message_params"]
        assert params["claim_id"] == "CLM1"
        assert rec["detail"] == (
            "SUT §2.2 mandates package billing for claim CLM1 "
            "(EK-2/C procedure present). Package total "
            f"{params['package_total_try']} TRY vs itemized "
            f"{params['itemized_total_try']} TRY."
        )
        # clause_ref resolves from the row's own sut_section coordinate.
        assert rec["clause_ref"]["clause_coordinate"] == rec["sut_section_id"]

    def test_tier_3_overridable_recommends_higher_legal_option(self) -> None:
        claim = _claim(facility_tier="egitim_arastirma", claim_type="yatis")
        lines = [
            _proc(
                procedure_code="600150",
                procedure_category="islem",
                expected_payable_try=Decimal("3000"),
            ),
        ]
        result = recommend_billing_strategy_from_claims(_ctx(claim, *lines))
        claim_rec = next(
            rec
            for rec in result.recommendations
            if rec.get("claim_id") == "CLM1" and "recommendation_kind" in rec
        )
        assert claim_rec["payment_method_kind"] == "DRG_OVERRIDABLE"
        assert claim_rec["recommendation_kind"] == "optional_override"
        assert claim_rec["recommendation"] in {"package", "itemized"}
        assert claim_rec["savings_try"] >= 0.0
        # Structured message contract for §2.2.2(2) optional overrides.
        code = claim_rec["message_code"]
        assert code in {
            "claim_optional_package_higher",
            "claim_optional_itemized_higher",
        }
        higher = "package" if code == "claim_optional_package_higher" else "itemized"
        assert claim_rec["recommendation"] == higher
        params = claim_rec["message_params"]
        higher_amount = params["package_total_try" if higher == "package" else "itemized_total_try"]
        lower_amount = params["itemized_total_try" if higher == "package" else "package_total_try"]
        lower = "itemized" if higher == "package" else "package"
        assert claim_rec["detail"] == (
            f"Claim CLM1: optional §2.2.2(2) override — {higher} billing "
            f"({higher_amount} TRY) is the higher legal option vs {lower} "
            f"({lower_amount} TRY)."
        )
        assert claim_rec["clause_ref"]["clause_coordinate"] == "2.2.2.(2)"

    def test_tier_3_starred_code_mandatory_package(self) -> None:
        claim = _claim(facility_tier="egitim_arastirma")
        lines = [
            _proc(
                procedure_code="550970",
                procedure_category="islem",
                expected_payable_try=Decimal("200"),
            ),
        ]
        result = recommend_billing_strategy_from_claims(_ctx(claim, *lines))
        # 550970 is billed as itemized but mandates package → a compliance
        # violation is emitted (no duplicate informational row).
        claim_rec = next(
            rec
            for rec in result.recommendations
            if rec.get("claim_id") == "CLM1"
            and rec.get("procedure_code") == "550970"
            and rec.get("type") == "compliance_violation"
        )
        assert claim_rec["payment_method_kind"] == "DRG_MANDATORY"
        assert claim_rec["mandated_method"] == "package"
        # Structured message contract for the "must use package billing" row.
        assert claim_rec["message_code"] == "procedure_must_package"
        params = claim_rec["message_params"]
        assert params["procedure_code"] == "550970"
        assert params["section"] == claim_rec["sut_section_id"]
        assert params["method"]
        assert claim_rec["detail"] == (
            f"Procedure 550970 must use package billing ({params['method']}) "
            f"per {params['section']}."
        )
        assert claim_rec["clause_ref"]["clause_coordinate"] == params["section"]
        # No informational duplicate should be present for this procedure.
        assert not any(
            rec.get("type") == "informational" and rec.get("procedure_code") == "550970"
            for rec in result.recommendations
        )

    def test_corrective_savings_zero_when_already_compliant(self) -> None:
        claim = _claim(facility_tier="2_basamak_kamu")
        lines = [
            _proc(
                procedure_code="610070",
                procedure_category="paket",
                expected_payable_try=Decimal("4000"),
            ),
        ]
        result = recommend_billing_strategy_from_claims(_ctx(claim, *lines))
        claim_rec = next(
            rec
            for rec in result.recommendations
            if rec.get("claim_id") == "CLM1" and "recommendation_kind" in rec
        )
        assert claim_rec["recommendation"] == "package"
        assert claim_rec["savings_try"] == 0.0
        # Already-compliant claim → claim_package_ok structured message.
        assert claim_rec["message_code"] == "claim_package_ok"
        params = claim_rec["message_params"]
        assert params["claim_id"] == "CLM1"
        assert claim_rec["detail"] == (
            "Claim CLM1 is billed correctly as package per SUT §2.2.2(1). "
            f"Package total {params['amount_try']} TRY."
        )
        assert claim_rec["clause_ref"]["clause_coordinate"] == claim_rec["sut_section_id"]

    def test_compliance_violation_includes_payment_method_kind(self) -> None:
        claim = _claim(facility_tier="2_basamak_kamu")
        lines = [
            _proc(
                procedure_code="610070",
                procedure_category="islem",
                expected_payable_try=Decimal("800"),
            ),
        ]
        result = recommend_billing_strategy_from_claims(_ctx(claim, *lines))
        violations = [
            rec for rec in result.recommendations if rec.get("type") == "compliance_violation"
        ]
        assert len(violations) == 1
        assert violations[0]["payment_method_kind"] == "DRG_MANDATORY"
        assert violations[0]["message_code"] == "procedure_must_package"
        assert violations[0]["message_params"]["procedure_code"] == "610070"

    def test_ek2b_only_claim_billed_itemized_message(self) -> None:
        from src.bilun.domain.prose_rules.catalog_membership import (
            get_ek2b_codes,
            get_ek2c_codes,
        )

        ek2b_only = sorted(get_ek2b_codes() - get_ek2c_codes())
        assert ek2b_only, "catalog must contain EK-2/B-only codes"
        code = ek2b_only[0]

        claim = _claim(facility_tier="2_basamak_kamu")
        lines = [
            _proc(
                procedure_code=code,
                procedure_category="islem",
                expected_payable_try=Decimal("700"),
            ),
        ]
        result = recommend_billing_strategy_from_claims(_ctx(claim, *lines))
        claim_rec = next(
            rec
            for rec in result.recommendations
            if rec.get("claim_id") == "CLM1" and "recommendation" in rec
        )
        assert claim_rec["payment_method_kind"] == "ITEMIZED"
        assert claim_rec["recommendation"] == "itemized"
        assert claim_rec["recommendation_kind"] == "mandatory_compliance"
        # Already billed itemized → claim_itemized_ok structured message.
        assert claim_rec["message_code"] == "claim_itemized_ok"
        params = claim_rec["message_params"]
        assert params["claim_id"] == "CLM1"
        assert claim_rec["detail"] == (
            f"Claim CLM1 is billed correctly as itemized per SUT §2.2. "
            f"Itemized total {params['amount_try']} TRY."
        )
        assert claim_rec["clause_ref"]["clause_coordinate"] == claim_rec["sut_section_id"]

    def test_ek2b_only_claim_billed_package_messages(self) -> None:
        from src.bilun.domain.prose_rules.catalog_membership import (
            get_ek2b_codes,
            get_ek2c_codes,
        )

        ek2b_only = sorted(get_ek2b_codes() - get_ek2c_codes())
        assert ek2b_only, "catalog must contain EK-2/B-only codes"
        code = ek2b_only[0]

        claim = _claim(facility_tier="2_basamak_kamu")
        lines = [
            _proc(
                procedure_code=code,
                procedure_category="paket",
                expected_payable_try=Decimal("700"),
            ),
        ]
        result = recommend_billing_strategy_from_claims(_ctx(claim, *lines))
        claim_rec = next(
            rec
            for rec in result.recommendations
            if rec.get("claim_id") == "CLM1" and "recommendation" in rec
        )
        assert claim_rec["payment_method_kind"] == "ITEMIZED"
        assert claim_rec["recommendation"] == "itemized"
        # Billed as package → claim_mandate_itemized structured message.
        assert claim_rec["message_code"] == "claim_mandate_itemized"
        params = claim_rec["message_params"]
        assert claim_rec["detail"] == (
            f"SUT §2.2 mandates itemized billing for claim CLM1. "
            f"Itemized total {params['itemized_total_try']} TRY vs package "
            f"{params['package_total_try']} TRY."
        )
        # The same line also emits the procedure_must_itemized violation row.
        violation = next(
            rec for rec in result.recommendations if rec.get("type") == "compliance_violation"
        )
        assert violation["message_code"] == "procedure_must_itemized"
        vparams = violation["message_params"]
        assert vparams["procedure_code"] == code
        assert vparams["section"] == violation["sut_section_id"]
        assert vparams["method"]
        assert violation["detail"] == (
            f"Procedure {code} must use itemized billing ({vparams['method']}) "
            f"per {vparams['section']}."
        )

    def test_itemized_totals_exclude_payment_method_violation(self) -> None:
        claim = _claim(
            facility_tier="2_basamak_kamu",
            claim_type="yatis",
            admission_date=date(2023, 10, 6),
            discharge_date=date(2023, 10, 13),
            claim_start_date=date(2023, 10, 6),
            claim_end_date=date(2023, 10, 13),
            primary_icd10="C92.0",
            scenario_tag="payment_method_compliance_demo",
        )
        lines = [
            _proc(
                procedure_line_id="PL-M",
                procedure_code="700390",
                procedure_specialty_code="same-specialty",
                procedure_category="muayene",
                expected_payable_try=Decimal("17.11"),
            ),
            _proc(
                procedure_line_id="PL-B",
                procedure_code="612070",
                procedure_category="yatak",
                quantity=7,
                expected_payable_try=Decimal("2337.01"),
            ),
            _proc(
                procedure_line_id="PL-L",
                procedure_code="L116470",
                procedure_specialty_code="same-specialty",
                procedure_category="laboratuvar",
                expected_payable_try=Decimal("107.55"),
            ),
            _proc(
                procedure_line_id="PL-I",
                procedure_code="G100580",
                procedure_specialty_code="same-specialty",
                procedure_category="islem",
                expected_payable_try=Decimal("1848.56"),
            ),
            _proc(
                procedure_line_id="PL-P",
                procedure_code="P615440",
                procedure_category="paket",
                expected_payable_try=Decimal("61956.35"),
            ),
        ]
        result = recommend_billing_strategy_from_claims(_ctx(claim, *lines))
        claim_rec = next(
            rec
            for rec in result.recommendations
            if rec.get("claim_id") == "CLM1" and "itemized_raw_try" in rec
        )
        assert claim_rec["itemized_raw_try"] == 1973.22
        # #261: exam, lab and genetic-test lines are not session operations, so
        # no session factor applies (was 1848.56 + (17.11 + 107.55) × 30%).
        assert claim_rec["itemized_total_try"] == 1973.22
        assert claim_rec["itemized_excluded_violation_count"] == 1
        assert claim_rec["itemized_excluded_procedure_codes"] == ["612070"]
        violations = [
            rec for rec in result.recommendations if rec.get("type") == "compliance_violation"
        ]
        assert any(v.get("procedure_code") == "612070" for v in violations)

    def test_tier_3_overridable_side_line_stays_in_itemized_total(self) -> None:
        claim = _claim(
            facility_tier="egitim_arastirma",
            claim_type="yatis",
            admission_date=date(2023, 10, 6),
            discharge_date=date(2023, 10, 8),
            claim_start_date=date(2023, 10, 6),
            claim_end_date=date(2023, 10, 8),
        )
        lines = [
            _proc(
                procedure_line_id="PL-O",
                procedure_code="600150",
                procedure_category="islem",
                expected_payable_try=Decimal("3000"),
            ),
            _proc(
                procedure_line_id="PL-P",
                procedure_code="P615440",
                procedure_category="paket",
                expected_payable_try=Decimal("50000"),
            ),
        ]
        result = recommend_billing_strategy_from_claims(_ctx(claim, *lines))
        claim_rec = next(
            rec
            for rec in result.recommendations
            if rec.get("claim_id") == "CLM1" and "itemized_raw_try" in rec
        )
        assert claim_rec["itemized_excluded_violation_count"] == 0
        assert claim_rec["itemized_raw_try"] == 3000.0

    def test_spot_check_showcase_package_bill_has_no_price_comparison(self) -> None:
        """Golden check on S5, the cemented hemiarthroplasty billed as its package: a mandated
        package that is billed correctly is confirmed in plain words, with no price comparison."""
        from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset

        role = cohort.role("showcase_S5")
        dataset = load_sut_claim_dataset()
        ctx = build_patient_claim_context(role.patient_id, dataset)
        assert ctx is not None
        # The premise: one package line, so the package total is that line's billed amount.
        package_lines = [line for line in ctx.procedure_lines if line.procedure_category == "paket"]
        assert len(package_lines) == 1
        amount = f"{package_lines[0].billed_amount_try:.2f}"

        result = recommend_billing_strategy_from_claims(ctx)
        claim_rec = next(
            rec
            for rec in result.recommendations
            if rec.get("claim_id") == role.claim_id
            and "recommendation" in rec
            and rec.get("payment_method_kind") == "DRG_MANDATORY"
        )
        assert claim_rec["recommendation"] == "package"
        assert "lower than" not in claim_rec["detail"]
        # Golden check: the structured contract does not alter the detail byte.
        assert claim_rec["message_code"] == "claim_package_ok"
        assert claim_rec["message_params"] == {
            "claim_id": role.claim_id,
            "amount_try": amount,
        }
        assert claim_rec["detail"] == (
            f"Claim {role.claim_id} is billed correctly as package "
            f"per SUT §2.2.2(1). Package total {amount} TRY."
        )

    def test_package_only_submission_resolves_catalog_itemized_alternative(self) -> None:
        claim = _claim(
            facility_tier="egitim_arastirma",
            claim_type="yatis",
            admission_date=date(2024, 3, 12),
            discharge_date=date(2024, 3, 14),
            claim_start_date=date(2024, 3, 12),
            claim_end_date=date(2024, 3, 14),
            scenario_tag="",
        )
        lines = [
            _proc(
                procedure_code="609270",
                procedure_category="paket",
                procedure_date=date(2024, 3, 12),
                unit_price_try=Decimal("2000.00"),
                billed_amount_try=Decimal("2000.00"),
                expected_payable_try=Decimal("2000.00"),
                package_code="609270",
            ),
        ]
        result = recommend_billing_strategy_from_claims(_ctx(claim, *lines))
        claim_rec = next(
            rec
            for rec in result.recommendations
            if rec.get("claim_id") == "CLM1"
            and rec.get("recommendation_kind") == "optional_override"
        )
        assert claim_rec["itemized_price_methodology"] == "ek2b_catalog"
        assert claim_rec["itemized_total_try"] == pytest.approx(3038.16)
        assert claim_rec["package_total_try"] == pytest.approx(2000.00)
        assert claim_rec["recommendation"] == "itemized"
        assert claim_rec["savings_try"] == pytest.approx(1038.16)

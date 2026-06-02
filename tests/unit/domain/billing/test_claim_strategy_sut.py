"""Unit tests for SUT-compliant claim-level billing strategy (Phase 4)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.claim_strategy import recommend_billing_strategy_from_claims
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext

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
        claim_rec = next(
            rec
            for rec in result.recommendations
            if rec.get("claim_id") == "CLM1" and "recommendation_kind" in rec
        )
        assert claim_rec["payment_method_kind"] == "DRG_MANDATORY"
        assert claim_rec["recommendation"] == "package"

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

    def test_spot_check_sentetik_0003_011_no_price_comparison(self) -> None:
        from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset

        dataset = load_sut_claim_dataset()
        ctx = build_patient_claim_context("SENTETIK-HASTA-0003", dataset)
        assert ctx is not None

        result = recommend_billing_strategy_from_claims(ctx)
        claim_rec = next(
            rec
            for rec in result.recommendations
            if rec.get("claim_id") == "F-SENTETIK-HASTA-0003-011"
            and "recommendation_kind" in rec
        )
        assert claim_rec["recommendation"] == "package"
        assert claim_rec["recommendation_kind"] == "mandatory_compliance"
        assert claim_rec["payment_method_kind"] == "DRG_MANDATORY"
        assert "lower than" not in claim_rec["detail"]

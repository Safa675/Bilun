"""Phase 1.3 — §2.2.2(2) optional override metadata and recoverable uplift."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.claim_strategy import recommend_billing_strategy_from_claims
from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.types import SAVINGS_BASIS_OPTIONAL_OVERRIDE, SAVINGS_CATEGORY_SGK_UPLIFT

pytestmark = pytest.mark.unit


def _claim(**overrides) -> ClaimHeader:
    base = dict(
        claim_id="CLM-OVERRIDE",
        patient_id="P1",
        episode_id="E1",
        claim_type="yatis",
        facility_tier="egitim_arastirma",
        provider_type="Universite",
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
        scenario_tag="sgk_optional_override_itemized_higher",
    )
    base.update(overrides)
    return ClaimHeader(**base)


def _proc(**overrides) -> ProcedureClaimLine:
    base = dict(
        procedure_line_id="PL1",
        claim_id="CLM-OVERRIDE",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 10),
        procedure_code="600150",
        procedure_name="Override procedure A",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("5000"),
        billed_amount_try=Decimal("0"),
        expected_payable_try=Decimal("5000"),
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


class TestOptionalOverrideSurfacing:
    def test_override_row_metadata_when_itemized_higher_than_package(self) -> None:
        claim = _claim()
        lines = [
            _proc(
                procedure_code="600150",
                expected_payable_try=Decimal("5000"),
                billed_amount_try=Decimal("0"),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="600160",
                procedure_name="Override procedure B",
                expected_payable_try=Decimal("4000"),
                billed_amount_try=Decimal("0"),
            ),
            _proc(
                procedure_line_id="PL3",
                procedure_code="609270",
                procedure_name="Package line",
                procedure_category="paket",
                expected_payable_try=Decimal("3500"),
                billed_amount_try=Decimal("3500"),
            ),
        ]
        result = recommend_billing_strategy_from_claims(_ctx(claim, *lines))
        override = next(
            rec
            for rec in result.recommendations
            if rec.get("recommendation_kind") == "optional_override"
        )
        assert override["payment_method_kind"] == "DRG_OVERRIDABLE"
        assert override["savings_basis"] == SAVINGS_BASIS_OPTIONAL_OVERRIDE
        assert override["savings_category"] == SAVINGS_CATEGORY_SGK_UPLIFT
        assert override["savings_try"] > 0
        assert result.optional_override_uplift_try == override["savings_try"]

    def test_compliant_override_choice_has_zero_recoverable_uplift(self) -> None:
        claim = _claim()
        lines = [
            _proc(
                procedure_code="600150",
                expected_payable_try=Decimal("2000"),
                billed_amount_try=Decimal("2000"),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="600160",
                procedure_name="Override procedure B",
                expected_payable_try=Decimal("1500"),
                billed_amount_try=Decimal("1500"),
            ),
            _proc(
                procedure_line_id="PL3",
                procedure_code="609270",
                procedure_name="Package line",
                procedure_category="paket",
                expected_payable_try=Decimal("9000"),
                billed_amount_try=Decimal("9000"),
            ),
        ]
        result = recommend_billing_strategy_from_claims(_ctx(claim, *lines))
        override = next(
            rec
            for rec in result.recommendations
            if rec.get("recommendation_kind") == "optional_override"
        )
        assert override["recommendation"] == "package"
        assert override["current_billing"] == "package"
        assert override["savings_try"] == 0.0
        assert result.optional_override_uplift_try == 0.0

    def test_override_uplift_in_sgk_headline(self) -> None:
        claim = _claim()
        lines = [
            _proc(
                procedure_code="600150",
                expected_payable_try=Decimal("5000"),
                billed_amount_try=Decimal("0"),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="600160",
                procedure_name="Override procedure B",
                expected_payable_try=Decimal("4000"),
                billed_amount_try=Decimal("0"),
            ),
            _proc(
                procedure_line_id="PL3",
                procedure_code="609270",
                procedure_name="Package line",
                procedure_category="paket",
                expected_payable_try=Decimal("3500"),
                billed_amount_try=Decimal("3500"),
            ),
        ]
        ctx = _ctx(claim, *lines)
        report = compute_patient_billing_report(
            "P1",
            claim_context=ctx,
            copay_exemption={"exempt": False},
            chapters={"I"},
        )
        assert report.billing_strategy.optional_override_uplift_try > 0
        assert report.sgk_uplift_try >= report.billing_strategy.optional_override_uplift_try

"""Wiring tests for DRG package adequacy review billing block."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.bilun.domain.billing.claim_drg_package_adequacy import (
    recommend_drg_package_adequacy_from_claims,
)
from src.bilun.domain.billing.types import EXACTNESS_STATUS_EXACT
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext


def _ctx() -> PatientClaimContext:
    claim = ClaimHeader(
        claim_id="F-DEMO-001",
        patient_id="P1",
        episode_id="E1",
        claim_type="yatis",
        facility_tier="egitim_arastirma",
        provider_type="Universite",
        department="Genel",
        admission_date=date(2024, 6, 1),
        discharge_date=date(2024, 6, 5),
        claim_start_date=date(2024, 6, 1),
        claim_end_date=date(2024, 6, 5),
        primary_icd10="K50.9",
        expected_total_billed_try=Decimal("13500.00"),
        expected_total_payable_try=Decimal("12000.00"),
        expected_denial_reason="",
        scenario_tag="sgk_package_adequacy_undercoded",
    )
    lines = (
        ProcedureClaimLine(
            procedure_line_id="ISL-1",
            claim_id="F-DEMO-001",
            patient_id="P1",
            episode_id="E1",
            procedure_date=date(2024, 6, 1),
            procedure_code="600150",
            procedure_name="A",
            procedure_category="islem",
            quantity=1,
            unit_price_try=Decimal("5000.00"),
            billed_amount_try=Decimal("5000.00"),
            expected_payable_try=Decimal("4500.00"),
            is_package_included=False,
            package_code="",
            surcharge_applicable=False,
            copay_rate_applicable=False,
            denial_reason_expected="",
            rule_trace_expected="",
        ),
        ProcedureClaimLine(
            procedure_line_id="ISL-2",
            claim_id="F-DEMO-001",
            patient_id="P1",
            episode_id="E1",
            procedure_date=date(2024, 6, 1),
            procedure_code="600160",
            procedure_name="B",
            procedure_category="islem",
            quantity=1,
            unit_price_try=Decimal("4000.00"),
            billed_amount_try=Decimal("4000.00"),
            expected_payable_try=Decimal("3600.00"),
            is_package_included=False,
            package_code="",
            surcharge_applicable=False,
            copay_rate_applicable=False,
            denial_reason_expected="",
            rule_trace_expected="",
        ),
        ProcedureClaimLine(
            procedure_line_id="ISL-3",
            claim_id="F-DEMO-001",
            patient_id="P1",
            episode_id="E1",
            procedure_date=date(2024, 6, 1),
            procedure_code="609270",
            procedure_name="Pkg",
            procedure_category="paket",
            quantity=1,
            unit_price_try=Decimal("3500.00"),
            billed_amount_try=Decimal("3500.00"),
            expected_payable_try=Decimal("3500.00"),
            is_package_included=False,
            package_code="609270",
            surcharge_applicable=False,
            copay_rate_applicable=False,
            denial_reason_expected="",
            rule_trace_expected="",
        ),
    )
    return PatientClaimContext(
        patient_id="P1",
        claims=(claim,),
        procedure_lines=lines,
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


class TestDrgPackageAdequacyWiring:
    def test_recommend_returns_review_opportunity(self) -> None:
        block = recommend_drg_package_adequacy_from_claims(_ctx())
        assert block.exactness_status == EXACTNESS_STATUS_EXACT
        assert len(block.opportunities) == 1
        assert block.confirmed_uplift_try == 0.0
        assert block.review_uplift_try >= 0.0

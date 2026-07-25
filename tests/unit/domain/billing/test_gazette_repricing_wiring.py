"""Wiring tests for gazette repricing billing block."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.bilun.domain.billing.claim_gazette_repricing import (
    recommend_gazette_repricing_from_claims,
)
from src.bilun.domain.billing.types import EXACTNESS_STATUS_EXACT
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from tests.unit._helpers.catalog_stubs import (
    FIXTURE_GAZETTE_SERVICE_TRY,
    install_gazette_price_stub,
)

import pytest

@pytest.fixture(autouse=True)
def _stub_gazette(monkeypatch):
    return install_gazette_price_stub(monkeypatch)



def _ctx() -> PatientClaimContext:
    # Service date within 30 days of the 2026-01-01 tebliğ (2025-12-02 = 30 days).
    claim = ClaimHeader(
        claim_id="F-DEMO-001",
        patient_id="P1",
        episode_id="E1",
        claim_type="poliklinik",
        facility_tier="2_basamak_kamu",
        provider_type="Kamu",
        department="Genel",
        admission_date=None,
        discharge_date=None,
        claim_start_date=date(2025, 12, 2),
        claim_end_date=date(2025, 12, 2),
        primary_icd10="L98.9",
        package_candidate=False,
        expected_total_billed_try=Decimal(str(FIXTURE_GAZETTE_SERVICE_TRY)),
        expected_total_payable_try=Decimal(str(FIXTURE_GAZETTE_SERVICE_TRY)),
        expected_denial_reason="",
        scenario_tag="sgk_gazette_repricing_600150",
    )
    line = ProcedureClaimLine(
        procedure_line_id="ISL-1",
        claim_id="F-DEMO-001",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2025, 12, 2),
        procedure_code="600150",
        procedure_name="Proc",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal(str(FIXTURE_GAZETTE_SERVICE_TRY)),
        billed_amount_try=Decimal(str(FIXTURE_GAZETTE_SERVICE_TRY)),
        expected_payable_try=Decimal(str(FIXTURE_GAZETTE_SERVICE_TRY)),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    return PatientClaimContext(
        patient_id="P1",
        claims=(claim,),
        procedure_lines=(line,),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


class TestGazetteRepricingWiring:
    def test_recommend_returns_review_opportunity(self, _stub_gazette) -> None:
        _stub = _stub_gazette
        block = recommend_gazette_repricing_from_claims(_ctx())
        assert block.exactness_status == EXACTNESS_STATUS_EXACT
        assert len(block.opportunities) == 1
        assert block.confirmed_repricing_try == 0.0
        assert block.review_repricing_try == pytest.approx(float(_stub['recoverable']), abs=0.01)

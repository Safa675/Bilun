"""Wiring tests for procedure capture gap billing block."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.bilun.domain.billing.claim_procedure_capture_gap import (
    recommend_procedure_capture_gap_from_claims,
)
from src.bilun.domain.billing.orchestrator import _dedupe_addon_against_capture
from src.bilun.domain.billing.types import (
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_NOT_APPLICABLE,
    ProcedureAddonUplift,
    ProcedureCaptureGap,
)
from src.bilun.domain.claims.models import (
    ClaimHeader,
    PerformedProcedureLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext


def _ctx_with_performed() -> PatientClaimContext:
    claim = ClaimHeader(
        claim_id="F-DEMO-001",
        patient_id="P1",
        episode_id="E1",
        claim_type="gunubirlik",
        facility_tier="egitim_arastirma",
        provider_type="Universite",
        department="Gastro",
        admission_date=date(2024, 6, 1),
        discharge_date=date(2024, 6, 1),
        claim_start_date=date(2024, 6, 1),
        claim_end_date=date(2024, 6, 1),
        primary_icd10="K50.9",
        package_candidate=False,
        expected_total_billed_try=Decimal("1200.00"),
        expected_total_payable_try=Decimal("1080.00"),
        expected_denial_reason="",
        scenario_tag="sgk_procedure_capture_kolonoskopi",
    )
    proc = ProcedureClaimLine(
        procedure_line_id="ISL-1",
        claim_id="F-DEMO-001",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2024, 6, 1),
        procedure_code="701450",
        procedure_name="Kolonoskopi",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("1200.00"),
        billed_amount_try=Decimal("1200.00"),
        expected_payable_try=Decimal("1080.00"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    performed = PerformedProcedureLine(
        performed_line_id="EMR-1",
        claim_id="F-DEMO-001",
        patient_id="P1",
        episode_id="E1",
        service_date=date(2024, 6, 1),
        procedure_code="701460",
        procedure_name="Polipektomi",
        source="emr",
    )
    return PatientClaimContext(
        patient_id="P1",
        claims=(claim,),
        procedure_lines=(proc,),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
        performed_procedure_lines=(performed,),
    )


class TestProcedureCaptureWiring:
    def test_missing_emr_returns_not_applicable(self) -> None:
        ctx = _ctx_with_performed()
        ctx = PatientClaimContext(
            patient_id=ctx.patient_id,
            claims=ctx.claims,
            procedure_lines=ctx.procedure_lines,
            material_lines=ctx.material_lines,
            drug_lines=ctx.drug_lines,
            diagnoses=ctx.diagnoses,
            performed_procedure_lines=(),
        )
        block = recommend_procedure_capture_gap_from_claims(ctx)
        assert block.exactness_status == EXACTNESS_STATUS_NOT_APPLICABLE
        assert block.opportunities == []

    def test_recommend_returns_exact_with_opportunity(self) -> None:
        block = recommend_procedure_capture_gap_from_claims(_ctx_with_performed())
        assert block.exactness_status == EXACTNESS_STATUS_EXACT
        assert len(block.opportunities) == 1
        assert block.confirmed_gap_try > 0

    def test_dedupe_removes_matching_addon(self) -> None:
        capture = ProcedureCaptureGap(
            opportunities=[
                {
                    "claim_id": "F-DEMO-001",
                    "procedure_code": "701460",
                    "service_date": "2024-06-01",
                    "recoverable_gap_try": 500.0,
                }
            ],
            exactness_status=EXACTNESS_STATUS_EXACT,
        )
        addon = ProcedureAddonUplift(
            opportunities=[
                {
                    "claim_id": "F-DEMO-001",
                    "expected_addon_procedure_code": "701460",
                    "session_date": "2024-06-01",
                    "recoverable_uplift_try": 360.0,
                    "included_in_sgk_total": True,
                }
            ],
            exactness_status=EXACTNESS_STATUS_EXACT,
        )
        deduped = _dedupe_addon_against_capture(addon, capture)
        assert deduped.opportunities == []
        assert deduped.confirmed_uplift_try == 0.0

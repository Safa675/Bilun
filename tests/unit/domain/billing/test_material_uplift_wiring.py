"""Phase 2.1 — missing billable material uplift wiring."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.claim_material_uplift import recommend_material_uplift_from_claims
from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims.models import ClaimHeader, MaterialClaimLine, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext

pytestmark = pytest.mark.unit


def _claim(**overrides) -> ClaimHeader:
    base = dict(
        claim_id="CLM-MAT",
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
        package_candidate=False,
        expected_total_billed_try=Decimal("5000"),
        expected_total_payable_try=Decimal("5000"),
        expected_denial_reason="",
        scenario_tag="sgk_material_uplift_yatis",
    )
    base.update(overrides)
    return ClaimHeader(**base)


def _proc(**overrides) -> ProcedureClaimLine:
    base = dict(
        procedure_line_id="PL1",
        claim_id="CLM-MAT",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 10),
        procedure_code="600150",
        procedure_name="Pairing procedure",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("4500"),
        billed_amount_try=Decimal("4500"),
        expected_payable_try=Decimal("4500"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    base.update(overrides)
    return ProcedureClaimLine(**base)


def _ctx(claim: ClaimHeader, *lines: ProcedureClaimLine, materials=()) -> PatientClaimContext:
    return PatientClaimContext(
        patient_id=claim.patient_id,
        claims=(claim,),
        procedure_lines=tuple(lines),
        material_lines=tuple(materials),
        drug_lines=(),
        diagnoses=(),
    )


class TestMaterialUpliftWiring:
    def test_missing_material_counts_in_sgk_headline(self) -> None:
        claim = _claim()
        lines = [_proc()]
        ctx = _ctx(claim, *lines)
        uplift = recommend_material_uplift_from_claims(ctx)
        assert len(uplift.opportunities) == 1
        assert uplift.confirmed_uplift_try == pytest.approx(667.01, rel=0.01)
        assert uplift.opportunities[0]["material_code"] == "OR2640"

        report = compute_patient_billing_report(
            "P1",
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )
        assert report.material_uplift.confirmed_uplift_try == uplift.confirmed_uplift_try
        assert report.sgk_uplift_try >= uplift.confirmed_uplift_try

    def test_fully_billed_material_suppresses_uplift(self) -> None:
        claim = _claim()
        proc = _proc()
        material = MaterialClaimLine(
            material_line_id="ML1",
            claim_id="CLM-MAT",
            procedure_line_id="PL1",
            patient_id="P1",
            material_date=date(2026, 1, 10),
            material_code="OR2640",
            material_name="Expected material",
            material_type="genel",
            specialty_category="genel",
            quantity=1,
            unit_price_try=Decimal("667.01"),
            billed_amount_try=Decimal("667.01"),
            expected_payable_try=Decimal("667.01"),
            is_bundled=False,
            requires_pre_auth=False,
            denial_reason_expected="",
            rule_trace_expected="",
        )
        ctx = _ctx(claim, proc, materials=(material,))
        uplift = recommend_material_uplift_from_claims(ctx)
        assert uplift.opportunities == []
        assert uplift.confirmed_uplift_try == 0.0

    def test_partial_material_billing_counts_gap_only(self) -> None:
        claim = _claim()
        proc = _proc()
        material = MaterialClaimLine(
            material_line_id="ML1",
            claim_id="CLM-MAT",
            procedure_line_id="PL1",
            patient_id="P1",
            material_date=date(2026, 1, 10),
            material_code="OR2640",
            material_name="Expected material",
            material_type="genel",
            specialty_category="genel",
            quantity=1,
            unit_price_try=Decimal("100"),
            billed_amount_try=Decimal("100"),
            expected_payable_try=Decimal("100"),
            is_bundled=False,
            requires_pre_auth=False,
            denial_reason_expected="",
            rule_trace_expected="",
        )
        ctx = _ctx(claim, proc, materials=(material,))
        uplift = recommend_material_uplift_from_claims(ctx)
        assert len(uplift.opportunities) == 1
        assert uplift.confirmed_uplift_try == pytest.approx(567.01, rel=0.01)

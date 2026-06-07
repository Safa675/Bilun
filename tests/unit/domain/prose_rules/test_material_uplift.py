"""Unit tests for missing billable material detector."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, MaterialClaimLine, ProcedureClaimLine
from src.bilun.domain.prose_rules.material_uplift import (
    detect_missing_billable_material_opportunities,
)

pytestmark = pytest.mark.unit


def _claim() -> ClaimHeader:
    return ClaimHeader(
        claim_id="C1",
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
        expected_total_billed_try=Decimal("1000"),
        expected_total_payable_try=Decimal("1000"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _proc(**overrides) -> ProcedureClaimLine:
    base = dict(
        procedure_line_id="PL1",
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 10),
        procedure_code="600150",
        procedure_name="Test",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
        expected_payable_try=Decimal("1000"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    base.update(overrides)
    return ProcedureClaimLine(**base)


def test_detects_missing_or2640_for_procedure_600150() -> None:
    claim = _claim()
    proc = _proc()
    rows = detect_missing_billable_material_opportunities(claim, [proc], [])
    assert len(rows) == 1
    assert rows[0]["recoverable_uplift_try"] > 0


def test_coronary_stent_specialty_pairing() -> None:
    claim = _claim()
    proc = _proc(
        procedure_code="700910",
        procedure_name="PTCA and stent",
    )
    rows = detect_missing_billable_material_opportunities(claim, [proc], [])
    assert len(rows) == 1
    assert rows[0]["material_code"] == "KR1151"
    assert rows[0]["pairing_mode"] == "specialty_annex"
    assert rows[0]["recoverable_uplift_try"] == pytest.approx(2890.39, rel=0.01)


def test_tavi_valve_specialty_pairing() -> None:
    claim = _claim()
    proc = _proc(
        procedure_code="700944",
        procedure_name="TAVI",
    )
    rows = detect_missing_billable_material_opportunities(claim, [proc], [])
    assert len(rows) == 1
    assert rows[0]["material_code"] == "KV1012"
    assert rows[0]["specialty_annex"] == "EK-3I"
    assert rows[0]["recoverable_uplift_try"] > 100000


def test_partial_material_billing_emits_gap_uplift() -> None:
    claim = _claim()
    proc = _proc()
    material = MaterialClaimLine(
        material_line_id="ML1",
        claim_id="C1",
        procedure_line_id="PL1",
        patient_id="P1",
        material_date=date(2026, 1, 10),
        material_code="OR2640",
        material_name="Material",
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
    rows = detect_missing_billable_material_opportunities(claim, [proc], [material])
    assert len(rows) == 1
    assert rows[0]["actual_billed_try"] == 100.0
    assert rows[0]["recoverable_uplift_try"] == pytest.approx(
        rows[0]["ceiling_try"] - 100.0, rel=0.01
    )


def test_unlinked_material_on_claim_does_not_suppress_uplift() -> None:
    claim = _claim()
    proc = _proc()
    other_proc = _proc(procedure_line_id="PL2", procedure_code="600160")
    material = MaterialClaimLine(
        material_line_id="ML1",
        claim_id="C1",
        procedure_line_id="PL2",
        patient_id="P1",
        material_date=date(2026, 1, 10),
        material_code="OR2640",
        material_name="Material",
        material_type="genel",
        specialty_category="genel",
        quantity=1,
        unit_price_try=Decimal("667"),
        billed_amount_try=Decimal("667"),
        expected_payable_try=Decimal("667"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    rows = detect_missing_billable_material_opportunities(
        claim, [proc, other_proc], [material]
    )
    assert len(rows) == 1
    assert rows[0]["procedure_line_id"] == "PL1"


def test_zero_billed_material_still_triggers_uplift() -> None:
    claim = _claim()
    proc = _proc()
    material = MaterialClaimLine(
        material_line_id="ML1",
        claim_id="C1",
        procedure_line_id="PL1",
        patient_id="P1",
        material_date=date(2026, 1, 10),
        material_code="OR2640",
        material_name="Material",
        material_type="genel",
        specialty_category="genel",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("0"),
        expected_payable_try=Decimal("0"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    rows = detect_missing_billable_material_opportunities(claim, [proc], [material])
    assert len(rows) == 1

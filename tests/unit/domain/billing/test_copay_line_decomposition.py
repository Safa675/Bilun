"""Copay waiver uses decomposed katılım payı, not full billed−payable gap."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.claim_copay import optimize_copay_from_claims
from src.bilun.domain.billing.copay_line_waivers import _waivable_copay_parts, waiver_ek1a_muayene
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext

pytestmark = pytest.mark.unit


def _package_line_with_copay_and_surcharge() -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id="PL-PKG",
        claim_id="F-TEST-001",
        patient_id="PT-1",
        episode_id="EP-1",
        procedure_date=date(2026, 3, 10),
        procedure_code="P619390",
        procedure_name="Package procedure",
        procedure_category="paket",
        quantity=1,
        unit_price_try=Decimal("1200.00"),
        billed_amount_try=Decimal("1200.00"),
        expected_payable_try=Decimal("600.00"),
        is_package_included=False,
        package_code="P619390",
        surcharge_applicable=True,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
        copay_rate=Decimal("0.40"),
        surcharge_rate=Decimal("0.20"),
    )


def test_waivable_copay_parts_split_copay_from_ilave() -> None:
    line = _package_line_with_copay_and_surcharge()
    copay, ilave = _waivable_copay_parts(line)

    assert copay == pytest.approx(Decimal("400.00"))
    assert ilave == pytest.approx(Decimal("200.00"))
    assert copay + ilave == pytest.approx(Decimal("600.00"))


def test_ek1a_waiver_carries_ilave_separately() -> None:
    line = ProcedureClaimLine(
        procedure_line_id="PL-MUAYENE",
        claim_id="F-TEST-002",
        patient_id="PT-1",
        episode_id="EP-1",
        procedure_date=date(2026, 3, 10),
        procedure_code="703720",
        procedure_name="Muayene",
        procedure_category="muayene",
        quantity=1,
        unit_price_try=Decimal("120.00"),
        billed_amount_try=Decimal("120.00"),
        expected_payable_try=Decimal("60.00"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=True,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
        copay_rate=Decimal("0.40"),
        surcharge_rate=Decimal("0.20"),
    )
    claim = ClaimHeader(
        claim_id=line.claim_id,
        patient_id=line.patient_id,
        episode_id=line.episode_id,
        claim_type="poliklinik",
        facility_tier="2",
        provider_type="kamu",
        department="onkoloji",
        admission_date=None,
        discharge_date=None,
        claim_start_date=date(2026, 3, 10),
        claim_end_date=date(2026, 3, 10),
        primary_icd10="C83.1",
        package_candidate=False,
        expected_total_billed_try=Decimal("120.00"),
        expected_total_payable_try=Decimal("60.00"),
        expected_denial_reason="",
        scenario_tag="sentetik",
    )

    waiver = waiver_ek1a_muayene(
        line,
        claim,
        {
            "category": "ek1a_chronic",
            "counts_toward_exempt": True,
            "waives_sections": ("1.8.1",),
        },
        has_health_report=True,
    )

    assert waiver is not None
    assert waiver.component_try == pytest.approx(Decimal("40.00"))
    assert waiver.ilave_ucret_try == pytest.approx(Decimal("20.00"))
    correction = waiver.to_rate_correction()
    assert correction["copay_component_try"] == pytest.approx(40.0)
    assert correction["ilave_ucret_try"] == pytest.approx(20.0)


def test_optimize_copay_populates_decomposition_totals() -> None:
    line = _package_line_with_copay_and_surcharge()
    claim = ClaimHeader(
        claim_id=line.claim_id,
        patient_id=line.patient_id,
        episode_id=line.episode_id,
        claim_type="yatis",
        facility_tier="3",
        provider_type="ozel",
        department="ortopedi",
        admission_date=date(2026, 3, 10),
        discharge_date=date(2026, 3, 12),
        claim_start_date=date(2026, 3, 10),
        claim_end_date=date(2026, 3, 12),
        primary_icd10="M17.9",
        package_candidate=True,
        expected_total_billed_try=Decimal("1200.00"),
        expected_total_payable_try=Decimal("600.00"),
        expected_denial_reason="",
        scenario_tag="sentetik",
    )
    ctx = PatientClaimContext(
        patient_id="PT-1",
        claims=(claim,),
        diagnoses=(),
        procedure_lines=(line,),
        material_lines=(),
        drug_lines=(),
    )

    result = optimize_copay_from_claims(
        ctx,
        {
            "exempt": True,
            "qualifying_diagnoses": [{"disease": "Endokrin", "range": "E00-E90"}],
            "exemption_sources": [
                {
                    "category": "ek1a_chronic",
                    "counts_toward_exempt": True,
                    "waives_sections": ("1.8.1",),
                }
            ],
        },
    )

    assert result.patient_copay_try == pytest.approx(400.0)
    assert result.ilave_ucret_total_try == pytest.approx(200.0)
    assert result.line_decomposition_status == "exact"

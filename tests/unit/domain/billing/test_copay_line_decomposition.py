"""Copay waiver uses decomposed katılım payı, not full billed−payable gap."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.claim_copay import optimize_copay_from_claims
from src.bilun.domain.billing.copay_line_waivers import (
    _waivable_copay_parts,
    waiver_composite_procedure,
    waiver_ek1a_muayene,
    waiver_inpatient_drug,
)
from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.sut.clause_reference import RULE_TYPE_COPAY_WAIVER

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

    # Track E clause link + ilave ücret status on the rate correction.
    assert correction["ilave_ucret_status"] == "none"
    clause_ref = correction["clause_ref"]
    assert clause_ref["clause_coordinate"] == "1.8.5.(7)"
    assert clause_ref["clause_key"]  # resolved, non-empty
    assert clause_ref["clause_key"].startswith("1.8.5.(7)#")
    assert clause_ref["rule_type"] == RULE_TYPE_COPAY_WAIVER
    assert clause_ref["annex"] == "EK-1/A"


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


def test_inpatient_drug_waiver_correction_is_drug_prohibited() -> None:
    line = DrugClaimLine(
        drug_claim_line_id="DL-INP",
        prescription_id="RX-INP",
        claim_id="F-TEST-003",
        patient_id="PT-1",
        episode_id="EP-1",
        drug_claim_date=date(2026, 3, 10),
        drug_name="Inpatient Drug",
        drug_code="P-INP",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("100.00"),
        billed_amount_try=Decimal("100.00"),
        expected_payable_try=Decimal("80.00"),
        discount_tier_expected=Decimal("0"),
        denial_reason_expected="",
        rule_trace_expected="",
        copay_rate=Decimal("0.20"),
    )
    claim = ClaimHeader(
        claim_id=line.claim_id,
        patient_id=line.patient_id,
        episode_id=line.episode_id,
        claim_type="yatis",
        facility_tier="2",
        provider_type="kamu",
        department="dahiliye",
        admission_date=date(2026, 3, 10),
        discharge_date=date(2026, 3, 12),
        claim_start_date=date(2026, 3, 10),
        claim_end_date=date(2026, 3, 12),
        primary_icd10="E11.9",
        package_candidate=False,
        expected_total_billed_try=Decimal("100.00"),
        expected_total_payable_try=Decimal("80.00"),
        expected_denial_reason="",
        scenario_tag="sentetik",
    )

    waiver = waiver_inpatient_drug(line, claim)

    assert waiver is not None
    assert waiver.component_try == pytest.approx(Decimal("20.00"))
    correction = waiver.to_rate_correction()

    # Drug waiver rows carry the §1.9.1 + 5510 md.73 prohibition status.
    assert correction["ilave_ucret_status"] == "drug_prohibited"
    ilave_ref = correction["ilave_clause_ref"]
    assert ilave_ref["clause_coordinate"] == "1.9.1"
    assert ilave_ref["clause_key"]  # resolved, non-empty
    assert ilave_ref["statutory_law"] == "5510 Sayılı Kanun Madde 73"

    clause_ref = correction["clause_ref"]
    assert clause_ref["clause_coordinate"] == "1.8.5.(8)"
    assert clause_ref["clause_key"]  # resolved, non-empty
    assert clause_ref["clause_key"].startswith("1.8.5.(8)#")
    assert clause_ref["rule_type"] == RULE_TYPE_COPAY_WAIVER


def test_composite_acil_procedure_waiver_correction_is_emergency_exempt() -> None:
    line = ProcedureClaimLine(
        procedure_line_id="PL-ACIL",
        claim_id="F-TEST-004",
        patient_id="PT-1",
        episode_id="EP-1",
        procedure_date=date(2026, 3, 10),
        procedure_code="520030",
        procedure_name="Acil muayene",
        procedure_category="muayene",
        quantity=1,
        unit_price_try=Decimal("100.00"),
        billed_amount_try=Decimal("100.00"),
        expected_payable_try=Decimal("70.00"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    claim = ClaimHeader(
        claim_id=line.claim_id,
        patient_id=line.patient_id,
        episode_id=line.episode_id,
        claim_type="acil",
        facility_tier="2",
        provider_type="kamu",
        department="acil",
        admission_date=None,
        discharge_date=None,
        claim_start_date=date(2026, 3, 10),
        claim_end_date=date(2026, 3, 10),
        primary_icd10="S06.0",
        package_candidate=False,
        expected_total_billed_try=Decimal("100.00"),
        expected_total_payable_try=Decimal("70.00"),
        expected_denial_reason="",
        scenario_tag="sentetik",
    )

    waiver = waiver_composite_procedure(
        line,
        claim,
        [
            {
                "category": "acil_servis",
                "rule_source": "SUT §1.8.5(5) emergency visit copay waiver",
                "counts_toward_exempt": True,
                "waives_sections": ("1.8.1", "1.8.2", "1.8.3"),
            }
        ],
        {claim.claim_id: {line.procedure_code}},
    )

    assert waiver is not None
    assert waiver.exemption_ground == "composite_acil_servis"
    correction = waiver.to_rate_correction()

    assert correction["ilave_ucret_status"] == "emergency_exempt"
    clause_ref = correction["clause_ref"]
    assert clause_ref["clause_coordinate"] == "1.8.5"
    assert clause_ref["rule_type"] == RULE_TYPE_COPAY_WAIVER

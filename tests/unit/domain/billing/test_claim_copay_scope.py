"""Line-scoped copay waiver scope tests (EK-1A vs §1.8.5(8) vs EK-4/D)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.claim_copay import optimize_copay_from_claims
from src.bilun.domain.claims.models import (
    ClaimDiagnosis,
    ClaimHeader,
    DrugClaimLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext

pytestmark = pytest.mark.unit

_EK1A_EXEMPTION = {
    "exempt": True,
    "partial_exempt": False,
    "has_chronic_health_report": True,
    "qualifying_diagnoses": [
        {
            "icd10": "C83.1",
            "disease": "Yaygın Non-Hodgkin Lenfoma",
            "range": "C81-C96",
        }
    ],
    "exemption_sources": [
        {
            "category": "ek1a_chronic",
            "rule_source": "SUT §1.8.5(7) + EK-1/A chronic disease copay exemptions",
            "counts_toward_exempt": True,
            "waives_sections": ("1.8.1",),
            "evidence": {
                "qualifying_diagnoses": [
                    {
                        "icd10": "C83.1",
                        "disease": "Yaygın Non-Hodgkin Lenfoma",
                        "range": "C81-C96",
                    }
                ]
            },
        }
    ],
}


def _gunubirlik_claim() -> ClaimHeader:
    return ClaimHeader(
        claim_id="F-SENTETIK-HASTA-0039-104",
        patient_id="SENTETIK-HASTA-0039",
        episode_id="B-SENTETIK-HASTA-0039-39",
        claim_type="gunubirlik",
        facility_tier="2",
        provider_type="kamu",
        department="onkoloji",
        admission_date=date(2026, 3, 10),
        discharge_date=date(2026, 3, 10),
        claim_start_date=date(2026, 3, 10),
        claim_end_date=date(2026, 3, 10),
        primary_icd10="C83.1",
        package_candidate=True,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="sentetik",
    )


def _build_0039_104_context() -> PatientClaimContext:
    claim = _gunubirlik_claim()
    return PatientClaimContext(
        patient_id="SENTETIK-HASTA-0039",
        claims=(claim,),
        diagnoses=(
            ClaimDiagnosis(
                diagnosis_id="DX-0039-104",
                claim_id=claim.claim_id,
                patient_id=claim.patient_id,
                episode_id=claim.episode_id,
                icd10_code="C83.1",
                is_primary=True,
                diagnosis_role="primary",
                diagnosis_date=date(2026, 3, 10),
                exemption_eligible=True,
            ),
        ),
        procedure_lines=(
            ProcedureClaimLine(
                procedure_line_id="PL-MUAYENE",
                claim_id=claim.claim_id,
                patient_id=claim.patient_id,
                episode_id=claim.episode_id,
                procedure_date=date(2026, 3, 10),
                procedure_code="703720",
                procedure_name="Muayene",
                procedure_category="muayene",
                quantity=1,
                unit_price_try=Decimal("66.05"),
                billed_amount_try=Decimal("66.05"),
                expected_payable_try=Decimal("52.84"),
                is_package_included=False,
                package_code="",
                surcharge_applicable=False,
                copay_rate_applicable=True,
                denial_reason_expected="",
                rule_trace_expected="",
            ),
            ProcedureClaimLine(
                procedure_line_id="PL-LAB-1",
                claim_id=claim.claim_id,
                patient_id=claim.patient_id,
                episode_id=claim.episode_id,
                procedure_date=date(2026, 3, 10),
                procedure_code="L110580",
                procedure_name="Lab 1",
                procedure_category="laboratuvar",
                quantity=1,
                unit_price_try=Decimal("40"),
                billed_amount_try=Decimal("40"),
                expected_payable_try=Decimal("33.33"),
                is_package_included=False,
                package_code="",
                surcharge_applicable=False,
                copay_rate_applicable=True,
                denial_reason_expected="",
                rule_trace_expected="",
            ),
            ProcedureClaimLine(
                procedure_line_id="PL-LAB-2",
                claim_id=claim.claim_id,
                patient_id=claim.patient_id,
                episode_id=claim.episode_id,
                procedure_date=date(2026, 3, 10),
                procedure_code="L117370",
                procedure_name="Lab 2",
                procedure_category="laboratuvar",
                quantity=1,
                unit_price_try=Decimal("40"),
                billed_amount_try=Decimal("40"),
                expected_payable_try=Decimal("33.34"),
                is_package_included=False,
                package_code="",
                surcharge_applicable=False,
                copay_rate_applicable=True,
                denial_reason_expected="",
                rule_trace_expected="",
            ),
        ),
        material_lines=(),
        drug_lines=(
            DrugClaimLine(
                drug_claim_line_id="DL-ROLA",
                prescription_id="RX-ROLA",
                claim_id=claim.claim_id,
                patient_id=claim.patient_id,
                episode_id=claim.episode_id,
                drug_claim_date=date(2026, 3, 10),
                drug_name="ROLASTYM",
                drug_code="P-ROLA",
                barkod="",
                equivalence_group="",
                quantity=1,
                unit_price_try=Decimal("200"),
                billed_amount_try=Decimal("200"),
                expected_payable_try=Decimal("141.30"),
                discount_tier_expected=Decimal("0"),
                denial_reason_expected="",
                rule_trace_expected="",
            ),
            DrugClaimLine(
                drug_claim_line_id="DL-MODI",
                prescription_id="RX-MODI",
                claim_id=claim.claim_id,
                patient_id=claim.patient_id,
                episode_id=claim.episode_id,
                drug_claim_date=date(2026, 3, 10),
                drug_name="MODIOGEN",
                drug_code="P-MODI",
                barkod="",
                equivalence_group="",
                quantity=1,
                unit_price_try=Decimal("800"),
                billed_amount_try=Decimal("800"),
                expected_payable_try=Decimal("581.57"),
                discount_tier_expected=Decimal("0"),
                denial_reason_expected="",
                rule_trace_expected="",
            ),
            DrugClaimLine(
                drug_claim_line_id="DL-KADC",
                prescription_id="RX-KADC",
                claim_id=claim.claim_id,
                patient_id=claim.patient_id,
                episode_id=claim.episode_id,
                drug_claim_date=date(2026, 3, 10),
                drug_name="KADCYLA",
                drug_code="P-KADC",
                barkod="",
                equivalence_group="",
                quantity=1,
                unit_price_try=Decimal("50"),
                billed_amount_try=Decimal("50"),
                expected_payable_try=Decimal("35.70"),
                discount_tier_expected=Decimal("0"),
                denial_reason_expected="",
                rule_trace_expected="",
            ),
            DrugClaimLine(
                drug_claim_line_id="DL-ZINC",
                prescription_id="RX-ZINC",
                claim_id=claim.claim_id,
                patient_id=claim.patient_id,
                episode_id=claim.episode_id,
                drug_claim_date=date(2026, 3, 10),
                drug_name="ZINCOPLEX",
                drug_code="P-ZINC",
                barkod="",
                equivalence_group="",
                quantity=1,
                unit_price_try=Decimal("500"),
                billed_amount_try=Decimal("500"),
                expected_payable_try=Decimal("348.67"),
                discount_tier_expected=Decimal("0"),
                denial_reason_expected="",
                rule_trace_expected="",
            ),
        ),
    )


def test_sentetik_0039_104_equivalent() -> None:
    result = optimize_copay_from_claims(_build_0039_104_context(), _EK1A_EXEMPTION)

    # Günübirlik muayene is excluded from EK-1A; labs never qualify.
    assert result.visit_copay_savings_try == 0.0
    assert result.rx_copay_savings_try == pytest.approx(442.76)
    assert result.rx_copay_savings_by_ground == {
        "inpatient_drug_1_8_5_8": pytest.approx(442.76),
    }

    drug_rows = [
        row
        for row in result.rate_corrections
        if row.get("exemption_ground") == "inpatient_drug_1_8_5_8"
    ]
    assert len(drug_rows) == 4
    assert all(row.get("copay_component_try", 0) > 0 for row in drug_rows)
    assert "ek1a_chronic" not in str(result.rx_copay_savings_by_ground)


def test_ek1a_excludes_labs() -> None:
    claim = ClaimHeader(
        claim_id="C-POLI",
        patient_id="P1",
        episode_id="E1",
        claim_type="poliklinik",
        facility_tier="2",
        provider_type="kamu",
        department="",
        admission_date=None,
        discharge_date=None,
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 1),
        primary_icd10="E11.9",
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test",
    )
    ctx = PatientClaimContext(
        patient_id="P1",
        claims=(claim,),
        procedure_lines=(
            ProcedureClaimLine(
                procedure_line_id="PL-LAB",
                claim_id=claim.claim_id,
                patient_id="P1",
                episode_id="E1",
                procedure_date=date(2026, 1, 1),
                procedure_code="L110580",
                procedure_name="Lab",
                procedure_category="laboratuvar",
                quantity=1,
                unit_price_try=Decimal("40"),
                billed_amount_try=Decimal("40"),
                expected_payable_try=Decimal("30"),
                is_package_included=False,
                package_code="",
                surcharge_applicable=False,
                copay_rate_applicable=True,
                denial_reason_expected="",
                rule_trace_expected="",
            ),
            ProcedureClaimLine(
                procedure_line_id="PL-MUAYENE",
                claim_id=claim.claim_id,
                patient_id="P1",
                episode_id="E1",
                procedure_date=date(2026, 1, 1),
                procedure_code="703720",
                procedure_name="Muayene",
                procedure_category="muayene",
                quantity=1,
                unit_price_try=Decimal("100"),
                billed_amount_try=Decimal("100"),
                expected_payable_try=Decimal("80"),
                is_package_included=False,
                package_code="",
                surcharge_applicable=False,
                copay_rate_applicable=True,
                denial_reason_expected="",
                rule_trace_expected="",
            ),
        ),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )
    exemption = {
        "exempt": True,
        "has_chronic_health_report": True,
        "qualifying_diagnoses": [{"disease": "Diabetes", "range": "E10-E14"}],
        "exemption_sources": [
            {
                "category": "ek1a_chronic",
                "counts_toward_exempt": True,
                "waives_sections": ("1.8.1",),
                "evidence": {
                    "qualifying_diagnoses": [{"disease": "Diabetes", "range": "E10-E14"}]
                },
            }
        ],
    }

    result = optimize_copay_from_claims(ctx, exemption)

    assert result.visit_copay_savings_try == pytest.approx(20.0)
    assert result.rx_copay_savings_try == 0.0
    grounds = {row.get("code"): row.get("exemption_ground") for row in result.rate_corrections}
    assert grounds.get("703720") == "ek1a_muayene"
    assert "L110580" not in grounds


def test_exempt_true_ek4d_poliklinik_drug() -> None:
    claim = ClaimHeader(
        claim_id="C-POLI-RX",
        patient_id="P1",
        episode_id="E1",
        claim_type="poliklinik",
        facility_tier="2",
        provider_type="kamu",
        department="",
        admission_date=None,
        discharge_date=None,
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 1),
        primary_icd10="A16.9",
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test",
    )
    ctx = PatientClaimContext(
        patient_id="P1",
        claims=(claim,),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(
            DrugClaimLine(
                drug_claim_line_id="D1",
                prescription_id="RX1",
                claim_id=claim.claim_id,
                patient_id="P1",
                episode_id="E1",
                drug_claim_date=date(2026, 1, 2),
                drug_name="Morfozinamid",
                drug_code="",
                barkod="",
                equivalence_group="",
                quantity=1,
                unit_price_try=Decimal("100"),
                billed_amount_try=Decimal("100"),
                expected_payable_try=Decimal("60"),
                discount_tier_expected=Decimal("0"),
                denial_reason_expected="",
                rule_trace_expected="",
            ),
        ),
        diagnoses=(
            ClaimDiagnosis(
                diagnosis_id="DX1",
                claim_id=claim.claim_id,
                patient_id="P1",
                episode_id="E1",
                icd10_code="A16.9",
                is_primary=True,
                diagnosis_role="primary",
                diagnosis_date=date(2026, 1, 1),
                exemption_eligible=False,
            ),
        ),
    )
    result = optimize_copay_from_claims(
        ctx,
        {
            "exempt": True,
            "has_chronic_health_report": True,
            "qualifying_diagnoses": [{"disease": "Tuberculosis", "range": "A15-A19"}],
            "exemption_sources": [
                {
                    "category": "ek1a_chronic",
                    "counts_toward_exempt": True,
                    "waives_sections": ("1.8.1",),
                    "evidence": {
                        "qualifying_diagnoses": [
                            {"disease": "Tuberculosis", "range": "A15-A19"}
                        ]
                    },
                }
            ],
        },
    )

    assert result.rx_copay_savings_try == pytest.approx(40.0)
    assert result.rx_copay_savings_by_ground.get("ek4d_drug") == pytest.approx(40.0)
    drug_rows = [
        row for row in result.rate_corrections if row.get("exemption_ground") == "ek4d_drug"
    ]
    assert len(drug_rows) == 1


def test_gunubirlik_drugs_inpatient_ground() -> None:
    result = optimize_copay_from_claims(_build_0039_104_context(), _EK1A_EXEMPTION)

    grounds = {
        row.get("name"): row.get("exemption_ground") for row in result.rate_corrections
    }
    assert grounds["ROLASTYM"] == "inpatient_drug_1_8_5_8"
    assert grounds["MODIOGEN"] == "inpatient_drug_1_8_5_8"
    assert grounds["KADCYLA"] == "inpatient_drug_1_8_5_8"
    assert grounds["ZINCOPLEX"] == "inpatient_drug_1_8_5_8"
    assert "ek1a_muayene" not in grounds.values()

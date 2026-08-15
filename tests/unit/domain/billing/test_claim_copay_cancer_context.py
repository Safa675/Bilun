"""Structured cancer/emergency exemption context for copay clause refs (Track E)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.claim_copay import (
    _emergency_claim_ids,
    _has_malignant_qualifying_diagnosis,
    optimize_copay_from_claims,
)
from src.bilun.domain.claims.models import (
    ClaimHeader,
    DrugClaimLine,
    MaterialClaimLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.sut.clause_reference import (
    RULE_TYPE_COPAY_RATE,
    RULE_TYPE_COPAY_WAIVER,
)

pytestmark = pytest.mark.unit


def _claim(
    *,
    claim_id: str,
    claim_type: str,
    primary_icd10: str = "E11.9",
) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="PT-1",
        episode_id="EP-1",
        claim_type=claim_type,
        facility_tier="2",
        provider_type="kamu",
        department="",
        admission_date=None,
        discharge_date=None,
        claim_start_date=date(2026, 3, 10),
        claim_end_date=date(2026, 3, 10),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _ek1a_source(icd10: str) -> dict:
    return {
        "category": "ek1a_chronic",
        "rule_source": "SUT §1.8.5(7) + EK-1/A chronic disease copay exemptions",
        "counts_toward_exempt": True,
        "waives_sections": ("1.8.1",),
        "evidence": {
            "qualifying_diagnoses": [
                {"icd10": icd10, "disease": "Test", "range": f"{icd10}-{icd10}"}
            ]
        },
    }


def test_malignant_diagnosis_detection_from_structured_sources() -> None:
    assert _has_malignant_qualifying_diagnosis([_ek1a_source("C50")])
    assert _has_malignant_qualifying_diagnosis([_ek1a_source("C83.1")])
    assert _has_malignant_qualifying_diagnosis([_ek1a_source("c90")])

    assert not _has_malignant_qualifying_diagnosis([_ek1a_source("E11.9")])
    assert not _has_malignant_qualifying_diagnosis([_ek1a_source("A16.9")])
    assert not _has_malignant_qualifying_diagnosis([_ek1a_source("CH50")])
    assert not _has_malignant_qualifying_diagnosis([_ek1a_source("C5")])

    # Diagnoses without an icd10 key (e.g. range-only evidence) never match.
    no_icd = {
        "category": "ek1a_chronic",
        "counts_toward_exempt": True,
        "waives_sections": ("1.8.1",),
        "evidence": {"qualifying_diagnoses": [{"disease": "Diabetes", "range": "E10-E14"}]},
    }
    assert not _has_malignant_qualifying_diagnosis([no_icd])
    assert not _has_malignant_qualifying_diagnosis([])


def test_emergency_claim_ids_normalize_claim_type() -> None:
    claims = (
        _claim(claim_id="C-ACIL", claim_type="acil"),
        _claim(claim_id="C-ACIL-SPACE", claim_type="Acil Servis"),
        _claim(claim_id="C-POLI", claim_type="poliklinik"),
    )
    acil_sources = [{"category": "acil_servis", "counts_toward_exempt": True}]

    assert _emergency_claim_ids(claims, acil_sources) == {"C-ACIL", "C-ACIL-SPACE"}

    # No acil_servis exemption source → no emergency claim ids, even for
    # emergency-typed claims.
    assert _emergency_claim_ids(claims, [_ek1a_source("E11.9")]) == frozenset()


def test_cancer_context_upgrades_procedure_waiver_row() -> None:
    claim = _claim(claim_id="C-POLI", claim_type="poliklinik", primary_icd10="C50")
    line = ProcedureClaimLine(
        procedure_line_id="PL-MUAYENE",
        claim_id=claim.claim_id,
        patient_id="PT-1",
        episode_id="EP-1",
        procedure_date=date(2026, 3, 10),
        procedure_code="703720",
        procedure_name="Muayene",
        procedure_category="muayene",
        quantity=1,
        unit_price_try=Decimal("100.00"),
        billed_amount_try=Decimal("100.00"),
        expected_payable_try=Decimal("60.00"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    ctx = PatientClaimContext(
        patient_id="PT-1",
        claims=(claim,),
        procedure_lines=(line,),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )

    result = optimize_copay_from_claims(
        ctx,
        {
            "exempt": True,
            "has_chronic_health_report": True,
            "qualifying_diagnoses": [
                {"icd10": "C50", "disease": "Malignant neoplasm of breast", "range": "C50"}
            ],
            "exemption_sources": [_ek1a_source("C50")],
        },
    )

    assert result.visit_copay_savings_try == pytest.approx(40.0)
    rows = [r for r in result.rate_corrections if r.get("exemption_ground") == "ek1a_muayene"]
    assert len(rows) == 1
    row = rows[0]

    # Cancer context upgrades the ek1a row's "none" ilave status (SUT §1.9.3(ç)).
    assert row["ilave_ucret_status"] == "cancer_exempt"
    ilave_ref = row["ilave_clause_ref"]
    assert ilave_ref["clause_coordinate"] == "1.9.3.ç"
    assert ilave_ref["clause_key"]  # resolved, non-empty

    clause_ref = row["clause_ref"]
    assert clause_ref["clause_coordinate"] == "1.8.5.(7)"
    assert clause_ref["clause_key"]  # resolved, non-empty
    assert clause_ref["rule_type"] == RULE_TYPE_COPAY_WAIVER
    assert clause_ref["annex"] == "EK-1/A"


def test_cancer_context_keeps_drug_waiver_rows_drug_prohibited() -> None:
    claim = _claim(claim_id="C-GUNU", claim_type="gunubirlik", primary_icd10="C83.1")
    line = DrugClaimLine(
        drug_claim_line_id="DL-1",
        prescription_id="RX-1",
        claim_id=claim.claim_id,
        patient_id="PT-1",
        episode_id="EP-1",
        drug_claim_date=date(2026, 3, 10),
        drug_name="SENTETIK-ILAC",
        drug_code="P-SENT",
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
    ctx = PatientClaimContext(
        patient_id="PT-1",
        claims=(claim,),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(line,),
        diagnoses=(),
    )

    result = optimize_copay_from_claims(
        ctx,
        {
            "exempt": True,
            "has_chronic_health_report": True,
            "qualifying_diagnoses": [
                {"icd10": "C83.1", "disease": "Non-Hodgkin lenfoma", "range": "C81-C96"}
            ],
            "exemption_sources": [_ek1a_source("C83.1")],
        },
    )

    rows = [
        r
        for r in result.rate_corrections
        if r.get("exemption_ground") == "inpatient_drug_1_8_5_8"
    ]
    assert len(rows) == 1
    row = rows[0]

    # Drug prohibition wins over the cancer upgrade; money unchanged (20 TRY).
    assert result.rx_copay_savings_try == pytest.approx(20.0)
    assert row["ilave_ucret_status"] == "drug_prohibited"
    assert row["ilave_clause_ref"]["clause_coordinate"] == "1.9.1"
    assert row["clause_ref"]["clause_coordinate"] == "1.8.5.(8)"
    assert row["clause_ref"]["clause_key"]  # resolved, non-empty


def test_partial_exempt_informational_row_carries_clause_ref() -> None:
    ctx = PatientClaimContext(
        patient_id="PT-1",
        claims=(),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )

    result = optimize_copay_from_claims(
        ctx,
        {
            "exempt": False,
            "partial_exempt": True,
            "has_chronic_health_report": False,
            "qualifying_diagnoses": [{"icd10": "E11.9", "disease": "Diabetes", "range": "E10-E14"}],
            "exemption_sources": [],
        },
    )

    assert len(result.rate_corrections) == 1
    row = result.rate_corrections[0]
    assert row["rule_id"] == "copay_exemption_ek1a"
    assert row["sut_section"] == "1.8.5(7)"
    clause_ref = row["clause_ref"]
    assert clause_ref["clause_coordinate"] == "1.8.5.(7)"
    assert clause_ref["clause_key"]  # resolved, non-empty
    assert clause_ref["rule_type"] == RULE_TYPE_COPAY_WAIVER
    assert clause_ref["annex"] == "EK-1/A"


def test_informational_rate_rows_carry_clause_refs() -> None:
    claim = _claim(claim_id="C-POLI", claim_type="poliklinik")
    drug_line = DrugClaimLine(
        drug_claim_line_id="DL-NOGAP",
        prescription_id="RX-1",
        claim_id=claim.claim_id,
        patient_id="PT-1",
        episode_id="EP-1",
        drug_claim_date=date(2026, 3, 10),
        drug_name="SENTETIK-ILAC",
        drug_code="P-SENT",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("50.00"),
        billed_amount_try=Decimal("50.00"),
        expected_payable_try=Decimal("50.00"),
        discount_tier_expected=Decimal("0"),
        denial_reason_expected="",
        rule_trace_expected="",
    )
    material_line = MaterialClaimLine(
        material_line_id="ML-1",
        claim_id=claim.claim_id,
        procedure_line_id="",
        patient_id="PT-1",
        material_date=date(2026, 3, 10),
        material_code="M100",
        material_name="Test Material",
        material_type="ortez",
        specialty_category="",
        quantity=1,
        unit_price_try=Decimal("100.00"),
        billed_amount_try=Decimal("100.00"),
        expected_payable_try=Decimal("100.00"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    ctx = PatientClaimContext(
        patient_id="PT-1",
        claims=(claim,),
        procedure_lines=(),
        material_lines=(material_line,),
        drug_lines=(drug_line,),
        diagnoses=(),
    )

    result = optimize_copay_from_claims(ctx, {})

    drug_rows = [r for r in result.rate_corrections if r.get("sut_section") == "1.8.2.(1)"]
    assert len(drug_rows) == 1
    assert drug_rows[0]["clause_ref"]["clause_coordinate"] == "1.8.2.(1)"
    assert drug_rows[0]["clause_ref"]["clause_key"]  # resolved, non-empty
    assert drug_rows[0]["clause_ref"]["rule_type"] == RULE_TYPE_COPAY_RATE

    material_rows = [
        r for r in result.rate_corrections if r.get("sut_section") == "1.8.3.(2)"
    ]
    assert len(material_rows) == 1
    assert material_rows[0]["clause_ref"]["clause_coordinate"] == "1.8.3.(2)"
    assert material_rows[0]["clause_ref"]["clause_key"]  # resolved, non-empty
    assert material_rows[0]["clause_ref"]["rule_type"] == RULE_TYPE_COPAY_RATE
    # Structured message contract (Aşama 3 §2.2 surface): detail unchanged,
    # rate carried as a number for i18n interpolation.
    assert material_rows[0]["message_code"] == "material_copay_rate"
    assert material_rows[0]["message_params"] == {"rate_pct": 20}
    assert (
        material_rows[0]["detail"]
        == "SUT §1.8.3(2) material copay reference rate: 20%"
    )

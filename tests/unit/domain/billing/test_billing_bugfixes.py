"""Tests for billing bugfixes: copay/drug dedupe and orchestrator totals."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit


def test_copay_total_excludes_rx_component() -> None:
    from src.bilun.domain.billing.claim_copay import optimize_copay_from_claims
    from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine, ProcedureClaimLine
    from src.bilun.domain.claims.patient_context import PatientClaimContext

    poli_claim = ClaimHeader(
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
    rx_claim = ClaimHeader(
        claim_id="C-RX",
        patient_id="P1",
        episode_id="E1",
        claim_type="gunubirlik",
        facility_tier="2",
        provider_type="kamu",
        department="",
        admission_date=date(2026, 1, 2),
        discharge_date=date(2026, 1, 2),
        claim_start_date=date(2026, 1, 2),
        claim_end_date=date(2026, 1, 2),
        primary_icd10="E11.9",
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test",
    )
    ctx = PatientClaimContext(
        patient_id="P1",
        claims=(poli_claim, rx_claim),
        procedure_lines=(
            ProcedureClaimLine(
                procedure_line_id="PL1",
                claim_id=poli_claim.claim_id,
                patient_id="P1",
                episode_id="E1",
                procedure_date=date(2026, 1, 1),
                procedure_code="703720",
                procedure_name="Visit proc",
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
        drug_lines=(
            DrugClaimLine(
                drug_claim_line_id="D1",
                prescription_id="RX1",
                claim_id=rx_claim.claim_id,
                patient_id="P1",
                episode_id="E1",
                drug_claim_date=date(2026, 1, 2),
                drug_name="Drug",
                drug_code="D001",
                barkod="",
                equivalence_group="",
                quantity=1,
                unit_price_try=Decimal("50"),
                billed_amount_try=Decimal("50"),
                expected_payable_try=Decimal("40"),
                discount_tier_expected=Decimal("0"),
                denial_reason_expected="",
                rule_trace_expected="",
            ),
        ),
        diagnoses=(),
    )

    result = optimize_copay_from_claims(
        ctx,
        {
            "exempt": True,
            "has_chronic_health_report": True,
            "qualifying_diagnoses": [{"disease": "Diabetes", "range": "E10-E14"}],
            "exemption_sources": [
                {
                    "category": "ek1a_chronic",
                    "counts_toward_exempt": True,
                    "waives_sections": ("1.8.1",),
                    "evidence": {
                        "qualifying_diagnoses": [
                            {"disease": "Diabetes", "range": "E10-E14"}
                        ]
                    },
                }
            ],
        },
    )

    assert result.visit_copay_savings_try == 20.0
    assert result.rx_copay_savings_try == 10.0
    assert result.total_copay_savings_try == 20.0
    assert result.patient_copay_waived_total_try == 30.0
    assert result.savings_beneficiary == "patient_and_sgk"
    assert result.gap_kind == "exemption_correction"


def test_orchestrator_without_claim_context_returns_missing_inputs() -> None:
    import src.bilun.domain.billing.orchestrator as billing_mod

    report = billing_mod.compute_patient_billing_report("P1")

    assert report.exactness_status == "missing_exact_inputs"
    assert report.total_recoverable_try == 0.0
    assert report.copay.exactness_status == "missing_exact_inputs"
    assert report.billing_strategy.exactness_status == "missing_exact_inputs"
    assert report.materials.exactness_status == "missing_exact_inputs"
    assert report.lab.exactness_status == "missing_exact_inputs"

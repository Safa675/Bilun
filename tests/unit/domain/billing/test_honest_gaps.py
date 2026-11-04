"""Tests for billing honest-gap integrity (no fabricated TRY in heuristics)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_orchestrator_total_includes_only_exact_blocks() -> None:
    import src.bilun.domain.billing.orchestrator as billing_mod

    report = billing_mod.compute_patient_billing_report("P1")

    # Without claim lines every block is missing inputs; amounts are uncomputed.
    assert report.compliance_adjustment_try is None
    assert report.sgk_uplift_try is None
    assert report.total_recoverable_try is None
    assert report.exactness_status == "missing_exact_inputs"


def test_orchestrator_claim_context_required_constant_defaults_true() -> None:
    from src.bilun.domain.constants import SUT_REQUIRE_CLAIM_LINES

    assert SUT_REQUIRE_CLAIM_LINES is True


def test_exempt_copay_from_claims_reports_waived_amounts_not_heuristic_savings() -> None:
    from datetime import date
    from decimal import Decimal

    from src.bilun.domain.billing.claim_copay import optimize_copay_from_claims
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
    from src.bilun.domain.claims.patient_context import PatientClaimContext

    claim = ClaimHeader(
        claim_id="C1",
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
                procedure_line_id="PL1",
                claim_id=claim.claim_id,
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
        drug_lines=(),
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

    assert result.exactness_status == "exact"
    assert result.visit_copay_savings_try == 20.0
    assert "EK-1A exemption may apply" not in str(result.rate_corrections)

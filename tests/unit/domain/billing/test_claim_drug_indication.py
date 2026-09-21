"""Billing report wiring for §4.2 drug indication prose."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from dataclasses import replace

import pytest

from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.billing.drug_indication_findings import (
    evaluate_drug_indication_findings,
)
from src.bilun.domain.claims.models import ClaimDiagnosis, ClaimHeader, DrugClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext

pytestmark = pytest.mark.unit


def _ctx(*, report_present: bool | None = False) -> PatientClaimContext:
    claim = ClaimHeader(
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        claim_type="yatis",
        facility_tier="2",
        provider_type="kamu",
        department="onkoloji",
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 5),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 5),
        primary_icd10="C34.9",
        package_candidate=False,
        expected_total_billed_try=Decimal("10000"),
        expected_total_payable_try=Decimal("7200"),
        expected_denial_reason="",
        scenario_tag="sgk_drug_indication_bevacizumab_missing_report",
    )
    drug_line = DrugClaimLine(
        drug_claim_line_id="D1",
        prescription_id="RX1",
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=date(2026, 1, 2),
        drug_name="AVASTIN 400 MG (BEVACIZUMAB)",
        drug_code="A00000",
        barkod="8690000000001",
        equivalence_group="bevasizumab",
        quantity=1,
        unit_price_try=Decimal("10000"),
        billed_amount_try=Decimal("10000"),
        expected_payable_try=Decimal("7200"),
        discount_tier_expected=Decimal("0.28"),
        denial_reason_expected="",
        rule_trace_expected="",
        drug_specialty_board_report_present=report_present,
    )
    return PatientClaimContext(
        patient_id="P1",
        claims=(claim,),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(drug_line,),
        diagnoses=(
            ClaimDiagnosis(
                diagnosis_id="DG1",
                claim_id="C1",
                patient_id="P1",
                episode_id="E1",
                icd10_code="C34.9",
                is_primary=True,
                diagnosis_role="birincil",
                diagnosis_date=date(2026, 1, 1),
                exemption_eligible=False,
            ),
        ),
    )


def test_billing_report_surfaces_drug_indication_violations() -> None:
    report = compute_patient_billing_report("P1", claim_context=_ctx(report_present=False))
    assert report.drug_indication.exactness_status == "exact"
    assert report.drug_indication.violation_count == 1
    assert report.drug_indication.error_count == 1
    assert report.drug_indication_violation_count == 1
    assert report.drug_indication.violations[0]["violation_kind"] == "missing_board_report"
    assert report.drug_indication.coverage_scope["pilot_rule_count"] >= 131


def test_billing_report_clean_when_report_present() -> None:
    report = compute_patient_billing_report("P1", claim_context=_ctx(report_present=True))
    assert report.drug_indication.exactness_status == "exact"
    assert report.drug_indication.violation_count == 0
    assert report.drug_indication_violation_count == 0


def test_billing_report_evaluates_drug_indication_once(monkeypatch) -> None:
    import src.bilun.domain.billing.patient_report as patient_report

    original = patient_report.evaluate_drug_indication_findings
    calls = 0

    def counted(patient_id, ctx, *, rules=None):
        nonlocal calls
        calls += 1
        return original(patient_id, ctx, rules=rules)

    monkeypatch.setattr(patient_report, "evaluate_drug_indication_findings", counted)

    report = compute_patient_billing_report("P1", claim_context=_ctx(report_present=False))

    assert calls == 1
    drug_action = next(
        row for row in report.recommended_actions if row["surface"] == "drug_indication"
    )
    assert drug_action["action_id"] == (
        "drug_indication:P1:C1:D1:missing_board_report"
    )
    assert drug_action["sgk_uplift_try"] is None
    assert drug_action["audit_risk_try"] is None
    assert drug_action["compliance_savings_try"] is None
    assert report.sgk_uplift_try == 0.0
    assert report.compliance_adjustment_try == 0.0
    assert report.audit_exposure_try == 0.0
    assert report.total_recoverable_try == 0.0


def test_claim_review_accepts_supplied_canonical_batch_without_rerun(monkeypatch) -> None:
    from src.bilun.domain.billing.claim_drug_indication import (
        validate_drug_indication_from_claims,
    )

    ctx = _ctx(report_present=False)
    batch = evaluate_drug_indication_findings(ctx.patient_id, ctx)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("projection must not rerun the detector")

    monkeypatch.setattr(
        "src.bilun.domain.billing.claim_drug_indication.evaluate_drug_indication_findings",
        fail_if_called,
    )

    review = validate_drug_indication_from_claims(ctx, evaluation_batch=batch)

    assert review.findings[0].finding_id == batch.findings[0].finding_id
    assert review.violations[0]["finding_id"] == batch.findings[0].finding_id


def test_billing_report_drug_indication_not_applicable_without_drug_lines() -> None:
    ctx = _ctx(report_present=False)
    ctx = PatientClaimContext(
        patient_id=ctx.patient_id,
        claims=ctx.claims,
        procedure_lines=ctx.procedure_lines,
        material_lines=ctx.material_lines,
        drug_lines=(),
        diagnoses=ctx.diagnoses,
    )
    report = compute_patient_billing_report("P1", claim_context=ctx)
    assert report.drug_indication.exactness_status == "not_applicable"
    assert report.drug_indication_violation_count == 0


def test_complete_unencoded_drug_is_manual_review_without_invented_missing_inputs() -> None:
    ctx = _ctx(report_present=True)
    unencoded_line = replace(ctx.drug_lines[0], drug_name="UNENCODED MEDICINE")
    ctx = replace(ctx, drug_lines=(unencoded_line,))

    report = compute_patient_billing_report("P1", claim_context=ctx)

    assert report.drug_indication.findings == []
    assert report.drug_indication.violations == []
    assert len(report.drug_indication.evaluations) == 1
    evaluation = report.drug_indication.evaluations[0]
    assert evaluation.applicability_status == "not_in_encoded_corpus"
    assert evaluation.evaluation_status == "unavailable"
    assert evaluation.missing_inputs == ()
    assert report.drug_indication.required_inputs_missing == []
    assert report.drug_indication.unavailable_reason
    assert not any(
        action.get("surface") == "drug_indication"
        for action in report.recommended_actions
    )

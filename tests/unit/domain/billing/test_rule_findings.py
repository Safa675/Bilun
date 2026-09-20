from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.bilun.domain.billing import claim_compliance, engine, patient_report, rule_findings
from src.bilun.domain.billing.rule_findings import (
    RuleEvaluation,
    RuleEvaluationBatch,
    RuleFinding,
    build_finding_id,
    evaluate_rule_findings,
)
from src.bilun.domain.claims.models import (
    ClaimHeader,
    DrugClaimLine,
    MaterialClaimLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("line_kind", "line_id", "expected_suffix"),
    [
        ("claim", None, "rule%3A1:P%3A1:C%2F1:claim:"),
        ("procedure", "PROC:1/2", "rule%3A1:P%3A1:C%2F1:procedure:PROC%3A1%2F2"),
        ("drug", "DRUG 1", "rule%3A1:P%3A1:C%2F1:drug:DRUG%201"),
        ("material", "MAT%1", "rule%3A1:P%3A1:C%2F1:material:MAT%251"),
    ],
)
def test_finding_identity_is_stable_and_urlquoted(
    line_kind: str,
    line_id: str | None,
    expected_suffix: str,
) -> None:
    finding_id = build_finding_id(
        rule_id="rule:1",
        patient_id="P:1",
        claim_id="C/1",
        line_kind=line_kind,
        line_id=line_id,
    )
    finding = RuleFinding(
        finding_id=finding_id,
        patient_id="P:1",
        claim_id="C/1",
        line_kind=line_kind,
        line_id=line_id,
        rule_id="rule:1",
        kind="rule:1",
        severity="warning",
        detail="detail",
        sut_section_id=None,
        regulatory_source=None,
        source_engine="test_detector",
        evaluation_status="evaluated",
        required_inputs=[],
        missing_inputs=[],
    )

    assert finding_id == f"claim_compliance:{expected_suffix}"
    assert finding.action_id == finding.finding_id
    assert asdict(RuleEvaluationBatch(findings=(finding,), evaluations=()))["findings"][0][
        "finding_id"
    ] == finding_id
    assert RuleEvaluation(
        patient_id="P:1",
        claim_id="C/1",
        rule_id="rule:1",
        evaluation_status="evaluated",
        required_inputs=[],
        missing_inputs=[],
    ).evaluation_status == "evaluated"


def test_finding_identity_distinguishes_line_kind_for_same_line_id() -> None:
    common = {
        "rule_id": "rule",
        "patient_id": "P1",
        "claim_id": "C1",
        "line_id": "L1",
    }

    procedure_id = build_finding_id(line_kind="procedure", **common)
    drug_id = build_finding_id(line_kind="drug", **common)

    assert procedure_id != drug_id
    assert procedure_id == "claim_compliance:rule:P1:C1:procedure:L1"
    assert drug_id == "claim_compliance:rule:P1:C1:drug:L1"


def _claim() -> ClaimHeader:
    return ClaimHeader(
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        claim_type="yatis",
        facility_tier="2",
        provider_type="kamu",
        department="dahiliye",
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 2),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 2),
        primary_icd10="",
        package_candidate=False,
        expected_total_billed_try=Decimal("500"),
        expected_total_payable_try=Decimal("500"),
        expected_denial_reason="",
        scenario_tag="rule_findings",
        primary_icd10_available=True,
    )


def _procedure(
    line_id: str,
    code: str,
    *,
    lab_billing_status: str = "",
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 1),
        procedure_code=code,
        procedure_name=code,
        procedure_category="laboratuvar" if lab_billing_status else "diger",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("100"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
        lab_billing_status=lab_billing_status,
    )


def _drug() -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D1",
        prescription_id="RX1",
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=date(2026, 1, 1),
        drug_name="Drug",
        drug_code="DRUG",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("100"),
        discount_tier_expected=Decimal("0"),
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _material() -> MaterialClaimLine:
    return MaterialClaimLine(
        material_line_id="M1",
        claim_id="C1",
        procedure_line_id="",
        patient_id="P1",
        material_date=date(2026, 1, 1),
        material_code="MAT",
        material_name="Material",
        material_type="consumable",
        specialty_category="general",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("100"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
        barcode_sut_mismatch=True,
    )


def _positive_context() -> PatientClaimContext:
    anchor = _procedure("ICU", "510090")
    bundled = _procedure("VENT", "530130")
    lab = _procedure("LAB", "901320", lab_billing_status="pending")
    drug = _drug()
    material = _material()
    return PatientClaimContext(
        patient_id="P1",
        claims=(_claim(),),
        procedure_lines=(anchor, bundled, lab, bundled, lab),
        material_lines=(material, material),
        drug_lines=(drug, drug),
        diagnoses=(),
    )


def test_canonical_evaluator_normalizes_five_rules_once_and_dedupes_findings() -> None:
    batch = evaluate_rule_findings("P1", _positive_context())

    assert [(row.rule_id, row.line_kind, row.line_id) for row in batch.findings] == [
        ("icu_bundled_leakage_510090", "procedure", "VENT"),
        ("tablo15_10_unreported_lab_result", "procedure", "LAB"),
        ("tablo15_20_missing_drug_barcode", "drug", "D1"),
        ("tablo15_5_material_identity_error", "material", "M1"),
        ("tablo15_8_missing_diagnosis", "claim", None),
    ]
    assert [row.finding_id for row in batch.findings] == sorted(
        row.finding_id for row in batch.findings
    )
    assert len({row.finding_id for row in batch.findings}) == 5
    assert all(row.action_id == row.finding_id for row in batch.findings)
    assert all(row.evaluation_status == "evaluated" for row in batch.findings)
    assert all(
        (
            row.amount_try,
            row.billed_try,
            row.payable_try,
            row.savings_try,
            row.recoverable_uplift_try,
            row.compliance_savings_try,
            row.risk_amount_try,
            row.audit_exposure_try,
        )
        == (None,) * 8
        for row in batch.findings
    )
    assert len(batch.evaluations) == 5
    assert all(row.evaluation_status == "evaluated" for row in batch.evaluations)
    assert len(batch.legacy_violations) > len(batch.findings)


def test_canonical_evaluator_keeps_missing_context_explicit() -> None:
    batch = evaluate_rule_findings("P1", None)

    assert batch.findings == ()
    assert len(batch.evaluations) == 5
    assert all(row.evaluation_status == "missing_inputs" for row in batch.evaluations)
    assert all(row.missing_inputs == ["claim_context"] for row in batch.evaluations)


def test_canonical_evaluator_preserves_patient_ownership_guard() -> None:
    ctx = _positive_context()
    mismatched = replace(ctx, drug_lines=(replace(ctx.drug_lines[0], patient_id="P2"),))

    with pytest.raises(ValueError, match="Claim compliance context"):
        evaluate_rule_findings("P1", mismatched)


def test_analyze_claim_reuses_canonical_batch_and_preserves_selected_legacy_output() -> None:
    ctx = _positive_context()
    expected = list(evaluate_rule_findings("P1", ctx).legacy_violations)
    selected_rule_ids = {row["rule_id"] for row in expected}

    with (
        patch.object(
            rule_findings,
            "detect_icu_bundled_leakage",
            wraps=rule_findings.detect_icu_bundled_leakage,
        ) as icu,
        patch.object(
            rule_findings,
            "detect_missing_diagnosis",
            wraps=rule_findings.detect_missing_diagnosis,
        ) as diagnosis,
        patch.object(
            rule_findings,
            "detect_unreported_lab_result",
            wraps=rule_findings.detect_unreported_lab_result,
        ) as lab,
        patch.object(
            rule_findings,
            "detect_missing_drug_barcode",
            wraps=rule_findings.detect_missing_drug_barcode,
        ) as drug,
        patch.object(
            rule_findings,
            "detect_material_identity_errors",
            wraps=rule_findings.detect_material_identity_errors,
        ) as material,
    ):
        violations = engine.analyze_claim(ctx)

    assert [icu.call_count, diagnosis.call_count, lab.call_count, drug.call_count, material.call_count] == [
        1,
        1,
        1,
        1,
        1,
    ]
    assert [
        row for row in violations if row.get("rule_id") in selected_rule_ids
    ] == expected


def test_patient_report_evaluates_once_and_projector_is_pure() -> None:
    ctx = _positive_context()

    with (
        patch.object(
            rule_findings,
            "detect_icu_bundled_leakage",
            wraps=rule_findings.detect_icu_bundled_leakage,
        ) as icu,
        patch.object(
            rule_findings,
            "detect_missing_diagnosis",
            wraps=rule_findings.detect_missing_diagnosis,
        ) as diagnosis,
        patch.object(
            rule_findings,
            "detect_unreported_lab_result",
            wraps=rule_findings.detect_unreported_lab_result,
        ) as lab,
        patch.object(
            rule_findings,
            "detect_missing_drug_barcode",
            wraps=rule_findings.detect_missing_drug_barcode,
        ) as drug,
        patch.object(
            rule_findings,
            "detect_material_identity_errors",
            wraps=rule_findings.detect_material_identity_errors,
        ) as material,
    ):
        report = patient_report.compute_patient_billing_report("P1", claim_context=ctx)

    assert [icu.call_count, diagnosis.call_count, lab.call_count, drug.call_count, material.call_count] == [
        1,
        1,
        1,
        1,
        1,
    ]
    findings = report.claim_compliance.findings
    assert {(row["rule_id"], row["line_kind"], row["line_id"]) for row in findings} == {
        ("icu_bundled_leakage_510090", "procedure", "VENT"),
        ("tablo15_8_missing_diagnosis", "claim", None),
        ("tablo15_10_unreported_lab_result", "procedure", "LAB"),
        ("tablo15_20_missing_drug_barcode", "drug", "D1"),
        ("tablo15_5_material_identity_error", "material", "M1"),
    }
    assert all(row["finding_id"] == row["action_id"] for row in findings)
    assert all(row["amount_try"] is None and row["risk_amount_try"] is None for row in findings)

    batch = evaluate_rule_findings("P1", ctx)
    detector_names = (
        "detect_icu_bundled_leakage",
        "detect_missing_diagnosis",
        "detect_unreported_lab_result",
        "detect_missing_drug_barcode",
        "detect_material_identity_errors",
    )
    with (
        patch.object(
            claim_compliance,
            detector_names[0],
            side_effect=AssertionError("projector executed detector"),
            create=True,
        ),
        patch.object(
            claim_compliance,
            detector_names[1],
            side_effect=AssertionError("projector executed detector"),
            create=True,
        ),
        patch.object(
            claim_compliance,
            detector_names[2],
            side_effect=AssertionError("projector executed detector"),
            create=True,
        ),
        patch.object(
            claim_compliance,
            detector_names[3],
            side_effect=AssertionError("projector executed detector"),
            create=True,
        ),
        patch.object(
            claim_compliance,
            detector_names[4],
            side_effect=AssertionError("projector executed detector"),
            create=True,
        ),
    ):
        projection = claim_compliance.project_claim_compliance("P1", batch)

    assert projection.findings == findings

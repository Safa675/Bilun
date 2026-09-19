from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

import pytest

from src.bilun.domain.billing import claim_compliance, patient_report, rule_findings
from src.bilun.domain.billing.claim_compliance import DIAGNOSIS_RULE_ID, ICU_RULE_ID
from src.bilun.domain.billing.rule_findings import (
    RuleEvaluationBatch,
    evaluate_rule_findings,
)
from src.bilun.domain.billing.types import ClaimCompliance
from src.bilun.domain.claims import dataset as dataset_module
from src.bilun.domain.claims.dataset import SUTClaimDataset
from src.bilun.domain.claims.errors import ClaimValidationError
from src.bilun.domain.claims.models import ClaimHeader
from src.bilun.domain.claims.patient_context import build_patient_claim_context
from src.bilun.domain.prose_rules.common_billing_errors import detect_missing_diagnosis
from src.bilun.domain.prose_rules.icu_bundled_leakage import detect_icu_bundled_leakage

pytestmark = pytest.mark.unit


def _header(claim_id="C1", patient_id="P1", **changes):
    return {
        "claim_id": claim_id,
        "patient_id": patient_id,
        "episode_id": f"E-{claim_id}",
        "claim_type": "yatis",
        "facility_tier": "2",
        "provider_type": "kamu",
        "department": "dahiliye",
        "admission_date": "2026-01-01",
        "discharge_date": "2026-01-03",
        "claim_start_date": "2026-01-01",
        "claim_end_date": "2026-01-03",
        "primary_icd10": "",
        **changes,
    }


def _line(line_id, code, claim_id="C1", patient_id="P1", **changes):
    return {
        "procedure_line_id": line_id,
        "claim_id": claim_id,
        "patient_id": patient_id,
        "episode_id": f"E-{claim_id}",
        "procedure_date": "2026-01-01",
        "procedure_code": code,
        "procedure_name": code,
        "procedure_category": "diger",
        "quantity": 1,
        "unit_price_try": 100,
        "billed_amount_try": 100,
        "expected_payable_try": 100,
        **changes,
    }


def _diagnosis(
    diagnosis_id="D1", claim_id="C1", patient_id="P1", *,
    icd10_code="J96.0", is_primary=True,
):
    return {
        "diagnosis_id": diagnosis_id,
        "claim_id": claim_id,
        "patient_id": patient_id,
        "episode_id": f"E-{claim_id}",
        "icd10_code": icd10_code,
        "is_primary": is_primary,
        "diagnosis_role": "primary" if is_primary else "secondary",
        "diagnosis_date": "2026-01-01",
        "exemption_eligible": False,
    }


def _context(headers=None, lines=None, patient_id="P1", diagnoses=None):
    headers = [_header()] if headers is None else headers
    lines = [_line("L1", "510090"), _line("L2", "530130")] if lines is None else lines
    headers = [
        {
            **header,
            "expected_total_billed_try": sum(
                line["billed_amount_try"] for line in lines if line["claim_id"] == header["claim_id"]
            ),
            "expected_total_payable_try": sum(
                line["expected_payable_try"] for line in lines if line["claim_id"] == header["claim_id"]
            ),
        }
        for header in headers
    ]
    ds = SUTClaimDataset.from_rows(
        claim_headers=headers,
        diagnoses=[] if diagnoses is None else diagnoses,
        procedure_lines=lines,
        material_lines=[],
        drug_lines=[],
        expected_outputs=[
            {
                "expected_output_id": f"X-{header['claim_id']}",
                "claim_id": header["claim_id"],
                "patient_id": header["patient_id"],
                "line_type": "claim",
            }
            for header in headers
        ],
    )
    return build_patient_claim_context(patient_id, ds)


def _report(ctx):
    return patient_report.compute_patient_billing_report("P1", claim_context=ctx)


def _evaluation(projection, claim_id, rule_id):
    return next(
        row for row in projection.evaluations
        if row["claim_id"] == claim_id and row["rule_id"] == rule_id
    )


def test_normal_ingestion_real_detectors_and_worktree_module():
    root = Path(__file__).resolve().parents[4]
    assert Path(dataset_module.__file__).resolve().is_relative_to(root)
    positive = _context()
    negative = _context([_header(claim_type="poliklinik", primary_icd10="J96.0")])
    assert len(detect_icu_bundled_leakage(list(positive.claims), list(positive.procedure_lines))) == 1
    assert len(detect_missing_diagnosis(list(positive.claims))) == 1
    assert detect_icu_bundled_leakage(list(negative.claims), list(negative.procedure_lines)) == []
    assert detect_missing_diagnosis(list(negative.claims)) == []


def test_report_real_detectors_run_once_and_serialize_nonfinancial_findings():
    ctx = _context()
    with (
        patch.object(rule_findings, "detect_icu_bundled_leakage", wraps=rule_findings.detect_icu_bundled_leakage) as icu,
        patch.object(rule_findings, "detect_missing_diagnosis", wraps=rule_findings.detect_missing_diagnosis) as diagnosis,
        patch.object(rule_findings, "detect_unreported_lab_result", wraps=rule_findings.detect_unreported_lab_result) as lab,
        patch.object(rule_findings, "detect_missing_drug_barcode", wraps=rule_findings.detect_missing_drug_barcode) as drug,
        patch.object(rule_findings, "detect_material_identity_errors", wraps=rule_findings.detect_material_identity_errors) as material,
    ):
        report = _report(ctx)
    icu.assert_called_once()
    diagnosis.assert_called_once()
    lab.assert_called_once()
    drug.assert_called_once()
    material.assert_called_once()
    projection = asdict(report)["claim_compliance"]
    assert set(projection) == {"findings", "evaluations"}
    assert len(projection["findings"]) == 2
    assert {row["rule_id"] for row in projection["findings"]} == {ICU_RULE_ID, DIAGNOSIS_RULE_ID}
    for finding in projection["findings"]:
        assert finding["patient_id"] == "P1"
        assert finding["claim_id"] == "C1"
        assert finding["kind"] == finding["rule_id"]
        assert finding["status"] == "violation"
        assert finding["finding_type"] == "compliance"
        assert finding["detail"]
        assert finding["sut_section_id"]
        assert all(value is None for key, value in finding.items() if key.endswith("_try"))
        assert finding["savings_try"] is None
        assert finding["billed_try"] is None
    assert all(row["status"] == "evaluated" and row["missing_inputs"] == [] for row in projection["evaluations"])
    assert not any(row.get("rule_id") in {ICU_RULE_ID, DIAGNOSIS_RULE_ID} for row in report.recommended_actions)


@pytest.mark.parametrize("diagnosis,available,violation", [
    ("", True, True), (" \t ", True, True), ("J96.0", True, False),
    (None, False, False), (float("nan"), False, False), (123, False, False),
])
def test_diagnosis_provenance_through_normal_ingestion(diagnosis, available, violation):
    ctx = _context([_header(primary_icd10=diagnosis)])
    assert ctx.claims[0].primary_icd10_available is available
    projection = _report(ctx).claim_compliance
    evaluation = _evaluation(projection, "C1", DIAGNOSIS_RULE_ID)
    assert evaluation["status"] == ("evaluated" if available else "missing_inputs")
    assert evaluation["missing_inputs"] == ([] if available else ["primary_icd10"])
    assert any(row["rule_id"] == DIAGNOSIS_RULE_ID for row in projection.findings) is violation


def test_absent_diagnosis_and_legacy_constructor_are_unknown():
    header = _header()
    del header["primary_icd10"]
    ctx = _context([header])
    assert not ctx.claims[0].primary_icd10_available
    fields = asdict(ctx.claims[0])
    del fields["primary_icd10_available"]
    assert not ClaimHeader(**fields).primary_icd10_available
    assert _evaluation(_report(ctx).claim_compliance, "C1", DIAGNOSIS_RULE_ID)["status"] == "missing_inputs"


@pytest.mark.parametrize(
    "header_value,remove_header,diagnoses,expected_status,expected_finding",
    [
        ("", False, [_diagnosis()], "evaluated", False),
        (None, True, [_diagnosis()], "evaluated", False),
        ("", False, [], "evaluated", True),
        (None, True, [], "missing_inputs", False),
        ("J96.0", False, [_diagnosis(icd10_code="A41.9")], "evaluated", False),
        ("", False, [_diagnosis(is_primary=False)], "evaluated", True),
        ("", False, [_diagnosis(icd10_code=" ")], "evaluated", True),
        (None, True, [_diagnosis(icd10_code=" ")], "missing_inputs", False),
    ],
)
def test_k26_reconciles_header_and_normalized_primary_diagnosis(
    header_value, remove_header, diagnoses, expected_status, expected_finding,
):
    header = _header(primary_icd10=header_value)
    if remove_header:
        header.pop("primary_icd10")
    projection = _report(_context([header], diagnoses=diagnoses)).claim_compliance
    evaluation = _evaluation(projection, "C1", DIAGNOSIS_RULE_ID)
    assert evaluation["status"] == expected_status
    assert any(row["rule_id"] == DIAGNOSIS_RULE_ID for row in projection.findings) is expected_finding


def test_k26_legacy_nonblank_header_wins_even_when_availability_flag_false():
    ctx = _context([_header(primary_icd10="J96.0")])
    ctx = replace(
        ctx,
        claims=(replace(ctx.claims[0], primary_icd10_available=False),),
    )
    projection = _report(ctx).claim_compliance
    assert _evaluation(projection, "C1", DIAGNOSIS_RULE_ID)["status"] == "evaluated"
    assert not any(row["rule_id"] == DIAGNOSIS_RULE_ID for row in projection.findings)


@pytest.mark.parametrize("claim_type", ["", None, "unknown", "not_inpatient"])
def test_unknown_claim_type_never_uses_inpatient_fallback(claim_type):
    projection = _report(_context([_header(claim_type=claim_type)])).claim_compliance
    assert _evaluation(projection, "C1", ICU_RULE_ID)["missing_inputs"] == ["claim_type"]
    assert not any(row["rule_id"] == ICU_RULE_ID for row in projection.findings)


@pytest.mark.parametrize("claim_type", ["poliklinik", "ayakta", "outpatient", "gunubirlik"])
def test_recognized_outpatient_negative_is_evaluated(claim_type):
    projection = _report(_context([_header(claim_type=claim_type, primary_icd10="J96.0")])).claim_compliance
    assert projection.findings == []
    assert all(row["status"] == "evaluated" for row in projection.evaluations)


@pytest.mark.parametrize("lines,missing", [
    ([], "procedure_lines"),
    ([_line("L1", "510090"), _line("L2", "")], "procedure_code"),
    ([_line("L1", "510090"), _line("L2", None)], "procedure_code"),
])
def test_missing_procedure_inputs_not_clean_pass(lines, missing):
    projection = _report(_context(lines=lines)).claim_compliance
    assert _evaluation(projection, "C1", ICU_RULE_ID)["missing_inputs"] == [missing]
    assert not any(row["rule_id"] == ICU_RULE_ID for row in projection.findings)


def test_missing_date_rejected_at_ingestion_and_sentinel_context_not_evaluated():
    with pytest.raises(ClaimValidationError, match="missing procedure_date"):
        _context(lines=[_line("L1", "510090", procedure_date=None)])
    ctx = _context()
    ctx = replace(ctx, procedure_lines=(ctx.procedure_lines[0], replace(ctx.procedure_lines[1], procedure_date=date.min)))
    projection = claim_compliance.project_claim_compliance(
        "P1", evaluate_rule_findings("P1", ctx)
    )
    assert _evaluation(projection, "C1", ICU_RULE_ID)["missing_inputs"] == ["procedure_date"]
    assert not any(row["rule_id"] == ICU_RULE_ID for row in projection.findings)


@pytest.mark.parametrize("code", ["P552001", "P552008", "p552009"])
def test_intermediate_icu_package_exception_preserved(code):
    ctx = _context([_header(primary_icd10="J96.0")], [
        _line("L1", "510090"), _line("L2", code, procedure_name="Monitörizasyon"),
    ])
    assert _report(ctx).claim_compliance.findings == []


def test_multiple_claims_same_day_only_other_claim_reordered_and_duplicate_stable():
    ctx = _context(
        [_header("C1"), _header("C2", primary_icd10="J96.0"), _header("C3", primary_icd10=None)],
        [
            _line("L1", "510090"),
            _line("L2", "530130", procedure_date="2026-01-02"),
            _line("L3", "530330"),
            _line("L4", "530130", "C2"),
            _line("L5", "510090", "C3"),
        ],
    )
    with (
        patch.object(rule_findings, "detect_icu_bundled_leakage", wraps=rule_findings.detect_icu_bundled_leakage) as icu,
        patch.object(rule_findings, "detect_missing_diagnosis", wraps=rule_findings.detect_missing_diagnosis) as diagnosis,
    ):
        projection = _report(ctx).claim_compliance
    icu.assert_called_once()
    diagnosis.assert_called_once()
    assert {claim.claim_id for claim in diagnosis.call_args.args[0]} == {"C1", "C2", "C3"}
    assert len(projection.evaluations) == 15
    assert {(row["claim_id"], row.get("procedure_line_id")) for row in projection.findings} == {
        ("C1", "L3"), ("C1", None),
    }
    assert _report(ctx.slice_for_claim("C2")).claim_compliance.findings == []
    reordered = replace(ctx, claims=ctx.claims[::-1], procedure_lines=ctx.procedure_lines[::-1])
    assert asdict(_report(reordered).claim_compliance) == asdict(projection)
    duplicate = replace(ctx, procedure_lines=ctx.procedure_lines + (ctx.procedure_lines[1],))
    assert claim_compliance.project_claim_compliance(
        "P1", evaluate_rule_findings("P1", duplicate)
    ).findings == projection.findings


def test_identity_escaping_distinguishes_delimiters_and_patients():
    ids = []
    for patient_id, claim_id, line_id in [("P:1", "C1", "L:2"), ("P", "1:C1", "L:2"), ("P:1", "C1", "L%3A2")]:
        ctx = _context(
            [_header(claim_id, patient_id, primary_icd10="J96.0")],
            [_line("anchor", "510090", claim_id, patient_id), _line(line_id, "530130", claim_id, patient_id)],
            patient_id,
        )
        finding = patient_report.compute_patient_billing_report(patient_id, claim_context=ctx).claim_compliance.findings[0]
        assert finding["action_id"] == "claim_compliance:" + ":".join(
            quote(value, safe="")
            for value in (ICU_RULE_ID, patient_id, claim_id, "procedure", line_id)
        )
        ids.append(finding["action_id"])
    assert len(set(ids)) == 3


def test_missing_full_context_is_explicitly_unavailable():
    projection = _report(None).claim_compliance
    assert projection.findings == []
    assert len(projection.evaluations) == 5
    assert all(row["claim_id"] is None and row["status"] == "missing_inputs" and row["missing_inputs"] == ["claim_context"] for row in projection.evaluations)
    assert asdict(ClaimCompliance()) == {"findings": [], "evaluations": []}


def test_empty_headers_are_not_a_clean_pass():
    ctx = replace(_context(), claims=(), procedure_lines=())
    projection = claim_compliance.project_claim_compliance(
        "P1", evaluate_rule_findings("P1", ctx)
    )
    assert all(row["missing_inputs"] == ["claim_headers"] for row in projection.evaluations)


@pytest.mark.parametrize(
    "scope",
    ["context", "claim", "line", "orphan", "diagnosis_patient", "diagnosis_orphan"],
)
def test_patient_and_claim_scope_guard(scope):
    ctx = _context(diagnoses=[_diagnosis()]) if scope.startswith("diagnosis") else _context()
    if scope == "context":
        ctx = replace(ctx, patient_id="P2")
    elif scope == "claim":
        ctx = replace(ctx, claims=(replace(ctx.claims[0], patient_id="P2"),))
    elif scope == "line":
        ctx = replace(ctx, procedure_lines=(replace(ctx.procedure_lines[0], patient_id="P2"),))
    elif scope == "diagnosis_patient":
        ctx = replace(ctx, diagnoses=(replace(ctx.diagnoses[0], patient_id="P2"),))
    elif scope == "diagnosis_orphan":
        ctx = replace(ctx, diagnoses=(replace(ctx.diagnoses[0], claim_id="C2"),))
    else:
        ctx = replace(ctx, procedure_lines=(replace(ctx.procedure_lines[0], claim_id="C2"),))
    with pytest.raises(ValueError, match="Claim compliance"):
        _report(ctx)


@pytest.mark.parametrize("ctx", [_context(), _context(lines=[]), None])
def test_legacy_financial_report_unchanged_disabling_only_new_projection(ctx):
    actual = asdict(_report(ctx))
    with patch.object(patient_report, "project_claim_compliance", return_value=ClaimCompliance()) as projection:
        baseline = asdict(_report(ctx))
    projection.assert_called_once()
    assert projection.call_args.args[0] == "P1"
    assert isinstance(projection.call_args.args[1], RuleEvaluationBatch)
    actual.pop("claim_compliance")
    baseline.pop("claim_compliance")
    assert actual == baseline

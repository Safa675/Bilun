"""Regressions for bill-scoped checklists and incomplete drug constraint facts."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
import json
from pathlib import Path

import pytest

from src.bilun.api.public_responses import project_public_response
from src.bilun.api.routes.billing import _serialize_billing_report
from src.bilun.api.schemas import BillingReportResponse
from src.bilun.cache.build_streaming import json_ready
from src.bilun.domain.billing.claim_drug_indication import validate_drug_indication_from_claims
from src.bilun.domain.billing.claim_submission_checklist import (
    recommend_claim_submission_checklist_from_claims,
)
from src.bilun.domain.billing.drug_indication_findings import evaluate_drug_indication_findings
from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims.parsing.row_parsers import parse_procedure_line
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _drug_line


def _ctx(claim, line):
    return PatientClaimContext(
        patient_id=claim.patient_id,
        claims=(claim,),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(line,),
        diagnoses=(),
    )


def _ozurdex(**changes):
    return _drug_line(
        drug_name="OZURDEX (DEKSAMETAZON)",
        report_present=True,
        prescriber_specialty="göz hastalıkları",
        **changes,
    )


@pytest.mark.parametrize("phase", [None, False, True])
def test_authored_annual_constraint_requires_count_even_with_phase(phase):
    result = evaluate_drug_indication_line_detailed(
        drug_line=_ozurdex(is_loading_phase=phase),
        claim=_claim(primary_icd10="H34.8"),
        diagnoses=[],
    )
    assert result["selected_rule_id"] == "4.2.33.B.deksametazon_itv_implant_rvdt_srvt"
    assert result["violation"]["violation_kind"] == "needs_dose_verification"
    assert result["missing_inputs"] == ["annual_application_count"]
    assert result["evaluation_status"] == "missing_inputs"
    assert result["applicability_status"] == "eligible"


@pytest.mark.parametrize("count,kind", [(1, None), (5, "annual_max_exceeded")])
def test_authored_annual_count_controls(count, kind):
    result = evaluate_drug_indication_line_detailed(
        drug_line=_ozurdex(annual_application_count=count),
        claim=_claim(primary_icd10="H34.8"),
        diagnoses=[],
    )
    assert (result["violation"] or {}).get("violation_kind") == kind
    assert result["evaluation_status"] == "evaluated"
    assert result["missing_inputs"] == []


@pytest.mark.parametrize(
    "count,phase,missing,kind",
    [
        (None, None, ["is_loading_phase"], "needs_dose_verification"),
        (1, None, ["is_loading_phase"], "needs_dose_verification"),
        (None, True, ["annual_application_count"], "needs_dose_verification"),
        (None, False, [], None),
        (0, True, [], None),
        (4, True, [], "loading_dose_exceeded"),
    ],
)
def test_loading_only_constraint_requires_its_applicable_inputs(count, phase, missing, kind):
    rule = {
        "rule_id": "synthetic.loading",
        "drug_names": ["SYNTHETIC MEDICINE"],
        "icd10_codes": ["C34"],
        "loading_dose_count": 3,
    }
    result = evaluate_drug_indication_line_detailed(
        drug_line=_drug_line(
            drug_name="SYNTHETIC MEDICINE", annual_application_count=count, is_loading_phase=phase
        ),
        claim=_claim(),
        diagnoses=[],
        rules=[rule],
    )
    assert (result["violation"] or {}).get("violation_kind") == kind
    assert result["missing_inputs"] == missing
    assert result["evaluation_status"] == ("missing_inputs" if missing else "evaluated")


@pytest.mark.parametrize(
    "entry", [{}, {"drug_or_class": ""}, {"drug_or_class": "  "}, {"drug_or_class": None}]
)
def test_authored_prior_therapy_blank_identity_is_unknown(entry):
    result = evaluate_drug_indication_line_detailed(
        drug_line=_drug_line(
            drug_name="BOSUTINIB",
            report_present=True,
            prescriber_specialty="tıbbi onkoloji",
            biomarkers=({"marker": "BCR_ABL", "status": "positive"},),
            prior_therapies=(entry,),
        ),
        claim=_claim(primary_icd10="C92.1"),
        diagnoses=[],
    )
    assert result["violation"]["violation_kind"] == "needs_prior_therapy_verification"
    assert result["missing_inputs"] == ["prior_therapies.drug_or_class"]
    assert result["evaluation_status"] == "missing_inputs"


@pytest.mark.parametrize(
    "prior,kind",
    [
        (({"drug_or_class": "unrelated"},), "prior_therapy_mismatch"),
        (({"drug_or_class": "unrelated"}, {}), "needs_prior_therapy_verification"),
        (({}, {"drug_or_class": " IMATINIB ", "outcome": "complete_response"}), None),
    ],
)
def test_prior_therapy_named_controls_preserve_flexible_outcome(prior, kind):
    result = evaluate_drug_indication_line_detailed(
        drug_line=_drug_line(drug_name="SYNTHETIC MEDICINE", prior_therapies=prior),
        claim=_claim(),
        diagnoses=[],
        rules=[
            {
                "rule_id": "synthetic.prior",
                "drug_names": ["SYNTHETIC MEDICINE"],
                "icd10_codes": ["C34"],
                "requires_prior_therapy": {"drug_or_class": "imatinib", "outcome": "resistant"},
            }
        ],
    )
    assert (result["violation"] or {}).get("violation_kind") == kind


@pytest.mark.parametrize(
    "constraint,missing",
    [
        ({"report_required": True}, "drug_specialty_board_report_present"),
        ({"report_duration_months": 12}, "drug_report_duration_months"),
        ({"inpatient_only": True}, "drug_inpatient_supply"),
        ({"prescriber_specialties": ["onkoloji"]}, "prescriber_specialty"),
        ({"max_applications_per_year": 4}, "annual_application_count"),
        (
            {"required_biomarkers": [{"marker": "HER2", "status_any": ["positive"]}]},
            "biomarkers.HER2",
        ),
        ({"requires_prior_therapy": {"drug_or_class": "imatinib"}}, "prior_therapies"),
    ],
)
def test_missing_constraint_status_survives_all_domain_projections(constraint, missing):
    claim, line = _claim(), _drug_line(drug_name="SYNTHETIC MEDICINE")
    rule = {
        "rule_id": "synthetic.constraint",
        "drug_names": ["SYNTHETIC MEDICINE"],
        "icd10_codes": ["C34"],
        **constraint,
    }
    ctx = _ctx(claim, line)
    detailed = evaluate_drug_indication_line_detailed(
        drug_line=line,
        claim=claim,
        diagnoses=[],
        rules=[rule],
    )
    batch = evaluate_drug_indication_findings(ctx.patient_id, ctx, rules=[rule])
    review = validate_drug_indication_from_claims(ctx, evaluation_batch=batch)
    for row in [
        detailed,
        detailed["violation"],
        batch.findings[0].to_dict(),
        batch.evaluations[0].to_dict(),
        batch.legacy_violations[0],
    ]:
        assert row["applicability_status"] == "eligible"
        assert row["evaluation_status"] == "missing_inputs"
        assert row["missing_inputs"] == [missing]
        assert missing in row["required_inputs"]
    assert review.exactness_status == "missing_exact_inputs"
    assert review.required_inputs_missing == [missing]
    assert review.unavailable_reason


def test_missing_dose_public_live_and_cache_projections_preserve_null_money():
    ctx = _ctx(_claim(primary_icd10="H34.8"), _ozurdex(is_loading_phase=False))
    report = compute_patient_billing_report(ctx.patient_id, claim_context=ctx)
    live = _serialize_billing_report(report)
    cached = _serialize_billing_report(json_ready(report))
    for payload in (live, cached):
        payload["drug_indication"]["findings"][0]["private_probe"] = "DROP"
        payload = project_public_response(payload, "/api/billing-report/{patient_id}")
        assert "private_probe" not in payload["drug_indication"]["findings"][0]
        model = BillingReportResponse.model_validate(payload)
        review = model.drug_indication
        assert review.exactness_status == "missing_exact_inputs"
        assert review.required_inputs_missing == ["annual_application_count"]
        for row in [*review.findings, *review.evaluations]:
            assert row.evaluation_status == "missing_inputs"
            assert row.missing_inputs == ["annual_application_count"]
        assert review.violations[0]["evaluation_status"] == "missing_inputs"
        action = next(
            row for row in payload["recommended_actions"] if row.get("surface") == "drug_indication"
        )
        for key in ("sgk_uplift_try", "audit_risk_try", "compliance_savings_try"):
            assert action[key] is None
        assert "_legacy_base" not in payload["drug_indication"]["findings"][0]
    assert live["drug_indication"] == cached["drug_indication"]


@pytest.mark.parametrize("first_has_procedure", [False, True])
def test_patient_documentation_is_order_invariant_union_of_real_bill_slices(first_has_procedure):
    first = replace(_claim(), claim_type="ayaktan", department="Kardiyoloji")
    second = replace(first, claim_id="C2", department="Dermatoloji")
    errors = []
    proc = parse_procedure_line(
        {
            "procedure_line_id": "P2",
            "patient_id": first.patient_id,
            "claim_id": "C2",
            "procedure_date": date(2026, 1, 2),
            "procedure_code": "700280",
            "procedure_name": "Kriyoterapi malign lezyonlar",
            "procedure_category": "islem",
            "quantity": 1,
            "unit_price_try": 100,
            "billed_amount_try": 100,
            "expected_payable_try": 100,
        },
        errors,
    )
    assert not errors
    ctx = replace(
        _ctx(first, _drug_line(report_present=True)),
        claims=(first, second),
        drug_lines=(),
        procedure_lines=(
            (
                replace(
                    proc, claim_id=first.claim_id, procedure_line_id="P1", procedure_code="530030"
                ),
                proc,
            )
            if first_has_procedure
            else (proc,)
        ),
    )
    items = recommend_claim_submission_checklist_from_claims(ctx).items
    union = [
        item
        for claim in ctx.claims
        for item in recommend_claim_submission_checklist_from_claims(
            ctx.slice_for_claim(claim.claim_id)
        ).items
    ]
    reversed_items = recommend_claim_submission_checklist_from_claims(
        replace(ctx, claims=tuple(reversed(ctx.claims)))
    ).items
    by_id = lambda rows: {row["checklist_id"]: row for row in rows}
    assert by_id(items) == by_id(union) == by_id(reversed_items)
    assert any(row["fatura_inceleme_ref"] == "DERMATOLOJİ-2" for row in items)
    assert all(
        row["claim_id"] == "C2" for row in items if row["fatura_inceleme_ref"] == "DERMATOLOJİ-2"
    )
    if first_has_procedure:
        assert {row["claim_id"] for row in items} == {"C1", "C2"}
    else:
        assert all(row["claim_id"] == "C2" for row in items)


def test_readiness_ids_scope_actual_drug_line_patient_claim_and_trigger():
    claim = _claim()
    second = replace(claim, claim_id="C2")
    line = _drug_line(report_present=False)
    ctx = replace(
        _ctx(claim, line),
        claims=(claim, second),
        drug_lines=(
            line,
            replace(line, drug_claim_line_id="D2"),
            replace(line, claim_id="C2"),
        ),
    )
    rows = recommend_claim_submission_checklist_from_claims(ctx).items
    assert len(rows) == len({row["checklist_id"] for row in rows}) == 3
    assert {(row["claim_id"], row["line_id"]) for row in rows} == {
        ("C1", "D1"),
        ("C1", "D2"),
        ("C2", "D1"),
    }
    assert "0612_board_report_missing:" not in {row["checklist_id"] for row in rows}
    again = recommend_claim_submission_checklist_from_claims(
        replace(ctx, claims=tuple(reversed(ctx.claims)), drug_lines=tuple(reversed(ctx.drug_lines)))
    )
    assert {row["checklist_id"] for row in rows} == {row["checklist_id"] for row in again.items}


def test_known_annual_excess_is_retained_when_loading_phase_is_unknown():
    result = evaluate_drug_indication_line_detailed(
        drug_line=_drug_line(drug_name="SYNTHETIC MEDICINE", annual_application_count=5),
        claim=_claim(),
        diagnoses=[],
        rules=[
            {
                "rule_id": "synthetic.dose",
                "drug_names": ["SYNTHETIC MEDICINE"],
                "icd10_codes": ["C34"],
                "max_applications_per_year": 4,
                "loading_dose_count": 3,
            }
        ],
    )
    assert result["violation"]["violation_kind"] == "annual_max_exceeded"
    assert result["violation"]["severity"] == "error"
    assert result["evaluation_status"] == "missing_inputs"
    assert result["missing_inputs"] == ["is_loading_phase"]


def test_supplemental_missing_report_keeps_primary_identity_and_honest_certainty():
    result = evaluate_drug_indication_line_detailed(
        drug_line=_drug_line(drug_name="SYNTHETIC MEDICINE"),
        claim=_claim(),
        diagnoses=[],
        rules=[
            {
                "rule_id": "synthetic.primary",
                "drug_names": ["SYNTHETIC MEDICINE"],
                "icd10_codes": ["C34"],
            },
            {
                "rule_id": "synthetic.supplemental",
                "drug_names": ["SYNTHETIC MEDICINE"],
                "report_required": True,
            },
        ],
    )
    assert result["selected_rule_id"] == "synthetic.primary"
    assert result["violation"]["selected_rule_id"] == "synthetic.supplemental"
    assert (
        result["evaluation_status"] == result["violation"]["evaluation_status"] == "missing_inputs"
    )
    assert result["missing_inputs"] == ["drug_specialty_board_report_present"]


def _frontend_fixture():
    claim = _claim(primary_icd10="H34.8")
    line = replace(_ozurdex(is_loading_phase=False), drug_code="SYN-OZURDEX")
    ctx = _ctx(claim, line)
    review = project_public_response(
        _serialize_billing_report(
            compute_patient_billing_report(ctx.patient_id, claim_context=ctx)
        ),
        "/api/billing-report/{patient_id}",
    )["drug_indication"]
    ctx = replace(
        ctx,
        claims=(claim, replace(claim, claim_id="C2")),
        drug_lines=(
            replace(line, drug_specialty_board_report_present=False),
            replace(line, drug_specialty_board_report_present=False, drug_claim_line_id="D2"),
            replace(line, drug_specialty_board_report_present=False, claim_id="C2"),
        ),
    )
    rows = recommend_claim_submission_checklist_from_claims(ctx).items
    return {
        "drugReview": {
            key: review[key]
            for key in (
                "exactness_status",
                "required_inputs_missing",
                "unavailable_reason",
                "findings",
                "evaluations",
                "violations",
                "violation_count",
                "error_count",
            )
        },
        "checklistItems": [
            {
                key: row[key]
                for key in (
                    "checklist_id",
                    "claim_id",
                    "patient_id",
                    "line_id",
                    "sut_anchor",
                    "severity",
                )
            }
            for row in rows
        ],
    }


def test_ui_fixture_matches_real_public_backend_output():
    fixture = (
        Path(__file__).parents[4] / "frontend/src/test/fixtures/checklist-constraint-inputs.json"
    )
    assert json.loads(fixture.read_text()) == _frontend_fixture()


def test_readiness_identity_escapes_components_and_distinguishes_triggers(monkeypatch):
    from src.bilun.domain.prose_rules import claim_readiness as readiness

    original = readiness.load_claim_readiness_triggers()
    trigger = next(row for row in original["triggers"] if row["line_type"] == "drug")
    monkeypatch.setattr(
        readiness,
        "load_claim_readiness_triggers",
        lambda: {
            "triggers": [trigger, {**trigger, "trigger_key": trigger["trigger_key"] + ":other"}],
        },
    )
    ids = []
    for patient, claim_id in (("P:C", "X"), ("P", "C:X")):
        claim = replace(_claim(), patient_id=patient, claim_id=claim_id)
        line = replace(_drug_line(report_present=False), patient_id=patient, claim_id=claim_id)
        rows = readiness.detect_claim_readiness_items(claim, _ctx(claim, line))
        assert len(rows) == 2
        ids.extend(row["checklist_id"] for row in rows)
    assert len(ids) == len(set(ids)) == 4
    assert all("%3A" in value for value in ids)

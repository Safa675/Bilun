"""Canonical drug-indication finding and projection contracts."""

from __future__ import annotations

from dataclasses import replace

import pytest

from src.bilun.cache.build_streaming import json_ready
from tests.unit.domain.prose_rules.test_drug_indication import (
    _diagnosis,
    _orencia_claim,
    _orencia_line,
)

from src.bilun.domain.billing.drug_indication_findings import (
    DrugIndicationEvaluationBatch,
    evaluate_drug_indication_findings,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext


def _context(*, primary_icd10: str, primary_available: bool, secondary: tuple = ()):
    claim = _orencia_claim(
        primary_icd10=primary_icd10,
        primary_available=primary_available,
    )
    line = replace(
        _orencia_line(report_present=False),
        claim_id=claim.claim_id,
        patient_id=claim.patient_id,
        episode_id=claim.episode_id,
    )
    return PatientClaimContext(
        patient_id=claim.patient_id,
        claims=(claim,),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(line,),
        diagnoses=secondary,
    )


def test_full_corpus_mismatch_has_bounded_route_evidence_and_stable_id() -> None:
    ctx = _context(primary_icd10="E66.9", primary_available=True)

    first = evaluate_drug_indication_findings(ctx.patient_id, ctx)
    second = evaluate_drug_indication_findings(ctx.patient_id, ctx)

    assert isinstance(first, DrugIndicationEvaluationBatch)
    assert first == second
    assert len(first.evaluations) == 1
    assert len(first.findings) == 1
    finding = first.findings[0]
    assert finding.finding_kind == "indication_mismatch"
    assert finding.finding_id == (
        "drug_indication:P-ORENCIA:C-ORENCIA:D1:indication_mismatch"
    )
    assert finding.observed_icd10_codes == ("E66.9",)
    assert finding.matched_icd10_codes == ()
    assert {"M05", "M06", "M08"}.issubset(
        {
            code
            for route in finding.eligible_routes
            for code in (*route.icd10_codes, *route.icd10_ranges)
        }
    )
    assert len(finding.eligible_routes) <= 24
    assert finding.to_dict()["finding_id"] == finding.finding_id
    assert "sgk_uplift_try" not in finding.to_dict()
    from src.bilun.cache.build_streaming import json_ready

    cached = json_ready(finding)
    assert "_legacy_base" not in cached
    assert len(cached["eligible_routes"]) <= 24
    cached_batch = json_ready(first)
    assert "_legacy_base" not in cached_batch["findings"][0]
    assert first.legacy_violations[0]["finding_id"] == finding.finding_id


def test_secondary_diagnosis_is_evaluated_without_relabeling_primary() -> None:
    ctx = _context(
        primary_icd10="E66.9",
        primary_available=True,
        secondary=(_diagnosis(code="M06.9"),),
    )

    batch = evaluate_drug_indication_findings(ctx.patient_id, ctx)
    finding = batch.findings[0]

    assert finding.finding_kind == "ambiguous_route"
    assert finding.observed_icd10_codes == ("E66.9", "M06.9")
    assert finding.matched_icd10_codes == ("M06.9",)
    assert finding.unmatched_icd10_codes == ("E66.9",)
    assert finding.selected_rule_id is None


def test_missing_diagnosis_is_manual_review_not_mismatch() -> None:
    ctx = _context(primary_icd10="", primary_available=False)

    batch = evaluate_drug_indication_findings(ctx.patient_id, ctx)
    finding = batch.findings[0]

    assert finding.applicability_status == "missing_diagnosis"
    assert finding.finding_kind == "missing_diagnosis"
    assert finding.evaluation_status == "missing_inputs"
    assert "claim_diagnoses" in finding.missing_inputs
    assert "primary_icd10" in finding.missing_inputs


def test_canonical_line_evaluation_invokes_prose_detector_once(monkeypatch) -> None:
    from src.bilun.domain.prose_rules import drug_indication as prose

    ctx = _context(primary_icd10="E66.9", primary_available=True)
    original = prose.evaluate_drug_indication_line_detailed
    calls = 0

    def counted(*, drug_line, claim, diagnoses, rules=None):
        nonlocal calls
        calls += 1
        return original(
            drug_line=drug_line,
            claim=claim,
            diagnoses=diagnoses,
            rules=rules,
        )

    monkeypatch.setattr(prose, "evaluate_drug_indication_line_detailed", counted)

    batch = evaluate_drug_indication_findings(ctx.patient_id, ctx)

    assert calls == 1
    assert len(batch.findings) == 1


@pytest.mark.parametrize("primary_icd10", ["M06.9", "M08.0"])
def test_reversed_full_corpus_has_identical_canonical_result(primary_icd10: str) -> None:
    from src.bilun.domain.prose_rules.drug_indication import list_drug_indication_rules

    ctx = _context(primary_icd10=primary_icd10, primary_available=True)
    rules = list_drug_indication_rules()

    original = evaluate_drug_indication_findings(ctx.patient_id, ctx, rules=rules)
    reversed_corpus = evaluate_drug_indication_findings(
        ctx.patient_id,
        ctx,
        rules=list(reversed(rules)),
    )
    permuted_corpus = evaluate_drug_indication_findings(
        ctx.patient_id,
        ctx,
        rules=[*rules[1::2], *rules[::2]],
    )

    assert json_ready(original) == json_ready(reversed_corpus)
    assert json_ready(original) == json_ready(permuted_corpus)
    assert original.findings[0].finding_kind == "ambiguous_route"
    assert original.findings[0].selected_rule_id is None
    assert original.legacy_violations[0]["rule_id"] is None


def test_equivalent_diagnosis_inputs_have_canonical_observed_order() -> None:
    first = _context(
        primary_icd10="E66.9",
        primary_available=True,
        secondary=(_diagnosis(code="M08.0"), _diagnosis(code="M06.9")),
    )
    second = _context(
        primary_icd10="E66.9",
        primary_available=True,
        secondary=(_diagnosis(code="M06.9"), _diagnosis(code="M08.0")),
    )

    first_batch = evaluate_drug_indication_findings(first.patient_id, first)
    second_batch = evaluate_drug_indication_findings(second.patient_id, second)

    assert json_ready(first_batch) == json_ready(second_batch)
    assert first_batch.findings[0].observed_icd10_codes == ("E66.9", "M06.9", "M08.0")


def test_real_route_icd_evidence_exposes_original_count_and_truncation() -> None:
    from src.bilun.domain.prose_rules.drug_indication import list_drug_indication_rules

    antidote_rule = next(
        rule
        for rule in list_drug_indication_rules()
        if rule.get("rule_id") == "4.2.3.poisoning_antidote_full_coverage_no_report"
    )
    ctx = _context(primary_icd10="E66.9", primary_available=True)
    ctx = replace(
        ctx,
        drug_lines=(replace(ctx.drug_lines[0], drug_name="PANZEHIR"),),
    )

    batch = evaluate_drug_indication_findings(
        ctx.patient_id,
        ctx,
        rules=[antidote_rule],
    )

    route = batch.findings[0].eligible_routes[0]
    assert len(route.icd10_codes) == 12
    assert route.icd10_code_count == 23
    assert route.icd10_codes_truncated is True
    assert route.icd10_range_count == 0
    assert route.icd10_ranges_truncated is False


def test_observed_diagnosis_truncation_is_explicit() -> None:
    ctx = _context(
        primary_icd10="E66.9",
        primary_available=True,
        secondary=tuple(_diagnosis(code=f"Z{index:02d}.1") for index in range(70)),
    )

    batch = evaluate_drug_indication_findings(ctx.patient_id, ctx)
    finding = batch.findings[0]

    assert len(finding.observed_icd10_codes) <= 64
    assert finding.observed_icd10_count == 71
    assert finding.observed_icd10_truncated is True
    assert finding.to_dict()["observed_icd10_truncated"] is True


def _course_context(*, days: int = 3, other_report_line: bool = False):
    """One claim, one drug given on `days` days: a line per day, as a course is billed."""
    ctx = _context(primary_icd10="E66.9", primary_available=True)
    first = ctx.drug_lines[0]
    lines = tuple(replace(first, drug_claim_line_id=f"D{n}") for n in range(1, days + 1))
    if other_report_line:
        lines = (*lines, replace(first, drug_claim_line_id="D9", drug_name="BASKA ILAC", barkod="111", drug_code="X"))
    return replace(ctx, drug_lines=lines)


def test_the_same_finding_on_each_day_of_a_course_is_one_finding_naming_every_line() -> None:
    ctx = _course_context(days=3)
    batch = evaluate_drug_indication_findings(ctx.patient_id, ctx)

    (finding,) = batch.findings
    assert finding.finding_id == "drug_indication:P-ORENCIA:C-ORENCIA:D1:indication_mismatch"  # the first line's id
    assert finding.drug_claim_line_id == "D1"
    assert finding.drug_claim_line_ids == ("D1", "D2", "D3")
    assert finding.to_dict()["drug_claim_line_ids"] == ["D1", "D2", "D3"]
    assert finding.to_dict()["line_count"] == 3
    assert "3 fatura satırını" in finding.explanation_tr
    (legacy,) = batch.legacy_violations
    assert legacy["drug_claim_line_ids"] == ["D1", "D2", "D3"] and legacy["line_count"] == 3
    # every line is still evaluated, and each evaluation points at the one finding
    assert [e.drug_claim_line_id for e in batch.evaluations] == ["D1", "D2", "D3"]
    assert {e.finding_id for e in batch.evaluations} == {finding.finding_id}


def test_a_single_line_finding_is_unchanged() -> None:
    ctx = _context(primary_icd10="E66.9", primary_available=True)
    (finding,) = evaluate_drug_indication_findings(ctx.patient_id, ctx).findings
    assert finding.drug_claim_line_ids == ("D1",) and finding.to_dict()["line_count"] == 1
    assert "fatura satırını" not in finding.explanation_tr


def test_another_drug_on_the_claim_stays_its_own_finding() -> None:
    ctx = _course_context(days=2, other_report_line=True)
    batch = evaluate_drug_indication_findings(ctx.patient_id, ctx)
    same_drug = [f for f in batch.findings if f.drug_claim_line_id == "D1"]
    assert len(same_drug) == 1 and same_drug[0].drug_claim_line_ids == ("D1", "D2")
    assert all("D9" not in f.drug_claim_line_ids or f.drug_claim_line_ids == ("D9",) for f in batch.findings)


def test_the_same_drug_on_two_claims_is_two_findings() -> None:
    ctx = _context(primary_icd10="E66.9", primary_available=True)
    claim, line = ctx.claims[0], ctx.drug_lines[0]
    other_claim = replace(claim, claim_id="C-OTHER")
    other_line = replace(line, drug_claim_line_id="D2", claim_id="C-OTHER")
    batch = evaluate_drug_indication_findings(
        ctx.patient_id, replace(ctx, claims=(claim, other_claim), drug_lines=(line, other_line))
    )
    assert sorted(f.claim_id for f in batch.findings) == ["C-ORENCIA", "C-OTHER"]
    assert all(len(f.drug_claim_line_ids) == 1 for f in batch.findings)


def test_the_public_billing_report_keeps_every_line_of_a_grouped_finding() -> None:
    # The public contract drops a list it does not declare as a list.
    from src.bilun.api.public_responses import project_public_response

    ctx = _course_context(days=2)
    batch = evaluate_drug_indication_findings(ctx.patient_id, ctx)
    payload = {"drug_indication": {"findings": [f.to_dict() for f in batch.findings], "violations": list(batch.legacy_violations)}}
    review = project_public_response(payload, "/api/billing-report/{patient_id}")["drug_indication"]
    for row in (review["findings"][0], review["violations"][0]):
        assert row["drug_claim_line_ids"] == ["D1", "D2"]
        assert row["line_count"] == 2

"""Source, scope and clinical boundaries of the closed-epiphysis adult GH draft."""
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import polars as pl
import pytest

from scripts.sut.prose.clause_identity import normalize_for_hash
from src.bilun.domain.claims.adult_gh import AdultGhEvidence, AdultGhStimulationTest
from src.bilun.domain.prose_rules import adult_gh_draft as draft
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
from tests.unit.domain.prose_rules.test_drug_indication_4206 import _claim, _drug_line

DAY = date(2026, 10, 5)
RULE = "4.2.6.adult_somatropin_board_report"
ITT_RULE = "4.2.6.A2.insulin_tolerance_test_peak_gh_report"
PREFIX = "adult_gh_evidence."
REF_HASHES = {
    "4.2.6.A-2.(2)#5589013c": "5589013cf2695f8bafa21f7570ec2535352624b0488b4afbfbcd10a3889e7e1b",
    "4.2.6.A-2.a#80b6dded": "80b6dded934f6919ed8b77598dc26b367515f16620be8db808d322141445fe6f",
    "4.2.6.A-2.b#9b0bad75": "9b0bad7597bdb8f0a7aeaf559ce72afaff7f2694b90ea0078c851daef9e27acd",
    "4.2.6.A-2.(3)#3c094940": "3c09494073472c853e98614056687835dedbd249fafee44afdc9a73821a1580e",
    "4.2.6.A-2.(4)#e9d92dba": "e9d92dbac88d938159baea3ffd701f349bdbc8ecaebbc7bd647bf9fa0c97677c",
}


def stimulation(test_id="T1", *, kind="itt", **changes):
    return AdultGhStimulationTest(**{
        "test_id": test_id, "performed_on": DAY - timedelta(days=1), "kind": kind,
        "inadequate_response_documented": True, "peak_gh_mcg_l": 2.9,
        "peak_gh_documented_in_report": True,
        "retest_after_epiphyseal_closure_stop": True, **changes,
    })


def facts(**changes):
    return AdultGhEvidence(**{
        "applies_on": DAY, "assessment_date": DAY,
        "diagnosis_pathway": "adult_hypothalamic_pituitary",
        "adult_hypothalamic_pituitary_gh_deficiency_suspected": True,
        "childhood_gh_deficiency_diagnosed": True,
        "childhood_gh_treatment_received": True,
        "gh_stopped_due_to_epiphyseal_closure": True,
        "additional_anterior_pituitary_deficiency_confirmed": False,
        "itt_contraindicated": False,
        "stimulation_tests": (stimulation(), stimulation("T2", kind="other")),
        **changes,
    })


def line(evidence=None, **changes):
    return SimpleNamespace(**{
        "drug_name": "somatropin", "drug_claim_date": DAY, "gh_patient_group": "adult",
        "epiphyses_closed": True, "gh_treatment_phase": "initiation",
        "adult_gh_evidence": facts() if evidence is None else evidence,
        **changes,
    })


def candidate(evidence=None, *, rule=RULE, **changes):
    return draft.evaluate_adult_gh_closed_epiphysis_candidate(line(evidence, **changes), rule)


def authority(monkeypatch, status):
    calls = []

    def resolve(family, service):
        calls.append((family, service))
        return SimpleNamespace(status=status, model_dump=lambda: {
            "family_id": family, "status": status,
            "service_date": service.isoformat() if service else None,
        })

    monkeypatch.setattr(draft, "resolve_source_authority", resolve)
    return calls


def assert_incomplete(outcome):
    assert outcome["clinical_eligibility_complete"] is False
    assert outcome["verification_status"] == "ai_generated_pending_review"
    assert outcome["sut_section"] == "4.2.6.A-2"
    assert outcome["source_refs"] == list(REF_HASHES)
    assert "runtime_coverage" not in outcome


def test_five_operative_source_refs_match_both_pinned_active_contexts_and_corpus():
    context_path = Path("data/gazette/source_evidence/adult_gh_closed_epiphysis_context.json")
    context = json.loads(context_path.read_text())
    assert context["runtime_branch_eligibility_implemented"] is False
    assert context["predicate_ids"] == []
    assert context["source_applicability_condition"] == {
        "field": "epiphyses_closed", "value": True, "inferred_from_adult_age": False,
    }
    assert draft.SOURCE_REFS == tuple(REF_HASHES)
    assert len(context["sources"]) == 2
    for source in context["sources"]:
        for ref, expected in REF_HASHES.items():
            paragraphs = [row for row in source["paragraphs"] if row["text_sha256"] == expected]
            assert len(paragraphs) == 1, ref
            paragraph = paragraphs[0]
            assert paragraph["active_text"] == paragraph["text"]
            assert hashlib.sha256(normalize_for_hash(paragraph["active_text"]).encode()).hexdigest() == expected
            assert all(run["struck"] is False for run in paragraph["runs"])
    frame = pl.read_parquet("data/gazette/sut_clauses.parquet")
    for ref, expected in REF_HASHES.items():
        rows = frame.filter((pl.col("clause_key") == ref) & pl.col("is_in_force")).to_dicts()
        assert len(rows) == 1
        assert hashlib.sha256(normalize_for_hash(rows[0]["in_force_text"]).encode()).hexdigest() == expected

    evidence = json.loads(Path("data/gazette/source_evidence/adult_gh_closed_epiphysis_candidate.json").read_text())
    assert evidence["family_id"] == draft.AUTHORITY_ID
    assert evidence["contract_kind"] == "source_pinned_candidate_only"
    assert evidence["source_refs"] == list(REF_HASHES)
    assert evidence["source_context"]["sha256"] == hashlib.sha256(context_path.read_bytes()).hexdigest()
    assert evidence["verification_status"] == "ai_generated_pending_review"
    for flag in ("source_date_admission", "independent_clinical_interpretation_released",
                 "clinical_eligibility_complete", "runtime_branch_eligibility_implemented"):
        assert evidence[flag] is False
    assert len(evidence["operative_paragraphs"]) == 5
    for binding in evidence["operative_paragraphs"]:
        expected = REF_HASHES[binding["source_ref"]]
        assert binding["text_sha256"] == expected
        assert hashlib.sha256(normalize_for_hash(binding["active_text"]).encode()).hexdigest() == expected
        for source in context["sources"]:
            index = binding["source_paragraph_indices_zero_based"][source["file_name"]]
            paragraph = next(row for row in source["paragraphs"] if row["docx_paragraph_index_zero_based"] == index)
            assert paragraph["active_text"] == binding["active_text"]


@pytest.mark.parametrize("pathway", ["childhood_onset_retest", "adult_hypothalamic_pituitary"])
@pytest.mark.parametrize("rule", [RULE, ITT_RULE])
def test_two_diagnosis_paths_clear_only_complete_necessary_candidate_checks(pathway, rule):
    outcome = candidate(facts(diagnosis_pathway=pathway), rule=rule)
    assert outcome["criterion_status"] == "criterion_clear"
    assert outcome["missing_inputs"] == []
    assert all(check["status"] == "pass" for check in outcome["checks"])
    assert_incomplete(outcome)


@pytest.mark.parametrize("count,extra,status", [
    (0, False, "restriction_not_met"), (0, True, "restriction_not_met"),
    (0, None, "restriction_not_met"), (1, False, "restriction_not_met"),
    (1, True, "criterion_clear"), (1, None, "unknown"),
    (2, False, "criterion_clear"), (2, True, "criterion_clear"),
    (2, None, "criterion_clear"), (3, False, "criterion_clear"),
])
def test_explicit_distinct_test_count_and_documented_pituitary_exception(count, extra, status):
    tests = tuple(stimulation(f"T{index}") for index in range(count))
    outcome = candidate(facts(stimulation_tests=tests,
                              additional_anterior_pituitary_deficiency_confirmed=extra))
    assert outcome["criterion_status"] == status
    if count == 1 and extra is None:
        assert PREFIX + "additional_anterior_pituitary_deficiency_confirmed" in outcome["missing_inputs"]
    assert_incomplete(outcome)


@pytest.mark.parametrize("field,pathway", [
    ("childhood_gh_deficiency_diagnosed", "childhood_onset_retest"),
    ("childhood_gh_treatment_received", "childhood_onset_retest"),
    ("gh_stopped_due_to_epiphyseal_closure", "childhood_onset_retest"),
    ("adult_hypothalamic_pituitary_gh_deficiency_suspected", "adult_hypothalamic_pituitary"),
])
@pytest.mark.parametrize("value,status", [(False, "restriction_not_met"), (None, "unknown"), (1, "unknown")])
def test_exception_cannot_remove_selected_diagnosis_pathway_prerequisites(field, pathway, value, status):
    outcome = candidate(facts(**{
        "diagnosis_pathway": pathway, field: value,
        "additional_anterior_pituitary_deficiency_confirmed": True,
        "stimulation_tests": (stimulation(),),
    }))
    assert outcome["criterion_status"] == status
    if status == "unknown":
        assert PREFIX + field in outcome["missing_inputs"]


@pytest.mark.parametrize("field", ["childhood_gh_deficiency_diagnosed", "childhood_gh_treatment_received",
                                  "gh_stopped_due_to_epiphyseal_closure"])
def test_adult_path_does_not_require_childhood_facts(field):
    assert candidate(facts(**{field: None}))["criterion_status"] == "criterion_clear"


@pytest.mark.parametrize("value", [None, "other", "E23.0", True])
def test_diagnosis_pathway_never_inferred_from_icd_or_other_pathway_flags(value):
    outcome = candidate(facts(diagnosis_pathway=value), icd10_codes=["E23.0"])
    assert outcome["criterion_status"] == "unknown"
    assert outcome["missing_inputs"] == [PREFIX + "diagnosis_pathway"]


@pytest.mark.parametrize("peak,status", [(0, "criterion_clear"), (2.999, "criterion_clear"),
                                         (3, "restriction_not_met"), (3.001, "restriction_not_met"),
                                         (None, "unknown"), (True, "unknown"), (-1, "unknown"),
                                         ("2.9", "unknown"), (float("nan"), "unknown")])
def test_itt_peak_has_only_the_strict_below_three_threshold(peak, status):
    assert candidate(facts(stimulation_tests=(stimulation(peak_gh_mcg_l=peak),
                                               stimulation("T2", kind="other"))))["criterion_status"] == status


@pytest.mark.parametrize("field", ["inadequate_response_documented", "peak_gh_documented_in_report"])
@pytest.mark.parametrize("value,status", [(False, "restriction_not_met"), (None, "unknown"), (1, "unknown")])
def test_itt_requires_explicit_inadequacy_and_reported_peak(field, value, status):
    outcome = candidate(facts(stimulation_tests=(stimulation(**{field: value}),
                                                stimulation("T2", kind="other"))))
    assert outcome["criterion_status"] == status


@pytest.mark.parametrize("peak", [None, 0.1, 3, 100, "2.0", float("nan")])
def test_other_test_numeric_peak_never_supplies_or_changes_inadequacy(peak):
    other = stimulation("T2", kind="other", peak_gh_mcg_l=peak,
                        peak_gh_documented_in_report=None)
    assert candidate(facts(stimulation_tests=(stimulation(), other)))["criterion_status"] == "criterion_clear"
    missing = candidate(facts(stimulation_tests=(stimulation(), replace(other, inadequate_response_documented=None))))
    assert missing["criterion_status"] == "unknown"
    assert missing["missing_inputs"] == [PREFIX + "stimulation_tests[1].inadequate_response_documented"]


@pytest.mark.parametrize("contraindicated,status", [(True, "criterion_clear"), (False, "unknown"), (None, "unknown")])
@pytest.mark.parametrize("extra,count", [(False, 2), (True, 1)])
def test_itt_preference_without_itt_is_not_a_denial(contraindicated, status, extra, count):
    outcome = candidate(facts(
        stimulation_tests=tuple(stimulation(f"T{i}", kind="other") for i in range(count)),
        itt_contraindicated=contraindicated,
        additional_anterior_pituitary_deficiency_confirmed=extra,
    ))
    assert outcome["criterion_status"] == status
    if status == "unknown":
        assert PREFIX + "clinical_interpretation_required" in outcome["missing_inputs"]


def test_itt_and_explicit_contraindication_need_context_reconciliation():
    outcome = candidate(facts(itt_contraindicated=True))
    assert outcome["criterion_status"] == "unknown"
    assert outcome["missing_inputs"] == [PREFIX + "itt_contraindication_context_reconciliation"]


@pytest.mark.parametrize("retest,status", [(False, "restriction_not_met"), (None, "unknown"), (1, "unknown")])
def test_childhood_each_test_must_document_retesting_after_closure_stop(retest, status):
    tests = (stimulation(), stimulation("T2", kind="other", retest_after_epiphyseal_closure_stop=retest))
    assert candidate(facts(diagnosis_pathway="childhood_onset_retest", stimulation_tests=tests))["criterion_status"] == status
    assert candidate(facts(stimulation_tests=tests))["criterion_status"] == "criterion_clear"


@pytest.mark.parametrize("tests,missing", [
    (None, "stimulation_tests"),
    ([stimulation(), None], "stimulation_tests"),
    ([stimulation(), stimulation("T2"), "invalid"], "stimulation_tests"),
    ((stimulation(), replace(stimulation("T2"), test_id=None)), "stimulation_tests[1].test_id"),
    ((stimulation(), stimulation("T2", kind="unknown")), "stimulation_tests[1].kind"),
    ((stimulation(), stimulation("T2", performed_on=None)), "stimulation_tests[1].performed_on"),
    ((stimulation(), stimulation("T1")), "stimulation_tests.distinct_test_records"),
    ((stimulation(), stimulation(" T1 ", performed_on=DAY - timedelta(days=2))), "stimulation_tests.distinct_test_records"),
])
def test_missing_malformed_duplicate_records_unknown_before_negative_diagnosis(tests, missing):
    outcome = candidate(facts(stimulation_tests=tests,
                              adult_hypothalamic_pituitary_gh_deficiency_suspected=False))
    assert outcome["criterion_status"] == "unknown"
    assert PREFIX + missing in outcome["missing_inputs"]


def test_unknown_relevant_test_fact_overrides_another_explicit_negative_fact():
    outcome = candidate(facts(
        adult_hypothalamic_pituitary_gh_deficiency_suspected=False,
        stimulation_tests=(stimulation(), stimulation("T2", kind="other", inadequate_response_documented=None)),
    ))
    assert outcome["criterion_status"] == "unknown"


@pytest.mark.parametrize("extra,count", [(False, 3), (True, 2)])
def test_supportive_subset_does_not_cherry_pick_contradictory_extra_test(extra, count):
    tests = tuple(stimulation(f"T{i}") for i in range(count - 1)) + (
        stimulation("contradictory", kind="other", inadequate_response_documented=False),)
    outcome = candidate(facts(stimulation_tests=tests,
                              additional_anterior_pituitary_deficiency_confirmed=extra))
    assert outcome["criterion_status"] == "unknown"
    assert PREFIX + "stimulation_tests.test_set_interpretation" in outcome["missing_inputs"]


@pytest.mark.parametrize("extra", [None, "true", 1])
@pytest.mark.parametrize("count", [2, 3])
def test_unknown_exception_cannot_deny_one_supportive_test_with_conflicting_other_records(extra, count):
    tests = (stimulation(),) + tuple(
        stimulation(f"other-{i}", kind="other", inadequate_response_documented=False)
        for i in range(1, count)
    )
    outcome = candidate(facts(stimulation_tests=tests,
                              additional_anterior_pituitary_deficiency_confirmed=extra))
    assert outcome["criterion_status"] == "unknown"
    assert PREFIX + "additional_anterior_pituitary_deficiency_confirmed" in outcome["missing_inputs"]


@pytest.mark.parametrize("test_date", [DAY + timedelta(days=1), None, datetime(2026, 10, 4), "2026-10-4"])
def test_invalid_or_future_test_dates_remain_unknown(test_date):
    outcome = candidate(facts(stimulation_tests=(stimulation(), stimulation("T2", performed_on=test_date))))
    assert outcome["criterion_status"] == "unknown"
    assert PREFIX + "stimulation_tests[1].performed_on" in outcome["missing_inputs"]


def test_test_date_must_not_follow_assessment_even_before_service():
    outcome = candidate(facts(assessment_date=DAY - timedelta(days=2)))
    assert outcome["criterion_status"] == "unknown"
    assert PREFIX + "stimulation_tests[0].performed_on" in outcome["missing_inputs"]


def test_source_does_not_invent_recency_or_require_distinct_test_kinds_or_dates():
    tests = (stimulation(performed_on=date(1990, 1, 1)),
             stimulation("T2", performed_on=date(1990, 1, 1)))
    assert candidate(facts(stimulation_tests=tests))["criterion_status"] == "criterion_clear"


@pytest.mark.parametrize("changes,missing", [
    ({"drug_claim_date": None}, "drug_claim_date"),
    ({"drug_claim_date": datetime(2026, 10, 5)}, "drug_claim_date"),
    ({"adult_gh_evidence": facts(applies_on=DAY - timedelta(days=1))}, PREFIX + "applies_on"),
    ({"adult_gh_evidence": facts(assessment_date=None)}, PREFIX + "assessment_date"),
    ({"adult_gh_evidence": facts(assessment_date=DAY + timedelta(days=1))}, PREFIX + "assessment_date"),
])
def test_candidate_date_gates_precede_all_predicates(changes, missing):
    outcome = candidate(**changes)
    assert outcome["criterion_status"] == "not_evaluated"
    assert missing in outcome["missing_inputs"]
    assert outcome["checks"] == []


@pytest.mark.parametrize("field", ["gh_patient_group", "epiphyses_closed", "gh_treatment_phase"])
@pytest.mark.parametrize("value", [None, 1, "unknown"])
def test_missing_or_invalid_explicit_scope_unknown_even_with_adult_age(field, value):
    outcome = candidate(facts(adult_hypothalamic_pituitary_gh_deficiency_suspected=False),
                        patient_age_years=65, **{field: value})
    assert outcome["criterion_status"] == "unknown"
    assert outcome["missing_inputs"] == [field]


@pytest.mark.parametrize("changes", [
    {"gh_patient_group": "pediatric"}, {"epiphyses_closed": False},
    {"gh_treatment_phase": "continuation"},
    {"drug_name": "somatrogon"}, {"drug_name": "growth hormone"},
    {"drug_name": "büyüme hormonu"}, {"drug_name": "mecasermin"},
    {"drug_name": "somatropinlike"}, {"drug_name": "Genotropin (somatrogon)"},
])
def test_out_of_scope_context_and_drugs_are_excluded_before_source_lookup(changes, monkeypatch):
    def forbidden(*args):
        raise AssertionError("Out-of-scope input cannot reach source admission")

    monkeypatch.setattr(draft, "resolve_source_authority", forbidden)
    supplied = line(**changes)
    assert draft.evaluate_adult_gh_closed_epiphysis_candidate(supplied, RULE) is None
    assert draft.evaluate_adult_gh_closed_epiphysis(supplied, RULE) is None


@pytest.mark.parametrize("drug", ["Genotropin 12mg", "NORDITROPIN", "Omnitrope (somatropin)", "Saizen", "Nutropin"])
def test_existing_somatropin_brands_are_narrowly_accepted(drug):
    assert candidate(drug_name=drug)["criterion_status"] == "criterion_clear"


@pytest.mark.parametrize("rule", [None, "4.2.6.pediatric_somatropin_initiation_board", "4.2.6.A-2", "unrelated"])
def test_only_the_exact_existing_selected_rules_can_reach_the_draft(rule):
    assert candidate(rule=rule) is None
    assert draft.evaluate_adult_gh_closed_epiphysis(line(), rule) is None


@pytest.mark.parametrize("admitted,released,status", [
    (False, False, "not_evaluated"), (True, False, "not_evaluated"),
    (False, True, "not_evaluated"), (True, True, "criterion_clear"),
])
def test_runtime_source_and_independent_interpretation_gates_are_both_required(monkeypatch, admitted, released, status):
    calls = authority(monkeypatch, "admitted" if admitted else "review_required")
    monkeypatch.setattr(draft, "_ADULT_GH_INTERPRETATION_RELEASED", released)
    outcome = draft.evaluate_adult_gh_closed_epiphysis(line(), RULE)
    assert calls == [("adult_gh_closed_epiphysis", DAY)]
    assert outcome["criterion_status"] == status
    assert_incomplete(outcome)
    if not admitted or not released:
        assert outcome["checks"] == []
        assert ("verified_source_for_service_date" in outcome["missing_inputs"]) is (not admitted)
        assert ("adult_gh_clinical_interpretation_release" in outcome["missing_inputs"]) is (not released)


def test_gated_runtime_never_attempts_candidate_denial_or_accepts_request_release_flags(monkeypatch):
    authority(monkeypatch, "admitted")
    assert draft._ADULT_GH_INTERPRETATION_RELEASED is False

    def forbidden(*args):
        raise AssertionError("Candidate must not run before both release gates")

    monkeypatch.setattr(draft, "_candidate", forbidden)
    supplied = line(facts(adult_hypothalamic_pituitary_gh_deficiency_suspected=False),
                    adult_gh_clinical_interpretation_release=True,
                    _ADULT_GH_INTERPRETATION_RELEASED=True)
    outcome = draft.evaluate_adult_gh_closed_epiphysis(supplied, RULE)
    assert outcome["criterion_status"] == "not_evaluated"
    assert outcome["checks"] == []


def test_even_both_mocked_releases_cannot_bypass_dated_inputs(monkeypatch):
    authority(monkeypatch, "admitted")
    monkeypatch.setattr(draft, "_ADULT_GH_INTERPRETATION_RELEASED", True)
    outcome = draft.evaluate_adult_gh_closed_epiphysis(line(drug_claim_date=None), RULE)
    assert outcome["criterion_status"] == "not_evaluated"
    assert outcome["checks"] == []


def test_actual_twelve_family_renewal_does_not_admit_adult_gh_or_fill_history():
    catalog = json.loads(Path("data/gazette/source_authority/clinical_versions.json").read_text())
    assert draft.AUTHORITY_ID not in {row["family_id"] for row in catalog["versions"]}
    receipt = json.loads(Path("data/gazette/source_authority/review_receipt_2026_10_05.json").read_text())
    assert len(receipt["named_families"]) == 12
    assert draft.AUTHORITY_ID not in receipt["named_families"]
    for day in (date(2024, 5, 17), date(2026, 10, 2), DAY, DAY + timedelta(days=1)):
        evidence = facts(applies_on=day, assessment_date=day,
                         stimulation_tests=(stimulation(performed_on=day), stimulation("T2", performed_on=day)))
        outcome = draft.evaluate_adult_gh_closed_epiphysis(line(evidence, drug_claim_date=day), RULE)
        assert outcome["criterion_status"] == "not_evaluated"
        assert outcome["source_authority"]["family_id"] == draft.AUTHORITY_ID
        assert outcome["source_authority"]["status"] == "review_required"
        assert "verified_source_for_service_date" in outcome["missing_inputs"]
        assert outcome["checks"] == []
        assert_incomplete(outcome)


@pytest.mark.parametrize("report_present", [True, False])
def test_registered_somatropin_route_keeps_independent_interpretation_closed(monkeypatch, report_present):
    def forbidden(*args):
        raise AssertionError("The gated production route must not execute candidate predicates")

    monkeypatch.setattr(draft, "_candidate", forbidden)
    authority(monkeypatch, "admitted")
    assert draft._ADULT_GH_INTERPRETATION_RELEASED is False
    recorded = replace(_drug_line(
        drug_name="GENOTROPIN (SOMATROPIN)", report_present=report_present,
        report_duration_months=12, prescriber_specialty="endokrinoloji",
    ), drug_claim_date=DAY, gh_patient_group="adult", epiphyses_closed=True,
        gh_treatment_phase="initiation")
    claim = _claim(primary_icd10="E23.0")
    for evidence in (None, facts(), facts(adult_hypothalamic_pituitary_gh_deficiency_suspected=False)):
        supplied = SimpleNamespace(**{**asdict(recorded), "adult_gh_evidence": evidence})
        outcome = evaluate_drug_indication_line_detailed(drug_line=supplied, claim=claim, diagnoses=[])
        assert outcome["selected_rule_id"] == RULE
        restriction = next(item for item in outcome["clinical_restrictions"]
                           if item["constraint_set"] == draft.KIND)
        assert restriction["criterion_status"] == "not_evaluated"
        assert restriction["checks"] == []
        assert restriction["clinical_eligibility_complete"] is False
        assert "adult_gh_clinical_interpretation_release" in outcome["missing_inputs"]
        assert all(name not in outcome for name in ("payable_try", "savings_try", "recoverable_uplift_try"))

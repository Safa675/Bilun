"""Differential documentary checks at the actual adult GH candidate boundary.

§4.2.6.A-2(2)(a/b) supplies the diagnosis paths and inadequate test responses;
§(3) changes only the required test count; §(4) requires the ITT peak <3 mcg/L
to be documented in the report. These tests do not interpret non-ITT numbers,
admit source dates or release clinical evaluation.
"""
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import pytest

from src.bilun.domain.claims.adult_gh import AdultGhEvidence, AdultGhStimulationTest
from src.bilun.domain.prose_rules import adult_gh_draft as draft


SERVICE = date(2026, 10, 5)
RULE = "4.2.6.adult_somatropin_board_report"
PREFIX = "adult_gh_evidence."


def _test(test_id, *, kind="itt", **facts):
    return AdultGhStimulationTest(**{
        "test_id": test_id,
        "performed_on": date(2026, 10, 2),
        "kind": kind,
        "inadequate_response_documented": True,
        "peak_gh_mcg_l": 2.9,
        "peak_gh_documented_in_report": True,
        "retest_after_epiphyseal_closure_stop": True,
        **facts,
    })


def _evidence(**facts):
    return AdultGhEvidence(**{
        "applies_on": SERVICE,
        "assessment_date": date(2026, 10, 4),
        "diagnosis_pathway": "adult_hypothalamic_pituitary",
        "adult_hypothalamic_pituitary_gh_deficiency_suspected": True,
        "childhood_gh_deficiency_diagnosed": True,
        "childhood_gh_treatment_received": True,
        "gh_stopped_due_to_epiphyseal_closure": True,
        "additional_anterior_pituitary_deficiency_confirmed": False,
        "two_distinct_stimulation_procedures_documented": True,
        "itt_contraindicated": False,
        "stimulation_tests": (_test("DOCUMENTED-ITT"), _test("DOCUMENTED-OTHER", kind="other")),
        **facts,
    })


def _line(evidence, *, report_present=True):
    return SimpleNamespace(
        drug_name="somatropin", drug_claim_date=SERVICE,
        gh_patient_group="adult", epiphyses_closed=True, gh_treatment_phase="initiation",
        adult_gh_evidence=evidence, drug_specialty_board_report_present=report_present,
    )


def _candidate(evidence, *, report_present=True):
    return draft.evaluate_adult_gh_closed_epiphysis_candidate(
        _line(evidence, report_present=report_present), RULE,
    )


def _status(outcome, field):
    return next(check["status"] for check in outcome["checks"] if check["field"] == PREFIX + field)


@pytest.mark.parametrize("documented,expected", [
    (False, "restriction_not_met"), (None, "unknown"),
])
def test_generic_report_presence_cannot_repair_the_specific_itt_report_fact(documented, expected):
    evidence = _evidence(stimulation_tests=(
        _test("DOCUMENTED-ITT", peak_gh_documented_in_report=documented),
        _test("DOCUMENTED-OTHER", kind="other"),
    ))
    present = _candidate(evidence, report_present=True)
    absent = _candidate(evidence, report_present=False)
    assert present == absent
    assert present["criterion_status"] == expected
    assert _status(present, "stimulation_tests[0].peak_gh_mcg_l") == "pass"
    field = "stimulation_tests[0].peak_gh_documented_in_report"
    assert _status(present, field) == ("fail" if documented is False else "unknown")
    assert present["missing_inputs"] == ([] if documented is False else [PREFIX + field])

    # The reverse boundary also holds: the explicit per-test fact remains
    # sufficient for these narrow candidate checks without a generic flag.
    repaired = replace(evidence, stimulation_tests=(
        replace(evidence.stimulation_tests[0], peak_gh_documented_in_report=True),
        evidence.stimulation_tests[1],
    ))
    assert _candidate(repaired, report_present=False)["criterion_status"] == "criterion_clear"


@pytest.mark.parametrize("field", [
    "childhood_gh_deficiency_diagnosed", "childhood_gh_treatment_received",
    "gh_stopped_due_to_epiphyseal_closure",
])
@pytest.mark.parametrize("fact,expected", [
    (True, "criterion_clear"), (False, "restriction_not_met"), (None, "unknown"),
])
def test_one_test_exception_changes_count_but_never_repairs_childhood_documentation(field, fact, expected):
    ordinary = _evidence(
        diagnosis_pathway="childhood_onset_retest",
        stimulation_tests=(_test("POST-CLOSURE-RETEST"),),
        two_distinct_stimulation_procedures_documented=None,
        **{field: fact},
    )
    before = _candidate(ordinary)
    after = _candidate(replace(ordinary, additional_anterior_pituitary_deficiency_confirmed=True))
    assert _status(before, "stimulation_tests.count") == "fail"
    assert _status(after, "stimulation_tests.count") == "pass"
    assert _status(before, field) == _status(after, field)
    assert after["criterion_status"] == expected
    if fact is None:
        assert before["criterion_status"] == "unknown"
        assert after["missing_inputs"] == [PREFIX + field]
    else:
        assert before["criterion_status"] == "restriction_not_met"
        assert after["missing_inputs"] == []


def test_incomplete_test_interpretation_preserves_known_report_failure_until_facts_are_completed():
    incomplete = _evidence(stimulation_tests=(
        _test("DOCUMENTED-ITT", peak_gh_documented_in_report=False),
        _test("DOCUMENTED-OTHER", kind="other", inadequate_response_documented=None),
    ))
    unknown = _candidate(incomplete)
    known_failure = "stimulation_tests[0].peak_gh_documented_in_report"
    missing = "stimulation_tests[1].inadequate_response_documented"
    assert unknown["criterion_status"] == "unknown"
    assert _status(unknown, known_failure) == "fail"
    assert _status(unknown, missing) == "unknown"
    assert unknown["missing_inputs"] == [PREFIX + missing]

    interpreted = replace(incomplete, stimulation_tests=(
        incomplete.stimulation_tests[0],
        replace(incomplete.stimulation_tests[1], inadequate_response_documented=True),
    ))
    negative = _candidate(interpreted)
    assert negative["criterion_status"] == "restriction_not_met"
    assert _status(negative, known_failure) == "fail"
    assert _status(negative, missing) == "pass"
    assert negative["missing_inputs"] == []

    documented = replace(interpreted, stimulation_tests=(
        replace(interpreted.stimulation_tests[0], peak_gh_documented_in_report=True),
        interpreted.stimulation_tests[1],
    ))
    positive = _candidate(documented)
    assert positive["criterion_status"] == "criterion_clear"
    assert positive["clinical_eligibility_complete"] is False


@pytest.mark.parametrize("peak,itt_status", [
    (2.9, "criterion_clear"), (3.0, "restriction_not_met"),
])
def test_same_numeric_peak_needs_other_test_interpretation_but_uses_cutoff_only_for_itt(peak, itt_status):
    other = _test("SECOND-TEST", kind="other", peak_gh_mcg_l=peak,
                  inadequate_response_documented=None)
    evidence = _evidence(stimulation_tests=(_test("FIRST-ITT"), other))
    undocumented = _candidate(evidence)
    assert undocumented["criterion_status"] == "unknown"
    assert undocumented["missing_inputs"] == [PREFIX + "stimulation_tests[1].inadequate_response_documented"]
    assert not any(check["field"] == PREFIX + "stimulation_tests[1].peak_gh_mcg_l"
                   for check in undocumented["checks"])

    documented_other = replace(other, inadequate_response_documented=True)
    assert _candidate(replace(evidence, stimulation_tests=(
        evidence.stimulation_tests[0], documented_other,
    )))["criterion_status"] == "criterion_clear"
    classified_itt = _candidate(replace(evidence, stimulation_tests=(
        evidence.stimulation_tests[0], replace(documented_other, kind="itt"),
    )))
    assert classified_itt["criterion_status"] == itt_status
    assert _status(classified_itt, "stimulation_tests[1].peak_gh_mcg_l") == (
        "pass" if peak < 3 else "fail"
    )


PAIR = "two_distinct_stimulation_procedures_documented"
EXCEPTION = "additional_anterior_pituitary_deficiency_confirmed"


@pytest.mark.parametrize("pair,exception,expected,missing", [
    (True, True, "criterion_clear", ()),
    (True, False, "criterion_clear", ()),
    (True, None, "criterion_clear", ()),
    (False, True, "criterion_clear", ()),
    (False, False, "restriction_not_met", ()),
    (False, None, "unknown", (EXCEPTION,)),
    (None, True, "criterion_clear", ()),
    (None, False, "unknown", (PAIR,)),
    (None, None, "unknown", (PAIR, EXCEPTION)),
])
def test_two_record_count_requires_documented_procedures_or_the_one_test_exception(pair, exception, expected, missing):
    outcome = _candidate(_evidence(**{PAIR: pair, EXCEPTION: exception}))
    assert outcome["criterion_status"] == expected
    assert outcome["missing_inputs"] == sorted(PREFIX + field for field in missing)
    assert _status(outcome, "stimulation_tests.count") == (
        "unknown" if missing else "pass" if expected == "criterion_clear" else "fail"
    )
    checked = {check["field"] for check in outcome["checks"]}
    if exception is True:
        assert PREFIX + PAIR not in checked
    elif pair is True:
        assert PREFIX + EXCEPTION not in checked
    else:
        assert _status(outcome, PAIR) == ("unknown" if pair is None else "fail")
        assert _status(outcome, EXCEPTION) == ("unknown" if exception is None else "fail")


@pytest.mark.parametrize("pair", [True, False, None])
def test_documented_single_test_exception_does_not_require_the_two_procedure_fact(pair):
    outcome = _candidate(_evidence(
        stimulation_tests=(_test("SINGLE-ITT"),), **{PAIR: pair, EXCEPTION: True},
    ))
    assert outcome["criterion_status"] == "criterion_clear"
    assert outcome["missing_inputs"] == []
    assert _status(outcome, "stimulation_tests.count") == "pass"
    assert not any(check["field"] == PREFIX + PAIR for check in outcome["checks"])


@pytest.mark.parametrize("count", [0, 1])
def test_two_procedure_flag_cannot_supply_an_absent_submitted_test(count):
    outcome = _candidate(_evidence(
        stimulation_tests=tuple(_test(f"RECORDED-{index}") for index in range(count)),
        **{PAIR: True, EXCEPTION: False},
    ))
    assert outcome["criterion_status"] == "restriction_not_met"
    assert _status(outcome, "stimulation_tests.count") == "fail"
    assert outcome["missing_inputs"] == []


def test_ids_different_methods_dates_and_generic_report_cannot_document_actual_distinct_procedures():
    evidence = _evidence(stimulation_tests=(
        _test("UNIQUE-ITT-ID"),
        _test("UNIQUE-OTHER-ID", kind="other", performed_on=date(2026, 10, 3)),
    ), **{PAIR: None, EXCEPTION: False})
    present = _candidate(evidence, report_present=True)
    assert present == _candidate(evidence, report_present=False)
    assert present["criterion_status"] == "unknown"
    assert present["missing_inputs"] == [PREFIX + PAIR]
    assert _status(present, PAIR) == "unknown"


def test_extra_compatible_complete_tests_do_not_block_a_documented_two_procedure_path():
    # Same methods and dates do not establish or negate the clinician's explicit
    # documentation of distinct procedures; the source imposes no such limits.
    evidence = _evidence(stimulation_tests=tuple(_test(f"ACTUAL-{index}") for index in range(3)),
                         **{PAIR: True, EXCEPTION: None})
    outcome = _candidate(evidence)
    assert outcome["criterion_status"] == "criterion_clear"
    assert outcome["missing_inputs"] == []
    assert _status(outcome, "stimulation_tests.count") == "pass"
    assert all(check["status"] == "pass" for check in outcome["checks"])


def test_mocked_source_admission_cannot_evaluate_a_candidate_while_real_clinical_gate_is_closed(monkeypatch):
    assert draft._ADULT_GH_INTERPRETATION_RELEASED is False
    admitted = SimpleNamespace(status="admitted", model_dump=lambda: {
        "family_id": draft.AUTHORITY_ID, "status": "admitted", "service_date": SERVICE.isoformat(),
    })
    monkeypatch.setattr(draft, "resolve_source_authority", lambda *_: admitted)

    def no_clinical_predicate(*_args, **_kwargs):
        pytest.fail("The closed clinical interpretation gate must run before any predicate")

    monkeypatch.setattr(draft.Reader, "test", no_clinical_predicate)
    outcome = draft.evaluate_adult_gh_closed_epiphysis(_line(_evidence()), RULE)
    assert outcome["criterion_status"] == "not_evaluated"
    assert outcome["checks"] == []
    assert outcome["missing_inputs"] == ["adult_gh_clinical_interpretation_release"]
    assert outcome["clinical_eligibility_complete"] is False
    assert draft._ADULT_GH_INTERPRETATION_RELEASED is False

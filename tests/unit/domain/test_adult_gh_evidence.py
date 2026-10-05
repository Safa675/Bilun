"""Adult somatropin evidence boundaries must never assert coerced facts."""
from dataclasses import FrozenInstanceError, asdict, replace
from datetime import date, datetime
import json
from types import MappingProxyType

import pytest

from src.bilun.domain.claims.adult_gh import (
    AdultGhEvidence,
    AdultGhStimulationTest,
    parse_adult_gh_evidence,
)


BOOLEAN_FIELDS = (
    "childhood_gh_deficiency_diagnosed",
    "childhood_gh_treatment_received",
    "gh_stopped_due_to_epiphyseal_closure",
    "adult_hypothalamic_pituitary_gh_deficiency_suspected",
    "additional_anterior_pituitary_deficiency_confirmed",
    "itt_contraindicated",
)
TEST_BOOLEAN_FIELDS = (
    "inadequate_response_documented",
    "peak_gh_documented_in_report",
    "retest_after_epiphyseal_closure_stop",
)


def _test_record(**changes):
    return {
        "test_id": "SYNTHETIC-ITT-1",
        "performed_on": "2026-10-03",
        "kind": "itt",
        "inadequate_response_documented": True,
        "peak_gh_mcg_l": 2.5,
        "peak_gh_documented_in_report": True,
        "retest_after_epiphyseal_closure_stop": True,
        **changes,
    }


def evidence_record(**changes):
    return {
        "applies_on": "2026-10-05",
        "assessment_date": "2026-10-04",
        "diagnosis_pathway": "childhood_onset_retest",
        "childhood_gh_deficiency_diagnosed": True,
        "childhood_gh_treatment_received": True,
        "gh_stopped_due_to_epiphyseal_closure": True,
        "adult_hypothalamic_pituitary_gh_deficiency_suspected": False,
        "additional_anterior_pituitary_deficiency_confirmed": False,
        "itt_contraindicated": False,
        "stimulation_tests": [_test_record()],
        **changes,
    }


def transport(payload, kind):
    if kind == "mapping":
        return MappingProxyType(payload)
    if kind == "json":
        return json.dumps(payload, default=lambda value: value.isoformat())
    payload = dict(payload)
    tests = payload.get("stimulation_tests")
    if type(tests) in (list, tuple):
        payload["stimulation_tests"] = tuple(
            AdultGhStimulationTest(**item) if isinstance(item, dict) else item
            for item in tests
        )
    return AdultGhEvidence(**payload)


@pytest.mark.parametrize("kind", ["mapping", "json", "typed"])
def test_complete_evidence_has_transport_parity(kind):
    payload = evidence_record(
        applies_on=date(2026, 10, 5), assessment_date=date(2026, 10, 4),
        stimulation_tests=[_test_record(
            test_id="  SYNTHETIC-ITT-1  ", performed_on=date(2026, 10, 3),
        ), _test_record(test_id="SYNTHETIC-OTHER-2", kind="other", peak_gh_mcg_l=9)],
    )
    parsed = parse_adult_gh_evidence(transport(payload, kind))
    expected = AdultGhEvidence(
        applies_on=date(2026, 10, 5), assessment_date=date(2026, 10, 4),
        diagnosis_pathway="childhood_onset_retest",
        childhood_gh_deficiency_diagnosed=True,
        childhood_gh_treatment_received=True,
        gh_stopped_due_to_epiphyseal_closure=True,
        adult_hypothalamic_pituitary_gh_deficiency_suspected=False,
        additional_anterior_pituitary_deficiency_confirmed=False,
        itt_contraindicated=False,
        stimulation_tests=(AdultGhStimulationTest(
            test_id="SYNTHETIC-ITT-1", performed_on=date(2026, 10, 3), kind="itt",
            inadequate_response_documented=True, peak_gh_mcg_l=2.5,
            peak_gh_documented_in_report=True, retest_after_epiphyseal_closure_stop=True,
        ), AdultGhStimulationTest(
            test_id="SYNTHETIC-OTHER-2", performed_on=date(2026, 10, 3), kind="other",
            inadequate_response_documented=True, peak_gh_mcg_l=9.0,
            peak_gh_documented_in_report=True, retest_after_epiphyseal_closure_stop=True,
        )),
    )
    assert parsed == expected
    assert parse_adult_gh_evidence(parsed) == expected


@pytest.mark.parametrize("kind", ["mapping", "json", "typed"])
@pytest.mark.parametrize("raw", [True, False])
def test_explicit_boolean_presence_and_absence_survive(kind, raw):
    payload = evidence_record(**{field: raw for field in BOOLEAN_FIELDS})
    payload["stimulation_tests"] = [_test_record(**{
        field: raw for field in TEST_BOOLEAN_FIELDS
    })]
    parsed = parse_adult_gh_evidence(transport(payload, kind))
    for field in BOOLEAN_FIELDS:
        assert getattr(parsed, field) is raw
    for field in TEST_BOOLEAN_FIELDS:
        assert getattr(parsed.stimulation_tests[0], field) is raw


@pytest.mark.parametrize("kind", ["mapping", "json", "typed"])
@pytest.mark.parametrize("raw", [None, "true", "false", 0, 1, [], {}, float("nan")])
def test_invalid_boolean_facts_are_unknown_in_every_transport(kind, raw):
    payload = evidence_record(**{field: raw for field in BOOLEAN_FIELDS})
    payload["stimulation_tests"] = [_test_record(**{
        field: raw for field in TEST_BOOLEAN_FIELDS
    })]
    parsed = parse_adult_gh_evidence(transport(payload, kind))
    for field in BOOLEAN_FIELDS:
        assert getattr(parsed, field) is None
    for field in TEST_BOOLEAN_FIELDS:
        assert getattr(parsed.stimulation_tests[0], field) is None
    assert parsed.stimulation_tests[0].peak_gh_mcg_l == 2.5


@pytest.mark.parametrize("kind", ["mapping", "json", "typed"])
@pytest.mark.parametrize("raw", [
    None, "2026-2-03", "2026-02-30", "2026-10-03T00:00:00", 20261003,
    " 2026-10-03", "2026-10-03 ", datetime(2026, 10, 3), True,
])
def test_invalid_dates_stay_unknown_without_conversion(kind, raw):
    payload = evidence_record(
        applies_on=raw, assessment_date=raw,
        stimulation_tests=[_test_record(performed_on=raw)],
    )
    parsed = parse_adult_gh_evidence(transport(payload, kind))
    assert parsed.applies_on is None
    assert parsed.assessment_date is None
    assert parsed.stimulation_tests[0].performed_on is None


@pytest.mark.parametrize("kind", ["mapping", "json", "typed"])
@pytest.mark.parametrize("raw", [
    None, True, False, "2.5", -0.001, float("nan"), float("inf"),
    float("-inf"), 10**400, [], {},
])
def test_invalid_peak_numbers_stay_unknown_without_raising(kind, raw):
    payload = evidence_record(stimulation_tests=[_test_record(peak_gh_mcg_l=raw)])
    parsed = parse_adult_gh_evidence(transport(payload, kind))
    assert parsed.stimulation_tests[0].peak_gh_mcg_l is None
    assert parsed.stimulation_tests[0].inadequate_response_documented is True


@pytest.mark.parametrize("raw", [0, 2.999, 3, 3.001, 1000])
def test_valid_peak_is_preserved_without_threshold_or_test_kind_inference(raw):
    for test_kind in ("itt", "other", None):
        parsed = parse_adult_gh_evidence(evidence_record(stimulation_tests=[_test_record(
            kind=test_kind, peak_gh_mcg_l=raw, inadequate_response_documented=None,
        )]))
        assert parsed.stimulation_tests[0].peak_gh_mcg_l == float(raw)
        assert parsed.stimulation_tests[0].inadequate_response_documented is None


@pytest.mark.parametrize("kind", ["mapping", "json", "typed"])
@pytest.mark.parametrize("raw", [None, "itt ", "ITT", "insulin", "other ", 1, True, []])
def test_stimulation_kind_requires_exact_enum(kind, raw):
    parsed = parse_adult_gh_evidence(transport(evidence_record(
        stimulation_tests=[_test_record(kind=raw)],
    ), kind))
    assert parsed.stimulation_tests[0].kind is None


@pytest.mark.parametrize("kind", ["mapping", "json", "typed"])
@pytest.mark.parametrize("raw", [None, "adult", " childhood_onset_retest", 1, True, []])
def test_diagnosis_pathway_requires_exact_enum(kind, raw):
    parsed = parse_adult_gh_evidence(transport(evidence_record(diagnosis_pathway=raw), kind))
    assert parsed.diagnosis_pathway is None


@pytest.mark.parametrize("pathway", ["childhood_onset_retest", "adult_hypothalamic_pituitary"])
def test_both_explicit_diagnosis_pathways_are_preserved(pathway):
    assert parse_adult_gh_evidence({"diagnosis_pathway": pathway}).diagnosis_pathway == pathway


@pytest.mark.parametrize("raw", [None, "", " \n\t ", "x" * 121, 12, False, {}])
def test_test_id_is_bounded_explicit_text(raw):
    parsed = parse_adult_gh_evidence(evidence_record(stimulation_tests=[_test_record(test_id=raw)]))
    assert parsed.stimulation_tests[0].test_id is None


def test_test_id_trims_whitespace_and_accepts_exact_length_boundary():
    parsed = parse_adult_gh_evidence(evidence_record(stimulation_tests=[_test_record(
        test_id="  " + "x" * 120 + "  ",
    )]))
    assert parsed.stimulation_tests[0].test_id == "x" * 120


@pytest.mark.parametrize("kind", ["mapping", "json", "typed"])
@pytest.mark.parametrize("malformed", [None, True, 1, "not-a-record", [], [_test_record()]])
def test_malformed_test_member_never_disappears_to_leave_an_adequate_set(kind, malformed):
    tests = [_test_record(), malformed, _test_record(test_id="SYNTHETIC-OTHER-2", kind="other")]
    parsed = parse_adult_gh_evidence(transport(evidence_record(stimulation_tests=tests), kind))
    assert parsed.stimulation_tests is None
    assert parsed.childhood_gh_deficiency_diagnosed is True


def test_unknown_fields_in_a_test_record_are_preserved_as_unknown_record():
    parsed = parse_adult_gh_evidence(evidence_record(stimulation_tests=[_test_record(), {}]))
    assert len(parsed.stimulation_tests) == 2
    assert parsed.stimulation_tests[1] == AdultGhStimulationTest()


@pytest.mark.parametrize("kind", ["mapping", "json", "typed"])
@pytest.mark.parametrize("count", [0, 20, 21])
def test_test_collection_is_bounded_without_truncation(kind, count):
    tests = [_test_record(test_id=f"SYNTHETIC-{index}") for index in range(count)]
    parsed = parse_adult_gh_evidence(transport(evidence_record(stimulation_tests=tests), kind))
    if count > 20:
        assert parsed.stimulation_tests is None
    else:
        assert type(parsed.stimulation_tests) is tuple
        assert len(parsed.stimulation_tests) == count


@pytest.mark.parametrize("raw", [None, True, 2, "[]", {}, {"test_id": "SYNTHETIC-1"}])
def test_noncollection_test_values_are_unknown(raw):
    parsed = parse_adult_gh_evidence(evidence_record(stimulation_tests=raw))
    assert parsed.stimulation_tests is None


def test_nested_mapping_and_typed_tests_can_coexist_without_bypassing_revalidation():
    tests = [MappingProxyType(_test_record()), AdultGhStimulationTest(
        test_id="SYNTHETIC-2", kind="other", peak_gh_mcg_l=True,
        inadequate_response_documented="false",
    )]
    parsed = parse_adult_gh_evidence(evidence_record(stimulation_tests=tests))
    assert len(parsed.stimulation_tests) == 2
    assert parsed.stimulation_tests[1].kind == "other"
    assert parsed.stimulation_tests[1].peak_gh_mcg_l is None
    assert parsed.stimulation_tests[1].inadequate_response_documented is None


def test_typed_objects_are_frozen_but_still_revalidated_at_parser_boundary():
    evidence = AdultGhEvidence(itt_contraindicated="false", stimulation_tests=(
        AdultGhStimulationTest(test_id=123, peak_gh_documented_in_report=1),
    ))
    with pytest.raises(FrozenInstanceError):
        evidence.itt_contraindicated = True
    with pytest.raises(FrozenInstanceError):
        evidence.stimulation_tests[0].test_id = "SYNTHETIC-REPLACED"
    parsed = parse_adult_gh_evidence(evidence)
    assert parsed.itt_contraindicated is None
    assert parsed.stimulation_tests[0].test_id is None
    assert parsed.stimulation_tests[0].peak_gh_documented_in_report is None
    assert parse_adult_gh_evidence(replace(parsed, itt_contraindicated=False)).itt_contraindicated is False
    assert parse_adult_gh_evidence(asdict(parsed)) == parsed


def test_unrelated_age_icd_and_hormone_aliases_cannot_assert_source_facts():
    parsed = parse_adult_gh_evidence({
        "age": 65, "adult": True, "epiphyses_closed": True,
        "primary_icd10": "E23.0", "pituitary_deficiencies": ["gh", "prolactin", "TSH"],
        "itt_peak_gh": 2.5, "report_present": True,
    })
    assert parsed == AdultGhEvidence()


@pytest.mark.parametrize("raw", [None, 1, True, [], (), "null", "true", "[]", "{", ""])
def test_nonobject_and_malformed_json_inputs_do_not_produce_evidence(raw):
    assert parse_adult_gh_evidence(raw) is None


def test_deep_malformed_json_is_unknown_without_a_parser_exception():
    assert parse_adult_gh_evidence("[" * 1500 + "]" * 1500) is None

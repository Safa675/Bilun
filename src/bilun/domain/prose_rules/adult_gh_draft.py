"""Gated draft of closed-epiphysis adult somatropin diagnosis prerequisites.

The candidate inspects explicit dated facts for §4.2.6.A-2(2)-(4). It never
certifies reimbursement, infers epiphyseal closure from age, or supplies the
clinical interpretation required for stimulation tests other than ITT.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from ..claims.adult_gh import AdultGhEvidence, parse_adult_gh_evidence
from ..claims.clinical_evidence import clinical_date
from ..claims.growth_hormone import validated_growth_hormone_value
from ._drug_indication.clinical_common import Predicate, Reader, all_of, any_of, result
from ._drug_indication.matching import _drug_name_matches
from ._drug_indication.source_authority import resolve_source_authority

KIND = "adult_gh_closed_epiphysis"
AUTHORITY_ID = "adult_gh_closed_epiphysis"
_PREFIX = "adult_gh_evidence"
_ADULT_GH_INTERPRETATION_RELEASED = False

_SELECTED_RULES = (
    "4.2.6.adult_somatropin_board_report",
    "4.2.6.A2.insulin_tolerance_test_peak_gh_report",
)
_SOMATROPIN_NAMES = ["somatropin", "genotropin", "norditropin", "omnitrope", "saizen", "nutropin"]
SOURCE_REFS = (
    "4.2.6.A-2.(2)#5589013c",
    "4.2.6.A-2.a#80b6dded",
    "4.2.6.A-2.b#9b0bad75",
    "4.2.6.A-2.(3)#3c094940",
    "4.2.6.A-2.(4)#e9d92dba",
)


def _selected(line: Any, selected_rule_id: str | None) -> bool:
    name = getattr(line, "drug_name", "")
    if (selected_rule_id not in _SELECTED_RULES
            or not _drug_name_matches(name, _SOMATROPIN_NAMES)
            or _drug_name_matches(name, ["somatrogon"])):
        return False
    # Explicit out-of-scope facts do not become failures of this draft. Missing
    # facts remain unresolved; age and diagnosis codes never supply these facts.
    return not (
        validated_growth_hormone_value("gh_patient_group", getattr(line, "gh_patient_group", None)) == "pediatric"
        or validated_growth_hormone_value("epiphyses_closed", getattr(line, "epiphyses_closed", None)) is False
        or validated_growth_hormone_value("gh_treatment_phase", getattr(line, "gh_treatment_phase", None)) == "continuation"
    )


def _scope_missing(line: Any) -> list[str]:
    expected = {"gh_patient_group": "adult", "epiphyses_closed": True, "gh_treatment_phase": "initiation"}
    return [field for field, value in expected.items()
            if validated_growth_hormone_value(field, getattr(line, field, None)) != value]


def _date_missing(evidence: AdultGhEvidence | None, service: date | None) -> list[str]:
    if service is None:
        return ["drug_claim_date"]
    missing = []
    if getattr(evidence, "applies_on", None) != service:
        missing.append(_PREFIX + ".applies_on")
    assessed = getattr(evidence, "assessment_date", None)
    if assessed is None or assessed > service:
        missing.append(_PREFIX + ".assessment_date")
    return missing


def _output(reader: Reader, predicate: Predicate, *, date_missing: list[str] | None = None) -> dict[str, Any]:
    return {**result(KIND, reader, predicate, list(SOURCE_REFS), date_missing=date_missing),
            "sut_section": "4.2.6.A-2"}


def _necessary(*items: Predicate) -> Predicate:
    # Unknown relevant evidence cannot manufacture a clinical denial, even if
    # a different supplied fact is negative. Known, complete failures remain
    # available to the reviewer as candidate restrictions.
    if any(item.value is None for item in items):
        return Predicate(None, tuple(sorted({field for item in items for field in item.missing})))
    return all_of(*items)


def _check(reader: Reader, field: str, predicate: Predicate) -> Predicate:
    reader.checks.append({"field": field,
                          "status": "unknown" if predicate.value is None else "pass" if predicate.value else "fail"})
    return predicate


def _test_records_missing(reader: Reader, service: date) -> list[str]:
    tests = reader.get("stimulation_tests")
    if tests is None:
        return [_PREFIX + ".stimulation_tests"]
    missing = []
    ids = []
    assessed = reader.get("assessment_date")
    for index, test in enumerate(tests):
        prefix = f"{_PREFIX}.stimulation_tests[{index}]"
        if test.test_id is None:
            missing.append(prefix + ".test_id")
        else:
            ids.append(test.test_id)
        if test.kind is None:
            missing.append(prefix + ".kind")
        if test.performed_on is None or test.performed_on > assessed or test.performed_on > service:
            missing.append(prefix + ".performed_on")
    if len(ids) != len(set(ids)):
        missing.append(_PREFIX + ".stimulation_tests.distinct_test_records")
    return missing


def _test_count(reader: Reader, count: int) -> Predicate:
    if count == 0:
        predicate = Predicate(False)
    elif count == 1 or reader.get("additional_anterior_pituitary_deficiency_confirmed") is True:
        # The documented one-test exception does not require a pair of tests.
        predicate = reader.bool("additional_anterior_pituitary_deficiency_confirmed")
    elif reader.get("two_distinct_stimulation_procedures_documented") is True:
        predicate = reader.bool("two_distinct_stimulation_procedures_documented")
    else:
        # Multiple record IDs alone do not prove two actual procedures. An
        # unresolved exception can still supply the alternative one-test path.
        predicate = any_of(
            reader.bool("two_distinct_stimulation_procedures_documented"),
            reader.bool("additional_anterior_pituitary_deficiency_confirmed"),
        )
    return _check(reader, _PREFIX + ".stimulation_tests.count", predicate)


def _candidate(line: Any, reader: Reader, service: date) -> dict[str, Any]:
    missing = _scope_missing(line)
    if missing:
        for field in missing:
            _check(reader, field, Predicate(None, (field,)))
        return _output(reader, Predicate(None, tuple(missing)))
    pathway = reader.get("diagnosis_pathway")
    if pathway is None:
        return _output(reader, reader.one_of("diagnosis_pathway", (
            "childhood_onset_retest", "adult_hypothalamic_pituitary")))
    missing = _test_records_missing(reader, service)
    if missing:
        for field in missing:
            _check(reader, field, Predicate(None, (field,)))
        return _output(reader, Predicate(None, tuple(missing)))

    predicates = [reader.one_of("diagnosis_pathway", (
        "childhood_onset_retest", "adult_hypothalamic_pituitary"))]
    childhood = pathway == "childhood_onset_retest"
    if childhood:
        predicates.extend(reader.bool(field) for field in (
            "childhood_gh_deficiency_diagnosed", "childhood_gh_treatment_received",
            "gh_stopped_due_to_epiphyseal_closure"))
    else:
        predicates.append(reader.bool("adult_hypothalamic_pituitary_gh_deficiency_suspected"))

    tests = reader.get("stimulation_tests")
    predicates.append(_test_count(reader, len(tests)))
    test_predicates = []
    for index, test in enumerate(tests):
        test_reader = Reader(test, f"{_PREFIX}.stimulation_tests[{index}]")
        items = [test_reader.bool("inadequate_response_documented")]
        if childhood:
            items.append(test_reader.bool("retest_after_epiphyseal_closure_stop"))
        if test.kind == "itt":
            items.extend((test_reader.number("peak_gh_mcg_l", "<", 3),
                          test_reader.bool("peak_gh_documented_in_report")))
        # Other-test adequacy requires the explicit clinical interpretation;
        # neither its numerical peak nor ITT's threshold can substitute for it.
        reader.checks.extend(test_reader.checks)
        test_predicates.append(_necessary(*items))

    additional = reader.get("additional_anterior_pituitary_deficiency_confirmed")
    supportive_count = sum(item.value is True for item in test_predicates)
    required_count = 1 if additional is True else 2
    if (additional is None and supportive_count == 1
            and any(item.value is False for item in test_predicates)):
        # Counting two submitted records cannot resolve whether the one
        # supportive result satisfies the source's still-unknown exception.
        predicates.append(reader.bool("additional_anterior_pituitary_deficiency_confirmed"))
    if (len(tests) > required_count
            and supportive_count >= required_count
            and any(item.value is False for item in test_predicates)):
        # The source does not say that a contradictory additional result must
        # deny a patient who also has the required inadequate tests. Do not
        # cherry-pick the supportive records or invent that broader denial.
        predicates.append(_check(reader, _PREFIX + ".stimulation_tests.test_set_interpretation",
                                 Predicate(None, (_PREFIX + ".stimulation_tests.test_set_interpretation",))))
    predicates.extend(test_predicates)

    has_itt = any(test.kind == "itt" for test in tests)
    if has_itt and reader.get("itt_contraindicated") is True:
        predicates.append(_check(reader, _PREFIX + ".itt_contraindication_context_reconciliation",
                                 Predicate(None, (_PREFIX + ".itt_contraindication_context_reconciliation",))))
    elif tests and not has_itt:
        contraindicated = reader.get("itt_contraindicated")
        if contraindicated is True:
            predicates.append(reader.bool("itt_contraindicated"))
        else:
            preference_missing = [_PREFIX + ".clinical_interpretation_required"]
            if contraindicated is None:
                preference_missing.append(_PREFIX + ".itt_contraindicated")
            predicates.append(_check(reader, _PREFIX + ".itt_preference_interpretation",
                                     Predicate(None, tuple(preference_missing))))
    return _output(reader, _necessary(*predicates))


def evaluate_adult_gh_closed_epiphysis_candidate(
    line: Any, selected_rule_id: str | None = None,
) -> dict[str, Any] | None:
    """Expose source-linked candidate semantics for review, outside runtime use."""
    if not _selected(line, selected_rule_id):
        return None
    evidence = parse_adult_gh_evidence(getattr(line, "adult_gh_evidence", None))
    reader = Reader(evidence, _PREFIX)
    service = clinical_date(getattr(line, "drug_claim_date", None))
    missing = _date_missing(evidence, service)
    if missing:
        return _output(reader, Predicate(None), date_missing=missing)
    return _candidate(line, reader, service)


def evaluate_adult_gh_closed_epiphysis(
    line: Any, selected_rule_id: str | None = None,
) -> dict[str, Any] | None:
    """Require this family's source admission and independent clinical release.

    Existing family reviews, legacy GH heading dates and request flags cannot
    activate this branch. No source history is inferred from an observation.
    """
    if not _selected(line, selected_rule_id):
        return None
    evidence = parse_adult_gh_evidence(getattr(line, "adult_gh_evidence", None))
    reader = Reader(evidence, _PREFIX)
    service = clinical_date(getattr(line, "drug_claim_date", None))
    authority = resolve_source_authority(AUTHORITY_ID, service)
    reader.source_authority = authority.model_dump()
    missing = _date_missing(evidence, service)
    if authority.status != "admitted":
        missing.append("verified_source_for_service_date")
    if not _ADULT_GH_INTERPRETATION_RELEASED:
        missing.append("adult_gh_clinical_interpretation_release")
    if missing:
        return _output(reader, Predicate(None), date_missing=missing)
    return _candidate(line, reader, service)

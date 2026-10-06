"""Explicit dated inputs for the closed-epiphysis adult somatropin draft.

These inputs record clinical facts; they infer neither epiphyseal closure from
age nor stimulation-test adequacy from a generic numerical threshold.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import date
import json
import math
from typing import Any, Literal

from .clinical_evidence import clinical_date


@dataclass(frozen=True)
class AdultGhStimulationTest:
    test_id: str | None = None
    performed_on: date | None = None
    kind: Literal["itt", "other"] | None = None
    inadequate_response_documented: bool | None = None
    peak_gh_mcg_l: float | None = None
    peak_gh_documented_in_report: bool | None = None
    retest_after_epiphyseal_closure_stop: bool | None = None


@dataclass(frozen=True)
class AdultGhEvidence:
    applies_on: date | None = None
    assessment_date: date | None = None
    diagnosis_pathway: Literal[
        "childhood_onset_retest", "adult_hypothalamic_pituitary"
    ] | None = None
    childhood_gh_deficiency_diagnosed: bool | None = None
    childhood_gh_treatment_received: bool | None = None
    gh_stopped_due_to_epiphyseal_closure: bool | None = None
    adult_hypothalamic_pituitary_gh_deficiency_suspected: bool | None = None
    # An explicit clinical record of >=1 additional anterior pituitary hormone
    # deficiency, excluding prolactin and GH; never derived from ICDs or aliases.
    additional_anterior_pituitary_deficiency_confirmed: bool | None = None
    # Explicit documentation that the submitted records include two actual,
    # distinct stimulation procedures; IDs, methods and dates cannot assert it.
    two_distinct_stimulation_procedures_documented: bool | None = None
    itt_contraindicated: bool | None = None
    stimulation_tests: tuple[AdultGhStimulationTest, ...] | None = None


def _exact_bool(value: Any) -> bool | None:
    return value if type(value) is bool else None


def _finite_nonnegative(value: Any) -> float | None:
    if type(value) not in (int, float):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def _test_id(value: Any) -> str | None:
    if type(value) is not str:
        return None
    trimmed = value.strip()
    return trimmed if 0 < len(trimmed) <= 120 else None


def _stimulation_tests(value: Any) -> tuple[AdultGhStimulationTest, ...] | None:
    if type(value) not in (list, tuple) or len(value) > 20:
        return None
    parsed = []
    for raw in value:
        if isinstance(raw, AdultGhStimulationTest):
            raw = {
                field.name: getattr(raw, field.name)
                for field in fields(AdultGhStimulationTest)
            }
        if not isinstance(raw, Mapping):
            # Never discard a malformed record and make the remaining tests
            # appear to be a complete, adequate set.
            return None
        kind = raw.get("kind")
        parsed.append(AdultGhStimulationTest(
            test_id=_test_id(raw.get("test_id")),
            performed_on=clinical_date(raw.get("performed_on")),
            kind=kind if type(kind) is str and kind in {"itt", "other"} else None,
            inadequate_response_documented=_exact_bool(
                raw.get("inadequate_response_documented")
            ),
            peak_gh_mcg_l=_finite_nonnegative(raw.get("peak_gh_mcg_l")),
            peak_gh_documented_in_report=_exact_bool(raw.get("peak_gh_documented_in_report")),
            retest_after_epiphyseal_closure_stop=_exact_bool(
                raw.get("retest_after_epiphyseal_closure_stop")
            ),
        ))
    return tuple(parsed)


def parse_adult_gh_evidence(value: Any) -> AdultGhEvidence | None:
    """Revalidate mappings, JSON objects and typed objects without coercion.

    Absent or invalid individual facts stay unknown. An invalid test collection
    stays unknown as a whole rather than being dropped or truncated to fit.
    """
    if isinstance(value, AdultGhEvidence):
        value = {field.name: getattr(value, field.name) for field in fields(AdultGhEvidence)}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError, RecursionError):
            return None
    if not isinstance(value, Mapping):
        return None
    pathway = value.get("diagnosis_pathway")
    return AdultGhEvidence(
        applies_on=clinical_date(value.get("applies_on")),
        assessment_date=clinical_date(value.get("assessment_date")),
        diagnosis_pathway=pathway if type(pathway) is str and pathway in {
            "childhood_onset_retest", "adult_hypothalamic_pituitary"
        } else None,
        childhood_gh_deficiency_diagnosed=_exact_bool(
            value.get("childhood_gh_deficiency_diagnosed")
        ),
        childhood_gh_treatment_received=_exact_bool(value.get("childhood_gh_treatment_received")),
        gh_stopped_due_to_epiphyseal_closure=_exact_bool(
            value.get("gh_stopped_due_to_epiphyseal_closure")
        ),
        adult_hypothalamic_pituitary_gh_deficiency_suspected=_exact_bool(
            value.get("adult_hypothalamic_pituitary_gh_deficiency_suspected")
        ),
        additional_anterior_pituitary_deficiency_confirmed=_exact_bool(
            value.get("additional_anterior_pituitary_deficiency_confirmed")
        ),
        two_distinct_stimulation_procedures_documented=_exact_bool(
            value.get("two_distinct_stimulation_procedures_documented")
        ),
        itt_contraindicated=_exact_bool(value.get("itt_contraindicated")),
        stimulation_tests=_stimulation_tests(value.get("stimulation_tests")),
    )

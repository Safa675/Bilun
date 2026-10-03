"""Request-local observation wiring for the explicitly instrumented GH protocols."""

from __future__ import annotations

from typing import Any

from .runtime_observations import ClinicalObservationCollector
from .matching import _drug_name_matches

VERSION = "gh.atomic.v1.2026-10-02"
_PROTOCOLS = {
    "growth_hormone_continuation_protocol": {"turner_somatropin_v1", "pediatric_gh_v1"},
    "pws_continuation_protocol": {"pws_somatropin_v1"},
    "ckd_growth_hormone_protocol": {"ckd_somatropin_v1"},
    "mecasermin_source_scope": {"mecasermin_laron_v1"},
    "pediatric_gh_initiation_protocol": {"pediatric_gh_initiation_v1"},
}
_REVIEWED_MECASERMIN_LETTERS = {
    "4.2.6.B-3#dde3c8f6": "a",
    "4.2.6.B-3#11e1f077": "b",
    "4.2.6.B-3#de2f2b31": "c",
}


def make_gh_observer(line: Any, rules: list[dict[str, Any]]) -> ClinicalObservationCollector | None:
    if not any(
        any(
            isinstance(rule.get(field), str) and rule[field] in protocols
            for field, protocols in _PROTOCOLS.items()
        )
        and _drug_name_matches(line.drug_name, rule.get("drug_names") or [])
        for rule in rules
    ):
        return None
    observer = ClinicalObservationCollector(line, "growth_hormone", VERSION)
    observer.context("drug_name")  # The real name-scoped candidate test just ran.
    return observer


def gh_selected_scope(observer: ClinicalObservationCollector | None, rule: dict[str, Any]) -> None:
    declared = [
        (rule[field], protocols)
        for field, protocols in _PROTOCOLS.items()
        if rule.get(field) is not None
    ]
    if observer is not None and (
        not declared
        or not all(isinstance(value, str) and value in protocols for value, protocols in declared)
    ):
        # A name-matched GH family may select legacy or source-only context.
        # Its uninstrumented comparisons must not appear as measured zero.
        observer.route(
            "gh.caller.uninstrumented_protocol",
            "blocked_source",
            ["selected_route_has_no_reviewed_predicate_instrumentation"],
        )


def gh_caller_skip(observer: ClinicalObservationCollector | None, route: str, reason: str) -> None:
    if observer is not None:
        observer.route(route, "skipped_not_applicable", [reason])


def gh_caller_input_block(
    observer: ClinicalObservationCollector | None, route: str, reason: str, fields: list[str]
) -> None:
    if observer is not None:
        observer.route(route, "blocked_inputs", [reason], fields)


def gh_source_view():
    """Apply only the three already-reviewed Word-list identities, never arbitrary prose."""
    from ...sut.rules_catalog import _load_sut_clauses_frame
    from scripts.sut.prose.clause_type_overrides import (
        apply_clause_type_overrides,
        load_clause_type_overrides,
    )
    import yaml

    raw = _load_sut_clauses_frame()
    try:
        declared = load_clause_type_overrides()
        reviewed = {}
        for key, letter in _REVIEWED_MECASERMIN_LETTERS.items():
            spec = declared.get(key, {})
            if (
                spec.get("clause_type") == "bent"
                and spec.get("clause_letter") == letter
                and spec.get("source_evidence")
                == "data/gazette/source_evidence/mecasermin_known_as_of_continuation.json"
            ):
                reviewed[key] = {"clause_type": "bent", "clause_letter": letter}
        return apply_clause_type_overrides(raw, reviewed)
    except (OSError, TypeError, ValueError, AttributeError, yaml.YAMLError):
        # Observations must not change a clinical decision on source-load failure.
        # Uncorrected prose leaves source metrics unavailable in the aggregator.
        return raw


def attach_gh_runtime(
    base: dict[str, Any], observer: ClinicalObservationCollector | None
) -> dict[str, Any]:
    if observer is None:
        return base
    result = dict(base)
    summary = (
        {
            "schema_version": 1,
            "available": False,
            "instrumented_families": ["growth_hormone"],
            "unavailable_reason": "The selected GH route has no reviewed predicate instrumentation.",
        }
        if any(
            row.get("route_id") == "gh.caller.uninstrumented_protocol" for row in observer.receipts
        )
        else observer.summary(gh_source_view())
    )
    result["runtime_coverage"] = summary
    if isinstance(base.get("violation"), dict):
        result["violation"] = {**base["violation"], "runtime_coverage": summary}
    return result

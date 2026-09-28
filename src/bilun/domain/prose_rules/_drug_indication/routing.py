"""Drug candidate grouping, route applicability, and deterministic arbitration."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .matching import (
    _diagnosis_matches_specific_rule,
    _drug_name_matches,
    _has_biomarker_requirement,
    _has_dose_protocol,
    _has_prior_therapy_requirement,
    _has_tier_b_constraints,
    _is_indication_route_rule,
    _normalize_tr,
    _rule_has_icd_selector,
    _rule_icd_selectors,
    _rule_tier_b_score,
    _specialty_matches,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimDiagnosis, DrugClaimLine


def _drug_rule_candidates(
    drug_name: str,
    rules: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    # Canonicalize candidate order at the boundary. Even when arbitration
    # correctly returns an honest ambiguity, the evidence payload must not
    # leak source-corpus ordering through ``eligible_route_rules``.
    drug_hits = sorted(
        (rule for rule in rules if _drug_name_matches(drug_name, rule.get("drug_names") or [])),
        key=lambda rule: str(rule.get("rule_id") or ""),
    )
    specific = [
        rule
        for rule in drug_hits
        if _rule_has_icd_selector(rule) and _is_indication_route_rule(rule)
    ]
    supplemental = [rule for rule in drug_hits if not _rule_has_icd_selector(rule)]
    return drug_hits, specific, supplemental


def _route_group_key(rule: dict[str, Any]) -> tuple[str, ...]:
    return tuple(sorted(_rule_icd_selectors(rule)))


def _route_preference_key(rule: dict[str, Any]) -> tuple[int, int, str]:
    """Prefer constrained, specifically named routes with a stable final tie-break."""
    return (
        -_rule_tier_b_score(rule),
        len(rule.get("drug_names") or []),
        str(rule.get("rule_id") or ""),
    )


def _semantic_route_signature(rule: dict[str, Any]) -> str:
    """Return the stable, implemented constraint semantics for a route.

    Identity, source prose, and provenance are evidence rather than claim-side
    discriminators. Two rules are operationally equivalent only when every
    structured field consumed by this evaluator is equal. In particular,
    duration, specialty, inpatient, dose, biomarker, and prior-therapy
    differences remain ambiguous until claim inputs select one of them.
    """
    constraint_fields = (
        "report_required",
        "report_duration_months",
        "report_specialties",
        "prescriber_specialties",
        "inpatient_only",
        "loading_dose_count",
        "max_applications_per_year",
        "max_drops_per_day",
        "min_gap_months_after_antivegf",
        "required_biomarkers",
        "requires_prior_therapy",
        "pay",
    )
    return json.dumps(
        {key: rule.get(key) for key in constraint_fields},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _select_semantically_equivalent_route(
    routes: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not routes:
        return None
    if len({_semantic_route_signature(rule) for rule in routes}) != 1:
        return None
    return min(routes, key=lambda rule: str(rule.get("rule_id") or ""))


def _preferred_route_rule(
    routes: list[dict[str, Any]],
    drug_line: DrugClaimLine | None = None,
) -> dict[str, Any] | None:
    del drug_line
    return _select_semantically_equivalent_route(routes)


def _route_specificity_key(
    key: tuple[str, ...],
    routes: list[dict[str, Any]] | None = None,
) -> tuple[int, int, int, tuple[str, ...]]:
    """Rank explicit ICD prefixes above broad ICD ranges, then narrower sets."""
    shortest_drug_name_set = min(
        (len(rule.get("drug_names") or []) for rule in routes or []),
        default=10_000,
    )
    return (
        sum("-" in selector for selector in key),
        shortest_drug_name_set,
        len(key),
        key,
    )


def _select_route_rule(
    routes: list[dict[str, Any]],
    drug_line: DrugClaimLine,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Select a route only when available claim fields justify its constraints."""
    pool = list(routes)
    if not pool:
        return None, []

    # An explicitly supplied field, including an empty tuple, is evidence that
    # the corresponding gated route should be considered.  An unavailable
    # field must not force a gated route when an ordinary route is available.
    if drug_line.biomarkers is not None:
        biomarker_rules = [rule for rule in pool if _has_biomarker_requirement(rule)]
        if biomarker_rules:
            pool = biomarker_rules
    else:
        non_biomarker_rules = [rule for rule in pool if not _has_biomarker_requirement(rule)]
        if non_biomarker_rules:
            pool = non_biomarker_rules

    if drug_line.prior_therapies is not None:
        prior_therapy_rules = [rule for rule in pool if _has_prior_therapy_requirement(rule)]
        if prior_therapy_rules:
            pool = prior_therapy_rules
    else:
        non_prior_therapy_rules = [
            rule for rule in pool if not _has_prior_therapy_requirement(rule)
        ]
        if non_prior_therapy_rules:
            pool = non_prior_therapy_rules

    duration = drug_line.drug_report_duration_months
    if duration is not None:
        exact_duration = [rule for rule in pool if rule.get("report_duration_months") == duration]
        if exact_duration:
            pool = exact_duration
        else:
            duration_rules = [
                rule for rule in pool if rule.get("report_duration_months") is not None
            ]
            if duration_rules:
                pool = duration_rules

    if drug_line.drug_inpatient_supply is not None:
        inpatient = [rule for rule in pool if rule.get("inpatient_only")]
        if inpatient:
            pool = inpatient
    else:
        non_inpatient = [rule for rule in pool if not rule.get("inpatient_only")]
        if non_inpatient:
            pool = non_inpatient

    has_dose_input = (
        drug_line.annual_application_count is not None or drug_line.is_loading_phase is not None
    )
    if has_dose_input:
        dose_rules = [rule for rule in pool if _has_dose_protocol(rule)]
        if dose_rules:
            pool = dose_rules

    specialty = (drug_line.prescriber_specialty or "").strip()
    if specialty:
        matching = [
            rule
            for rule in pool
            if rule.get("prescriber_specialties")
            and _specialty_matches(specialty, list(rule.get("prescriber_specialties") or []))
        ]
        if matching:
            pool = matching
        else:
            prescriber_rules = [rule for rule in pool if rule.get("prescriber_specialties")]
            if prescriber_rules:
                pool = prescriber_rules
    else:
        no_prescriber_rules = [rule for rule in pool if not rule.get("prescriber_specialties")]
        if no_prescriber_rules:
            pool = no_prescriber_rules

    if duration is None:
        no_duration_rules = [rule for rule in pool if rule.get("report_duration_months") is None]
        if no_duration_rules:
            pool = no_duration_rules

    if len(pool) == 1:
        return pool[0], []

    selected = _select_semantically_equivalent_route(pool)
    if selected is not None:
        return selected, []
    return None, ["route_discriminator"]


def _has_supplemental_constraint(rule: dict[str, Any]) -> bool:
    return bool(
        rule.get("report_required")
        or rule.get("report_specialties")
        or _has_tier_b_constraints(rule)
    )


def _supplemental_matches_route(
    supplemental: dict[str, Any],
    selected_route: dict[str, Any],
) -> bool:
    """Require route metadata before treating a generic rule as applicable."""
    supplemental_specialties = {
        _normalize_tr(value)
        for value in (
            *(supplemental.get("report_specialties") or []),
            *(supplemental.get("prescriber_specialties") or []),
        )
        if str(value).strip()
    }
    if not supplemental_specialties:
        return True
    route_specialties = {
        _normalize_tr(value)
        for value in (
            *(selected_route.get("report_specialties") or []),
            *(selected_route.get("prescriber_specialties") or []),
        )
        if str(value).strip()
    }
    return bool(route_specialties & supplemental_specialties)


def _select_supplemental_rule(
    resolution: dict[str, Any],
    drug_line: DrugClaimLine,
) -> dict[str, Any] | None:
    selected_route = resolution.get("selected_rule")
    if not isinstance(selected_route, dict):
        return None
    candidates = [
        rule
        for rule in (resolution.get("supplemental_rules") or [])
        if rule.get("pay") is not False
        and _has_supplemental_constraint(rule)
        and _supplemental_matches_route(rule, selected_route)
    ]
    selected, _ = _select_route_rule(candidates, drug_line)
    return selected


def _resolve_drug_indication_route(
    *,
    drug_line: DrugClaimLine,
    icd_codes: list[str],
    rules: list[dict[str, Any]],
    diagnoses: list[ClaimDiagnosis] | None = None,
    primary_icd10: str | None = None,
) -> dict[str, Any]:
    """Resolve applicability before any report or clinical constraint is checked."""
    drug_hits, specific_routes, supplemental_rules = _drug_rule_candidates(
        drug_line.drug_name, rules
    )
    if not drug_hits:
        return {
            "applicability_status": "not_in_encoded_corpus",
            "drug_hits": [],
            "specific_routes": [],
            "supplemental_rules": [],
            "matched_routes": [],
            "matched_icd10_codes": [],
            "unmatched_icd10_codes": list(icd_codes),
            "selected_rule": None,
            "missing_inputs": [],
        }

    if not specific_routes:
        # A caller that supplies an isolated supplemental rule is retained for
        # backwards compatibility with direct unit-level rule evaluation.  The
        # full-corpus path always has diagnosis-specific candidates before any
        # supplemental constraint can be evaluated.
        if rules and len(rules) == 1 and supplemental_rules:
            selected_rule, missing_inputs = _select_route_rule(
                supplemental_rules,
                drug_line,
            )
            return {
                "applicability_status": "supplemental_only",
                "drug_hits": drug_hits,
                "specific_routes": [],
                "supplemental_rules": supplemental_rules,
                "matched_routes": [],
                "matched_icd10_codes": [],
                "unmatched_icd10_codes": list(icd_codes),
                "selected_rule": selected_rule,
                "missing_inputs": missing_inputs,
            }
        return {
            "applicability_status": "not_in_encoded_corpus",
            "drug_hits": drug_hits,
            "specific_routes": [],
            "supplemental_rules": supplemental_rules,
            "matched_routes": [],
            "matched_icd10_codes": [],
            "unmatched_icd10_codes": list(icd_codes),
            "selected_rule": None,
            "missing_inputs": [],
        }

    if not icd_codes:
        return {
            "applicability_status": "missing_diagnosis",
            "drug_hits": drug_hits,
            "specific_routes": specific_routes,
            "supplemental_rules": supplemental_rules,
            "matched_routes": [],
            "matched_icd10_codes": [],
            "unmatched_icd10_codes": [],
            "selected_rule": None,
            "missing_inputs": ["claim_diagnoses", "primary_icd10"],
        }

    has_normalized_primary = any(
        row.claim_id == drug_line.claim_id
        and bool(str(row.icd10_code or "").strip())
        and row.is_primary
        for row in diagnoses or ()
    )
    if (
        primary_icd10 is not None
        and not str(primary_icd10 or "").strip()
        and not has_normalized_primary
    ):
        return {
            "applicability_status": "missing_diagnosis",
            "drug_hits": drug_hits,
            "specific_routes": specific_routes,
            "supplemental_rules": supplemental_rules,
            "matched_routes": [],
            "matched_icd10_codes": [],
            "unmatched_icd10_codes": [],
            "selected_rule": None,
            "missing_inputs": ["primary_icd10"],
        }

    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    group_matches: dict[tuple[str, ...], list[str]] = {}
    for rule in specific_routes:
        key = _route_group_key(rule)
        groups.setdefault(key, []).append(rule)
        group_matches.setdefault(key, [])
        for code in icd_codes:
            if _diagnosis_matches_specific_rule([code], rule) and code not in group_matches[key]:
                group_matches[key].append(code)

    groups = {key: value for key, value in groups.items() if group_matches[key]}
    group_matches = {key: value for key, value in group_matches.items() if value}
    if not groups:
        return {
            "applicability_status": "indication_mismatch",
            "drug_hits": drug_hits,
            "specific_routes": specific_routes,
            "supplemental_rules": supplemental_rules,
            "matched_routes": [],
            "matched_icd10_codes": [],
            "unmatched_icd10_codes": list(icd_codes),
            "selected_rule": None,
            "missing_inputs": [],
        }

    # A broad family rule must not compete with a narrower diagnosis route for
    # the same observed code. Keep one best route group per observed code; if
    # different observed codes select different groups, applicability is
    # genuinely ambiguous rather than file-order dependent.
    best_group_by_code: dict[str, tuple[str, ...]] = {}
    for code in icd_codes:
        candidates = [key for key, matched in group_matches.items() if code in matched]
        if candidates:
            best_group_by_code[code] = min(
                candidates,
                key=lambda candidate: _route_specificity_key(
                    candidate,
                    groups[candidate],
                ),
            )
    effective_keys = tuple(dict.fromkeys(best_group_by_code.values()))
    matched_codes = [code for code in icd_codes if code in best_group_by_code]
    unmatched_codes = [code for code in icd_codes if code not in matched_codes]
    effective_key = effective_keys[0] if len(effective_keys) == 1 else None
    matched_routes = list(groups[effective_key]) if effective_key is not None else []
    if effective_key is not None:
        # A broader route may carry a structured downstream discriminator that
        # the narrower route does not (for example biomarker or inpatient
        # supply evidence).  It joins the constraint pool only when that field
        # is actually present; broad prescriber/duration routes never override
        # a more specific diagnosis route by themselves.
        for rule in specific_routes:
            if rule in matched_routes or not any(
                _diagnosis_matches_specific_rule([code], rule) for code in matched_codes
            ):
                continue
            has_dose_input = (
                drug_line.annual_application_count is not None
                or drug_line.is_loading_phase is not None
            )
            downstream_gate_present = (
                (_has_biomarker_requirement(rule) and drug_line.biomarkers is not None)
                or (_has_prior_therapy_requirement(rule) and drug_line.prior_therapies is not None)
                or (
                    bool(rule.get("inpatient_only")) and drug_line.drug_inpatient_supply is not None
                )
                or (_has_dose_protocol(rule) and has_dose_input)
                or (
                    drug_line.drug_report_duration_months is not None
                    and rule.get("report_duration_months") == drug_line.drug_report_duration_months
                )
            )
            if downstream_gate_present:
                matched_routes.append(rule)

    if len(effective_keys) != 1:
        return {
            "applicability_status": "ambiguous_route",
            "drug_hits": drug_hits,
            "specific_routes": specific_routes,
            "supplemental_rules": supplemental_rules,
            "matched_routes": matched_routes,
            "matched_icd10_codes": matched_codes,
            "unmatched_icd10_codes": unmatched_codes,
            "selected_rule": None,
            "missing_inputs": ["route_discriminator"],
        }

    selected_rule, missing_inputs = _select_route_rule(matched_routes, drug_line)
    if selected_rule is None:
        return {
            "applicability_status": "ambiguous_route",
            "drug_hits": drug_hits,
            "specific_routes": specific_routes,
            "supplemental_rules": supplemental_rules,
            "matched_routes": matched_routes,
            "matched_icd10_codes": matched_codes,
            "unmatched_icd10_codes": unmatched_codes,
            "selected_rule": None,
            "missing_inputs": missing_inputs or ["route_discriminator"],
        }

    return {
        "applicability_status": "eligible",
        "drug_hits": drug_hits,
        "specific_routes": specific_routes,
        "supplemental_rules": supplemental_rules,
        "matched_routes": matched_routes,
        "matched_icd10_codes": matched_codes,
        "unmatched_icd10_codes": unmatched_codes,
        "selected_rule": selected_rule,
        "missing_inputs": [],
    }


def _find_matching_rule(
    drug_name: str,
    icd_codes: list[str],
    rules: list[dict[str, Any]],
    drug_line: DrugClaimLine,
) -> dict[str, Any] | None:
    resolution = _resolve_drug_indication_route(
        drug_line=drug_line,
        icd_codes=icd_codes,
        rules=rules,
    )
    return resolution.get("selected_rule")

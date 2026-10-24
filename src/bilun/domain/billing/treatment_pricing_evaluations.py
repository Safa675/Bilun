"""Claim-scoped observations of all 202 treatment-pricing authored rules.

Raw output follows the original predicates and order. Typed candidates do not
confirm money or violations, and documented builder proxies cannot certify
annual history, session identity, supervision, or treatment-report evidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from math import isfinite
from types import MappingProxyType
from typing import Any

from src.bilun.domain.billing.broad_rule_catalog import (
    CandidateClassification,
    load_broad_rule_catalog,
)
from src.bilun.domain.billing.payment_traceability_evaluations import _ObservedContext
from src.bilun.domain.billing.rule_findings import RuleEvaluation
from src.bilun.domain.claims.claim_type import care_setting_gap
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.treatment_pricing import (
    _build_treatment_pricing_context,
    _condition_matches,
    _source_review_required,
    _suffix_len,
    _violation_from_rule,
    load_treatment_pricing_rules,
)

_FAMILY = "treatment_pricing_2_4"
_RULE_COUNT = 202
_PROXY_REASONS = {
    "sessions": "procedure_dates_not_treatment_sessions",
    "sessions_per_day": "procedure_counts_not_treatment_sessions",
    "same_day_physio_rehab": "procedure_counts_not_treatment_sessions",
    "sessions_within_year": "cross_claim_history_unavailable",
    "sessions_same_region_within_1y": "cross_claim_history_unavailable",
    "sessions_per_patient_per_year": "cross_claim_history_unavailable",
    "daily_exams_per_physician": "physician_identity_or_workload_unavailable",
    "daily_billing_hours_per_physician": "physician_identity_or_workload_unavailable",
    "days_from_report_to_treatment": "board_report_date_unavailable",
    "diagnosis_category_any": "diagnosis_category_mapping_unverified",
    "diagnosis_category_not_in": "diagnosis_category_mapping_unverified",
    "prescriber_specialty_any": "prescriber_specialty_not_established",
    "supervised_by_pmr_specialty": "pmr_supervision_not_established",
    "concomitant_service": "co_billed_services_not_verified_treatment_overlap",
    "billed_with_other_physiotherapy": "co_billed_services_not_verified_treatment_overlap",
    "origin_is_traffic_accident": "traffic_accident_origin_unverified",
}
_FACILITY_TIERS = {
    "third_step_public",
    "ghdm_licensed_2nd_private",
    "moh_2nd_step_public",
    "moh_provider",
    "state_university_provider",
}
_FACILITY_TYPES_DERIVED = {"training_research_hospital", "foundation_university", "private"}


@dataclass(frozen=True)
class _CatalogSource:
    source_file: str
    source_locators: tuple[str, ...]
    billable: bool | None
    candidate_classification: CandidateClassification


@dataclass(frozen=True)
class TreatmentPricingMatch:
    patient_id: str
    claim_id: str
    rule_id: str
    family: str
    source_file: str
    source_locators: tuple[str, ...]
    authored_action: dict[str, Any]
    billable: bool | None
    candidate_classification: CandidateClassification
    legacy_row: dict[str, Any]


@dataclass(frozen=True)
class LegacyTreatmentPricingRow:
    patient_id: str
    claim_id: str
    rule_id: str
    family: str
    legacy_row: dict[str, Any]


@dataclass(frozen=True)
class TreatmentPricingBatch:
    evaluations: tuple[RuleEvaluation, ...] = ()
    matches: tuple[TreatmentPricingMatch, ...] = ()
    legacy_rows: tuple[LegacyTreatmentPricingRow, ...] = ()


@lru_cache(maxsize=1)
def _treatment_catalog_sources() -> Mapping[str, _CatalogSource]:
    return MappingProxyType(
        {
            row.rule_id: _CatalogSource(
                row.source_file, row.source_locators, row.billable, row.candidate_classification
            )
            for row in load_broad_rule_catalog()
            if row.family == _FAMILY
        }
    )


def _observe_condition(
    condition: dict[str, Any],
    flat: dict[str, Any],
) -> tuple[bool, str, list[str], str | None]:
    """Observe original predicate branches in their unchanged conjunction order.

    Each condition key invokes the original implementation once, including
    its ICD prefix, numeric-range, and collection fallback logic. No second
    wrapper or parallel clinical matcher is run to recover raw decisions.
    """
    issue: tuple[str, list[str], str] | None = None
    for key, expected in condition.items():
        observed = _ObservedContext(flat)
        matched = _condition_matches({key: expected}, observed)
        if isinstance(expected, dict) and ("min" in expected or "max" in expected):
            actual = flat.get(key)
            if actual is not None:
                try:
                    numeric_valid = isfinite(float(actual))
                except (TypeError, ValueError):
                    numeric_valid = False
                if not numeric_valid:
                    issue = ("unavailable", [], "invalid_numeric_input")
        if not matched:
            if issue is not None:
                return False, *issue
            if not observed.reads:
                return False, "unavailable", [], "unsupported_predicate_shape"
            if key == "procedure_in_annex":
                if not any(value for _, value in observed.reads):
                    return (
                        False,
                        "missing_inputs",
                        ["procedure_code"],
                        "required_treatment_inputs_missing",
                    )
                return False, "unavailable", [], "annex_membership_not_confirmed"
            if all(value is None for _, value in observed.reads):
                missing = list(dict.fromkeys(field for field, _ in observed.reads))
                return False, "missing_inputs", missing, "required_treatment_inputs_missing"
            return False, "evaluated", [], None
    if issue is not None:
        return True, *issue
    return True, "evaluated", [], None


def _available_value(key: str, flat: dict[str, Any]) -> Any:
    """Read the existing predicate's fallback inputs, without matching values."""
    suffix = _suffix_len(key)
    base = key[:-suffix] if suffix else key
    for field in (key, base, base + "_any"):
        if flat.get(field) is not None:
            return flat[field]
    return None


def _metadata_gate(condition, claim_ctx, flat) -> tuple[str, list[str], str] | None:
    for key in condition:
        if key in _PROXY_REASONS:
            if _available_value(key, flat) is None:
                return "missing_inputs", [key], "required_treatment_inputs_missing"
            return "unavailable", [], _PROXY_REASONS[key]
    if set(condition) & {"health_board_report_present", "health_report_present"}:
        flags = [r.drug_specialty_board_report_present for r in claim_ctx.drug_lines]
        if not flags or all(flag is None for flag in flags):
            return "missing_inputs", ["treatment_board_report"], "treatment_board_report_missing"
        return "unavailable", ["treatment_board_report"], "treatment_board_report_not_established"
    header = claim_ctx.claims[0]
    if "provider_type" in condition:
        provider = str(header.provider_type or "").strip()
        if not provider:
            return "missing_inputs", ["provider_type"], "raw_provider_type_missing"
        if provider.casefold() in {"sozlesmeli", "contracted", "sozlesmesiz", "uncontracted"}:
            return "unavailable", [], "provider_ownership_not_established"
    if any(key.startswith("facility_tier") for key in condition):
        tier = str(header.facility_tier or "").strip()
        if not tier:
            return "missing_inputs", ["facility_tier"], "raw_facility_tier_missing"
        if tier not in _FACILITY_TIERS:
            return "unavailable", [], "facility_tier_vocabulary_not_derived"
    for key in ("facility_type", "facility_type_any"):
        if key in condition:
            if flat.get("facility_type") is None:
                return "unavailable", [], "facility_type_not_derived"
            expected = condition[key]
            values = {expected} if isinstance(expected, str) else set(expected)
            if values - _FACILITY_TYPES_DERIVED:
                return "unavailable", [], "facility_type_vocabulary_not_derived"
    if set(condition) & {"visit_type", "treatment_setting"}:
        # One claim-type vocabulary (claims/claim_type.py, #335).
        gap = care_setting_gap(header.claim_type)
        if gap == "missing":
            return "missing_inputs", ["claim_type"], "raw_claim_type_missing"
        if gap == "unrecognized":
            return "unavailable", [], "claim_type_unrecognized"
        if gap == "not_settled":
            return "unavailable", [], "claim_type_care_setting_not_settled"
    return None


def _validate_ownership(patient_id, ctx):
    groups = (
        ctx.claims,
        ctx.procedure_lines,
        ctx.material_lines,
        ctx.drug_lines,
        ctx.diagnoses,
        ctx.performed_procedure_lines,
        ctx.medula_rejection_events,
    )
    if ctx.patient_id != patient_id or any(
        r.patient_id != patient_id for rows in groups for r in rows
    ):
        raise ValueError("Treatment context belongs to another patient")
    claims = {r.claim_id for r in ctx.claims}
    if len(claims) != len(ctx.claims):
        raise ValueError("Duplicate treatment claim header")
    if any(r.claim_id not in claims for rows in groups[1:] for r in rows):
        raise ValueError("Treatment lines include a foreign claim")


def evaluate_treatment_pricing(
    patient_id: str, ctx: PatientClaimContext | None
) -> TreatmentPricingBatch:
    """Evaluate all authored rules independently on each real claim slice."""
    sources = _treatment_catalog_sources()
    ruleset = load_treatment_pricing_rules()
    rules = ruleset["rules"]
    if (
        ruleset["rule_set_id"] != _FAMILY
        or len(rules) != _RULE_COUNT
        or {r["rule_id"] for r in rules} != set(sources)
    ):
        raise ValueError("Treatment corpus differs from the authored catalog")
    if any(r["action"].get("billable") is not sources[r["rule_id"]].billable for r in rules):
        raise ValueError("Treatment authored classification changed")
    if ctx is not None:
        _validate_ownership(patient_id, ctx)
    if ctx is None or not ctx.claims:
        missing = "claim_context" if ctx is None else "claim_headers"
        return TreatmentPricingBatch(
            evaluations=tuple(
                RuleEvaluation(
                    patient_id=patient_id,
                    claim_id=None,
                    rule_id=r["rule_id"],
                    evaluation_status="missing_inputs",
                    required_inputs=list(r["condition"]) + [missing],
                    missing_inputs=[missing],
                    reason="claim_context_unavailable",
                )
                for r in rules
            )
        )
    evaluations, matches, legacy_rows = [], [], []
    for claim_id in sorted(c.claim_id for c in ctx.claims):
        claim_ctx = ctx.slice_for_claim(claim_id)
        if claim_ctx is None:
            raise ValueError(f"Claim disappeared from treatment context: {claim_id}")
        flat = _build_treatment_pricing_context(claim_ctx)
        for rule in rules:
            rule_id = rule["rule_id"]
            if _source_review_required(rule):
                evaluations.append(RuleEvaluation(
                    patient_id=patient_id, claim_id=claim_id, rule_id=rule_id,
                    evaluation_status="unavailable", required_inputs=[], missing_inputs=[],
                    reason="source_review_required",
                ))
                legacy_rows.append(LegacyTreatmentPricingRow(
                    patient_id, claim_id, rule_id, _FAMILY, _violation_from_rule(rule, _FAMILY),
                ))
                continue
            condition = rule["condition"]
            raw_matched, status, missing, reason = _observe_condition(condition, flat)
            gate = _metadata_gate(condition, claim_ctx, flat)
            if gate is not None:
                status, missing, reason = gate
            decision = (
                ("matched" if raw_matched else "not_matched") if status == "evaluated" else None
            )
            evaluations.append(
                RuleEvaluation(
                    patient_id=patient_id,
                    claim_id=claim_id,
                    rule_id=rule_id,
                    evaluation_status=status,
                    required_inputs=list(dict.fromkeys(list(condition) + missing)),
                    missing_inputs=missing,
                    decision=decision,
                    reason=reason,
                )
            )
            if raw_matched:
                raw = _violation_from_rule(rule, _FAMILY)
                legacy_rows.append(
                    LegacyTreatmentPricingRow(patient_id, claim_id, rule_id, _FAMILY, raw)
                )
                if decision == "matched":
                    source = sources[rule_id]
                    matches.append(
                        TreatmentPricingMatch(
                            patient_id=patient_id,
                            claim_id=claim_id,
                            rule_id=rule_id,
                            family=_FAMILY,
                            source_file=source.source_file,
                            source_locators=source.source_locators,
                            authored_action=deepcopy(rule["action"]),
                            billable=source.billable,
                            candidate_classification=source.candidate_classification,
                            legacy_row=deepcopy(raw),
                        )
                    )
    return TreatmentPricingBatch(tuple(evaluations), tuple(matches), tuple(legacy_rows))

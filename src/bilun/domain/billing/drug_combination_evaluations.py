"""Claim-scoped observation of the 53 authored drug-combination predicates.

Original matches remain available as legacy rows. Typed candidates additionally
require usable inputs; none is a confirmed denial, clinical conclusion, or
monetary adjustment merely because an authored action or predicate matches.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
from typing import Any

from src.bilun.domain.billing.broad_rule_catalog import (
    CandidateClassification,
    load_broad_rule_catalog,
)
from src.bilun.domain.billing.rule_findings import RuleEvaluation
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.drug_combination import (
    _BLOCKED_KEYS,
    _DEFER_NO_SOURCE_KEYS,
    _WIREABLE_KEYS,
    _check_combo_condition,
    _collect_diagnoses,
    _collect_drug_names,
    _violation_from_rule,
    load_drug_combination_rules,
)

_FAMILY = "drug_combination_4_2"
_RULE_COUNT = 53


@dataclass(frozen=True)
class _CatalogSource:
    source_file: str
    source_locators: tuple[str, ...]
    billable: bool | None
    candidate_classification: CandidateClassification


@dataclass(frozen=True)
class DrugCombinationMatch:
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
class LegacyDrugCombinationRow:
    patient_id: str
    claim_id: str
    rule_id: str
    family: str
    legacy_row: dict[str, Any]


@dataclass(frozen=True)
class DrugCombinationBatch:
    evaluations: tuple[RuleEvaluation, ...] = ()
    matches: tuple[DrugCombinationMatch, ...] = ()
    legacy_rows: tuple[LegacyDrugCombinationRow, ...] = ()


@lru_cache(maxsize=1)
def _combination_catalog_sources() -> Mapping[str, _CatalogSource]:
    """Validate authored identities once without caching mutable rule payloads."""
    return MappingProxyType(
        {
            row.rule_id: _CatalogSource(
                row.source_file, row.source_locators, row.billable, row.candidate_classification
            )
            for row in load_broad_rule_catalog()
            if row.family == _FAMILY
        }
    )


def _validate_ownership(patient_id: str, ctx: PatientClaimContext) -> None:
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
        row.patient_id != patient_id for rows in groups for row in rows
    ):
        raise ValueError("Drug-combination context belongs to another patient")
    claim_ids = {row.claim_id for row in ctx.claims}
    if len(claim_ids) != len(ctx.claims):
        raise ValueError("Duplicate drug-combination claim header")
    if any(row.claim_id not in claim_ids for rows in groups[1:] for row in rows):
        raise ValueError("Drug-combination lines include a foreign claim")


def _metadata_gate(
    condition: dict[str, Any],
    claim_ctx: PatientClaimContext,
    diagnoses: list[str],
    facility_tier: str,
) -> tuple[str, list[str], str] | None:
    """Preflight unsupported inputs without changing the legacy short circuit."""
    if not claim_ctx.drug_lines:
        return "missing_inputs", ["drug_lines"], "drug_feed_unavailable"
    keys = set(condition)
    unknown = keys - _WIREABLE_KEYS - _BLOCKED_KEYS - _DEFER_NO_SOURCE_KEYS
    if unknown:
        return "unavailable", sorted(unknown), "unsupported_condition_keys"
    blocked = keys & (_BLOCKED_KEYS | _DEFER_NO_SOURCE_KEYS)
    if blocked:
        return "unavailable", sorted(blocked), "unsupported_condition_inputs"
    if "indication_not_in" in keys:
        # The authored values are semantic labels (ckd_anemia/mds_anemia),
        # whereas the original matcher compares them with ICD strings. A
        # negative comparison cannot establish clinical non-entitlement.
        return "unavailable", ["indication"], "semantic_indication_not_derived"
    if "two_distinct_agents_same_class_concurrent" in keys:
        return "unavailable", ["drug_class"], "drug_class_membership_not_derived"
    if "two_distinct_active_ingredients_concurrent" in keys:
        return "unavailable", ["active_ingredient"], "active_ingredient_identity_not_derived"
    if any(not str(line.drug_name or "").strip() for line in claim_ctx.drug_lines):
        return "missing_inputs", ["drug_name"], "drug_names_incomplete"
    if "diagnosis_any" in keys and not diagnoses:
        return "missing_inputs", ["diagnoses"], "diagnoses_unavailable"
    if "facility_tier_in" in keys:
        if not facility_tier:
            return "missing_inputs", ["facility_tier"], "facility_tier_missing"
        if facility_tier not in {"first_step", "second_step", "third_step"}:
            return "unavailable", [], "facility_tier_vocabulary_not_derived"
    return None


def evaluate_drug_combinations(
    patient_id: str,
    ctx: PatientClaimContext | None,
) -> DrugCombinationBatch:
    """Observe each existing rule once per drug claim; account for every claim.

    Empty drug feeds are missing inputs, not clean passes. Raw rows retain the
    original wrapper's claim encounter order and original payloads, including
    matches withheld from typed candidates. Consumers must reuse these rows
    instead of invoking the legacy wrapper again.
    """
    sources = _combination_catalog_sources()
    ruleset = load_drug_combination_rules()
    rules = ruleset["rules"]
    if (
        ruleset["rule_set_id"] != _FAMILY
        or len(rules) != _RULE_COUNT
        or {row["rule_id"] for row in rules} != set(sources)
    ):
        raise ValueError("Drug-combination corpus differs from the authored catalog")
    if any(
        rule["action"].get("billable") is not sources[rule["rule_id"]].billable for rule in rules
    ):
        raise ValueError("Drug-combination authored classification changed")
    if ctx is not None:
        _validate_ownership(patient_id, ctx)
    if ctx is None or not ctx.claims:
        return DrugCombinationBatch(
            evaluations=tuple(
                RuleEvaluation(
                    patient_id=patient_id,
                    claim_id=None,
                    rule_id=rule["rule_id"],
                    evaluation_status="missing_inputs",
                    required_inputs=list(rule["condition"]),
                    missing_inputs=["claim_context" if ctx is None else "claim_headers"],
                    reason="claim_context_unavailable",
                )
                for rule in rules
            )
        )

    evaluations: list[RuleEvaluation] = []
    matches: list[DrugCombinationMatch] = []
    legacy_by_claim: dict[str, list[LegacyDrugCombinationRow]] = {}
    for claim_id in sorted(row.claim_id for row in ctx.claims):
        claim_ctx = ctx.slice_for_claim(claim_id)
        if claim_ctx is None:
            raise ValueError(f"Claim disappeared from drug-combination context: {claim_id}")
        names = _collect_drug_names(claim_ctx, claim_id)
        diagnoses = _collect_diagnoses(claim_ctx, claim_id)
        facility_tier = (claim_ctx.claims[0].facility_tier or "").strip().lower()
        claim_legacy = legacy_by_claim[claim_id] = []
        for rule in rules:
            rule_id = rule["rule_id"]
            condition = rule["condition"]
            # The existing wrapper never evaluates a claim with no drug rows.
            matched, predicate_reason = (
                _check_combo_condition(condition, names, diagnoses, facility_tier=facility_tier)
                if claim_ctx.drug_lines
                else (False, "skipped_no_data")
            )
            gate = _metadata_gate(condition, claim_ctx, diagnoses, facility_tier)
            if gate is not None:
                status, missing, reason = gate
                decision = None
            elif predicate_reason in {"matched", "not_matched"}:
                status, missing, reason = "evaluated", [], predicate_reason
                decision = "matched" if matched else "not_matched"
            else:
                status, missing, reason = "unavailable", [], predicate_reason
                decision = None
            evaluations.append(
                RuleEvaluation(
                    patient_id=patient_id,
                    claim_id=claim_id,
                    rule_id=rule_id,
                    evaluation_status=status,
                    required_inputs=list(condition),
                    missing_inputs=missing,
                    decision=decision,
                    reason=reason,
                )
            )
            if matched:
                raw = _violation_from_rule(rule, claim_id)
                claim_legacy.append(
                    LegacyDrugCombinationRow(patient_id, claim_id, rule_id, _FAMILY, raw)
                )
                if decision == "matched":
                    source = sources[rule_id]
                    matches.append(
                        DrugCombinationMatch(
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

    # Preserve the original wrapper's first-drug-line claim ordering even
    # though typed evaluations and matches have stable sorted claim order.
    legacy_claim_order = dict.fromkeys(line.claim_id for line in ctx.drug_lines)
    legacy_rows = tuple(row for cid in legacy_claim_order for row in legacy_by_claim[cid])
    return DrugCombinationBatch(tuple(evaluations), tuple(matches), legacy_rows)

"""Claim-scoped metadata for the 46 misc and 43 treatment gap-closing rules.

The existing predicate and serializer remain authoritative for legacy output.
Authored adverse/permission labels are candidates, not verified violations,
payment denials, mandatory charges, or monetary adjustments.
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
from src.bilun.domain.billing.payment_traceability_evaluations import (
    _evaluate_condition,
    _raw_header_gate,
)
from src.bilun.domain.billing.rule_findings import RuleEvaluation
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.gap_closing import (
    _build_gap_closing_context,
    _violation_from_rule,
    load_gap_closing_misc_rules,
    load_gap_closing_treatment_rules,
)

_FAMILY_COUNTS = {"gap_closing_misc": 46, "gap_closing_treatment_2": 43}


@dataclass(frozen=True)
class _CatalogSource:
    family: str
    source_file: str
    source_locators: tuple[str, ...]
    billable: bool | None
    candidate_classification: CandidateClassification


@dataclass(frozen=True)
class GapClosingMatch:
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
class LegacyGapClosingRow:
    patient_id: str
    claim_id: str
    rule_id: str
    family: str
    legacy_row: dict[str, Any]


@dataclass(frozen=True)
class GapClosingBatch:
    evaluations: tuple[RuleEvaluation, ...] = ()
    matches: tuple[GapClosingMatch, ...] = ()
    legacy_rows: tuple[LegacyGapClosingRow, ...] = ()


@lru_cache(maxsize=1)
def _gap_catalog_sources() -> Mapping[str, _CatalogSource]:
    """Validate the corpus once; cached source metadata has no mutable payloads."""
    return MappingProxyType(
        {
            entry.rule_id: _CatalogSource(
                entry.family,
                entry.source_file,
                entry.source_locators,
                entry.billable,
                entry.candidate_classification,
            )
            for entry in load_broad_rule_catalog()
            if entry.family in _FAMILY_COUNTS
        }
    )


def _base_key(key: str) -> str:
    for suffix in ("_not_any", "_not_in", "_any", "_in"):
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return key


def _metadata_gate(
    condition: dict[str, Any],
    claim_ctx: PatientClaimContext,
    flat: dict[str, Any],
) -> tuple[str, list[str], str] | None:
    """Check provenance of derived defaults without altering predicate results.

    The reused payment observer calls the very same gap-closing predicate and
    preserves authored short circuit/fallback behavior. These additional gates
    prevent missing raw fields or a negative emergency inference from becoming
    certified typed metadata. Raw legacy matches remain available separately.
    """
    header = claim_ctx.claims[0]
    keys = {_base_key(key) for key in condition}
    raw_keys = dict.fromkeys(keys)
    if keys & {"payment_method", "payment_method_path"}:
        raw_keys["care_setting"] = None
    if keys & {"facility_contracted", "facility_uncontracted"}:
        raw_keys["provider_type"] = None
    raw_gate = _raw_header_gate(raw_keys, header)
    if raw_gate is not None:
        return raw_gate
    if condition.get("care_setting") == "emergency":
        # Legacy care_setting represents inpatient/outpatient while emergency
        # evidence is a separate flag. Its scalar nonmatch is not proof that
        # either emergency-specific authored rule is inapplicable.
        return (
            "unavailable",
            [],
            "emergency_care_setting_not_derived",
        )
    if "facility_tier" in keys and not (header.facility_tier or "").strip():
        return "missing_inputs", ["facility_tier"], "raw facility tier is absent"
    if keys & {"facility_type", "facility_tier_basamak"}:
        if not (header.provider_type or "").strip() and not (header.facility_tier or "").strip():
            return (
                "missing_inputs",
                ["provider_type", "facility_tier"],
                "facility evidence is absent",
            )
    if keys & {"facility_contracted", "facility_uncontracted", "provider_contract_status"}:
        if header.provider_type not in {
            "sozlesmeli",
            "contracted",
            "sozlesmesiz",
            "uncontracted",
        }:
            return (
                "unavailable",
                [],
                "provider contracting status is not established by this provider type",
            )
    if "is_emergency" in keys and flat.get("is_emergency") is False:
        return (
            "unavailable",
            [],
            "absence of an emergency tag does not establish non-emergency care",
        )
    if "health_report_present" in keys:
        flags = [line.drug_specialty_board_report_present for line in claim_ctx.drug_lines]
        if not any(flag is True for flag in flags) and (
            not flags or any(flag is None for flag in flags)
        ):
            return (
                "missing_inputs",
                ["drug_specialty_board_report_present"],
                "health report evidence is incomplete",
            )
    return None


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
        raise ValueError("Gap-closing context belongs to another patient")
    claim_ids = {claim.claim_id for claim in ctx.claims}
    if len(claim_ids) != len(ctx.claims):
        raise ValueError("Duplicate gap-closing claim header")
    if any(row.claim_id not in claim_ids for rows in groups[1:] for row in rows):
        raise ValueError("Gap-closing lines include a foreign claim")


def evaluate_gap_closing(
    patient_id: str,
    ctx: PatientClaimContext | None,
) -> GapClosingBatch:
    """Evaluate all 89 authored rules once at each real claim scope.

    ``legacy_rows`` preserves every original match and payload even if a raw
    input gate prevents a typed candidate. A downstream consumer must reuse
    these rows rather than run the two legacy wrappers again.
    """
    sources = _gap_catalog_sources()
    rulesets = (load_gap_closing_misc_rules(), load_gap_closing_treatment_rules())
    for ruleset, family in zip(rulesets, _FAMILY_COUNTS, strict=True):
        rules = ruleset["rules"]
        expected = {rid for rid, source in sources.items() if source.family == family}
        if (
            ruleset["rule_set_id"] != family
            or len(rules) != _FAMILY_COUNTS[family]
            or {r["rule_id"] for r in rules} != expected
        ):
            raise ValueError("Gap-closing corpus differs from the authored catalog")
        if any(
            rule["action"].get("billable") is not sources[rule["rule_id"]].billable
            for rule in rules
        ):
            raise ValueError("Gap-closing authored classification changed")

    if ctx is not None:
        _validate_ownership(patient_id, ctx)
    if ctx is None or not ctx.claims:
        return GapClosingBatch(
            evaluations=tuple(
                RuleEvaluation(
                    patient_id=patient_id,
                    claim_id=None,
                    rule_id=rule["rule_id"],
                    evaluation_status="missing_inputs",
                    required_inputs=list(rule["condition"]),
                    missing_inputs=["claim_context" if ctx is None else "claim_headers"],
                    reason="claim context is unavailable",
                )
                for ruleset in rulesets
                for rule in ruleset["rules"]
            )
        )

    evaluations: list[RuleEvaluation] = []
    matches: list[GapClosingMatch] = []
    legacy_rows: list[LegacyGapClosingRow] = []
    for claim_id in sorted(claim.claim_id for claim in ctx.claims):
        claim_ctx = ctx.slice_for_claim(claim_id)
        if claim_ctx is None:
            raise ValueError(f"Claim disappeared from gap-closing context: {claim_id}")
        flat = _build_gap_closing_context(claim_ctx)
        for ruleset in rulesets:
            family = ruleset["rule_set_id"]
            for rule in ruleset["rules"]:
                rule_id = rule["rule_id"]
                condition = rule["condition"]
                predicate_decision, missing, reason = _evaluate_condition(condition, flat)
                decision = predicate_decision
                gate = _metadata_gate(condition, claim_ctx, flat)
                if gate is not None:
                    decision, missing, reason = gate
                status = (
                    "evaluated"
                    if decision in {"matched", "not_matched"}
                    else "missing_inputs"
                    if decision == "missing_inputs"
                    else "unavailable"
                )
                evaluations.append(
                    RuleEvaluation(
                        patient_id=patient_id,
                        claim_id=claim_id,
                        rule_id=rule_id,
                        evaluation_status=status,
                        required_inputs=list(condition),
                        missing_inputs=list(dict.fromkeys(missing)),
                        decision=decision if status == "evaluated" else None,
                        reason=reason,
                    )
                )
                if predicate_decision == "matched":
                    raw_row = _violation_from_rule(rule, family)
                    legacy_rows.append(
                        LegacyGapClosingRow(patient_id, claim_id, rule_id, family, raw_row)
                    )
                if decision == "matched":
                    source = sources[rule_id]
                    matches.append(
                        GapClosingMatch(
                            patient_id=patient_id,
                            claim_id=claim_id,
                            rule_id=rule_id,
                            family=family,
                            source_file=source.source_file,
                            source_locators=source.source_locators,
                            authored_action=deepcopy(rule["action"]),
                            billable=source.billable,
                            candidate_classification=source.candidate_classification,
                            legacy_row=deepcopy(raw_row),
                        )
                    )
    return GapClosingBatch(tuple(evaluations), tuple(matches), tuple(legacy_rows))

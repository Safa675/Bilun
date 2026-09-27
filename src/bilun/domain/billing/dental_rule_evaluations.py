"""Material-scoped metadata for the 19 authored dental rules.

The original first winner and raw monetary payload remain unchanged. Typed
candidates retain source/line identity without confirming payment, violation,
or risk, particularly when an optional board flag was defaulted by legacy code.
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
from src.bilun.domain.prose_rules.dental_2_4_1 import (
    _build_dental_materials,
    _condition_matches,
    _violation_from_rule,
    load_dental_2_4_1_rules,
)

_FAMILY = "dental_2_4_1"
_RULE_COUNT = 19
_EXPLICIT_SHAPES = {
    "material_name_any",
    "procedure_category",
    "procedure_category_any",
    "facility_type",
    "facility_type_any",
}


@dataclass(frozen=True)
class _CatalogSource:
    source_file: str
    source_locators: tuple[str, ...]
    billable: bool | None
    candidate_classification: CandidateClassification


@dataclass(frozen=True)
class DentalRuleMatch:
    patient_id: str
    claim_id: str
    material_line_id: str
    rule_id: str
    family: str
    source_file: str
    source_locators: tuple[str, ...]
    authored_action: dict[str, Any]
    billable: bool | None
    candidate_classification: CandidateClassification
    legacy_row: dict[str, Any]


@dataclass(frozen=True)
class LegacyDentalRuleRow:
    patient_id: str
    claim_id: str
    material_line_id: str
    rule_id: str
    family: str
    legacy_row: dict[str, Any]


@dataclass(frozen=True)
class DentalRuleBatch:
    evaluations: tuple[RuleEvaluation, ...] = ()
    matches: tuple[DentalRuleMatch, ...] = ()
    legacy_rows: tuple[LegacyDentalRuleRow, ...] = ()


@lru_cache(maxsize=1)
def _dental_catalog_sources() -> Mapping[str, _CatalogSource]:
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
        raise ValueError("Dental context belongs to another patient")
    claim_ids = {row.claim_id for row in ctx.claims}
    if len(claim_ids) != len(ctx.claims):
        raise ValueError("Duplicate dental claim header")
    if any(row.claim_id not in claim_ids for rows in groups[1:] for row in rows):
        raise ValueError("Dental lines include a foreign claim")
    for rows, field in (
        (ctx.material_lines, "material_line_id"),
        (ctx.procedure_lines, "procedure_line_id"),
    ):
        identities = [(row.claim_id, getattr(row, field)) for row in rows]
        if any(not line_id.strip() for _, line_id in identities) or len(set(identities)) != len(
            identities
        ):
            raise ValueError(f"Ambiguous dental source identity: {field}")


def _metadata_gate(
    condition: dict[str, Any],
    mat: dict[str, Any],
) -> tuple[str, list[str], str] | None:
    """Qualify source inputs without reimplementing the original predicate."""
    missing: list[str] = []
    unsupported: list[str] = []
    facility_unavailable = False
    for key, expected in condition.items():
        if key == "material_name_any":
            if not str(mat.get("name") or mat.get("material_name") or "").strip():
                missing.append("material_name")
        elif key in {"procedure_category", "procedure_category_any"}:
            if not mat.get("procedure_category"):
                missing.append("procedure_category")
        elif key in {"facility_type", "facility_type_any"}:
            if not mat.get("facility_type"):
                facility_unavailable = True
        elif key == "material_contains_precious_metal" and mat.get(key) is None:
            # The existing name predicate supplies this redundant flag's
            # evidence. Its absent False default cannot create a positive
            # precious-metal match; a missing name is handled separately.
            if not str(mat.get("name") or mat.get("material_name") or "").strip():
                missing.append("material_name")
        elif mat.get(key) is None:
            # In particular, optional board/kinship/signatory None remains
            # unknown here, although the raw legacy matcher defaults False.
            missing.append(key)
        elif key not in _EXPLICIT_SHAPES and type(expected) is not bool:
            # Legacy truthiness is not an age/range/board-composition test.
            unsupported.append(key)
    if missing:
        return "missing_inputs", list(dict.fromkeys(missing)), "required_dental_inputs_missing"
    if unsupported:
        return "unavailable", [], "dental_predicate_shape_not_supported"
    if facility_unavailable:
        return "unavailable", [], "facility_type_not_derived"
    return None


def _missing_evaluations(
    patient_id: str,
    claim_id: str | None,
    rules: list[dict[str, Any]],
    missing: str,
) -> list[RuleEvaluation]:
    return [
        RuleEvaluation(
            patient_id=patient_id,
            claim_id=claim_id,
            rule_id=rule["rule_id"],
            evaluation_status="missing_inputs",
            required_inputs=list(dict.fromkeys(list(rule["condition"]) + [missing])),
            missing_inputs=[missing],
            reason="dental_source_context_unavailable",
        )
        for rule in rules
    ]


def evaluate_dental_rules(
    patient_id: str,
    ctx: PatientClaimContext | None,
) -> DentalRuleBatch:
    """Observe each material's legacy first winner without changing its order.

    Zip exact builder rows with actual claim material lines before evaluating.
    Reuse the resulting rows in downstream reports; do not invoke the original
    wrapper again or recover line identity from a possibly repeated name.

    Legacy parity is with each claim-scoped wrapper call. Calling the direct
    legacy wrapper on an entire patient instead reuses its first claim header
    for every material; that separate direct-call behavior is unchanged.
    """
    sources = _dental_catalog_sources()
    ruleset = load_dental_2_4_1_rules()
    rules = ruleset["rules"]
    if (
        ruleset["rule_set_id"] != _FAMILY
        or len(rules) != _RULE_COUNT
        or {r["rule_id"] for r in rules} != set(sources)
    ):
        raise ValueError("Dental corpus differs from the authored catalog")
    if any(r["action"].get("billable") is not sources[r["rule_id"]].billable for r in rules):
        raise ValueError("Dental authored classification changed")
    if ctx is not None:
        _validate_ownership(patient_id, ctx)
    if ctx is None or not ctx.claims:
        return DentalRuleBatch(
            evaluations=tuple(
                _missing_evaluations(
                    patient_id, None, rules, "claim_context" if ctx is None else "claim_headers"
                )
            )
        )

    rows_by_identity: dict[tuple[str, str], dict[str, Any]] = {}
    empty_claim_ids: list[str] = []
    for header in ctx.claims:
        claim_ctx = ctx.slice_for_claim(header.claim_id)
        if claim_ctx is None:
            raise ValueError(f"Claim disappeared from dental context: {header.claim_id}")
        if not claim_ctx.material_lines:
            empty_claim_ids.append(header.claim_id)
        built = _build_dental_materials(claim_ctx)
        for line, mat in zip(claim_ctx.material_lines, built, strict=True):
            rows_by_identity[line.claim_id, line.material_line_id] = mat

    evaluations: list[RuleEvaluation] = []
    matches: list[DentalRuleMatch] = []
    legacy_rows: list[LegacyDentalRuleRow] = []
    for line in ctx.material_lines:
        mat = rows_by_identity[line.claim_id, line.material_line_id]
        winner: str | None = None
        for rule in rules:
            rule_id = rule["rule_id"]
            condition = rule["condition"]
            if winner is not None:
                evaluations.append(
                    RuleEvaluation(
                        patient_id=patient_id,
                        claim_id=line.claim_id,
                        rule_id=rule_id,
                        line_kind="material",
                        line_id=line.material_line_id,
                        evaluation_status="unavailable",
                        required_inputs=list(condition),
                        missing_inputs=[],
                        decision="suppressed_by_prior_match",
                        reason=f"prior_rule:{winner}",
                    )
                )
                continue
            matched = _condition_matches(condition, mat)
            gate = _metadata_gate(condition, mat)
            if gate is not None:
                status, missing, reason = gate
                decision = None
            else:
                status, missing, reason = "evaluated", [], None
                decision = "matched" if matched else "not_matched"
            evaluations.append(
                RuleEvaluation(
                    patient_id=patient_id,
                    claim_id=line.claim_id,
                    rule_id=rule_id,
                    line_kind="material",
                    line_id=line.material_line_id,
                    evaluation_status=status,
                    required_inputs=list(dict.fromkeys(list(condition) + missing)),
                    missing_inputs=missing,
                    decision=decision,
                    reason=reason,
                )
            )
            if matched:
                winner = rule_id
                raw = _violation_from_rule(rule, mat)
                legacy_rows.append(
                    LegacyDentalRuleRow(
                        patient_id, line.claim_id, line.material_line_id, rule_id, _FAMILY, raw
                    )
                )
                if decision == "matched":
                    source = sources[rule_id]
                    matches.append(
                        DentalRuleMatch(
                            patient_id=patient_id,
                            claim_id=line.claim_id,
                            material_line_id=line.material_line_id,
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
    for claim_id in empty_claim_ids:
        evaluations.extend(_missing_evaluations(patient_id, claim_id, rules, "material_lines"))
    return DentalRuleBatch(tuple(evaluations), tuple(matches), tuple(legacy_rows))

"""Claim-scoped observations of the separate SGK Fatura İnceleme guideline.

The 91 authored rows are not SUT rules. Their raw matches retain legacy output;
typed matches are review-only candidates, with SUT taking precedence and no
confirmed violation, entitlement, or monetary amount inferred from a match.
A rule whose condition names no billed evidence (only its branch and care
setting, EI-24) is ``unavailable`` with the reason
``authored_condition_names_no_billed_evidence`` wherever its branch and
setting match, and has no raw row; outside them it stays ``not_matched``.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
from typing import Any, Literal

from src.bilun.domain.billing.broad_rule_catalog import (
    CandidateClassification,
    load_broad_rule_catalog,
)
from src.bilun.domain.billing.gap_closing_evaluations import _metadata_gate as _claim_input_gate
from src.bilun.domain.billing.payment_traceability_evaluations import _evaluate_condition
from src.bilun.domain.billing.rule_findings import RuleEvaluation
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.fatura_inceleme import (
    _BRANCH_KEYWORDS,
    _branch_matches,
    _build_fatura_inceleme_context,
    _names_billed_evidence,
    _violation_from_rule,
    load_fatura_inceleme_rules,
)

_FAMILY = "fatura_inceleme_prose"
_RULE_COUNT = 91


@dataclass(frozen=True)
class _CatalogSource:
    source_file: str
    source_locators: tuple[str, ...]
    fatura_inceleme_ref: str
    billable: bool | None
    candidate_classification: CandidateClassification


@dataclass(frozen=True)
class FaturaIncelemeMatch:
    patient_id: str
    claim_id: str
    rule_id: str
    family: str
    source_file: str
    source_locators: tuple[str, ...]
    fatura_inceleme_ref: str
    authored_action: dict[str, Any]
    billable: bool | None
    candidate_classification: CandidateClassification
    legacy_row: dict[str, Any]
    outcome: Literal["review_only"] = "review_only"
    source_authority: Literal["sgk_fatura_inceleme_guideline"] = "sgk_fatura_inceleme_guideline"
    requires_source_review: Literal[True] = True
    sut_takes_precedence: Literal[True] = True


@dataclass(frozen=True)
class LegacyFaturaIncelemeRow:
    patient_id: str
    claim_id: str
    rule_id: str
    family: str
    legacy_row: dict[str, Any]


@dataclass(frozen=True)
class FaturaIncelemeBatch:
    evaluations: tuple[RuleEvaluation, ...] = ()
    matches: tuple[FaturaIncelemeMatch, ...] = ()
    legacy_rows: tuple[LegacyFaturaIncelemeRow, ...] = ()


@lru_cache(maxsize=1)
def _fatura_catalog_sources() -> Mapping[str, _CatalogSource]:
    sources: dict[str, _CatalogSource] = {}
    for row in load_broad_rule_catalog():
        if row.family != _FAMILY:
            continue
        if not row.fatura_inceleme_ref or any(
            not ref.startswith("F") for ref in row.source_locators
        ):
            raise ValueError("Fatura source must retain its own guideline authority")
        sources[row.rule_id] = _CatalogSource(
            row.source_file,
            row.source_locators,
            row.fatura_inceleme_ref,
            row.billable,
            row.candidate_classification,
        )
    return MappingProxyType(sources)


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
        raise ValueError("Fatura context belongs to another patient")
    claim_ids = {row.claim_id for row in ctx.claims}
    if len(claim_ids) != len(ctx.claims):
        raise ValueError("Duplicate Fatura claim header")
    if any(row.claim_id not in claim_ids for rows in groups[1:] for row in rows):
        raise ValueError("Fatura lines include a foreign claim")


def _branch_input_gate(
    branch: str | None,
    flat: dict[str, Any],
    branch_matched: bool,
    claim_ctx: PatientClaimContext,
    department_branches: frozenset[str],
) -> tuple[str, list[str], str] | None:
    if branch is None:
        return None  # ORTAK is deliberately independent of department.
    if branch not in _BRANCH_KEYWORDS:
        return "unavailable", [], "authored_branch_unrecognized"
    department = str(flat.get("department") or "").strip().lower()
    specialty = str(flat.get("provider_specialty") or "").strip().lower()
    if not department and not specialty:
        return "missing_inputs", ["department", "procedure_specialty_code"], "branch_inputs_missing"
    department_matches = branch in department_branches
    if department_matches and len(department_branches) > 1:
        return "unavailable", [], "branch_keyword_overlap_unresolved"
    if branch_matched and not department_matches:
        # Preserve the legacy first-procedure match, but it is not an
        # authoritative claim-wide branch signal (and may vary by line order).
        return "unavailable", [], "first_procedure_specialty_proxy"
    if not department_matches and any(
        kw in str(line.procedure_specialty_code or "").lower()
        for line in claim_ctx.procedure_lines
        for kw in _BRANCH_KEYWORDS[branch]
    ):
        # A later line can carry the relevant specialty even though the
        # legacy first-line bridge missed it. Do not manufacture a match or
        # certify a negative that depends on procedure encounter order.
        return "unavailable", [], "procedure_specialty_branch_uncertain"
    if not branch_matched and not department_branches:
        return "unavailable", [], "branch_evidence_unrecognized"
    return None


def _metadata_gate(
    rule: dict[str, Any],
    claim_ctx: PatientClaimContext,
    flat: dict[str, Any],
    predicate_decision: str,
) -> tuple[str, list[str], str] | None:
    condition = rule["condition"]
    # This legacy bridge has not received gap_closing's yatarak correction.
    # Do not certify a raw Turkish setting as an evaluated inpatient decision.
    if set(condition) & {"care_setting", "payment_method", "payment_method_path"}:
        raw_type = str(claim_ctx.claims[0].claim_type or "").strip().lower()
        if "yatarak" in raw_type and flat.get("care_setting") != "inpatient":
            return "unavailable", [], "care_setting_normalization_unavailable"
    gate = _claim_input_gate(condition, claim_ctx, flat)
    if gate is not None:
        return gate
    if predicate_decision == "matched":
        # The branch and the setting match every bill of the department; no
        # billed line says the guideline's case happened (EI-24).
        if not _names_billed_evidence(condition):
            return "unavailable", [], "authored_condition_names_no_billed_evidence"
        # Official guideline ORTAK-10 requires the diagnosis condition;
        # ORTAK-16 requires evidence of actual IV-drug use. The authored
        # predicates omit those decisive facts. Keep their raw rows only.
        if rule["rule_id"] == "ORTAK-10.sunnet_z412":
            return "unavailable", [], "guideline_diagnosis_condition_not_evaluated"
        if rule["rule_id"] == "ORTAK-16.iv_infuzyon_530160":
            return "unavailable", ["iv_infusion_drug_use"], "iv_drug_use_not_derived"
    return None


def _required_inputs(rule: dict[str, Any]) -> list[str]:
    branch_inputs = ["department", "procedure_specialty_code"] if rule.get("branch") else []
    source_inputs = {
        "ORTAK-10.sunnet_z412": ["diagnosis_z41_2"],
        "ORTAK-16.iv_infuzyon_530160": ["iv_infusion_drug_use"],
    }.get(rule["rule_id"], [])
    return branch_inputs + list(rule["condition"]) + source_inputs


def evaluate_fatura_inceleme(
    patient_id: str,
    ctx: PatientClaimContext | None,
) -> FaturaIncelemeBatch:
    """Observe all 91 rules per claim, preserving exact legacy claim payloads.

    Each original branch decision runs once; only matched branches enter the
    shared original condition observer. No patient/cohort/report consumer
    should rerun the legacy wrapper after this batch has been calculated.
    """
    sources = _fatura_catalog_sources()
    ruleset = load_fatura_inceleme_rules()
    rules = ruleset["rules"]
    if (
        ruleset["rule_set_id"] != _FAMILY
        or len(rules) != _RULE_COUNT
        or {rule["rule_id"] for rule in rules} != set(sources)
    ):
        raise ValueError("Fatura corpus differs from the authored catalog")
    if any(
        rule["action"].get("billable") is not sources[rule["rule_id"]].billable for rule in rules
    ):
        raise ValueError("Fatura authored classification changed")
    if ctx is not None:
        _validate_ownership(patient_id, ctx)
    if ctx is None or not ctx.claims:
        return FaturaIncelemeBatch(
            evaluations=tuple(
                RuleEvaluation(
                    patient_id=patient_id,
                    claim_id=None,
                    rule_id=rule["rule_id"],
                    evaluation_status="missing_inputs",
                    required_inputs=_required_inputs(rule)
                    + ["claim_context" if ctx is None else "claim_headers"],
                    missing_inputs=["claim_context" if ctx is None else "claim_headers"],
                    reason="claim_context_unavailable",
                )
                for rule in rules
            )
        )

    evaluations: list[RuleEvaluation] = []
    matches: list[FaturaIncelemeMatch] = []
    legacy_rows: list[LegacyFaturaIncelemeRow] = []
    for claim_id in sorted(row.claim_id for row in ctx.claims):
        claim_ctx = ctx.slice_for_claim(claim_id)
        if claim_ctx is None:
            raise ValueError(f"Claim disappeared from Fatura context: {claim_id}")
        flat = _build_fatura_inceleme_context(claim_ctx)
        department = str(flat.get("department") or "").strip().lower()
        department_branches = frozenset(
            branch
            for branch, keywords in _BRANCH_KEYWORDS.items()
            if any(keyword in department for keyword in keywords)
        )
        for rule in rules:
            rule_id = rule["rule_id"]
            branch_matched = _branch_matches(rule.get("branch"), flat)
            predicate_decision, missing, reason = (
                _evaluate_condition(rule["condition"], flat)
                if branch_matched
                else ("not_matched", [], "branch_not_matched")
            )
            decision = predicate_decision
            gate = _branch_input_gate(
                rule.get("branch"), flat, branch_matched, claim_ctx, department_branches
            )
            if gate is None and branch_matched:
                gate = _metadata_gate(rule, claim_ctx, flat, predicate_decision)
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
                    required_inputs=list(dict.fromkeys(_required_inputs(rule) + missing)),
                    missing_inputs=missing,
                    decision=decision if status == "evaluated" else None,
                    reason=reason,
                )
            )
            # The legacy matcher gives no row for a rule naming no billed evidence.
            if predicate_decision == "matched" and _names_billed_evidence(rule["condition"]):
                raw = _violation_from_rule(rule, _FAMILY)
                legacy_rows.append(
                    LegacyFaturaIncelemeRow(patient_id, claim_id, rule_id, _FAMILY, raw)
                )
                if decision == "matched":
                    source = sources[rule_id]
                    matches.append(
                        FaturaIncelemeMatch(
                            patient_id=patient_id,
                            claim_id=claim_id,
                            rule_id=rule_id,
                            family=_FAMILY,
                            source_file=source.source_file,
                            source_locators=source.source_locators,
                            fatura_inceleme_ref=source.fatura_inceleme_ref,
                            authored_action=deepcopy(rule["action"]),
                            billable=source.billable,
                            candidate_classification=source.candidate_classification,
                            legacy_row=deepcopy(raw),
                        )
                    )
    return FaturaIncelemeBatch(tuple(evaluations), tuple(matches), tuple(legacy_rows))

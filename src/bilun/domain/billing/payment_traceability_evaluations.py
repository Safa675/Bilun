"""Claim-scoped evaluation metadata for the 42 payment-method prose rows.

The existing traceability matcher remains the authority for each predicate.
These results are information only: even a matched authored ``billable=false``
row cannot become a confirmed compliance finding or monetary adjustment here.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
from typing import Any, Literal

from src.bilun.domain.billing.broad_rule_catalog import load_broad_rule_catalog
from src.bilun.domain.billing.rule_findings import RuleEvaluation
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.payment_method import (
    _build_payment_method_traceability_context,
    _gap_closing_condition_matches,
    _traceability_violation_from_rule,
    load_payment_method_rules,
)


class _ObservedContext(dict[str, Any]):
    """Record the inputs the existing predicate actually reads, including fallbacks."""

    def __init__(self, values: dict[str, Any]) -> None:
        super().__init__(values)
        self.reads: list[tuple[str, Any]] = []

    def get(self, key: str, default: Any = None) -> Any:
        value = super().get(key, default)
        self.reads.append((key, value))
        return value


@dataclass(frozen=True)
class PaymentTraceabilityMatch:
    patient_id: str
    claim_id: str
    rule_id: str
    source_file: str
    source_locators: tuple[str, ...]
    legacy_row: dict[str, Any]
    candidate_classification: Literal["information_only"] = "information_only"


@dataclass(frozen=True)
class LegacyPaymentTraceabilityRow:
    """Raw legacy match retained even when its derived facts are not certified."""

    patient_id: str
    claim_id: str
    rule_id: str
    legacy_row: dict[str, Any]


@dataclass(frozen=True)
class PaymentTraceabilityBatch:
    evaluations: tuple[RuleEvaluation, ...] = ()
    matches: tuple[PaymentTraceabilityMatch, ...] = ()
    legacy_rows: tuple[LegacyPaymentTraceabilityRow, ...] = ()


@lru_cache(maxsize=1)
def _payment_catalog_sources() -> Mapping[str, tuple[str, tuple[str, ...]]]:
    """Validate the full corpus once, then retain only immutable payment sources."""
    return MappingProxyType(
        {
            entry.rule_id: (entry.source_file, entry.source_locators)
            for entry in load_broad_rule_catalog()
            if entry.family == "payment_method_2_2"
        }
    )


def _evaluate_condition(
    condition: dict[str, Any], flat_context: dict[str, Any]
) -> tuple[str, list[str], str | None]:
    """Use the legacy predicate in authored order, preserving its short circuit.

    The read trace distinguishes its genuine missing-input branches from known
    mismatches and unsupported shapes. Annex membership returns False for both
    a nonmember and an unavailable catalog, so a failed annex lookup with
    billed codes stays unavailable rather than claiming a clean nonmatch.
    """
    for key, expected in condition.items():
        observed = _ObservedContext(flat_context)
        if _gap_closing_condition_matches({key: expected}, observed):
            continue

        if not observed.reads:
            return "unavailable", [], f"unsupported predicate: {key}"
        if key == "procedure_in_annex":
            if not any(value for _, value in observed.reads):
                return "missing_inputs", ["procedure_code"], "required predicate inputs are absent"
            return "unavailable", [], f"annex membership not confirmed: {expected}"
        if all(value is None for _, value in observed.reads):
            return "missing_inputs", [key], "required predicate inputs are absent"
        return "not_matched", [], None

    return "matched", [], None


def _raw_header_gate(condition: dict[str, Any], header: Any) -> tuple[str, list[str], str] | None:
    """Reject metadata inferred from the builder's blank/unknown header defaults."""
    missing: list[str] = []
    if any(key in condition for key in ("provider_type", "provider_contract_status")):
        if not str(getattr(header, "provider_type", "") or "").strip():
            missing.append("provider_type")

    if "care_setting" in condition:
        claim_type = str(getattr(header, "claim_type", "") or "").strip().lower()
        if not claim_type:
            missing.append("claim_type")
        elif not any(
            token in claim_type
            for token in ("yatis", "inpatient", "ayakta", "outpatient", "poliklinik", "gunubirlik")
        ):
            return "unavailable", missing, f"unrecognized claim_type: {claim_type}"

    if missing:
        return "missing_inputs", missing, "raw claim header inputs are absent"
    return None


def evaluate_payment_method_traceability(
    patient_id: str, ctx: PatientClaimContext | None
) -> PaymentTraceabilityBatch:
    """Evaluate every payment row for every real claim, without finding promotion."""
    ruleset = load_payment_method_rules()
    rules = ruleset["rules"]
    catalog = _payment_catalog_sources()
    if len(rules) != 42 or {rule["rule_id"] for rule in rules} != set(catalog):
        raise ValueError("Payment traceability corpus differs from the authored catalog")

    if ctx is not None:
        rows_by_source = (
            ctx.claims,
            ctx.procedure_lines,
            ctx.material_lines,
            ctx.drug_lines,
            ctx.diagnoses,
            ctx.performed_procedure_lines,
            ctx.medula_rejection_events,
        )
        if ctx.patient_id != patient_id or any(
            row.patient_id != patient_id for rows in rows_by_source for row in rows
        ):
            raise ValueError("Payment traceability context belongs to another patient")
        if len({claim.claim_id for claim in ctx.claims}) != len(ctx.claims):
            raise ValueError("Duplicate payment traceability claim header")
        claim_ids = {claim.claim_id for claim in ctx.claims}
        if claim_ids and any(
            row.claim_id not in claim_ids for rows in rows_by_source[1:] for row in rows
        ):
            raise ValueError("Payment traceability lines include a foreign claim")
    if ctx is None or not ctx.claims:
        missing = "claim_context" if ctx is None else "claim_headers"
        return PaymentTraceabilityBatch(
            evaluations=tuple(
                RuleEvaluation(
                    patient_id=patient_id,
                    claim_id=None,
                    rule_id=rule["rule_id"],
                    evaluation_status="missing_inputs",
                    required_inputs=list(rule["condition"]),
                    missing_inputs=[missing],
                    reason="claim context is unavailable",
                )
                for rule in rules
            )
        )

    evaluations: list[RuleEvaluation] = []
    matches: list[PaymentTraceabilityMatch] = []
    legacy_rows: list[LegacyPaymentTraceabilityRow] = []
    for claim_id in sorted({claim.claim_id for claim in ctx.claims}):
        claim_ctx = ctx.slice_for_claim(claim_id)
        if claim_ctx is None:
            raise ValueError(f"Claim disappeared from payment context: {claim_id}")
        flat_context = _build_payment_method_traceability_context(claim_ctx)
        header = claim_ctx.claims[0]
        for rule in rules:
            rule_id = rule["rule_id"]
            condition = rule["condition"]
            predicate_decision, missing, reason = _evaluate_condition(condition, flat_context)
            raw_gate = _raw_header_gate(condition, header)
            decision = predicate_decision
            if raw_gate is not None:
                decision, missing, reason = raw_gate
            status = (
                "evaluated"
                if decision in ("matched", "not_matched")
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
                raw_row = _traceability_violation_from_rule(rule, ruleset["rule_set_id"])
                legacy_rows.append(
                    LegacyPaymentTraceabilityRow(patient_id, claim_id, rule_id, raw_row)
                )
            if decision == "matched":
                source_file, source_locators = catalog[rule_id]
                matches.append(
                    PaymentTraceabilityMatch(
                        patient_id=patient_id,
                        claim_id=claim_id,
                        rule_id=rule_id,
                        source_file=source_file,
                        source_locators=source_locators,
                        legacy_row=deepcopy(raw_row),
                    )
                )

    return PaymentTraceabilityBatch(tuple(evaluations), tuple(matches), tuple(legacy_rows))

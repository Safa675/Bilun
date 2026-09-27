"""Materialize all seven authored prose families once, without classifying them.

The six adapters already own their original predicates and raw output. This
bundle only checks their shared scope/identity contract and keeps the raw rows
available at the historical engine positions. A consumer must not run a prose
wrapper again after receiving this bundle.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from types import MappingProxyType
from typing import Any

from src.bilun.domain.billing.broad_rule_catalog import load_broad_rule_catalog
from src.bilun.domain.billing.dental_rule_evaluations import evaluate_dental_rules
from src.bilun.domain.billing.drug_combination_evaluations import evaluate_drug_combinations
from src.bilun.domain.billing.fatura_inceleme_evaluations import evaluate_fatura_inceleme
from src.bilun.domain.billing.gap_closing_evaluations import evaluate_gap_closing
from src.bilun.domain.billing.payment_traceability_evaluations import (
    evaluate_payment_method_traceability,
)
from src.bilun.domain.billing.rule_findings import RuleEvaluation, build_evaluation_id
from src.bilun.domain.billing.treatment_pricing_evaluations import evaluate_treatment_pricing
from src.bilun.domain.claims.patient_context import PatientClaimContext


BROAD_FAMILY_ORDER = (
    "dental_2_4_1",
    "gap_closing_misc",
    "gap_closing_treatment_2",
    "fatura_inceleme_prose",
    "payment_method_2_2",
    "drug_combination_4_2",
    "treatment_pricing_2_4",
)
_DENTAL_FAMILY = "dental_2_4_1"


@lru_cache(maxsize=1)
def _authored_ids() -> Mapping[str, frozenset[str]]:
    """Freeze the validated source roster for this process/build boundary."""
    by_family: dict[str, set[str]] = defaultdict(set)
    for entry in load_broad_rule_catalog():
        by_family[entry.family].add(entry.rule_id)
    if set(by_family) != set(BROAD_FAMILY_ORDER) or sum(map(len, by_family.values())) != 496:
        raise ValueError("Broad authored family roster differs from the reviewed inventory")
    return MappingProxyType({family: frozenset(by_family[family]) for family in BROAD_FAMILY_ORDER})


def _validate_context(patient_id: str, ctx: PatientClaimContext | None) -> None:
    if not patient_id.strip():
        raise ValueError("Broad materialization requires a real patient ID")
    if ctx is None:
        return
    if ctx.patient_id != patient_id:
        raise ValueError("Broad materialization context belongs to another patient")
    claims = {claim.claim_id for claim in ctx.claims}
    if len(claims) != len(ctx.claims) or any(not value.strip() for value in claims):
        raise ValueError("Broad materialization has duplicate or blank claim IDs")
    for rows in (
        ctx.claims,
        ctx.procedure_lines,
        ctx.material_lines,
        ctx.drug_lines,
        ctx.diagnoses,
        ctx.performed_procedure_lines,
        ctx.medula_rejection_events,
    ):
        for row in rows:
            if row.patient_id != patient_id or row.claim_id not in claims:
                raise ValueError("Broad materialization has foreign or orphan source rows")
    for rows, identity_field in (
        (ctx.procedure_lines, "procedure_line_id"),
        (ctx.material_lines, "material_line_id"),
        (ctx.drug_lines, "drug_claim_line_id"),
        (ctx.diagnoses, "diagnosis_id"),
        (ctx.performed_procedure_lines, "performed_line_id"),
        (ctx.medula_rejection_events, "rejection_event_id"),
    ):
        identities = [(row.claim_id, getattr(row, identity_field)) for row in rows]
        if any(not value.strip() for _, value in identities) or len(set(identities)) != len(
            identities
        ):
            raise ValueError(f"Broad materialization has ambiguous {identity_field}")


def _legacy_identity(patient_id: str, family: str, row: Any) -> str:
    if (
        getattr(row, "patient_id", None) != patient_id
        or getattr(row, "family", family) != family
        or not isinstance(getattr(row, "claim_id", None), str)
        or not isinstance(getattr(row, "rule_id", None), str)
        or not isinstance(getattr(row, "legacy_row", None), dict)
        or row.legacy_row.get("rule_id") != row.rule_id
    ):
        raise ValueError("Broad raw row has foreign or malformed identity")
    material_id = getattr(row, "material_line_id", None) if family == _DENTAL_FAMILY else None
    return build_evaluation_id(
        rule_id=row.rule_id,
        patient_id=patient_id,
        claim_id=row.claim_id,
        line_kind="material" if family == _DENTAL_FAMILY else "claim",
        line_id=material_id,
    )


@dataclass(frozen=True)
class BroadMaterialized:
    patient_id: str
    evaluations: tuple[RuleEvaluation, ...]
    _legacy_rows_by_family: Mapping[str, tuple[Any, ...]] = field(repr=False)
    _matches_by_family: Mapping[str, tuple[Any, ...]] = field(repr=False)
    _evaluation_by_id: Mapping[str, RuleEvaluation] = field(repr=False)
    _legacy_by_evaluation_id: Mapping[str, Any] = field(repr=False)

    @property
    def legacy_rows_by_family(self) -> Mapping[str, tuple[Any, ...]]:
        """Ownership-bearing rows copied so callers cannot mutate this bundle."""
        return MappingProxyType(
            {
                family: tuple(deepcopy(row) for row in self._legacy_rows_by_family[family])
                for family in BROAD_FAMILY_ORDER
            }
        )

    @property
    def matches_by_family(self) -> Mapping[str, tuple[Any, ...]]:
        """Typed matches are observational and copied at the API boundary."""
        return MappingProxyType(
            {
                family: tuple(deepcopy(row) for row in self._matches_by_family[family])
                for family in BROAD_FAMILY_ORDER
            }
        )

    def raw_rows(self, family: str) -> tuple[dict[str, Any], ...]:
        """Return exact legacy payloads for one original engine position."""
        if family not in BROAD_FAMILY_ORDER:
            raise KeyError(f"Unknown broad family: {family}")
        return tuple(deepcopy(row.legacy_row) for row in self._legacy_rows_by_family[family])

    def legacy_row_for(self, evaluation: RuleEvaluation) -> Any | None:
        if (
            evaluation.patient_id != self.patient_id
            or self._evaluation_by_id.get(evaluation.evaluation_id) != evaluation
        ):
            raise ValueError("Broad evaluation does not belong to this materialization")
        source = self._legacy_by_evaluation_id.get(evaluation.evaluation_id)
        return deepcopy(source) if source is not None else None


def materialize_broad_rules(
    patient_id: str,
    ctx: PatientClaimContext | None,
) -> BroadMaterialized:
    """Run each existing adapter once and prove exact authored scope coverage."""
    _validate_context(patient_id, ctx)
    authored = _authored_ids()
    dental = evaluate_dental_rules(patient_id, ctx)
    gap = evaluate_gap_closing(patient_id, ctx)
    fatura = evaluate_fatura_inceleme(patient_id, ctx)
    payment = evaluate_payment_method_traceability(patient_id, ctx)
    drug = evaluate_drug_combinations(patient_id, ctx)
    treatment = evaluate_treatment_pricing(patient_id, ctx)
    batches = {
        "dental_2_4_1": dental,
        "gap_closing_misc": gap,
        "gap_closing_treatment_2": gap,
        "fatura_inceleme_prose": fatura,
        "payment_method_2_2": payment,
        "drug_combination_4_2": drug,
        "treatment_pricing_2_4": treatment,
    }
    for batch, allowed_families in (
        (dental, (_DENTAL_FAMILY,)),
        (gap, ("gap_closing_misc", "gap_closing_treatment_2")),
        (fatura, ("fatura_inceleme_prose",)),
        (payment, ("payment_method_2_2",)),
        (drug, ("drug_combination_4_2",)),
        (treatment, ("treatment_pricing_2_4",)),
    ):
        allowed_ids = set().union(*(authored[family] for family in allowed_families))
        for collection in (batch.evaluations, batch.matches, batch.legacy_rows):
            for row in collection:
                if row.rule_id not in allowed_ids or getattr(
                    row, "family", allowed_families[0]
                ) not in allowed_families:
                    raise ValueError("Broad adapter emitted a foreign authored identity")
    evaluations_by_family: dict[str, tuple[RuleEvaluation, ...]] = {}
    raw_by_family: dict[str, tuple[Any, ...]] = {}
    matches_by_family: dict[str, tuple[Any, ...]] = {}
    for family in BROAD_FAMILY_ORDER:
        batch = batches[family]
        evaluations_by_family[family] = tuple(
            item for item in batch.evaluations if item.rule_id in authored[family]
        )
        raw_by_family[family] = tuple(
            item for item in batch.legacy_rows if getattr(item, "family", family) == family
        )
        matches_by_family[family] = tuple(
            item
            for item in batch.matches
            if getattr(item, "family", family) == family
        )
    evaluations = tuple(
        item for family in BROAD_FAMILY_ORDER for item in evaluations_by_family[family]
    )
    _validate_scope_and_identity(patient_id, ctx, authored, evaluations_by_family, raw_by_family)
    raw_by_id: dict[str, Any] = {}
    for family in BROAD_FAMILY_ORDER:
        for row in raw_by_family[family]:
            identity = _legacy_identity(patient_id, family, row)
            if identity in raw_by_id:
                raise ValueError("Duplicate broad raw evaluation identity")
            raw_by_id[identity] = row
    evaluation_by_id = {evaluation.evaluation_id: evaluation for evaluation in evaluations}
    if not raw_by_id.keys() <= evaluation_by_id.keys():
        raise ValueError("Broad raw row lacks a scoped evaluation")
    for identity in raw_by_id:
        evaluated = evaluation_by_id[identity]
        if evaluated.evaluation_status == "evaluated" and evaluated.decision != "matched":
            raise ValueError("Broad raw row contradicts an evaluated negative decision")
    for family in BROAD_FAMILY_ORDER:
        for match in matches_by_family[family]:
            if match.rule_id not in authored[family]:
                raise ValueError("Broad typed match uses a foreign authored family")
            identity = _legacy_identity(patient_id, family, match)
            evaluated = evaluation_by_id.get(identity)
            if (
                evaluated is None
                or evaluated.evaluation_status != "evaluated"
                or evaluated.decision != "matched"
                or identity not in raw_by_id
                or match.legacy_row != raw_by_id[identity].legacy_row
            ):
                raise ValueError("Broad typed match lacks its evaluated raw source")
    return BroadMaterialized(
        patient_id,
        evaluations,
        MappingProxyType(raw_by_family),
        MappingProxyType(matches_by_family),
        MappingProxyType(evaluation_by_id),
        MappingProxyType(raw_by_id),
    )


def _validate_scope_and_identity(
    patient_id: str,
    ctx: PatientClaimContext | None,
    authored: Mapping[str, frozenset[str]],
    evaluations_by_family: Mapping[str, tuple[RuleEvaluation, ...]],
    raw_by_family: Mapping[str, tuple[Any, ...]],
) -> None:
    """Reject missing, duplicate, foreign, or incorrectly scoped authored IDs."""
    claims = {claim.claim_id for claim in ctx.claims} if ctx is not None else set()
    materials: dict[str, set[str]] = {claim_id: set() for claim_id in claims}
    if ctx is not None:
        for line in ctx.material_lines:
            if not line.material_line_id.strip() or line.material_line_id in materials[line.claim_id]:
                raise ValueError("Duplicate or blank broad material source ID")
            materials[line.claim_id].add(line.material_line_id)
    all_ids: set[str] = set()
    for family in BROAD_FAMILY_ORDER:
        rows = evaluations_by_family[family]
        expected: set[tuple[str | None, str | None, str]] = set()
        if not claims:
            expected = {(None, None, rule_id) for rule_id in authored[family]}
        elif family == _DENTAL_FAMILY:
            expected = {
                (claim_id, line_id, rule_id)
                for claim_id in claims
                for line_id in (materials[claim_id] or {None})
                for rule_id in authored[family]
            }
        else:
            expected = {
                (claim_id, None, rule_id)
                for claim_id in claims
                for rule_id in authored[family]
            }
        observed: set[tuple[str | None, str | None, str]] = set()
        for row in rows:
            if row.patient_id != patient_id or row.rule_id not in authored[family]:
                raise ValueError("Broad evaluation belongs to another patient/family")
            key = (row.claim_id, row.line_id, row.rule_id)
            if key in observed or row.evaluation_id in all_ids:
                raise ValueError("Duplicate broad authored evaluation identity")
            observed.add(key)
            all_ids.add(row.evaluation_id)
            expected_line_kind = "material" if family == _DENTAL_FAMILY and row.line_id else "claim"
            if row.line_kind != expected_line_kind:
                raise ValueError("Broad authored evaluation has incorrect line scope")
            if not claims and row.evaluation_status != "missing_inputs":
                raise ValueError("No-header broad evaluation is not missing inputs")
            if family == _DENTAL_FAMILY and claims and row.line_id is None and (
                row.evaluation_status != "missing_inputs" or row.claim_id not in materials
            ):
                raise ValueError("No-material dental evaluation is not missing inputs")
        if observed != expected:
            raise ValueError(f"Broad authored evaluation scope is incomplete: {family}")
        for legacy in raw_by_family[family]:
            if legacy.rule_id not in authored[family]:
                raise ValueError("Broad raw row uses a foreign authored rule")

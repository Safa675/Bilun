"""Full 25-group Wave A evidence producer, still draft until release attestation.

All authored statuses live in the build-scoped detail. Default reports receive
only bounded matched observations, compact group counters, and any separately
proven unpriced findings. Static policy prose is referenced, not duplicated in
each of the 496 broad status rows per claim.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any

from src.bilun.domain.billing.broad_rule_classification import (
    BroadRuleClassifier,
    SourceApplicabilityAttestation,
    load_broad_classification_policy,
)
from src.bilun.domain.billing.broad_rule_materializer import BroadMaterialized
from src.bilun.domain.billing.focused_rule_projection import FocusedProjectionBatch
from src.bilun.domain.billing.focused_rule_projection import FOCUSED_RULE_SPECS
from src.bilun.domain.billing.rule_findings import RuleFinding, build_evaluation_id
from src.bilun.domain.billing.wavea_evidence import (
    DEFAULT_DETAIL_LIMIT,
    WaveAEvidenceBlock,
    _validate_evidence_row_semantics,
    project_focused_evidence,
    validate_wavea_evidence_detail,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext


FULL_EVIDENCE_SCHEMA_VERSION = "wavea-evidence-v2"
FULL_ROSTER_VERSION = "wavea-25-groups-528-rules-v1"
BROAD_POLICY_REF = "broad-classification-reviewed-2026-09-27"
_STATUSES = ("evaluated", "missing_inputs", "unavailable")
_DISPLAY_DISPOSITIONS = frozenset(
    {"review_only", "unavailable", "permission_or_instruction", "information_only"}
)
_FOCUSED_BY_ID = {spec.rule_id: spec for spec in FOCUSED_RULE_SPECS}
_MONEY_FIELDS = frozenset({
    "amount_try", "billed_try", "payable_try", "savings_try", "sgk_uplift_try",
    "recoverable_uplift_try", "compliance_savings_try", "risk_amount_try",
    "audit_exposure_try", "confirmed_amount_try", "expected_ga_fee_try",
    "actual_billed_try", "billed_amount_try", "recoverable_gap_try",
})
_BROAD_SPARSE_COMMON_FIELDS = frozenset({
    "source_evidence_id", "patient_id", "claim_id", "rule_id", "line_kind",
    "line_id", "source_engine", "evaluation_status", "disposition", "reason",
    "source_authority", "source_status", "regulatory_source", "policy_ref",
    "evidence_id", "money_semantics",
})


@dataclass(frozen=True)
class FullWaveAEvidenceProjection:
    claim_reviews: WaveAEvidenceBlock
    claim_advisories: WaveAEvidenceBlock
    financial_findings: WaveAEvidenceBlock
    coverage: dict[str, Any]
    detail: dict[str, Any]
    confirmed_broad_findings: tuple[RuleFinding, ...]


def build_claim_scope_inventory(ctx: PatientClaimContext | None) -> dict[str, Any]:
    """Record the producer's exact claim/material scope for independent audit."""
    if ctx is None:
        return {"context_state": "missing", "claims": []}
    if not ctx.claims:
        if ctx.material_lines:
            raise ValueError("No-header context has material rows")
        return {"context_state": "no_headers", "claims": []}
    material_ids: dict[str, set[str]] = {claim.claim_id: set() for claim in ctx.claims}
    if len(material_ids) != len(ctx.claims) or any(not claim_id.strip() for claim_id in material_ids):
        raise ValueError("Scope inventory has duplicate or blank claim IDs")
    for material in ctx.material_lines:
        if (
            material.claim_id not in material_ids
            or not material.material_line_id.strip()
            or material.material_line_id in material_ids[material.claim_id]
        ):
            raise ValueError("Scope inventory has foreign or duplicate material IDs")
        material_ids[material.claim_id].add(material.material_line_id)
    return {
        "context_state": "available",
        "claims": [
            {"claim_id": claim_id, "material_line_ids": sorted(material_ids[claim_id])}
            for claim_id in sorted(material_ids)
        ],
    }


def _status_counts() -> dict[str, int]:
    return dict.fromkeys(_STATUSES, 0)


def _bounded_block(
    rows: list[dict[str, Any]], available: bool, reason: str | None, limit: int
) -> WaveAEvidenceBlock:
    return WaveAEvidenceBlock(
        available=available,
        unavailable_reason=reason,
        total_rows=len(rows) if available else None,
        rows=deepcopy(rows[:limit]) if available else [],
        has_more=available and len(rows) > limit,
    )


def _broad_sparse_row(disposition: Any, kind: str) -> dict[str, Any]:
    evaluation = disposition.evaluation
    policy = disposition.policy
    base = {
        "source_evidence_id": evaluation.evaluation_id,
        "patient_id": evaluation.patient_id,
        "claim_id": evaluation.claim_id,
        "rule_id": evaluation.rule_id,
        "line_kind": evaluation.line_kind,
        "line_id": evaluation.line_id,
        "source_engine": policy.family,
        "evaluation_status": evaluation.evaluation_status,
        "disposition": disposition.disposition,
        "reason": disposition.reason,
        "source_authority": disposition.source_authority,
        "source_status": disposition.source_status,
        "regulatory_source": {
            "source_file": policy.source_file,
            "source_locators": list(policy.source_locators),
            "fatura_inceleme_ref": policy.fatura_inceleme_ref,
        },
        "policy_ref": BROAD_POLICY_REF,
    }
    if kind == "advisory":
        return {
            **base,
            "evidence_id": "wavea_advisory:" + evaluation.evaluation_id,
            "advisory_kind": "information"
            if disposition.disposition == "information_only"
            else "permission",
            "money_semantics": "unpriced_advisory",
        }
    return {
        **base,
        "evidence_id": "wavea_review:" + evaluation.evaluation_id,
        "review_kind": "unverified_adverse"
        if disposition.disposition == "unavailable"
        else "source_review",
        "money_semantics": "unpriced_review",
    }


def project_full_wavea_evidence(
    patient_id: str,
    ctx: PatientClaimContext | None,
    focused: FocusedProjectionBatch,
    broad: BroadMaterialized,
    *,
    detail_limit: int = DEFAULT_DETAIL_LIMIT,
    applicability: SourceApplicabilityAttestation | None = None,
) -> FullWaveAEvidenceProjection:
    """Classify one materialized bundle without changing raw legacy decisions."""
    if not patient_id.strip() or broad.patient_id != patient_id or (
        ctx is not None and ctx.patient_id != patient_id
    ):
        raise ValueError("Full Wave A evidence patient identity mismatch")
    if detail_limit < 0:
        raise ValueError("Wave A detail limit must be nonnegative")
    inventory = build_claim_scope_inventory(ctx)
    focused_projection = project_focused_evidence(
        patient_id, ctx, focused, detail_limit=detail_limit
    )
    focused_detail = focused_projection.detail
    policy = load_broad_classification_policy()
    classifier = BroadRuleClassifier(ctx, applicability) if ctx is not None and ctx.claims else None
    evaluations: dict[str, dict[str, Any]] = {
        row["evaluation_id"]: deepcopy(row) for row in focused_detail["evaluations"]
    }
    reviews: dict[str, dict[str, Any]] = {
        row["evidence_id"]: deepcopy(row) for row in focused_detail["reviews"]
    }
    advisories: dict[str, dict[str, Any]] = {}
    financial_rows = deepcopy(focused_detail["financial_rows"])
    confirmed_findings: list[RuleFinding] = []
    broad_groups = {entry.family for entry in policy.values()}
    by_rule = deepcopy(focused_detail["counts"]["by_rule"])
    by_rule.update({rule_id: _status_counts() for rule_id in policy})
    by_group = deepcopy(focused_detail["counts"]["by_group"])
    by_group.update({group: _status_counts() for group in broad_groups})
    for evaluation in broad.evaluations:
        if evaluation.rule_id not in policy:
            raise ValueError("Full Wave A evidence has a foreign broad rule")
        if classifier is not None:
            outcome = classifier.classify(evaluation, broad.legacy_row_for(evaluation))
            disposition = outcome.disposition
            reason = outcome.reason
            source_authority = outcome.source_authority
            source_status = outcome.source_status
        else:
            outcome = None
            disposition = evaluation.evaluation_status
            reason = evaluation.reason
            source_authority = (
                "sgk_fatura_guideline_sut_takes_precedence"
                if policy[evaluation.rule_id].family == "fatura_inceleme_prose"
                else "sut_authored_reference"
            )
            source_status = "not_evaluated"
        payload = {
            **asdict(evaluation),
            "disposition": disposition,
            "disposition_reason": reason,
            "source_authority": source_authority,
            "source_status": source_status,
            "policy_ref": BROAD_POLICY_REF,
        }
        if evaluation.evaluation_id in evaluations:
            raise ValueError("Focused and broad evidence identities collide")
        evaluations[evaluation.evaluation_id] = payload
        by_rule[evaluation.rule_id][evaluation.evaluation_status] += 1
        by_group[policy[evaluation.rule_id].family][evaluation.evaluation_status] += 1
        if outcome is None or evaluation.decision != "matched":
            continue
        if outcome.finding is not None:
            if outcome.disposition != "unpriced_compliance":
                raise ValueError("Broad finding has a noncompliance disposition")
            confirmed_findings.append(outcome.finding)
        elif disposition in _DISPLAY_DISPOSITIONS:
            if disposition in ("permission_or_instruction", "information_only"):
                row = _broad_sparse_row(outcome, "advisory")
                target = advisories
            else:
                row = _broad_sparse_row(outcome, "review")
                target = reviews
            if row["evidence_id"] in target:
                raise ValueError("Duplicate broad sparse evidence identity")
            target[row["evidence_id"]] = row

    review_rows = [reviews[key] for key in sorted(reviews)]
    advisory_rows = [advisories[key] for key in sorted(advisories)]
    available = focused_detail["available"]
    unavailable_reason = focused_detail["unavailable_reason"]
    detail = {
        "schema_version": FULL_EVIDENCE_SCHEMA_VERSION,
        "roster_version": FULL_ROSTER_VERSION,
        "patient_id": patient_id,
        "available": available,
        "unavailable_reason": unavailable_reason,
        "claim_scope_inventory": inventory,
        "evaluations": [evaluations[key] for key in sorted(evaluations)],
        "reviews": review_rows,
        "advisories": advisory_rows,
        "financial_rows": financial_rows,
        "counts": {
            "by_rule": by_rule,
            "by_group": by_group,
            "evaluation_count": len(evaluations),
            "review_count": len(review_rows),
            "advisory_count": len(advisory_rows),
            "financial_count": len(financial_rows),
            "review_by_rule": dict(Counter(row["rule_id"] for row in review_rows)),
            "advisory_by_rule": dict(Counter(row["rule_id"] for row in advisory_rows)),
            "financial_by_rule": dict(Counter(row["rule_id"] for row in financial_rows)),
        },
    }
    coverage = {
        "schema_version": FULL_EVIDENCE_SCHEMA_VERSION,
        "available": available,
        "unavailable_reason": unavailable_reason,
        "tracked_rule_count": len(by_rule),
        "evaluation_count": len(evaluations),
        "by_group": deepcopy(by_group),
    }
    return FullWaveAEvidenceProjection(
        claim_reviews=_bounded_block(review_rows, available, unavailable_reason, detail_limit),
        claim_advisories=_bounded_block(advisory_rows, available, unavailable_reason, detail_limit),
        financial_findings=_bounded_block(financial_rows, available, unavailable_reason, detail_limit),
        coverage=coverage,
        detail=detail,
        confirmed_broad_findings=tuple(confirmed_findings),
    )


def _checked_inventory(value: Any) -> tuple[str, dict[str, frozenset[str]]]:
    if not isinstance(value, dict) or set(value) != {"context_state", "claims"}:
        raise ValueError("Full Wave A detail lacks its claim scope inventory")
    state = value["context_state"]
    rows = value["claims"]
    if state not in ("available", "missing", "no_headers") or not isinstance(rows, list):
        raise ValueError("Full Wave A claim scope state is malformed")
    if state != "available" and rows:
        raise ValueError("Unavailable claim scope has claim rows")
    if state == "available" and not rows:
        raise ValueError("Available claim scope has no claims")
    claims: dict[str, frozenset[str]] = {}
    previous_id = ""
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"claim_id", "material_line_ids"}:
            raise ValueError("Full Wave A claim scope row is malformed")
        claim_id = row["claim_id"]
        material_ids = row["material_line_ids"]
        if (
            not isinstance(claim_id, str)
            or not claim_id.strip()
            or claim_id <= previous_id
            or not isinstance(material_ids, list)
            or any(not isinstance(line_id, str) or not line_id.strip() for line_id in material_ids)
            or material_ids != sorted(set(material_ids))
        ):
            raise ValueError("Full Wave A claim/material scope identity is ambiguous")
        claims[claim_id] = frozenset(material_ids)
        previous_id = claim_id
    return state, claims


def _checked_statuses(value: Any) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != set(_STATUSES) or any(
        type(value[status]) is not int or value[status] < 0 for status in _STATUSES
    ):
        raise ValueError("Full Wave A status counter is malformed")
    return value


def _expected_scope_keys(
    family: str, rule_id: str, claims: dict[str, frozenset[str]]
) -> set[tuple[str | None, str, str | None]]:
    if not claims:
        return {(None, "claim", None)}
    if family != "dental_2_4_1":
        return {(claim_id, "claim", None) for claim_id in claims}
    return {
        (claim_id, "material" if line_id is not None else "claim", line_id)
        for claim_id, material_ids in claims.items()
        for line_id in (material_ids or {None})
    }


def _validate_broad_disposition(row: dict[str, Any], policy: Any) -> None:
    status = row["evaluation_status"]
    decision = row.get("decision")
    disposition = row.get("disposition")
    if (
        (decision is not None and not isinstance(decision, str))
        or not isinstance(disposition, str)
        or (row.get("disposition_reason") is not None and not isinstance(row["disposition_reason"], str))
    ):
        raise ValueError("Full Wave A broad decision fields are malformed")
    if (
        row.get("policy_ref") != BROAD_POLICY_REF
        or row.get("source_authority") != (
            "sgk_fatura_guideline_sut_takes_precedence"
            if policy.family == "fatura_inceleme_prose"
            else "sut_authored_reference"
        )
        or row.get("source_status") not in (
            "not_evaluated", "authored_locator_unverified", "primary_meaning_and_date_verified"
        )
    ):
        raise ValueError("Full Wave A broad source classification is malformed")
    if row["source_status"] == "primary_meaning_and_date_verified" and (
        status != "evaluated" or disposition != "unpriced_compliance"
    ):
        raise ValueError("Broad source proof cannot certify an unevaluated outcome")
    if status != "evaluated":
        suppressed_dental = (
            policy.family == "dental_2_4_1"
            and status == "unavailable"
            and decision == "suppressed_by_prior_match"
            and isinstance(row.get("reason"), str)
            and row["reason"].startswith("prior_rule:")
        )
        if (
            (decision is not None and not suppressed_dental)
            or disposition != status
            or row.get("disposition_reason") != row.get("reason")
        ):
            raise ValueError("Missing broad predicate has a false outcome")
        return
    if row["source_status"] == "not_evaluated":
        raise ValueError("Evaluated broad predicate has no source classification")
    if decision == "not_matched":
        if disposition != "not_matched" or row.get("disposition_reason") is not None:
            raise ValueError("Negative broad predicate has a false outcome")
        return
    if decision != "matched":
        raise ValueError("Evaluated broad predicate lacks a decision")
    if policy.authored_verification_status == "ai_generated_pending_review":
        allowed = {"review_only"}
        expected_reason = "authored_source_pending_independent_review"
    elif policy.matched_surface == "dental_precious_metal_proof":
        allowed = {"review_only", "unavailable", "not_applicable", "unpriced_compliance"}
        expected_reason = None
    elif policy.matched_surface == "withheld_adverse":
        allowed = {"unavailable"}
        expected_reason = policy.gates[0]
    else:
        allowed = {policy.matched_surface}
        expected_reason = policy.gates[0]
    if disposition not in allowed or (
        disposition == "unpriced_compliance"
        and row["source_status"] != "primary_meaning_and_date_verified"
    ) or (
        expected_reason is not None and row.get("disposition_reason") != expected_reason
    ) or (
        row["source_status"] == "primary_meaning_and_date_verified"
        and disposition != "unpriced_compliance"
    ):
        raise ValueError("Matched broad predicate has an unsupported disposition")
    if policy.matched_surface == "dental_precious_metal_proof":
        expected_dental_reasons = {
            "review_only": {"exact_source_named_material_or_verified_composition_required"},
            "not_applicable": {"no_positive_actual_line_charge"},
            "unpriced_compliance": {None},
            "unavailable": {
                "request_field_provenance_unavailable",
                "authoritative_dental_category_and_line_link_required",
                "actual_line_charge_unavailable",
                "source_version_applicability_required",
                "effective_source_unavailable",
                "effective_source_missing_or_ambiguous",
                "effective_source_proof_changed",
            },
        }
        if row.get("disposition_reason") not in expected_dental_reasons[disposition]:
            raise ValueError("Dental source-proof outcome reason is unsupported")


def _validate_broad_sparse_row(
    row: Any,
    kind: str,
    evaluations: dict[str, dict[str, Any]],
    policy: dict[str, Any],
) -> None:
    if not isinstance(row, dict):
        raise ValueError("Full Wave A sparse row is malformed")
    source_id = row.get("source_evidence_id")
    rule_id = row.get("rule_id")
    if not isinstance(source_id, str) or not isinstance(rule_id, str) or (
        set(row) != _BROAD_SPARSE_COMMON_FIELDS | {
            "advisory_kind" if kind == "advisory" else "review_kind"
        }
    ):
        raise ValueError("Full Wave A sparse row has malformed fields")
    evaluation = evaluations.get(source_id)
    if (
        rule_id not in policy
        or evaluation is None
        or evaluation.get("rule_id") != rule_id
        or evaluation.get("evaluation_status") != "evaluated"
        or evaluation.get("decision") != "matched"
        or row.get("evidence_id") != f"wavea_{kind}:{source_id}"
        or row.get("policy_ref") != BROAD_POLICY_REF
        or any(field in row for field in _MONEY_FIELDS)
        or any(
            row.get(field) != evaluation.get(field)
            for field in (
                "patient_id", "claim_id", "rule_id", "line_kind", "line_id",
                "evaluation_status", "disposition", "source_authority", "source_status",
            )
        )
        or row.get("reason") != evaluation.get("disposition_reason")
        or row.get("source_engine") != policy[rule_id].family
        or row.get("regulatory_source") != {
            "source_file": policy[rule_id].source_file,
            "source_locators": list(policy[rule_id].source_locators),
            "fatura_inceleme_ref": policy[rule_id].fatura_inceleme_ref,
        }
    ):
        raise ValueError("Full Wave A sparse source does not match its evaluation")
    if kind == "advisory":
        disposition = evaluation["disposition"]
        if (
            disposition not in ("permission_or_instruction", "information_only")
            or row.get("advisory_kind") != (
                "information" if disposition == "information_only" else "permission"
            )
            or row.get("money_semantics") != "unpriced_advisory"
            or "review_kind" in row
        ):
            raise ValueError("Full Wave A advisory has false outcome semantics")
    elif (
        evaluation["disposition"] not in ("review_only", "unavailable")
        or row.get("review_kind") != (
            "unverified_adverse" if evaluation["disposition"] == "unavailable" else "source_review"
        )
        or row.get("money_semantics") != "unpriced_review"
        or "advisory_kind" in row
    ):
        raise ValueError("Full Wave A review has false outcome semantics")


def validate_full_wavea_evidence_detail(detail: dict[str, Any], patient_id: str) -> None:
    """Check roster, scope, status, and sparse evidence before cache storage."""
    if (
        not isinstance(detail, dict)
        or detail.get("schema_version") != FULL_EVIDENCE_SCHEMA_VERSION
        or detail.get("roster_version") != FULL_ROSTER_VERSION
        or detail.get("patient_id") != patient_id
        or not isinstance(patient_id, str)
        or not patient_id.strip()
    ):
        raise ValueError("Full Wave A detail has invalid identity or roster")
    state, claims = _checked_inventory(detail.get("claim_scope_inventory"))
    available = state == "available"
    if detail.get("available") is not available or detail.get("unavailable_reason") != (
        None if available else "claim_context_unavailable" if state == "missing" else "claim_headers_unavailable"
    ):
        raise ValueError("Full Wave A detail availability disagrees with scope")
    evaluations = detail.get("evaluations")
    reviews = detail.get("reviews")
    advisories = detail.get("advisories")
    financial = detail.get("financial_rows")
    counts = detail.get("counts")
    if not all(isinstance(rows, list) for rows in (evaluations, reviews, advisories, financial)) or not isinstance(counts, dict):
        raise ValueError("Full Wave A detail lacks evidence or counters")
    policy = dict(load_broad_classification_policy())
    roster = {**{key: spec.group for key, spec in _FOCUSED_BY_ID.items()}, **{
        key: item.family for key, item in policy.items()
    }}
    if len(roster) != 528 or len(set(roster.values())) != 25:
        raise ValueError("Full Wave A reviewed roster is not 25 groups/528 rules")
    by_rule = {rule_id: _status_counts() for rule_id in roster}
    by_group = {group: _status_counts() for group in set(roster.values())}
    evaluation_by_id: dict[str, dict[str, Any]] = {}
    scope_by_rule: dict[str, set[tuple[str | None, str, str | None]]] = {
        rule_id: set() for rule_id in roster
    }
    for row in evaluations:
        if not isinstance(row, dict):
            raise ValueError("Full Wave A evaluation is malformed")
        rule_id = row.get("rule_id")
        status = row.get("evaluation_status")
        claim_id = row.get("claim_id")
        line_kind = row.get("line_kind")
        line_id = row.get("line_id")
        identity = row.get("evaluation_id")
        if (
            row.get("patient_id") != patient_id
            or not isinstance(rule_id, str)
            or rule_id not in roster
            or status not in _STATUSES
            or not isinstance(claim_id, (str, type(None)))
            or claim_id not in (claims if available else {None})
            or line_kind not in ("claim", "procedure", "drug", "material")
            or (line_kind == "claim") != (line_id is None)
            or (line_kind != "claim" and (not isinstance(line_id, str) or not line_id.strip()))
            or not isinstance(identity, str)
            or identity != build_evaluation_id(
                rule_id=rule_id, patient_id=patient_id, claim_id=claim_id,
                line_kind=line_kind, line_id=line_id,
            )
            or identity in evaluation_by_id
        ):
            raise ValueError("Full Wave A evaluation identity is malformed")
        if not available and (status != "missing_inputs" or line_kind != "claim"):
            raise ValueError("No-header Wave A evaluation implies a false clean status")
        if rule_id in policy:
            _validate_broad_disposition(row, policy[rule_id])
            if row["source_status"] != (
                "authored_locator_unverified" if available else "not_evaluated"
            ) and row["source_status"] != "primary_meaning_and_date_verified":
                raise ValueError("Broad source status disagrees with claim availability")
        evaluation_by_id[identity] = row
        scope_by_rule[rule_id].add((claim_id, line_kind, line_id))
        by_rule[rule_id][status] += 1
        by_group[roster[rule_id]][status] += 1
    for rule_id, item in policy.items():
        if scope_by_rule[rule_id] != _expected_scope_keys(item.family, rule_id, claims):
            raise ValueError(f"Broad authored scope is incomplete: {rule_id}")
        if sum(by_rule[rule_id].values()) != len(scope_by_rule[rule_id]):
            raise ValueError("Duplicate broad authored scope")
    for rule_id in _FOCUSED_BY_ID:
        expected_claims = set(claims) if available else {None}
        if {claim_id for claim_id, _, _ in scope_by_rule[rule_id]} != expected_claims:
            raise ValueError(f"Focused authored scope is incomplete: {rule_id}")
    if counts.get("by_rule") != by_rule or counts.get("by_group") != by_group or (
        type(counts.get("evaluation_count")) is not int
        or counts["evaluation_count"] != len(evaluations)
    ):
        raise ValueError("Full Wave A status counters disagree with evaluations")
    if any(
        not isinstance(row, dict) or not isinstance(row.get("rule_id"), str)
        for rows in (reviews, advisories, financial)
        for row in rows
    ):
        raise ValueError("Full Wave A sparse row is malformed")
    focus_evaluations = [row for row in evaluations if row["rule_id"] in _FOCUSED_BY_ID]
    focus_reviews = [row for row in reviews if row.get("rule_id") in _FOCUSED_BY_ID]
    focus_detail = {
        "schema_version": "wavea-evidence-v1",
        "patient_id": patient_id,
        "available": available,
        "unavailable_reason": detail["unavailable_reason"],
        "evaluations": focus_evaluations,
        "reviews": focus_reviews,
        "financial_rows": financial,
        "counts": {
            "by_rule": {rule_id: by_rule[rule_id] for rule_id in _FOCUSED_BY_ID},
            "by_group": {
                group: by_group[group] for group in {spec.group for spec in FOCUSED_RULE_SPECS}
            },
            "evaluation_count": len(focus_evaluations),
            "review_count": len(focus_reviews),
            "financial_count": len(financial),
            "review_by_rule": dict(Counter(row["rule_id"] for row in focus_reviews)),
            "financial_by_rule": dict(Counter(row["rule_id"] for row in financial)),
        },
    }
    validate_wavea_evidence_detail(focus_detail, patient_id)
    broad_reviews = [row for row in reviews if row.get("rule_id") in policy]
    if len(broad_reviews) + len(focus_reviews) != len(reviews):
        raise ValueError("Full Wave A review uses an unknown authored rule")
    if financial and any(row.get("rule_id") in policy for row in financial):
        raise ValueError("Broad financial row lacks verified money basis")
    if advisories and any(row.get("rule_id") not in policy for row in advisories):
        raise ValueError("Only broad rules can currently produce an advisory")
    seen_sparse: set[str] = set()
    actual_broad_sources: set[str] = set()
    for kind, rows in (("review", broad_reviews), ("advisory", advisories)):
        prior = ""
        for row in rows:
            _validate_broad_sparse_row(row, kind, evaluation_by_id, policy)
            identity = row["evidence_id"]
            if identity in seen_sparse or identity <= prior:
                raise ValueError("Full Wave A sparse identity is duplicate or unsorted")
            seen_sparse.add(identity)
            if row["source_evidence_id"] in actual_broad_sources:
                raise ValueError("Full Wave A broad source is displayed twice")
            actual_broad_sources.add(row["source_evidence_id"])
            prior = identity
    expected_broad_sources = {
        row["evaluation_id"]
        for row in evaluations
        if row["rule_id"] in policy
        and row["evaluation_status"] == "evaluated"
        and row.get("decision") == "matched"
        and row.get("disposition") in _DISPLAY_DISPOSITIONS
    }
    if actual_broad_sources != expected_broad_sources:
        raise ValueError("Matched broad display evidence is incomplete")
    if not available and (reviews or advisories or financial):
        raise ValueError("Unavailable Wave A patient has sparse evidence")
    for label, rows in (("review", reviews), ("advisory", advisories), ("financial", financial)):
        if (
            type(counts.get(f"{label}_count")) is not int
            or counts[f"{label}_count"] != len(rows)
            or counts.get(f"{label}_by_rule") != dict(Counter(row["rule_id"] for row in rows))
        ):
            raise ValueError("Full Wave A sparse counts disagree with rows")


def build_full_wavea_evidence_index(
    details_by_patient: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate validated full details without duplicating exhaustive rows."""
    patients: dict[str, dict[str, Any]] = {}
    policy = load_broad_classification_policy()
    roster = {**{key: spec.group for key, spec in _FOCUSED_BY_ID.items()}, **{
        key: item.family for key, item in policy.items()
    }}
    aggregate_rule = {rule_id: _status_counts() for rule_id in roster}
    aggregate_group = {group: _status_counts() for group in set(roster.values())}
    evidence_rows: list[dict[str, Any]] = []
    review_count = advisory_count = financial_count = 0
    for patient_id in sorted(details_by_patient):
        detail = details_by_patient[patient_id]
        validate_full_wavea_evidence_detail(detail, patient_id)
        counts = detail["counts"]
        for source, aggregate in (
            (counts["by_rule"], aggregate_rule),
            (counts["by_group"], aggregate_group),
        ):
            for identity, statuses in source.items():
                destination = aggregate[identity]
                for status in _STATUSES:
                    destination[status] += statuses[status]
        review_count += counts["review_count"]
        advisory_count += counts["advisory_count"]
        financial_count += counts["financial_count"]
        evidence_rows.extend(deepcopy(detail["reviews"]))
        evidence_rows.extend(deepcopy(detail["advisories"]))
        evidence_rows.extend(deepcopy(detail["financial_rows"]))
        patients[patient_id] = {
            "available": detail["available"],
            "unavailable_reason": detail["unavailable_reason"],
            "counts": {
                key: deepcopy(counts[key])
                for key in (
                    "by_rule", "by_group", "evaluation_count", "review_count",
                    "advisory_count", "financial_count",
                )
            },
        }
    index = {
        "schema_version": FULL_EVIDENCE_SCHEMA_VERSION,
        "roster_version": FULL_ROSTER_VERSION,
        "capability": "draft",
        "available": True,
        "n_patients": len(patients),
        "n_patients_unavailable": sum(not summary["available"] for summary in patients.values()),
        "patients": patients,
        "counts": {
            "by_rule": aggregate_rule,
            "by_group": aggregate_group,
            "review_count": review_count,
            "advisory_count": advisory_count,
            "financial_count": financial_count,
        },
        "evidence_rows": sorted(evidence_rows, key=lambda row: row["evidence_id"]),
    }
    validate_full_wavea_evidence_index(index)
    return index


def validate_full_wavea_evidence_index(index: dict[str, Any]) -> None:
    """Reject false cohort counts, sparse IDs, or a partial authored roster."""
    if (
        not isinstance(index, dict)
        or index.get("schema_version") != FULL_EVIDENCE_SCHEMA_VERSION
        or index.get("roster_version") != FULL_ROSTER_VERSION
        or index.get("capability") != "draft"
        or index.get("available") is not True
        or not isinstance(index.get("patients"), dict)
        or not isinstance(index.get("counts"), dict)
        or not isinstance(index.get("evidence_rows"), list)
    ):
        raise ValueError("Full Wave A index lacks its exact schema or roster")
    patients = index["patients"]
    if (
        type(index.get("n_patients")) is not int
        or index["n_patients"] != len(patients)
        or type(index.get("n_patients_unavailable")) is not int
    ):
        raise ValueError("Full Wave A index patient cardinality disagrees")
    policy = dict(load_broad_classification_policy())
    roster = {**{key: spec.group for key, spec in _FOCUSED_BY_ID.items()}, **{
        key: item.family for key, item in policy.items()
    }}
    expected_groups = set(roster.values())
    if len(roster) != 528 or len(expected_groups) != 25:
        raise ValueError("Full Wave A index source roster changed")
    by_rule = {rule_id: _status_counts() for rule_id in roster}
    by_group = {group: _status_counts() for group in expected_groups}
    review_count = advisory_count = financial_count = unavailable_count = 0
    for patient_id, summary in patients.items():
        if not isinstance(patient_id, str) or not patient_id.strip() or not isinstance(summary, dict):
            raise ValueError("Full Wave A index has foreign patient identity")
        if type(summary.get("available")) is not bool or not isinstance(summary.get("counts"), dict):
            raise ValueError("Full Wave A index patient availability is malformed")
        if not summary["available"]:
            unavailable_count += 1
            if summary.get("unavailable_reason") not in (
                "claim_context_unavailable", "claim_headers_unavailable"
            ):
                raise ValueError("Full Wave A index unavailable reason is malformed")
        elif summary.get("unavailable_reason") is not None:
            raise ValueError("Full Wave A available patient has an unavailable reason")
        counts = summary["counts"]
        source_rules = counts.get("by_rule")
        source_groups = counts.get("by_group")
        if (
            not isinstance(source_rules, dict)
            or set(source_rules) != set(roster)
            or not isinstance(source_groups, dict)
            or set(source_groups) != expected_groups
        ):
            raise ValueError("Full Wave A index patient lacks 528 rules/25 groups")
        patient_group = {group: _status_counts() for group in expected_groups}
        evaluated_count = 0
        for rule_id, raw_statuses in source_rules.items():
            statuses = _checked_statuses(raw_statuses)
            for status in _STATUSES:
                by_rule[rule_id][status] += statuses[status]
                patient_group[roster[rule_id]][status] += statuses[status]
                evaluated_count += statuses[status]
            if not summary["available"] and any(
                statuses[status] for status in ("evaluated", "unavailable")
            ):
                raise ValueError("Unavailable full Wave A patient has nonmissing statuses")
        if (
            any(_checked_statuses(source_groups[group]) != patient_group[group] for group in expected_groups)
            or type(counts.get("evaluation_count")) is not int
            or counts["evaluation_count"] != evaluated_count
        ):
            raise ValueError("Full Wave A patient status counters disagree")
        for group in expected_groups:
            for status in _STATUSES:
                by_group[group][status] += patient_group[group][status]
        for label in ("review", "advisory", "financial"):
            value = counts.get(f"{label}_count")
            if type(value) is not int or value < 0 or (not summary["available"] and value):
                raise ValueError("Full Wave A patient sparse count is malformed")
        review_count += counts["review_count"]
        advisory_count += counts["advisory_count"]
        financial_count += counts["financial_count"]
    if index["n_patients_unavailable"] != unavailable_count:
        raise ValueError("Full Wave A unavailable patient count disagrees")
    aggregate = index["counts"]
    if aggregate.get("by_rule") != by_rule or aggregate.get("by_group") != by_group or any(
        type(aggregate.get(key)) is not int or aggregate[key] != expected
        for key, expected in (
            ("review_count", review_count),
            ("advisory_count", advisory_count),
            ("financial_count", financial_count),
        )
    ):
        raise ValueError("Full Wave A aggregate counts disagree with patients")
    seen_ids: set[str] = set()
    seen_sources: set[str] = set()
    per_patient: dict[str, Counter[str]] = {patient_id: Counter() for patient_id in patients}
    prior_id = ""
    for row in index["evidence_rows"]:
        if not isinstance(row, dict):
            raise ValueError("Full Wave A sparse cohort row is malformed")
        evidence_id = row.get("evidence_id")
        source_id = row.get("source_evidence_id")
        patient_id = row.get("patient_id")
        rule_id = row.get("rule_id")
        claim_id = row.get("claim_id")
        line_kind = row.get("line_kind")
        line_id = row.get("line_id")
        if (
            not isinstance(evidence_id, str)
            or not isinstance(source_id, str)
            or not isinstance(patient_id, str)
            or patient_id not in patients
            or not patients[patient_id]["available"]
            or not isinstance(rule_id, str)
            or rule_id not in roster
            or not isinstance(claim_id, str)
            or not claim_id.strip()
            or line_kind not in ("claim", "procedure", "drug", "material")
            or (line_kind == "claim") != (line_id is None)
            or (line_kind != "claim" and (not isinstance(line_id, str) or not line_id.strip()))
            or source_id != build_evaluation_id(
                rule_id=rule_id, patient_id=patient_id, claim_id=claim_id,
                line_kind=line_kind, line_id=line_id,
            )
            or evidence_id <= prior_id
            or evidence_id in seen_ids
            or source_id in seen_sources
        ):
            raise ValueError("Full Wave A sparse cohort identity is malformed")
        if evidence_id == "wavea_advisory:" + source_id:
            kind = "advisory"
            if rule_id not in policy:
                raise ValueError("Focused rule cannot be a broad advisory")
        elif evidence_id == "wavea_review:" + source_id:
            kind = "review"
        elif evidence_id == "wavea_financial:" + source_id:
            kind = "financial"
        else:
            raise ValueError("Full Wave A sparse cohort kind is malformed")
        if rule_id in policy:
            if kind == "financial":
                raise ValueError("Broad monetary evidence has no verified basis")
            synthetic = {
                **row,
                "evaluation_id": source_id,
                "decision": "matched",
                "disposition_reason": row.get("reason"),
            }
            _validate_broad_sparse_row(row, kind, {source_id: synthetic}, policy)
            _validate_broad_disposition(synthetic, policy[rule_id])
        else:
            if kind == "advisory" or row.get("source_engine") != _FOCUSED_BY_ID[rule_id].source_engine:
                raise ValueError("Focused sparse cohort source is malformed")
            _validate_evidence_row_semantics(row, kind, rule_id)
        per_patient[patient_id][kind] += 1
        seen_ids.add(evidence_id)
        seen_sources.add(source_id)
        prior_id = evidence_id
    for patient_id, summary in patients.items():
        if any(
            per_patient[patient_id][label] != summary["counts"][f"{label}_count"]
            for label in ("review", "advisory", "financial")
        ):
            raise ValueError("Full Wave A sparse cohort counts disagree with patients")

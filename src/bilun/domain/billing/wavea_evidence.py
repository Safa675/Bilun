"""Compact Wave A review and financial evidence from one focused detector pass.

The detailed rule statuses are retained for a build-scoped drill-down payload.
Only bounded review rows and group counts belong in default billing reports.
No candidate amount here contributes to a headline, action, or compliance finding.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any

from src.bilun.domain.billing.focused_rule_projection import (
    FOCUSED_RULE_SPECS,
    FocusedProjectionBatch,
)
from src.bilun.domain.billing.rule_findings import (
    DIAGNOSIS_RULE_ID,
    DRUG_BARCODE_RULE_ID,
    ICU_RULE_ID,
    LAB_RULE_ID,
    MATERIAL_IDENTITY_RULE_ID,
    build_evaluation_id,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext


EVIDENCE_SCHEMA_VERSION = "wavea-evidence-v1"
COMPLETE_EVIDENCE_CAPABILITY = "complete-25-v1"
DEFAULT_DETAIL_LIMIT = 20
_STATUSES = ("evaluated", "missing_inputs", "unavailable")
_SOURCE_STATUSES = frozenset({"structured_locator", "locator_only", "unverified"})
_UNSOURCED_MONEY_FIELDS = frozenset({
    "amount_try", "billed_try", "payable_try", "savings_try", "sgk_uplift_try",
    "recoverable_uplift_try", "compliance_savings_try", "risk_amount_try",
    "audit_exposure_try", "expected_ga_fee_try", "actual_billed_try",
    "billed_amount_try", "recoverable_gap_try", "risk_amount",
})
_FINANCIAL_ONLY_FIELDS = frozenset({
    "financial_kind", "confirmed_amount_try", "amount_status", "currency",
    "headline_relation",
})
_SPEC_BY_ID = {spec.rule_id: spec for spec in FOCUSED_RULE_SPECS}
ORIGINAL_FIVE_RULE_IDS = frozenset(
    {
        ICU_RULE_ID,
        DIAGNOSIS_RULE_ID,
        LAB_RULE_ID,
        DRUG_BARCODE_RULE_ID,
        MATERIAL_IDENTITY_RULE_ID,
    }
)


def original_five_report_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Show the pre-Wave-A compliance contract until the one activation."""
    result = dict(payload)
    block = result.get("claim_compliance")
    if isinstance(block, dict):
        original = dict(block)
        for collection in ("findings", "evaluations"):
            original[collection] = [
                row
                for row in block.get(collection) or []
                if isinstance(row, dict) and row.get("rule_id") in ORIGINAL_FIVE_RULE_IDS
            ]
        result["claim_compliance"] = original
    return result


def complete_evidence_available(index: Any, build_id: str) -> bool:
    """Require the activated build's exact completed evidence contract."""
    if not (
        isinstance(index, dict)
        and index.get("build_id") == build_id
        and index.get("schema_version") == EVIDENCE_SCHEMA_VERSION
        and index.get("capability") == COMPLETE_EVIDENCE_CAPABILITY
        and index.get("available") is True
        and isinstance(index.get("counts"), dict)
    ):
        return False
    try:
        validate_wavea_evidence_index(index)
    except ValueError:
        return False
    return True


@dataclass
class WaveAEvidenceBlock:
    available: bool = False
    unavailable_reason: str | None = "wavea_capability_unavailable"
    total_rows: int | None = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    has_more: bool = False


@dataclass(frozen=True)
class WaveAEvidenceProjection:
    claim_reviews: WaveAEvidenceBlock
    financial_findings: WaveAEvidenceBlock
    coverage: dict[str, Any]
    detail: dict[str, Any]


def _status_counts() -> dict[str, int]:
    return dict.fromkeys(_STATUSES, 0)


def _checked_status_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != set(_STATUSES):
        raise ValueError("Wave A index has malformed status counters")
    if any(type(value[status]) is not int or value[status] < 0 for status in _STATUSES):
        raise ValueError("Wave A index has malformed status count")
    return value


def validate_wavea_evidence_index(index: dict[str, Any]) -> None:
    """Reconcile every stored patient counter with the aggregate index."""
    if not isinstance(index, dict) or not isinstance(index.get("patients"), dict):
        raise ValueError("Wave A index lacks patient summaries")
    patients = index["patients"]
    if (
        type(index.get("n_patients")) is not int
        or index["n_patients"] != len(patients)
        or type(index.get("n_patients_unavailable")) is not int
        or index["n_patients_unavailable"] < 0
    ):
        raise ValueError("Wave A index patient counts disagree")
    by_rule: dict[str, dict[str, int]] = {}
    by_group: dict[str, dict[str, int]] = {}
    review_count = financial_count = unavailable_count = 0
    review_by_patient: Counter[str] = Counter()
    financial_by_patient: Counter[str] = Counter()
    expected_groups = {spec.group for spec in FOCUSED_RULE_SPECS}
    for patient_id, summary in patients.items():
        if not isinstance(patient_id, str) or not patient_id.strip() or not isinstance(summary, dict):
            raise ValueError("Wave A index has malformed patient identity")
        if summary.get("available") is False:
            unavailable_count += 1
            if summary.get("counts") is None:
                continue
        elif summary.get("available") is not True:
            raise ValueError("Wave A index has malformed patient availability")
        if not isinstance(summary.get("counts"), dict):
            raise ValueError("Wave A index has malformed patient availability")
        counts = summary["counts"]
        source_rules = counts.get("by_rule")
        source_groups = counts.get("by_group")
        if (
            not isinstance(source_rules, dict)
            or set(source_rules) != set(_SPEC_BY_ID)
            or not isinstance(source_groups, dict)
            or set(source_groups) != expected_groups
        ):
            raise ValueError("Wave A index patient lacks focused rule or group counters")
        patient_groups = {group: _status_counts() for group in expected_groups}
        patient_evaluations = 0
        for rule_id, raw_statuses in source_rules.items():
            statuses = _checked_status_counts(raw_statuses)
            aggregate = by_rule.setdefault(rule_id, _status_counts())
            for status in _STATUSES:
                value = statuses[status]
                aggregate[status] += value
                patient_groups[_SPEC_BY_ID[rule_id].group][status] += value
                patient_evaluations += value
        if any(
            _checked_status_counts(source_groups[group]) != patient_groups[group]
            for group in expected_groups
        ) or (
            type(counts.get("evaluation_count")) is not int
            or counts["evaluation_count"] != patient_evaluations
        ):
            raise ValueError("Wave A index patient counters disagree with rules")
        for group, statuses in patient_groups.items():
            aggregate = by_group.setdefault(group, _status_counts())
            for status in _STATUSES:
                aggregate[status] += statuses[status]
        for counter_name in ("review_count", "financial_count"):
            value = counts.get(counter_name)
            if type(value) is not int or value < 0:
                raise ValueError("Wave A index has malformed evidence count")
        if summary["available"] is False and (
            counts["review_count"]
            or counts["financial_count"]
            or any(statuses["evaluated"] or statuses["unavailable"] for statuses in source_rules.values())
        ):
            raise ValueError("Unavailable Wave A patient has non-missing evidence")
        review_count += counts["review_count"]
        financial_count += counts["financial_count"]
    if unavailable_count != index["n_patients_unavailable"]:
        raise ValueError("Wave A index unavailable patient count disagrees")
    aggregate = index.get("counts")
    if not isinstance(aggregate, dict):
        raise ValueError("Wave A index lacks aggregate counters")
    for counter_name in ("by_rule", "by_group"):
        source = aggregate.get(counter_name)
        if not isinstance(source, dict):
            raise ValueError("Wave A index has malformed aggregate counters")
        for statuses in source.values():
            _checked_status_counts(statuses)
    if any(
        type(aggregate.get(counter_name)) is not int
        for counter_name in ("review_count", "financial_count")
    ) or any(
        aggregate.get(counter_name) != value
        for counter_name, value in (
            ("by_rule", by_rule),
            ("by_group", by_group),
            ("review_count", review_count),
            ("financial_count", financial_count),
        )
    ):
        raise ValueError("Wave A index aggregate counts disagree with patients")
    evidence_rows = index.get("evidence_rows")
    if not isinstance(evidence_rows, list):
        raise ValueError("Wave A index lacks sparse evidence rows")
    seen_ids: set[str] = set()
    seen_sources: set[str] = set()
    prior_id = ""
    for row in evidence_rows:
        if not isinstance(row, dict):
            raise ValueError("Wave A index has malformed evidence row")
        identity = row.get("evidence_id")
        source = row.get("source_evidence_id")
        patient_id = row.get("patient_id")
        claim_id = row.get("claim_id")
        rule_id = row.get("rule_id")
        line_kind = row.get("line_kind")
        line_id = row.get("line_id")
        if (
            not isinstance(identity, str)
            or not isinstance(source, str)
            or not isinstance(patient_id, str)
            or patient_id not in patients
            or not isinstance(claim_id, str)
            or not claim_id.strip()
            or not isinstance(rule_id, str)
            or rule_id not in _SPEC_BY_ID
            or line_kind not in ("claim", "procedure", "drug", "material")
            or (line_kind == "claim" and line_id is not None)
            or (line_kind != "claim" and (not isinstance(line_id, str) or not line_id.strip()))
            or identity <= prior_id
            or identity in seen_ids
            or source in seen_sources
            or source != build_evaluation_id(
                rule_id=rule_id,
                patient_id=patient_id,
                claim_id=claim_id,
                line_kind=line_kind,
                line_id=line_id,
            )
            or row.get("source_engine") != _SPEC_BY_ID[rule_id].source_engine
            or row.get("evaluation_status") not in _STATUSES
        ):
            raise ValueError("Wave A index has malformed sparse evidence identity")
        if identity == "wavea_review:" + source:
            _validate_evidence_row_semantics(row, "review", rule_id)
            review_by_patient[patient_id] += 1
        elif identity == "wavea_financial:" + source:
            _validate_evidence_row_semantics(row, "financial", rule_id)
            financial_by_patient[patient_id] += 1
        else:
            raise ValueError("Wave A index has malformed sparse evidence kind or money")
        seen_ids.add(identity)
        seen_sources.add(source)
        prior_id = identity
    if sum(review_by_patient.values()) != review_count or sum(financial_by_patient.values()) != financial_count:
        raise ValueError("Wave A index sparse evidence counts disagree")
    for patient_id, summary in patients.items():
        counts = summary.get("counts")
        if counts is None:
            if review_by_patient[patient_id] or financial_by_patient[patient_id]:
                raise ValueError("Unavailable Wave A patient has sparse evidence")
            continue
        if (
            counts["review_count"] != review_by_patient[patient_id]
            or counts["financial_count"] != financial_by_patient[patient_id]
        ):
            raise ValueError("Wave A index patient sparse evidence counts disagree")


def _financial_kind(rule_id: str) -> str:
    return "uplift" if rule_id == "2-04.1.4_dental_ga_missing_uplift" else "risk"


def _source_status(raw: dict[str, Any]) -> str:
    ref = raw.get("clause_ref")
    if isinstance(ref, dict) and isinstance(ref.get("clause_key"), str) and ref["clause_key"]:
        return "structured_locator"
    return "locator_only" if raw.get("sut_section_id") or raw.get("source_type") else "unverified"


def _validate_evidence_row_semantics(row: dict[str, Any], label: str, rule_id: str) -> None:
    source_status = row.get("source_status")
    source = row.get("regulatory_source")
    structured = isinstance(source, dict) and isinstance(source.get("clause_key"), str) and bool(source["clause_key"])
    if (
        not isinstance(source_status, str)
        or source_status not in _SOURCE_STATUSES
        or (source_status == "structured_locator") != structured
    ):
        raise ValueError("Wave A evidence has inconsistent source status")
    if any(
        not isinstance(field, str)
        or field in _UNSOURCED_MONEY_FIELDS
        or (field.endswith("_try") and not (label == "financial" and field == "confirmed_amount_try"))
        for field in row
    ):
        raise ValueError("Wave A evidence has unsourced money fields")
    if label == "review":
        if row.get("money_semantics") != "unpriced_review" or any(
            field in row for field in _FINANCIAL_ONLY_FIELDS
        ):
            raise ValueError("Wave A review has financial semantics")
        return
    if (
        _SPEC_BY_ID[rule_id].disposition != "financial_review"
        or row.get("money_semantics") != "amount_unavailable"
        or row.get("financial_kind") != _financial_kind(rule_id)
        or row.get("confirmed_amount_try", object()) is not None
        or row.get("amount_status") != "unavailable"
        or row.get("currency") != "TRY"
        or row.get("headline_relation") != (
            "separate_yatak_reconciliation"
            if rule_id == "yatak_icu_overlap_510010"
            else "not_directly_included"
        )
    ):
        raise ValueError("Wave A financial evidence has unsupported amount semantics")


def project_focused_evidence(
    patient_id: str,
    ctx: PatientClaimContext | None,
    focused: FocusedProjectionBatch,
    *,
    detail_limit: int = DEFAULT_DETAIL_LIMIT,
) -> WaveAEvidenceProjection:
    """Build sparse display rows and exhaustive status counters without rerunning rules."""
    if not patient_id.strip() or (ctx is not None and ctx.patient_id != patient_id):
        raise ValueError("Wave A evidence patient identity mismatch")
    if detail_limit < 0:
        raise ValueError("Wave A detail limit must be nonnegative")

    evaluations: dict[str, dict[str, Any]] = {}
    by_rule = {spec.rule_id: _status_counts() for spec in FOCUSED_RULE_SPECS}
    for evaluation in focused.evaluations:
        if evaluation.patient_id != patient_id or evaluation.rule_id not in _SPEC_BY_ID:
            raise ValueError("Wave A evaluation has foreign identity")
        payload = asdict(evaluation)
        previous = evaluations.get(evaluation.evaluation_id)
        if previous is not None:
            if previous != payload:
                raise ValueError("Conflicting Wave A evaluation identity")
            continue
        evaluations[evaluation.evaluation_id] = payload
        by_rule[evaluation.rule_id][evaluation.evaluation_status] += 1

    review_rows: dict[str, dict[str, Any]] = {}
    financial_rows: dict[str, dict[str, Any]] = {}
    for review in focused.reviews:
        if review.patient_id != patient_id or review.rule_id not in _SPEC_BY_ID:
            raise ValueError("Wave A review has foreign identity")
        source_id = review.evaluation_id
        evaluation = evaluations.get(source_id)
        if evaluation is None:
            raise ValueError("Wave A review has no evaluated source identity")
        base = {
            "source_evidence_id": source_id,
            "patient_id": patient_id,
            "claim_id": review.claim_id,
            "rule_id": review.rule_id,
            "line_kind": review.line_kind,
            "line_id": review.line_id,
            "source_engine": review.source_engine,
            "evaluation_status": evaluation["evaluation_status"],
            "reason": review.reason,
            "source_status": _source_status(review.legacy_row),
            "regulatory_source": deepcopy(review.legacy_row.get("clause_ref")),
        }
        if review.kind == "financial_review":
            row = {
                **base,
                "evidence_id": "wavea_financial:" + source_id,
                "financial_kind": _financial_kind(review.rule_id),
                "confirmed_amount_try": None,
                "amount_status": "unavailable",
                "currency": "TRY",
                "headline_relation": "separate_yatak_reconciliation"
                if review.rule_id == "yatak_icu_overlap_510010"
                else "not_directly_included",
                "money_semantics": "amount_unavailable",
            }
            target = financial_rows
        else:
            row = {
                **base,
                "evidence_id": "wavea_review:" + source_id,
                "money_semantics": "unpriced_review",
            }
            target = review_rows
        prior = target.get(row["evidence_id"])
        if prior is not None and prior != row:
            raise ValueError("Conflicting Wave A review evidence identity")
        target.setdefault(row["evidence_id"], row)

    by_group = {
        group: _status_counts() for group in sorted({spec.group for spec in FOCUSED_RULE_SPECS})
    }
    for rule_id, counts in by_rule.items():
        group_counts = by_group[_SPEC_BY_ID[rule_id].group]
        for status, count in counts.items():
            group_counts[status] += count

    available = ctx is not None and bool(ctx.claims)
    unavailable_reason = None if available else "claim_context_unavailable" if ctx is None else "claim_headers_unavailable"
    ordered_reviews = [review_rows[key] for key in sorted(review_rows)]
    ordered_financial = [financial_rows[key] for key in sorted(financial_rows)]
    claim_reviews = WaveAEvidenceBlock(
        available=available,
        unavailable_reason=unavailable_reason,
        total_rows=len(ordered_reviews) if available else None,
        rows=deepcopy(ordered_reviews[:detail_limit]) if available else [],
        has_more=available and len(ordered_reviews) > detail_limit,
    )
    financial_findings = WaveAEvidenceBlock(
        available=available,
        unavailable_reason=unavailable_reason,
        total_rows=len(ordered_financial) if available else None,
        rows=deepcopy(ordered_financial[:detail_limit]) if available else [],
        has_more=available and len(ordered_financial) > detail_limit,
    )
    coverage = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "available": available,
        "unavailable_reason": unavailable_reason,
        "tracked_rule_count": len(FOCUSED_RULE_SPECS),
        "evaluation_count": len(evaluations),
        "by_group": deepcopy(by_group),
    }
    detail = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "patient_id": patient_id,
        "available": available,
        "unavailable_reason": unavailable_reason,
        "evaluations": [evaluations[key] for key in sorted(evaluations)],
        "reviews": ordered_reviews,
        "financial_rows": ordered_financial,
        "counts": {
            "by_rule": by_rule,
            "by_group": by_group,
            "evaluation_count": len(evaluations),
            "review_count": len(ordered_reviews),
            "financial_count": len(ordered_financial),
            "review_by_rule": {
                rule_id: sum(row["rule_id"] == rule_id for row in ordered_reviews)
                for rule_id in _SPEC_BY_ID
                if any(row["rule_id"] == rule_id for row in ordered_reviews)
            },
            "financial_by_rule": {
                rule_id: sum(row["rule_id"] == rule_id for row in ordered_financial)
                for rule_id in _SPEC_BY_ID
                if any(row["rule_id"] == rule_id for row in ordered_financial)
            },
        },
    }
    return WaveAEvidenceProjection(claim_reviews, financial_findings, coverage, detail)


def unavailable_evidence_detail(patient_id: str) -> dict[str, Any]:
    """Represent an old or partial producer without pretending it had zero findings."""
    if not patient_id.strip():
        raise ValueError("Wave A detail requires a patient")
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "patient_id": patient_id,
        "available": False,
        "unavailable_reason": "wavea_capability_unavailable",
        "evaluations": [],
        "reviews": [],
        "financial_rows": [],
        "counts": None,
    }


def validate_wavea_evidence_detail(detail: dict[str, Any], patient_id: str) -> None:
    """Reject a cache payload whose exact counts or evidence IDs disagree."""
    if not isinstance(detail, dict) or not isinstance(patient_id, str) or not patient_id:
        raise ValueError("Wave A detail lacks patient identity")
    if detail.get("patient_id") != patient_id:
        raise ValueError("Wave A detail patient identity mismatch")
    if detail.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        raise ValueError("Wave A detail schema mismatch")
    evaluations = detail.get("evaluations")
    reviews = detail.get("reviews")
    financial_rows = detail.get("financial_rows")
    if not all(isinstance(rows, list) for rows in (evaluations, reviews, financial_rows)):
        raise ValueError("Wave A detail lacks evidence collections")
    counts = detail.get("counts")
    if counts is None and detail.get("available") is False:
        if evaluations or reviews or financial_rows:
            raise ValueError("Unavailable Wave A detail has evidence without counters")
        return
    if type(detail.get("available")) is not bool or not isinstance(counts, dict):
        raise ValueError("Wave A detail lacks counters")
    if detail["available"] is False and (
        detail.get("unavailable_reason") not in ("claim_context_unavailable", "claim_headers_unavailable")
        or reviews
        or financial_rows
        or any(
            not isinstance(row, dict) or row.get("evaluation_status") != "missing_inputs"
            for row in evaluations
        )
    ):
        raise ValueError("Unavailable Wave A detail has non-missing evidence")

    by_rule = {rule_id: _status_counts() for rule_id in _SPEC_BY_ID}
    evaluations_by_id: dict[str, dict[str, Any]] = {}
    for evaluation in evaluations:
        if not isinstance(evaluation, dict) or evaluation.get("patient_id") != patient_id:
            raise ValueError("Wave A evaluation has foreign ownership")
        rule_id = evaluation.get("rule_id")
        status = evaluation.get("evaluation_status")
        identity = evaluation.get("evaluation_id")
        claim_id = evaluation.get("claim_id")
        line_kind = evaluation.get("line_kind")
        line_id = evaluation.get("line_id")
        if (
            not isinstance(rule_id, str)
            or rule_id not in by_rule
            or status not in _STATUSES
            or not isinstance(identity, str)
            or not identity
            or (claim_id is not None and (not isinstance(claim_id, str) or not claim_id.strip()))
            or line_kind not in ("claim", "procedure", "drug", "material")
            or (line_kind == "claim" and line_id is not None)
            or (
                line_kind != "claim"
                and (
                    claim_id is None
                    or not isinstance(line_id, str)
                    or not line_id.strip()
                )
            )
        ):
            raise ValueError("Wave A evaluation has malformed identity or status")
        if identity != build_evaluation_id(
            rule_id=rule_id,
            patient_id=patient_id,
            claim_id=claim_id,
            line_kind=line_kind,
            line_id=line_id,
        ):
            raise ValueError("Wave A evaluation has noncanonical identity")
        if identity in evaluations_by_id:
            raise ValueError("Duplicate Wave A evaluation identity")
        evaluations_by_id[identity] = evaluation
        by_rule[rule_id][status] += 1
    by_group = {group: _status_counts() for group in {spec.group for spec in FOCUSED_RULE_SPECS}}
    for rule_id, statuses in by_rule.items():
        for status, value in statuses.items():
            by_group[_SPEC_BY_ID[rule_id].group][status] += value
    source_rules = counts.get("by_rule")
    source_groups = counts.get("by_group")
    if not isinstance(source_rules, dict) or not isinstance(source_groups, dict):
        raise ValueError("Wave A detail lacks status counters")
    for source in (source_rules, source_groups):
        for statuses in source.values():
            _checked_status_counts(statuses)
    if source_rules != by_rule or source_groups != by_group:
        raise ValueError("Wave A detail status counters disagree with evaluations")

    for label, rows, namespace in (
        ("review", reviews, "wavea_review:"),
        ("financial", financial_rows, "wavea_financial:"),
    ):
        seen: set[str] = set()
        per_rule: Counter[str] = Counter()
        for row in rows:
            if not isinstance(row, dict) or row.get("patient_id") != patient_id:
                raise ValueError("Wave A evidence has foreign ownership")
            identity = row.get("evidence_id")
            source = row.get("source_evidence_id")
            rule_id = row.get("rule_id")
            if (
                not isinstance(identity, str)
                or not isinstance(source, str)
                or identity != namespace + source
                or identity in seen
                or source not in evaluations_by_id
                or not isinstance(rule_id, str)
                or rule_id not in by_rule
            ):
                raise ValueError("Wave A evidence has malformed source identity")
            evaluation = evaluations_by_id[source]
            if any(
                row.get(field) != evaluation.get(field)
                for field in ("patient_id", "claim_id", "rule_id", "line_kind", "line_id", "evaluation_status")
            ) or row.get("source_engine") != _SPEC_BY_ID[rule_id].source_engine:
                raise ValueError("Wave A evidence source does not match its evaluation")
            _validate_evidence_row_semantics(row, label, rule_id)
            seen.add(identity)
            per_rule[rule_id] += 1
        if (
            type(counts.get(f"{label}_count")) is not int
            or counts[f"{label}_count"] != len(rows)
        ):
            raise ValueError("Wave A evidence count disagrees with rows")
        if counts.get(f"{label}_by_rule") != dict(per_rule):
            raise ValueError("Wave A per-rule evidence count disagrees with rows")
    if (
        type(counts.get("evaluation_count")) is not int
        or counts["evaluation_count"] != len(evaluations)
    ):
        raise ValueError("Wave A evaluation count disagrees with rows")


def build_wavea_evidence_index(
    details_by_patient: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate only canonical patient details; bill detail is never added."""
    patients: dict[str, dict[str, Any]] = {}
    by_rule: dict[str, dict[str, int]] = {}
    by_group: dict[str, dict[str, int]] = {}
    total_review = 0
    total_financial = 0
    evidence_rows: list[dict[str, Any]] = []
    for patient_id in sorted(details_by_patient):
        detail = details_by_patient[patient_id]
        if detail.get("patient_id") != patient_id:
            raise ValueError("Wave A detail patient key mismatch")
        validate_wavea_evidence_detail(detail, patient_id)
        counts = detail.get("counts")
        if not isinstance(counts, dict):
            patients[patient_id] = {
                "available": False,
                "unavailable_reason": detail.get("unavailable_reason") or "wavea_capability_unavailable",
                "counts": None,
            }
            continue
        for label, aggregate in (("by_rule", by_rule), ("by_group", by_group)):
            source = counts.get(label)
            if not isinstance(source, dict):
                raise ValueError(f"Wave A detail lacks {label} counters")
            for identity, statuses in source.items():
                if not isinstance(identity, str) or not isinstance(statuses, dict):
                    raise ValueError("Wave A detail has malformed counters")
                target = aggregate.setdefault(identity, _status_counts())
                for status in target:
                    value = statuses.get(status)
                    if type(value) is not int or value < 0:
                        raise ValueError("Wave A detail has malformed status count")
                    target[status] += value
        review_count = counts.get("review_count")
        financial_count = counts.get("financial_count")
        if any(type(value) is not int or value < 0 for value in (review_count, financial_count)):
            raise ValueError("Wave A detail has malformed evidence counts")
        total_review += review_count
        total_financial += financial_count
        evidence_rows.extend(deepcopy(detail["reviews"]))
        evidence_rows.extend(deepcopy(detail["financial_rows"]))
        patients[patient_id] = {
            "available": detail["available"],
            "unavailable_reason": detail.get("unavailable_reason"),
            "counts": {
                "by_rule": deepcopy(counts["by_rule"]),
                "by_group": deepcopy(counts["by_group"]),
                "evaluation_count": counts["evaluation_count"],
                "review_count": review_count,
                "financial_count": financial_count,
            },
        }
    index = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "capability": "draft",
        "available": True,
        "n_patients": len(patients),
        "n_patients_unavailable": sum(not item["available"] for item in patients.values()),
        "patients": patients,
        "counts": {
            "by_rule": by_rule,
            "by_group": by_group,
            "review_count": total_review,
            "financial_count": total_financial,
        },
        "evidence_rows": sorted(evidence_rows, key=lambda row: row["evidence_id"]),
    }
    validate_wavea_evidence_index(index)
    return index

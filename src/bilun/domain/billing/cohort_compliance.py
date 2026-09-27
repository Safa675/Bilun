"""Cohort compliance index from cached billing ``recommended_actions``.

Built at cache time from in-memory patient billing reports so the Compliance
home tab never JSON-scans every patient on page load.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

import polars as pl

from .rule_findings import build_evaluation_id
from ..money import money_round_half_up_opt as _money

# Billing surface → Compliance subtab id. Copay exemption rows stay on
# /patient-alerts and are excluded even if a row is mis-tagged.
COMPLIANCE_INDEX_SURFACES: dict[str, str] = {
    "materials": "materials",
    "drug_indication": "drug_indication",
    "lab": "lab",
    "billing_strategy": "payment_methods",
}

INDEX_SURFACES: tuple[str, ...] = (
    "materials",
    "drug_indication",
    "lab",
    "payment_methods",
    "claim_compliance",
)

_CLAIM_LINE_ID_FIELDS: dict[str, str | None] = {
    "claim": None,
    "procedure": "procedure_line_id",
    "drug": "drug_claim_line_id",
    "material": "material_line_id",
}
_CLAIM_LINE_SOURCE_FIELDS = tuple(
    field for field in _CLAIM_LINE_ID_FIELDS.values() if field is not None
)
_CLAIM_MONEY_FIELDS = (
    "amount_try", "billed_try", "payable_try", "savings_try",
    "recoverable_uplift_try", "compliance_savings_try", "risk_amount_try",
    "audit_exposure_try",
)
_CLAIM_EVALUATION_DETAIL_LIMIT = 20
_CLAIM_EVALUATION_STATUSES = ("evaluated", "missing_inputs", "unavailable")
_CLAIM_EVALUATION_STATUS_MAP = {
    "evaluated": "evaluated",
    "missing_input": "missing_inputs",
    "missing_inputs": "missing_inputs",
    "unavailable": "unavailable",
}
_NONFINANCIAL_SURFACES = frozenset({"claim_compliance", "drug_indication"})


def _non_empty_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _claim_evaluation(
    patient_id: str,
    row: Mapping[str, Any],
) -> dict[str, Any] | None:
    if "claim_id" not in row:
        return None
    rule_id = _non_empty_string(row.get("rule_id"))
    row_patient_id = _non_empty_string(row.get("patient_id"))
    raw_claim_id = row.get("claim_id")
    claim_id = _non_empty_string(raw_claim_id) if raw_claim_id is not None else None
    raw_status = row.get("status")
    raw_evaluation_status = row.get("evaluation_status")
    status = (
        _CLAIM_EVALUATION_STATUS_MAP.get(raw_status)
        if isinstance(raw_status, str)
        else None
    )
    evaluation_status = (
        _CLAIM_EVALUATION_STATUS_MAP.get(raw_evaluation_status)
        if isinstance(raw_evaluation_status, str)
        else None
    )
    has_status = "status" in row
    has_evaluation_status = "evaluation_status" in row
    required_inputs = row.get("required_inputs")
    missing_inputs = row.get("missing_inputs")
    if (
        rule_id is None
        or row_patient_id != patient_id
        or (not has_status and not has_evaluation_status)
        or (has_status and status is None)
        or (has_evaluation_status and evaluation_status is None)
        or (
            has_status
            and has_evaluation_status
            and status != evaluation_status
        )
        or not isinstance(required_inputs, list)
        or not all(isinstance(value, str) for value in required_inputs)
        or not isinstance(missing_inputs, list)
        or not all(isinstance(value, str) for value in missing_inputs)
    ):
        return None

    normalized_status = status if status is not None else evaluation_status
    if normalized_status is None:
        return None

    if claim_id is None and (
        raw_claim_id is not None
        or normalized_status not in {"missing_inputs", "unavailable"}
        or not required_inputs
        or not missing_inputs
    ):
        return None

    has_identity = any(
        field in row for field in ("evaluation_id", "line_kind", "line_id")
    )
    if has_identity:
        line_kind = _non_empty_string(row.get("line_kind"))
        raw_line_id = row.get("line_id")
        if line_kind not in _CLAIM_LINE_ID_FIELDS:
            return None
        source_field = _CLAIM_LINE_ID_FIELDS[line_kind]
        if source_field is None:
            if raw_line_id is not None:
                return None
            line_id = None
        else:
            if claim_id is None:
                return None
            line_id = _non_empty_string(raw_line_id)
            if line_id is None or _non_empty_string(row.get(source_field)) != line_id:
                return None
        if any(
            field != source_field and row.get(field) is not None
            for field in _CLAIM_LINE_SOURCE_FIELDS
        ):
            return None
        expected_id = build_evaluation_id(
            rule_id=rule_id,
            patient_id=patient_id,
            claim_id=claim_id,
            line_kind=line_kind,
            line_id=line_id,
        )
        if row.get("evaluation_id") != expected_id:
            return None

    projected = dict(row)
    projected.update({
        "patient_id": patient_id,
        "claim_id": claim_id,
        "rule_id": rule_id,
        "status": normalized_status,
        "evaluation_status": normalized_status,
    })
    projected["surface"] = row.get("surface") or "claim_compliance"
    return projected


def _claim_finding(
    patient_id: str,
    row: Mapping[str, Any],
) -> dict[str, Any] | None:
    finding_id = _non_empty_string(row.get("finding_id"))
    action_id = row.get("action_id")
    rule_id = _non_empty_string(row.get("rule_id"))
    row_patient_id = _non_empty_string(row.get("patient_id"))
    claim_id = _non_empty_string(row.get("claim_id"))
    line_kind = _non_empty_string(row.get("line_kind"))
    if (
        finding_id is None
        or action_id != finding_id
        or rule_id is None
        or row_patient_id != patient_id
        or claim_id is None
        or line_kind not in _CLAIM_LINE_ID_FIELDS
    ):
        return None

    line_id_field = _CLAIM_LINE_ID_FIELDS[line_kind]
    raw_line_id = row.get("line_id")
    if line_id_field is None:
        if raw_line_id is not None:
            return None
        line_id = None
    else:
        line_id = _non_empty_string(raw_line_id)
        source_line_id = _non_empty_string(row.get(line_id_field))
        if line_id is None or source_line_id != line_id:
            return None

    if any(
        field != line_id_field and row.get(field) is not None
        for field in _CLAIM_LINE_SOURCE_FIELDS
    ):
        return None

    projected = dict(row)
    projected.update({
        "patient_id": patient_id,
        "claim_id": claim_id,
        "rule_id": rule_id,
        "finding_id": finding_id,
        "action_id": finding_id,
        "line_kind": line_kind,
        "line_id": line_id,
    })
    projected["kind"] = row.get("kind") or rule_id
    projected["status"] = row.get("status") or "violation"
    projected["finding_type"] = row.get("finding_type") or "compliance"
    projected["surface"] = row.get("surface") or "claim_compliance"
    projected["source_surface"] = row.get("source_surface") or "claim_compliance"
    for field in _CLAIM_MONEY_FIELDS:
        projected[field] = None
    return projected


def _claim_projection(patient_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    block = payload.get("claim_compliance")
    if not isinstance(block, Mapping):
        block = {}
    evaluations_by_identity: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in block.get("evaluations") or []:
        if not isinstance(row, Mapping):
            continue
        evaluation = _claim_evaluation(patient_id, row)
        if evaluation is None:
            continue
        if evaluation.get("line_kind") not in (None, "claim"):
            key = ("line", evaluation["evaluation_id"])
        else:
            # Old caches have no evaluation_id. A mixed payload can contain
            # their claim row and the new claim-scoped row for the same fact.
            key = ("claim", evaluation["rule_id"], evaluation["claim_id"] or "")
        prior = evaluations_by_identity.get(key)
        if prior is not None:
            if prior.get("evaluation_id") and evaluation.get("evaluation_id") and prior != evaluation:
                raise ValueError(f"Conflicting claim evaluation identity: {key[1]}")
            if key[0] == "claim" and (
                prior.get("evaluation_id") or evaluation.get("evaluation_id")
            ):
                if any(
                    prior[field] != evaluation[field]
                    for field in ("status", "required_inputs", "missing_inputs")
                ):
                    raise ValueError(f"Conflicting claim evaluation identity: {key[1:]}")
                if evaluation.get("evaluation_id"):
                    evaluations_by_identity[key] = evaluation
        else:
            evaluations_by_identity[key] = evaluation
    evaluations = [
        evaluations_by_identity[key]
        for key in sorted(evaluations_by_identity)
    ]

    findings: dict[str, dict[str, Any]] = {}
    for row in block.get("findings") or []:
        if not isinstance(row, Mapping):
            continue
        finding = _claim_finding(patient_id, row)
        if finding is None:
            continue
        findings.setdefault(finding["finding_id"], finding)
    return {
        "findings": [findings[finding_id] for finding_id in sorted(findings)],
        "evaluations": evaluations,
    }

_DEFAULT_LIMIT = 500
_MAX_LIMIT = 5000


def empty_cohort_compliance_index(
    *,
    n_patients: int | None = 0,
    artifacts_available: bool = True,
) -> dict[str, Any]:
    """Honest empty payload.

    When ``artifacts_available`` is False (old cache, missing table), counts
    stay ``None`` so the UI shows "—" instead of fake zeros.
    """
    if not artifacts_available:
        return {
            "n_patients": None,
            "n_findings": None,
            "n_patients_with_findings": None,
            "billed_at_risk_try": None,
            "by_surface": {},
            "rows": [],
            "artifacts_available": False,
            "claim_compliance": None,
        }
    return {
        "n_patients": int(n_patients or 0),
        "n_findings": 0,
        "n_patients_with_findings": 0,
        "billed_at_risk_try": 0.0,
        "by_surface": _zero_by_surface(),
        "rows": [],
        "artifacts_available": True,
    }


def _as_report_dict(report: Any) -> dict[str, Any]:
    if isinstance(report, Mapping):
        return dict(report)
    if dataclasses.is_dataclass(report) and not isinstance(report, type):
        return dataclasses.asdict(report)
    return {}


def _include_action(action: Mapping[str, Any]) -> bool:
    if action.get("finding_type") != "compliance":
        return False
    surface = action.get("surface")
    if surface == "copay":
        return False
    return surface in COMPLIANCE_INDEX_SURFACES


def _row_from_action(patient_id: str, action: Mapping[str, Any]) -> dict[str, Any]:
    surface = str(action.get("surface") or "")
    billed = None if surface in _NONFINANCIAL_SURFACES else action.get("billed_try")
    if billed is None and surface not in _NONFINANCIAL_SURFACES:
        billed = action.get("compliance_savings_try")
    finding_id = action.get("finding_id")
    if finding_id is None and surface == "drug_indication":
        finding_id = action.get("action_id")
    return {
        "patient_id": patient_id,
        "claim_id": action.get("claim_id"),
        "surface": COMPLIANCE_INDEX_SURFACES[surface],
        "source_surface": surface,
        "kind": action.get("kind"),
        "finding_type": "compliance",
        "billed_try": _money(billed) if billed is not None else None,
        "detail": action.get("detail"),
        "procedure_code": action.get("procedure_code"),
        "procedure_name": action.get("procedure_name"),
        "material_code": action.get("material_code"),
        "material_name": action.get("material_name"),
        "drug_code": action.get("drug_code"),
        "drug_name": action.get("drug_name"),
        "drug_claim_line_id": action.get("drug_claim_line_id"),
        "finding_id": finding_id,
        "severity": action.get("severity"),
        "applicability_status": action.get("applicability_status"),
        "evaluation_status": action.get("evaluation_status"),
        "observed_icd10_codes": action.get("observed_icd10_codes"),
        "matched_icd10_codes": action.get("matched_icd10_codes"),
        "unmatched_icd10_codes": action.get("unmatched_icd10_codes"),
        "eligible_routes": action.get("eligible_routes"),
        "eligible_route_count": action.get("eligible_route_count"),
        "eligible_routes_truncated": action.get("eligible_routes_truncated"),
        "observed_icd10_count": action.get("observed_icd10_count"),
        "observed_icd10_truncated": action.get("observed_icd10_truncated"),
        "recommended_action_tr": action.get("recommended_action_tr"),
        "sut_section_id": action.get("sut_section_id"),
        "action_id": action.get("action_id"),
    }


def _zero_by_surface() -> dict[str, dict[str, float | int | None]]:
    return {
        surface: {
            "n": 0,
            "billed_try": None if surface in _NONFINANCIAL_SURFACES else 0.0,
            "n_patients": 0,
        }
        for surface in INDEX_SURFACES
    }


def _summarize_rows(
    rows: list[dict[str, Any]],
    *,
    n_patients: int,
) -> dict[str, Any]:
    if not rows:
        empty = empty_cohort_compliance_index(n_patients=n_patients)
        empty["rows"] = []
        return empty

    df = pl.from_dicts(rows, infer_schema_length=None)
    billed = pl.col("billed_try").fill_null(0.0)
    billed_at_risk = float(df.select(billed.sum()).item() or 0.0)
    grouped = df.group_by("surface").agg(
        n=pl.len(),
        billed_try=billed.sum(),
        n_patients=pl.col("patient_id").n_unique(),
    )
    by_surface = _zero_by_surface()
    for rec in grouped.iter_rows(named=True):
        surface = rec["surface"]
        if surface not in by_surface:
            continue
        by_surface[surface] = {
            "n": int(rec["n"]),
            "billed_try": (
                None if surface in _NONFINANCIAL_SURFACES
                else float(_money(rec["billed_try"]) or 0.0)
            ),
            "n_patients": int(rec["n_patients"]),
        }
    return {
        "n_patients": n_patients,
        "n_findings": len(rows),
        "n_patients_with_findings": int(df["patient_id"].n_unique()),
        "billed_at_risk_try": float(_money(billed_at_risk) or 0.0),
        "by_surface": by_surface,
        "rows": rows,
        "artifacts_available": True,
    }


def build_cohort_compliance_index(reports: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten compliance ``recommended_actions`` from per-patient reports."""
    n_patients = len(reports)
    rows: list[dict[str, Any]] = []
    counts_by_patient: dict[str, dict[str, int]] = {}
    evaluation_details: list[dict[str, Any]] = []
    for patient_id, report in reports.items():
        payload = _as_report_dict(report)
        for action in payload.get("recommended_actions") or []:
            if not isinstance(action, Mapping):
                continue
            if not _include_action(action):
                continue
            rows.append(_row_from_action(str(patient_id), action))
        projection = _claim_projection(str(patient_id), payload)
        rows.extend(projection["findings"])
        counts = dict.fromkeys(_CLAIM_EVALUATION_STATUSES, 0)
        for evaluation in projection["evaluations"]:
            status = str(evaluation.get("status") or "unavailable")
            if status not in counts:
                status = "unavailable"
            counts[status] += 1
            if (
                status != "evaluated"
                and len(evaluation_details) < _CLAIM_EVALUATION_DETAIL_LIMIT
            ):
                evaluation_details.append(dict(evaluation))
        counts_by_patient[str(patient_id)] = counts
    result = _summarize_rows(rows, n_patients=n_patients)
    result["claim_compliance"] = {
        "counts_by_patient": counts_by_patient,
        "details": evaluation_details,
        "detail_limit": _CLAIM_EVALUATION_DETAIL_LIMIT,
    }
    return result


def _compact_claim_compliance(
    projection: Mapping[str, Any],
    *,
    patient_ids: frozenset[str] | None,
    include: bool,
) -> dict[str, Any]:
    counts = dict.fromkeys(_CLAIM_EVALUATION_STATUSES, 0)
    if not include:
        return {
            "counts": counts,
            "non_evaluated_total": 0,
            "details": [],
            "details_truncated": False,
            "evaluations": [],
        }

    counts_by_patient = projection.get("counts_by_patient")
    details_source = projection.get("details") or []
    if isinstance(counts_by_patient, Mapping):
        for patient_id, patient_counts in counts_by_patient.items():
            if patient_ids is not None and patient_id not in patient_ids:
                continue
            if not isinstance(patient_counts, Mapping):
                continue
            for status in _CLAIM_EVALUATION_STATUSES:
                counts[status] += int(patient_counts.get(status) or 0)
    else:
        # Backward compatibility for caches built by the first claim-compliance
        # implementation. New caches never persist successful evaluation ids.
        legacy = [
            dict(row)
            for row in projection.get("evaluations") or []
            if isinstance(row, Mapping)
            and (patient_ids is None or row.get("patient_id") in patient_ids)
        ]
        for evaluation in legacy:
            status = str(evaluation.get("status") or "unavailable")
            if status not in counts:
                status = "unavailable"
            counts[status] += 1
        details_source = [row for row in legacy if row.get("status") != "evaluated"]

    details = [
        dict(row)
        for row in details_source
        if isinstance(row, Mapping)
        and (patient_ids is None or row.get("patient_id") in patient_ids)
    ][:_CLAIM_EVALUATION_DETAIL_LIMIT]
    non_evaluated_total = counts["missing_inputs"] + counts["unavailable"]
    return {
        "counts": counts,
        "non_evaluated_total": non_evaluated_total,
        "details": details,
        "details_truncated": non_evaluated_total > len(details),
        "evaluations": [],
    }


def slice_compliance_index(
    payload: Mapping[str, Any],
    *,
    surface: str | None = None,
    patient_ids: frozenset[str] | None = None,
    limit: int = _DEFAULT_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    """Filter and paginate a cached index without rescanning billing reports."""
    artifacts_available = bool(payload.get("artifacts_available", True))
    if not artifacts_available:
        result = empty_cohort_compliance_index(artifacts_available=False)
        result["pagination"] = {
            "total_matching": 0,
            "limit": limit,
            "offset": offset,
            "has_more": False,
        }
        result["query"] = {
            "surface": surface,
            "limit": limit,
            "offset": offset,
        }
        return result

    source_rows = payload.get("rows") or []
    rows = [dict(row) for row in source_rows if isinstance(row, Mapping)]
    if surface:
        rows = [row for row in rows if row.get("surface") == surface]
    if patient_ids is not None:
        rows = [row for row in rows if str(row.get("patient_id") or "") in patient_ids]

    n_patients = payload.get("n_patients")
    if patient_ids is not None:
        n_patients = len(patient_ids)
    elif n_patients is None:
        n_patients = 0

    summarized = _summarize_rows(list(rows), n_patients=int(n_patients))
    if surface in _NONFINANCIAL_SURFACES:
        summarized["billed_at_risk_try"] = None
    projection = payload.get("claim_compliance")
    if isinstance(projection, Mapping):
        summarized["claim_compliance"] = _compact_claim_compliance(
            projection,
            patient_ids=patient_ids,
            include=surface is None or surface == "claim_compliance",
        )
    else:
        summarized["claim_compliance"] = None
    total_matching = len(rows)
    page = rows[offset : offset + limit] if limit else rows[offset:]
    summarized["rows"] = page
    summarized["pagination"] = {
        "total_matching": total_matching,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(page) < total_matching,
    }
    summarized["query"] = {
        "surface": surface,
        "limit": limit,
        "offset": offset,
    }
    return summarized

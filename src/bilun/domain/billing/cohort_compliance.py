"""Cohort compliance index from cached billing ``recommended_actions``.

Built at cache time from in-memory patient billing reports so the Compliance
home tab never JSON-scans every patient on page load.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

import polars as pl

from .rule_findings import build_finding_id
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

_CLAIM_COMPLIANCE_RULES = (
    "icu_bundled_leakage_510090",
    "tablo15_8_missing_diagnosis",
)
_CLAIM_MONEY_FIELDS = (
    "amount_try", "billed_try", "payable_try", "savings_try",
    "recoverable_uplift_try", "compliance_savings_try", "risk_amount_try",
    "audit_exposure_try",
)
_CLAIM_EVALUATION_DETAIL_LIMIT = 20
_CLAIM_EVALUATION_STATUSES = ("evaluated", "missing_inputs", "unavailable")


def _claim_projection(patient_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    block = payload.get("claim_compliance")
    if not isinstance(block, Mapping):
        block = {}
    evaluations = [
        dict(row, surface="claim_compliance")
        for row in block.get("evaluations") or []
        if isinstance(row, Mapping)
        and row.get("rule_id") in _CLAIM_COMPLIANCE_RULES
        and row.get("patient_id") == patient_id
    ]
    for rule_id in _CLAIM_COMPLIANCE_RULES:
        if not any(row["rule_id"] == rule_id for row in evaluations):
            evaluations.append({
                "patient_id": patient_id, "claim_id": None, "rule_id": rule_id,
                "surface": "claim_compliance", "status": "unavailable",
                "missing_inputs": ["claim_compliance"],
            })
    findings = {}
    for row in block.get("findings") or []:
        if not isinstance(row, Mapping):
            continue
        rule_id = row.get("rule_id")
        claim_id = row.get("claim_id")
        if (
            rule_id not in _CLAIM_COMPLIANCE_RULES
            or row.get("patient_id") != patient_id
            or not claim_id
        ):
            continue
        expected_line_kind = (
            "procedure"
            if rule_id == "icu_bundled_leakage_510090"
            else "claim"
        )
        line_kind = row.get("line_kind")
        line_id = row.get("line_id")
        if line_kind != expected_line_kind:
            continue
        if expected_line_kind == "procedure":
            if line_id != row.get("procedure_line_id"):
                continue
        elif line_id is not None:
            continue
        expected_id = build_finding_id(
            rule_id=str(rule_id),
            patient_id=patient_id,
            claim_id=str(claim_id),
            line_kind=expected_line_kind,
            line_id=str(line_id) if line_id is not None else None,
        )
        finding_id = row.get("finding_id")
        action_id = row.get("action_id")
        if finding_id != expected_id or action_id != expected_id:
            continue
        findings.setdefault(finding_id, {
            **{key: row.get(key) for key in (
                "patient_id", "claim_id", "rule_id", "detail", "sut_section_id",
                "procedure_line_id", "procedure_code", "procedure_name",
            )},
            "finding_id": finding_id, "action_id": action_id,
            "line_kind": line_kind, "line_id": line_id,
            "kind": rule_id, "status": "violation",
            "finding_type": "compliance", "surface": "claim_compliance",
            "source_surface": "claim_compliance", **dict.fromkeys(_CLAIM_MONEY_FIELDS),
        })
    return {"findings": list(findings.values()), "evaluations": evaluations}

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
    billed = action.get("billed_try")
    if billed is None:
        billed = action.get("compliance_savings_try")
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
        "sut_section_id": action.get("sut_section_id"),
        "action_id": action.get("action_id"),
    }


def _zero_by_surface() -> dict[str, dict[str, float | int | None]]:
    return {
        surface: {
            "n": 0,
            "billed_try": None if surface == "claim_compliance" else 0.0,
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
                None if surface == "claim_compliance"
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
    if surface == "claim_compliance":
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

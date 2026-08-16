"""Cohort compliance index from cached billing ``recommended_actions``.

Built at cache time from in-memory patient billing reports so the Compliance
home tab never JSON-scans every patient on page load.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

import polars as pl

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
)

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
        }
    return {
        "n_patients": int(n_patients or 0),
        "n_findings": 0,
        "n_patients_with_findings": 0,
        "billed_at_risk_try": 0.0,
        "by_surface": {
            surface: {"n": 0, "billed_try": 0.0, "n_patients": 0}
            for surface in INDEX_SURFACES
        },
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


def _zero_by_surface() -> dict[str, dict[str, float | int]]:
    return {
        surface: {"n": 0, "billed_try": 0.0, "n_patients": 0}
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

    df = pl.from_dicts(rows)
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
            "billed_try": float(_money(rec["billed_try"]) or 0.0),
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
    for patient_id, report in reports.items():
        payload = _as_report_dict(report)
        for action in payload.get("recommended_actions") or []:
            if not isinstance(action, Mapping):
                continue
            if not _include_action(action):
                continue
            rows.append(_row_from_action(str(patient_id), action))
    return _summarize_rows(rows, n_patients=n_patients)


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

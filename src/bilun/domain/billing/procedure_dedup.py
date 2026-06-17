"""Suppress procedure add-on uplift duplicated by EMR capture gap rows."""

from __future__ import annotations

from typing import Any

from .types import ProcedureAddonUplift, ProcedureCaptureGap


def _procedure_date_key(value: Any) -> str:
    text = str(value or "").strip()
    return text[:10] if text else ""


def _capture_gap_keys(capture: ProcedureCaptureGap) -> set[tuple[str, str, str]]:
    return {
        (
            str(row.get("claim_id") or ""),
            str(row.get("procedure_code") or ""),
            _procedure_date_key(row.get("service_date")),
        )
        for row in capture.opportunities
    }


def dedupe_addon_against_capture(
    addon: ProcedureAddonUplift,
    capture: ProcedureCaptureGap,
) -> ProcedureAddonUplift:
    """Suppress add-on uplift when EMR capture already flags the same code/date."""
    capture_keys = _capture_gap_keys(capture)
    if not capture_keys:
        return addon

    filtered = [
        row
        for row in addon.opportunities
        if (
            str(row.get("claim_id") or ""),
            str(row.get("expected_addon_procedure_code") or ""),
            _procedure_date_key(
                row.get("service_date") or row.get("session_date")
            ),
        )
        not in capture_keys
    ]
    if len(filtered) == len(addon.opportunities):
        return addon

    return ProcedureAddonUplift(
        opportunities=filtered,
        exactness_status=addon.exactness_status,
        unavailable_reason=addon.unavailable_reason,
        required_inputs_missing=list(addon.required_inputs_missing),
        rule_source=addon.rule_source,
    )

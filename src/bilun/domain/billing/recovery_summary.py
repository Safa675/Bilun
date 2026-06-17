"""Per-patient recovery summary rows for cohort tables and cached JSON payloads."""

from __future__ import annotations

from typing import Any

from .types import EXACTNESS_STATUS_EXACT, BillingActionReport

from .report_exactness import block_exactness_status


def exemption_gap_try(report: BillingActionReport) -> float:
    """Patient katılım payı exemption gap when copay block is exact."""
    copay = report.copay
    if block_exactness_status(copay) != EXACTNESS_STATUS_EXACT or not copay.is_exempt:
        return 0.0
    waived = float(getattr(copay, "patient_copay_waived_total_try", 0.0) or 0.0)
    if waived <= 0:
        waived = copay.total_copay_savings_try + copay.rx_copay_savings_try
    return round(waived, 2)


def total_opportunity_try(report: BillingActionReport) -> float:
    """Hospital SGK recoverable plus exemption gap (cohort ranking / directory display)."""
    return round(report.total_recoverable_try + exemption_gap_try(report), 2)


def _top_action_type_from_savings(savings: dict[str, float]) -> str:
    if not any(v > 0 for v in savings.values()):
        return "none"
    return max(savings, key=lambda k: savings[k])


def _get_top_action_type(report: BillingActionReport) -> str:
    """Determine the primary action type for a patient report."""
    return _top_action_type_from_savings(
        {
            "session_uplift": report.session_uplift.total_uplift_try,
            "drg_uplift": report.drg_uplift.confirmed_uplift_try,
            "blood_uplift": report.blood_uplift.confirmed_uplift_try,
            "material_uplift": report.material_uplift.confirmed_uplift_try,
            "procedure_addon_uplift": report.procedure_addon_uplift.confirmed_uplift_try,
            "strategy": report.billing_strategy.uplift_savings_try,
            "capture_gap": report.capture_gap_try,
            "package_adequacy_review": report.package_adequacy_review_try,
            "gazette_repricing": report.gazette_repricing_try,
            "medula_playbook": float(report.medula_playbook_entry_count),
            "lab": report.compliance_adjustment_try,
            "copay": float(
                getattr(report.copay, "patient_copay_waived_total_try", 0.0)
                or (
                    report.copay.total_copay_savings_try
                    + report.copay.rx_copay_savings_try
                )
            ),
        }
    )


def patient_recovery_summary_entry(report: BillingActionReport) -> dict[str, Any]:
    """Compact per-patient recovery row for cohort tables."""
    gap = exemption_gap_try(report)
    return {
        "patient_id": report.patient_id,
        "total_recoverable_try": report.total_recoverable_try,
        "sgk_uplift_try": report.sgk_uplift_try,
        "compliance_adjustment_try": report.compliance_adjustment_try,
        "exemption_gap_try": gap,
        "total_opportunity_try": total_opportunity_try(report),
        "priority": report.priority,
        "action_count": report.action_count,
        "top_action_type": _get_top_action_type(report),
    }


def _exemption_gap_from_copay_payload(copay: dict[str, Any] | None) -> float:
    if not copay or str(copay.get("exactness_status") or "") != EXACTNESS_STATUS_EXACT:
        return 0.0
    if not copay.get("is_exempt"):
        return 0.0
    waived = float(copay.get("patient_copay_waived_total_try") or 0)
    if waived <= 0:
        waived = float(copay.get("total_copay_savings_try") or 0) + float(
            copay.get("rx_copay_savings_try") or 0
        )
    return round(waived, 2)


def patient_recovery_summary_from_payload(report: dict[str, Any]) -> dict[str, Any]:
    """Build a recovery summary dict from cached billing report JSON."""
    copay_payload = report.get("copay") or {}
    hospital = float(report.get("total_recoverable_try") or 0)
    gap = _exemption_gap_from_copay_payload(copay_payload)
    savings = {
        "session_uplift": float(
            (report.get("session_uplift") or {}).get("total_uplift_try") or 0
        ),
        "drg_uplift": float(
            (report.get("drg_uplift") or {}).get("confirmed_uplift_try") or 0
        ),
        "blood_uplift": float(
            (report.get("blood_uplift") or {}).get("confirmed_uplift_try") or 0
        ),
        "material_uplift": float(
            (report.get("material_uplift") or {}).get("confirmed_uplift_try") or 0
        ),
        "lab": float(report.get("compliance_adjustment_try") or 0),
        "copay": gap,
        "strategy": float((report.get("billing_strategy") or {}).get("uplift_savings_try") or 0),
    }
    return {
        "patient_id": str(report.get("patient_id") or ""),
        "total_recoverable_try": hospital,
        "sgk_uplift_try": float(report.get("sgk_uplift_try") or hospital),
        "compliance_adjustment_try": float(report.get("compliance_adjustment_try") or 0),
        "exemption_gap_try": gap,
        "total_opportunity_try": round(hospital + gap, 2),
        "priority": str(report.get("priority") or "low"),
        "action_count": int(report.get("action_count") or 0),
        "top_action_type": _top_action_type_from_savings(savings),
    }

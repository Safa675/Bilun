"""Per-patient recovery summary rows for cohort tables and cached JSON payloads."""

from __future__ import annotations

from typing import Any

from .types import (
    EXACTNESS_STATUS_EXACT,
    AnesteziPuaniReview,
    BillingActionReport,
    BillingStrategyRecommendation,
    BloodComponentUplift,
    DrgUpliftRecommendation,
    IcuPuaniReview,
    MaterialUplift,
    ProcedureAddonUplift,
    RefakatciReview,
    SessionPricingUplift,
    YatakPuaniReview,
    YenidoganYatakReview,
)

from .report_exactness import block_exactness_status


def _amount(value: Any) -> float | None:
    return float(value) if value is not None else None


def _complete_sum(*amounts: float | None) -> float | None:
    if any(amount is None for amount in amounts):
        return None
    return round(sum(amount for amount in amounts if amount is not None), 2)


def exemption_gap_try(report: BillingActionReport) -> float | None:
    """Patient katılım payı exemption gap when copay block is exact."""
    copay = report.copay
    if block_exactness_status(copay) != EXACTNESS_STATUS_EXACT:
        return None
    if not copay.is_exempt:
        return 0.0
    waived = copay.patient_copay_waived_total_try
    if waived is not None:
        return round(waived, 2)
    return _complete_sum(copay.total_copay_savings_try, copay.rx_copay_savings_try)


def total_opportunity_try(report: BillingActionReport) -> float | None:
    """Hospital SGK recoverable plus exemption gap (cohort ranking / directory display)."""
    return _complete_sum(report.total_recoverable_try, exemption_gap_try(report))


def _top_action_type_from_savings(savings: dict[str, float]) -> str:
    if not any(v > 0 for v in savings.values()):
        return "none"
    return max(savings, key=lambda k: savings[k])


def _get_top_action_type(report: BillingActionReport) -> str:
    """Determine the primary action type for a patient report."""
    waived = getattr(report.copay, "patient_copay_waived_total_try", None)
    return _top_action_type_from_savings(
        {
            "session_uplift": report.session_uplift.total_uplift_try,
            "drg_uplift": report.drg_uplift.confirmed_uplift_try,
            "blood_uplift": report.blood_uplift.confirmed_uplift_try,
            "yatak_puani": report.yatak_puani.confirmed_yatak_try,
            "material_uplift": report.material_uplift.confirmed_uplift_try,
            "procedure_addon_uplift": report.procedure_addon_uplift.confirmed_uplift_try,
            "strategy": report.billing_strategy.uplift_savings_try,
            "capture_gap": report.capture_gap_try or 0.0,
            "package_adequacy_review": report.package_adequacy_review_try or 0.0,
            "medula_playbook": float(report.medula_playbook_entry_count),
            "lab": report.compliance_adjustment_try or 0.0,
            "copay": (
                waived
                if waived is not None
                else _complete_sum(
                    report.copay.total_copay_savings_try,
                    report.copay.rx_copay_savings_try,
                )
            ) or 0.0,
            # The puan motors that were missing here come last, in BILLING_BLOCK_SPECS order:
            # `max` keeps the first of equal amounts, so a tie still goes to the key it went to before.
            "icu_puani": report.icu_puani.confirmed_icu_try,
            "yenidogan_yatak": report.yenidogan_yatak.confirmed_yenidogan_yatak_try,
            "refakatci": report.refakatci.confirmed_refakat_try,
            "anestezi_puani": report.anestezi_puani.confirmed_anestezi_try,
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


def _exemption_gap_from_copay_payload(copay: dict[str, Any] | None) -> float | None:
    if not copay or str(copay.get("exactness_status") or "") != EXACTNESS_STATUS_EXACT:
        return None
    if not copay.get("is_exempt"):
        return 0.0
    waived = _amount(copay.get("patient_copay_waived_total_try"))
    if waived is not None:
        return round(waived, 2)
    return _complete_sum(
        _amount(copay.get("total_copay_savings_try")),
        _amount(copay.get("rx_copay_savings_try")),
    )


def _block_amount(
    report: dict[str, Any],
    name: str,
    block_type: type,
    amount: str,
    rows: str = "opportunities",
) -> float:
    """What the live path reads as ``getattr(report.<name>, amount)``, taken from a cached payload.

    The cache keeps dataclass fields only (``json_ready``), so the amount properties of a block
    (``confirmed_*_try``, ``total_uplift_try``, ``uplift_savings_try``) are normally not in a payload:
    the block is rebuilt from its rows and the same property is read. An amount the payload does carry
    (the billing endpoint's serializer adds some of them) is used as it is.
    """
    block = report.get(name) or {}
    stored = block.get(amount)
    if stored is not None:
        return float(stored)
    return float(getattr(block_type(**{rows: list(block.get(rows) or [])}), amount))


def patient_recovery_summary_from_payload(report: dict[str, Any]) -> dict[str, Any]:
    """Build a recovery summary dict from cached billing report JSON."""
    copay_payload = report.get("copay") or {}
    hospital = _amount(report.get("total_recoverable_try"))
    gap = _exemption_gap_from_copay_payload(copay_payload)
    # Mirror the 16 keys in _get_top_action_type, in the same order, so cached-payload and live-object
    # paths produce identical top_action_type (audit finding #12).
    savings = {
        "session_uplift": _block_amount(
            report, "session_uplift", SessionPricingUplift, "total_uplift_try"
        ),
        "drg_uplift": _block_amount(
            report, "drg_uplift", DrgUpliftRecommendation, "confirmed_uplift_try"
        ),
        "blood_uplift": _block_amount(
            report, "blood_uplift", BloodComponentUplift, "confirmed_uplift_try"
        ),
        "yatak_puani": _block_amount(
            report, "yatak_puani", YatakPuaniReview, "confirmed_yatak_try"
        ),
        "material_uplift": _block_amount(
            report, "material_uplift", MaterialUplift, "confirmed_uplift_try"
        ),
        "procedure_addon_uplift": _block_amount(
            report, "procedure_addon_uplift", ProcedureAddonUplift, "confirmed_uplift_try"
        ),
        "strategy": _block_amount(
            report,
            "billing_strategy",
            BillingStrategyRecommendation,
            "uplift_savings_try",
            rows="recommendations",
        ),
        "capture_gap": float(report.get("capture_gap_try") or 0),
        "package_adequacy_review": float(report.get("package_adequacy_review_try") or 0),
        "medula_playbook": float(report.get("medula_playbook_entry_count") or 0),
        "lab": float(report.get("compliance_adjustment_try") or 0),
        "copay": gap or 0.0,
        "icu_puani": _block_amount(report, "icu_puani", IcuPuaniReview, "confirmed_icu_try"),
        "yenidogan_yatak": _block_amount(
            report, "yenidogan_yatak", YenidoganYatakReview, "confirmed_yenidogan_yatak_try"
        ),
        "refakatci": _block_amount(report, "refakatci", RefakatciReview, "confirmed_refakat_try"),
        "anestezi_puani": _block_amount(
            report, "anestezi_puani", AnesteziPuaniReview, "confirmed_anestezi_try"
        ),
    }
    return {
        "patient_id": str(report.get("patient_id") or ""),
        "total_recoverable_try": hospital,
        "sgk_uplift_try": (
            _amount(report["sgk_uplift_try"]) if "sgk_uplift_try" in report else hospital
        ),
        "compliance_adjustment_try": _amount(report.get("compliance_adjustment_try")),
        "exemption_gap_try": gap,
        "total_opportunity_try": _complete_sum(hospital, gap),
        "priority": str(report.get("priority") or "low"),
        "action_count": int(report.get("action_count") or 0),
        "top_action_type": _top_action_type_from_savings(savings),
    }

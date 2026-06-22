"""Structured recommended-action rows for billing reports."""

from __future__ import annotations

from typing import Any

from ..money import money_round_half_up_opt as _money
from .types import BillingActionReport

_MATERIAL_KIND_SUT_SECTION: dict[str, str] = {
    "material_pre_auth": "3.1.2",
    "material_miat": "3.1.4",
    "material_miat_interval": "3.1.4",
    "material_bundling": "EK-3B-1",
    "material_prose_bundling": "3.1.5",
    "material_specialty_prose": "3.3",
}


def _material_row_billed_try(row: dict[str, object]) -> float | None:
    for key in ("price_try", "billed_try", "risk_amount"):
        value = row.get(key)
        if value is None:
            continue
        try:
            amount = float(value)
        except (TypeError, ValueError):
            continue
        if amount > 0:
            return amount
    return None


def _material_row_detail(row: dict[str, object]) -> str | None:
    for key in ("note", "detail", "message", "rule_id"):
        value = row.get(key)
        if value:
            return str(value)
    return None


def _action_row(
    *,
    action_id: str,
    surface: str,
    kind: str,
    claim_id: str | None = None,
    procedure_code: str | None = None,
    procedure_name: str | None = None,
    material_code: str | None = None,
    drug_code: str | None = None,
    sgk_uplift_try: float | None = None,
    audit_risk_try: float | None = None,
    compliance_savings_try: float | None = None,
    billed_try: float | None = None,
    material_name: str | None = None,
    detail: str | None = None,
    sut_section_id: str | None = None,
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "surface": surface,
        "kind": kind,
        "claim_id": claim_id,
        "procedure_code": procedure_code,
        "procedure_name": procedure_name,
        "material_code": material_code,
        "drug_code": drug_code,
        "sgk_uplift_try": _money(sgk_uplift_try),
        "audit_risk_try": _money(audit_risk_try),
        "compliance_savings_try": _money(compliance_savings_try),
        "billed_try": _money(billed_try),
        "material_name": material_name,
        "detail": detail,
        "sut_section_id": sut_section_id,
    }


def collect_billing_actions(report: BillingActionReport) -> list[dict[str, Any]]:
    """Return one structured row per counted recommended action."""

    actions: list[dict[str, Any]] = []

    for index, test in enumerate(report.lab.flagged_tests):
        actions.append(
            _action_row(
                action_id=f"lab:{test.get('sut_code') or index}",
                surface="lab",
                kind=str(test.get("flag_type") or "lab_flag"),
                procedure_code=test.get("sut_code"),
                procedure_name=test.get("test_name"),
                compliance_savings_try=test.get("savings_try"),
                detail=test.get("detail"),
            )
        )

    if report.copay.is_exempt:
        gap = report.copay.patient_copay_waived_total_try or report.copay.total_copay_savings_try
        actions.append(
            _action_row(
                action_id="copay:ek1a_exemption_review",
                surface="copay",
                kind="exemption_review",
                compliance_savings_try=gap if gap and gap > 0 else None,
                detail=report.copay.exemption_disease or None,
                sut_section_id="1.8.5(7)",
            )
        )

    for index, row in enumerate(report.billing_strategy.recommendations):
        if row.get("type") == "informational":
            continue
        code = row.get("procedure_code")
        claim_id = row.get("claim_id")
        kind = str(row.get("type") or row.get("recommendation_kind") or "strategy")
        savings = row.get("savings_try") or row.get("recoverable_uplift_try")
        included = row.get("included_in_sgk_total")
        sgk = savings if included is not False and savings else None
        actions.append(
            _action_row(
                action_id=f"strategy:{claim_id}:{code or index}:{kind}",
                surface="billing_strategy",
                kind=kind,
                claim_id=claim_id,
                procedure_code=code or row.get("recommended_package_code"),
                procedure_name=row.get("procedure_name"),
                sgk_uplift_try=sgk,
                detail=row.get("detail"),
                sut_section_id=row.get("sut_section_id") or row.get("sut_section"),
            )
        )

    for surface_name, block, uplift_field in (
        ("session_uplift", report.session_uplift, "recoverable_uplift_try"),
        ("drg_uplift", report.drg_uplift, "recoverable_uplift_try"),
        ("blood_uplift", report.blood_uplift, "recoverable_uplift_try"),
        ("material_uplift", report.material_uplift, "recoverable_uplift_try"),
        ("care_setting_review", report.care_setting_review, "recoverable_uplift_try"),
        ("procedure_addon_uplift", report.procedure_addon_uplift, "recoverable_uplift_try"),
        ("drg_package_adequacy", report.drg_package_adequacy, "recoverable_uplift_try"),
        ("gazette_repricing", report.gazette_repricing, "recoverable_repricing_try"),
    ):
        opportunities = getattr(block, "opportunities", [])
        for index, row in enumerate(opportunities):
            actions.append(
                _action_row(
                    action_id=f"{surface_name}:{row.get('claim_id')}:{index}",
                    surface=surface_name,
                    kind=str(row.get("type") or row.get("recommendation_kind") or surface_name),
                    claim_id=row.get("claim_id"),
                    procedure_code=row.get("procedure_code")
                    or row.get("trigger_procedure_code"),
                    procedure_name=row.get("procedure_name"),
                    material_code=row.get("material_code"),
                    sgk_uplift_try=row.get(uplift_field) or row.get("recoverable_uplift_try"),
                    detail=row.get("detail"),
                    sut_section_id=row.get("sut_section_id") or row.get("sut_section"),
                )
            )

    for index, row in enumerate(report.procedure_capture_gap.opportunities):
        actions.append(
            _action_row(
                action_id=f"procedure_capture:{row.get('claim_id')}:{index}",
                surface="procedure_capture_gap",
                kind=str(row.get("type") or "capture_gap"),
                claim_id=row.get("claim_id"),
                procedure_code=row.get("procedure_code"),
                procedure_name=row.get("procedure_name"),
                sgk_uplift_try=row.get("recoverable_gap_try"),
                detail=row.get("detail"),
            )
        )

    for index, row in enumerate(report.medula_rejection_playbook.entries):
        actions.append(
            _action_row(
                action_id=f"medula_playbook:{row.get('claim_id')}:{row.get('sonuc_kodu') or index}",
                surface="medula_playbook",
                kind=str(row.get("playbook_id") or "medula_rejection"),
                claim_id=row.get("claim_id"),
                detail=row.get("detail") or row.get("playbook_id"),
                sut_section_id=row.get("sut_section_id"),
            )
        )

    for index, row in enumerate(report.claim_submission_checklist.items):
        actions.append(
            _action_row(
                action_id=f"claim_checklist:{row.get('claim_id')}:{index}",
                surface="claim_checklist",
                kind=str(row.get("checklist_kind") or "submission_check"),
                claim_id=row.get("claim_id"),
                procedure_code=row.get("procedure_code"),
                material_code=row.get("material_code"),
                detail=row.get("detail"),
            )
        )

    for index, row in enumerate(report.drug_indication.violations):
        actions.append(
            _action_row(
                action_id=f"drug_indication:{row.get('claim_id')}:{index}",
                surface="drug_indication",
                kind=str(row.get("violation_kind") or "drug_indication"),
                claim_id=row.get("claim_id"),
                drug_code=row.get("drug_code") or row.get("inn"),
                detail=row.get("detail"),
                sut_section_id=row.get("sut_section_id"),
            )
        )

    material_lists = (
        ("pre_auth_required", "material_pre_auth"),
        ("miat_restricted", "material_miat"),
        ("bundled_separate_billing", "material_bundling"),
        ("miat_interval_violations", "material_miat_interval"),
        ("prose_bundling_violations", "material_prose_bundling"),
        ("specialty_prose_violations", "material_specialty_prose"),
    )
    materials = report.materials
    for attr, kind in material_lists:
        for index, row in enumerate(getattr(materials, attr, []) or []):
            row_dict = row if isinstance(row, dict) else {}
            actions.append(
                _action_row(
                    action_id=f"materials:{kind}:{row_dict.get('claim_id')}:{index}",
                    surface="materials",
                    kind=kind,
                    claim_id=row_dict.get("claim_id"),
                    procedure_code=row_dict.get("procedure_code"),
                    material_code=row_dict.get("material_code") or row_dict.get("sut_code"),
                    material_name=row_dict.get("material_name"),
                    billed_try=_material_row_billed_try(row_dict),
                    detail=_material_row_detail(row_dict),
                    sut_section_id=(
                        row_dict.get("sut_section_id")
                        or row_dict.get("sut_section")
                        or _MATERIAL_KIND_SUT_SECTION.get(kind)
                    ),
                )
            )

    return actions


def count_billing_actions(report: BillingActionReport) -> int:
    return len(collect_billing_actions(report))

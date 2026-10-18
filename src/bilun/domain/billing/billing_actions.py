"""Structured recommended-action rows for billing reports."""

from __future__ import annotations

from typing import Any

from ..money import money_round_half_up_opt as _money
from ..sut.clause_reference import RULE_TYPE_COPAY_WAIVER, sut_clause_reference
from .types import BillingActionReport, CopayOptimization
from .drug_clinical_evidence import (
    bounded_clinical_restrictions, clinical_evidence_payload, source_authority_payload,
)

_MATERIAL_KIND_SUT_SECTION: dict[str, str] = {
    "material_pre_auth": "3.1.2",
    "material_miat": "3.1.4",
    "material_miat_interval": "3.1.4",
    "material_bundling": "EK-3B-1",
    "material_prose_bundling": "3.1.5",
    "material_specialty_prose": "3.3",
}

# Mirror of frontend/src/lib/recommendedActions.ts getFindingType (UI badge
# taxonomy) so the backend can serve finding_type directly; billing_strategy
# keeps its kind-based special case.
_COMPLIANCE_SURFACES: frozenset[str] = frozenset(
    {"materials", "drug_indication", "lab", "audit_exposure"}
)
_OPPORTUNITY_SURFACES: frozenset[str] = frozenset(
    {
        "session_uplift",
        "drg_uplift",
        "blood_uplift",
        "yatak_puani",
        "anestezi_puani",
        "refakatci",
        "material_uplift",
        "procedure_addon_uplift",
        "procedure_capture_gap",
        "drg_package_adequacy",
        "care_setting_review",
        "copay",
    }
)
_INFORMATIONAL_SURFACES: frozenset[str] = frozenset({"medula_playbook", "claim_checklist"})


def _finding_type(surface: str, kind: str | None = None) -> str:
    """User-facing finding class for a row; mirrors frontend getFindingType.

    billing_strategy is classified by kind (parity with the frontend); every
    other surface is surface-primary and unlisted surfaces default to
    informational.
    """
    if surface == "billing_strategy":
        if kind == "optional_override":
            return "opportunity"
        if kind in ("compliance_violation", "mandatory_compliance", "strategy"):
            return "compliance"
        return "informational"
    if surface in _COMPLIANCE_SURFACES:
        return "compliance"
    if surface in _OPPORTUNITY_SURFACES:
        return "opportunity"
    if surface in _INFORMATIONAL_SURFACES:
        return "informational"
    return "informational"


# Reason-specific copay exemption review rows (Track E, plan Aşama 1):
# category -> (action_id, clause_coordinate, annex). Coordinates use the
# canonical dot form ("1.8.5.(7)"), never the legacy "1.8.5(7)" string.
_COPAY_CATEGORY_ROW_SPECS: dict[str, tuple[str, str, str]] = {
    "ek1a_chronic": ("copay:ek1a_exemption_review", "1.8.5.(7)", "EK-1/A"),
    "acil_servis": ("copay:acil_servis_exemption_review", "1.8.5", ""),
    "is_kazasi_meslek": ("copay:is_kazasi_exemption_review", "1.8.5", ""),
    "yesil_kart": ("copay:yesil_kart_exemption_review", "1.8.5", ""),
    "sehit_gazi": ("copay:sehit_gazi_exemption_review", "1.8.5", ""),
    "vatani_hizmet": ("copay:vatani_hizmet_exemption_review", "1.8.5", ""),
    "koruyucu_saglik": ("copay:koruyucu_saglik_exemption_review", "1.8.5", ""),
}
_COPAY_EK4D_ROW_SPEC: tuple[str, str, str] = (
    "copay:ek4d_exemption_review",
    "1.8.2.(3)",
    "EK-4/D",
)
_COPAY_FALLBACK_ROW_SPEC: tuple[str, str, str] = ("copay:exemption_review", "1.8.5", "")


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
    material_line_id: str | None = None,
    drug_code: str | None = None,
    drug_name: str | None = None,
    drug_claim_line_id: str | None = None,
    finding_id: str | None = None,
    severity: str | None = None,
    applicability_status: str | None = None,
    evaluation_status: str | None = None,
    observed_icd10_codes: list[str] | None = None,
    matched_icd10_codes: list[str] | None = None,
    unmatched_icd10_codes: list[str] | None = None,
    eligible_routes: list[dict[str, Any]] | None = None,
    eligible_route_count: int | None = None,
    eligible_routes_truncated: bool | None = None,
    observed_icd10_count: int | None = None,
    observed_icd10_truncated: bool | None = None,
    clinical_restrictions: list[dict[str, Any]] | None = None,
    source_authority: dict[str, Any] | None = None,
    selected_rule_id: str | None = None,
    recommended_action_tr: str | None = None,
    sgk_uplift_try: float | None = None,
    audit_risk_try: float | None = None,
    compliance_savings_try: float | None = None,
    billed_try: float | None = None,
    material_name: str | None = None,
    detail: str | None = None,
    sut_section_id: str | None = None,
    clause_ref: dict | None = None,
    finding_type: str | None = None,
    message_code: str | None = None,
    message_params: dict | None = None,
) -> dict[str, Any]:
    authority = source_authority_payload(source_authority)
    clinical = clinical_evidence_payload(bounded_clinical_restrictions(clinical_restrictions))
    return {
        "action_id": action_id,
        "surface": surface,
        "kind": kind,
        "claim_id": claim_id,
        "procedure_code": procedure_code,
        "procedure_name": procedure_name,
        "material_code": material_code,
        "material_line_id": material_line_id,
        "drug_code": drug_code,
        "drug_name": drug_name,
        "drug_claim_line_id": drug_claim_line_id,
        "finding_id": finding_id,
        "severity": severity,
        "applicability_status": applicability_status,
        "evaluation_status": evaluation_status,
        "observed_icd10_codes": observed_icd10_codes,
        "matched_icd10_codes": matched_icd10_codes,
        "unmatched_icd10_codes": unmatched_icd10_codes,
        "eligible_routes": eligible_routes,
        "eligible_route_count": eligible_route_count,
        "eligible_routes_truncated": eligible_routes_truncated,
        "observed_icd10_count": observed_icd10_count,
        "observed_icd10_truncated": observed_icd10_truncated,
        **clinical,
        **authority,
        **({"selected_rule_id": selected_rule_id} if clinical or authority else {}),
        "recommended_action_tr": recommended_action_tr,
        "sgk_uplift_try": _money(sgk_uplift_try),
        "audit_risk_try": _money(audit_risk_try),
        "compliance_savings_try": _money(compliance_savings_try),
        "billed_try": _money(billed_try),
        "material_name": material_name,
        "detail": detail,
        "sut_section_id": sut_section_id,
        "clause_ref": clause_ref,
        "finding_type": finding_type,
        "message_code": message_code,
        "message_params": message_params,
    }


# Puan motors whose rows must add up to the block's component of ``sgk_uplift_try``
# (``confirmed_anestezi_try`` / ``confirmed_refakat_try``).
_SGK_COUNTED_ONLY_SURFACES: frozenset[str] = frozenset({"anestezi_puani", "refakatci"})


def _sgk_counted_uplift(row: dict[str, Any]) -> float | None:
    """The uplift an opportunity adds to the SGK headline, or None when it adds nothing.

    Mirrors ``confirmed_anestezi_try`` / ``confirmed_refakat_try``: a row flagged out of the
    SGK total makes no action row, and neither does one without a positive amount (companion
    days already billed; day-case, ICU and package-window suppressions).
    """
    if not row.get("included_in_sgk_total", True):
        return None
    amount = row.get("recoverable_uplift_try")
    if amount is None:
        amount = row.get("expected_try") or 0.0
    return float(amount) if float(amount) > 0 else None


def _detail_with_notes(row: dict[str, Any]) -> str | None:
    """The row's detail followed by its verification notes (SUT §2.6.3.(2): the stay certificate)."""
    detail = row.get("detail")
    notes = [str(note) for note in row.get("suppression_notes") or [] if note]
    return " ".join([str(detail), *notes]) if detail and notes else detail


def _copay_exemption_rows(copay: CopayOptimization) -> list[dict[str, Any]]:
    """Reason-specific copay exemption-review rows (EK-1/A, EK-4/D, acil, ...).

    Emits one row per identified exemption ground instead of the previous
    single hardcoded EK-1/A row: EK-4/D, emergency (acil), work-accident
    (iş kazası), yeşil kart and other grounds each get their own action row.
    """
    categories: list[str] = []
    for source in copay.exemption_sources:
        category = str(source.get("category") or "") if isinstance(source, dict) else ""
        if category and category not in categories:
            categories.append(category)

    ek4d_present = any(
        str(ground).startswith("ek4d") for ground in copay.rx_copay_savings_by_ground
    ) or any(
        str(row.get("exemption_ground") or "").startswith("ek4d")
        for row in copay.rate_corrections
        if isinstance(row, dict)
    )

    if not copay.is_exempt and not ek4d_present:
        return []

    # (category, action_id, clause_coordinate, annex), sources order preserved.
    row_specs: list[tuple[str, str, str, str]] = []
    for category in categories:
        spec = _COPAY_CATEGORY_ROW_SPECS.get(category)
        if spec is not None:
            row_specs.append((category, *spec))
    if ek4d_present:
        row_specs.append(("ek4d", *_COPAY_EK4D_ROW_SPEC))
    if copay.is_exempt and not row_specs:
        row_specs.append(("", *_COPAY_FALLBACK_ROW_SPEC))

    # B-H5: patient_copay_waived_total_try IS the true total (visit + rx
    # copay savings). The previous `or total_copay_savings_try` fallback
    # was a bug: when the true total is 0 (falsy), it fell back to
    # total_copay_savings_try which holds ONLY visit savings (legacy
    # misleading field name), injecting a non-zero gap where there is
    # none. Use the true total directly.
    gap = copay.patient_copay_waived_total_try
    waived_total = gap if gap and gap > 0 else None

    # Money rides the PRIMARY ground row only (primary_exemption_category
    # when it matches an emitted row, else the first row).
    primary_index = 0
    if copay.primary_exemption_category:
        for index, (category, *_spec) in enumerate(row_specs):
            if category == copay.primary_exemption_category:
                primary_index = index
                break

    rows: list[dict[str, Any]] = []
    for index, (_category, action_id, coordinate, annex) in enumerate(row_specs):
        rows.append(
            _action_row(
                action_id=action_id,
                surface="copay",
                kind="exemption_review",
                compliance_savings_try=waived_total if index == primary_index else None,
                detail=copay.exemption_disease or None,
                sut_section_id=coordinate,
                clause_ref=sut_clause_reference(
                    coordinate, rule_type=RULE_TYPE_COPAY_WAIVER, annex=annex
                ).to_dict(),
                finding_type=_finding_type("copay"),
            )
        )
    return rows


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
                finding_type=_finding_type("lab"),
            )
        )

    actions.extend(_copay_exemption_rows(report.copay))

    for index, row in enumerate(report.billing_strategy.recommendations):
        if row.get("type") == "informational":
            continue
        message_code = row.get("message_code")
        savings = row.get("savings_try") or row.get("recoverable_uplift_try")
        if (
            message_code in ("claim_package_ok", "claim_itemized_ok")
            and not (savings and savings > 0)
        ):
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
                finding_type=_finding_type("billing_strategy", kind),
                message_code=row.get("message_code"),
                message_params=row.get("message_params"),
            )
        )

    for surface_name, block, uplift_field in (
        ("session_uplift", report.session_uplift, "recoverable_uplift_try"),
        ("drg_uplift", report.drg_uplift, "recoverable_uplift_try"),
        ("blood_uplift", report.blood_uplift, "recoverable_uplift_try"),
        ("yatak_puani", report.yatak_puani, "recoverable_uplift_try"),
        ("anestezi_puani", report.anestezi_puani, "recoverable_uplift_try"),
        ("refakatci", report.refakatci, "recoverable_uplift_try"),
        ("material_uplift", report.material_uplift, "recoverable_uplift_try"),
        ("care_setting_review", report.care_setting_review, "recoverable_uplift_try"),
        ("procedure_addon_uplift", report.procedure_addon_uplift, "recoverable_uplift_try"),
        ("drg_package_adequacy", report.drg_package_adequacy, "recoverable_uplift_try"),
    ):
        opportunities = getattr(block, "opportunities", [])
        for index, row in enumerate(opportunities):
            detail = row.get("detail")
            if surface_name == "yatak_puani":
                raw_uplift = (
                    row.get("recoverable_uplift_try")
                    if row.get("recoverable_uplift_try") is not None
                    else row.get("expected_yatak_try")
                )
                if raw_uplift is not None and float(raw_uplift) <= 0:
                    continue
                sgk_uplift = raw_uplift
            elif surface_name in _SGK_COUNTED_ONLY_SURFACES:
                sgk_uplift = _sgk_counted_uplift(row)
                if sgk_uplift is None:
                    continue
                detail = _detail_with_notes(row)
            else:
                sgk_uplift = row.get(uplift_field) or row.get("recoverable_uplift_try")
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
                    material_name=row.get("material_name"),
                    sgk_uplift_try=sgk_uplift,
                    detail=detail,
                    sut_section_id=row.get("sut_section_id") or row.get("sut_section"),
                    finding_type=_finding_type(surface_name),
                )
            )

    for row in report.audit_exposure_rows:
        risk = row.get("risk_amount_try")
        actions.append(
            _action_row(
                action_id=(
                    f"audit_exposure:{row.get('claim_id')}:{row.get('kind')}:"
                    f"{row.get('procedure_line_id')}"
                ),
                surface="audit_exposure",
                kind=str(row.get("kind") or "audit_exposure"),
                claim_id=row.get("claim_id"),
                procedure_code=row.get("procedure_code"),
                procedure_name=row.get("procedure_name"),
                audit_risk_try=risk,
                billed_try=risk,
                detail=row.get("detail"),
                sut_section_id=row.get("sut_section"),
                finding_type=_finding_type("audit_exposure"),
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
                finding_type=_finding_type("procedure_capture_gap"),
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
                finding_type=_finding_type("medula_playbook"),
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
                finding_type=_finding_type("claim_checklist"),
            )
        )

    if report.drug_indication.findings:
        for finding in report.drug_indication.findings:
            route_section = next(
                (route.sut_section for route in finding.eligible_routes if route.sut_section),
                None,
            )
            actions.append(
                _action_row(
                    action_id=finding.finding_id,
                    surface="drug_indication",
                    kind=finding.finding_kind,
                    claim_id=finding.claim_id,
                    drug_code=finding.drug_code,
                    drug_name=finding.drug_name,
                    drug_claim_line_id=finding.drug_claim_line_id,
                    finding_id=finding.finding_id,
                    severity=finding.severity,
                    applicability_status=finding.applicability_status,
                    evaluation_status=finding.evaluation_status,
                    observed_icd10_codes=list(finding.observed_icd10_codes),
                    matched_icd10_codes=list(finding.matched_icd10_codes),
                    unmatched_icd10_codes=list(finding.unmatched_icd10_codes),
                    eligible_routes=[
                        route.to_dict() for route in finding.eligible_routes
                    ],
                    eligible_route_count=finding.eligible_route_count,
                    eligible_routes_truncated=finding.eligible_routes_truncated,
                    observed_icd10_count=finding.observed_icd10_count,
                    observed_icd10_truncated=finding.observed_icd10_truncated,
                    clinical_restrictions=[x.to_dict() for x in finding.clinical_restrictions],
                    source_authority=finding.source_authority,
                    selected_rule_id=finding.selected_rule_id,
                    detail=finding.explanation_tr,
                    recommended_action_tr=finding.recommended_action_tr,
                    sut_section_id=route_section,
                    finding_type=_finding_type("drug_indication"),
                )
            )
    else:
        for index, row in enumerate(report.drug_indication.violations):
            actions.append(
                _action_row(
                    action_id=row.get("finding_id")
                    or f"drug_indication:{row.get('claim_id')}:{index}",
                    surface="drug_indication",
                    kind=str(row.get("violation_kind") or "drug_indication"),
                    claim_id=row.get("claim_id"),
                    drug_code=row.get("drug_code") or row.get("inn"),
                    drug_name=row.get("drug_name"),
                    drug_claim_line_id=row.get("drug_claim_line_id"),
                    finding_id=row.get("finding_id"),
                    severity=row.get("severity"),
                    applicability_status=row.get("applicability_status"),
                    evaluation_status=row.get("evaluation_status"),
                    observed_icd10_codes=row.get("observed_icd10_codes"),
                    matched_icd10_codes=row.get("matched_icd10_codes"),
                    unmatched_icd10_codes=row.get("unmatched_icd10_codes"),
                    eligible_routes=row.get("eligible_routes"),
                    clinical_restrictions=row.get("clinical_restrictions"),
                    source_authority=row.get("source_authority"),
                    selected_rule_id=row.get("selected_rule_id"),
                    eligible_route_count=row.get("eligible_route_count"),
                    eligible_routes_truncated=row.get("eligible_routes_truncated"),
                    observed_icd10_count=row.get("observed_icd10_count"),
                    observed_icd10_truncated=row.get("observed_icd10_truncated"),
                    detail=row.get("detail") or row.get("message_tr"),
                    sut_section_id=row.get("sut_section_id") or row.get("sut_section"),
                    finding_type=_finding_type("drug_indication"),
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
                    material_line_id=row_dict.get("material_line_id"),
                    material_name=row_dict.get("material_name"),
                    billed_try=_material_row_billed_try(row_dict),
                    detail=_material_row_detail(row_dict),
                    sut_section_id=(
                        row_dict.get("sut_section_id")
                        or row_dict.get("sut_section")
                        or _MATERIAL_KIND_SUT_SECTION.get(kind)
                    ),
                    finding_type=_finding_type("materials"),
                )
            )

    return actions


def count_billing_actions(report: BillingActionReport) -> int:
    return len(collect_billing_actions(report))

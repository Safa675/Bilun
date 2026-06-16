"""
src/bilun/domain/billing/orchestrator.py
Main orchestrators: compute_patient_billing_report, compute_all_billing_reports.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import time
from typing import TYPE_CHECKING, Any

import polars as pl

from .types import (
    BILLING_REPORT_PARTIAL_REASON,
    BILLING_STRATEGY_REQUIRED_INPUTS,
    BILLING_STRATEGY_UNAVAILABLE_REASON,
    BLOOD_UPLIFT_REQUIRED_INPUTS,
    BLOOD_UPLIFT_UNAVAILABLE_REASON,
    CARE_SETTING_REVIEW_REQUIRED_INPUTS,
    CARE_SETTING_REVIEW_UNAVAILABLE_REASON,
    COHORT_RECOVERY_PARTIAL_REASON,
    COPAY_REQUIRED_INPUTS,
    COPAY_UNAVAILABLE_REASON,
    DRG_PACKAGE_ADEQUACY_REQUIRED_INPUTS,
    DRG_PACKAGE_ADEQUACY_UNAVAILABLE_REASON,
    DRG_UPLIFT_REQUIRED_INPUTS,
    DRG_UPLIFT_UNAVAILABLE_REASON,
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    EXACTNESS_STATUS_NOT_APPLICABLE,
    EXACTNESS_STATUS_PARTIAL,
    GAZETTE_REPRICING_REQUIRED_INPUTS,
    GAZETTE_REPRICING_UNAVAILABLE_REASON,
    MATERIAL_UPLIFT_REQUIRED_INPUTS,
    MATERIAL_UPLIFT_UNAVAILABLE_REASON,
    MATERIALS_PARTIAL_REASON,
    MATERIALS_REQUIRED_INPUTS,
    MEDULA_PLAYBOOK_REQUIRED_INPUTS,
    MEDULA_PLAYBOOK_UNAVAILABLE_REASON,
    BillingActionReport,
    CohortRecoverySummary,
    LabOptimization,
    PROCEDURE_ADDON_UPLIFT_REQUIRED_INPUTS,
    PROCEDURE_ADDON_UPLIFT_UNAVAILABLE_REASON,
    PROCEDURE_CAPTURE_GAP_REQUIRED_INPUTS,
    PROCEDURE_CAPTURE_GAP_UNAVAILABLE_REASON,
    ProcedureAddonUplift,
    ProcedureCaptureGap,
    SESSION_UPLIFT_REQUIRED_INPUTS,
    SESSION_UPLIFT_UNAVAILABLE_REASON,
)
from src.bilun.domain.claims.patient_context import (
    PatientClaimContext,
    build_bill_claim_context,
    build_patient_claim_context,
)
from src.bilun.domain.billing.claim_copay import optimize_copay_from_claims
from src.bilun.domain.billing.claim_materials import precheck_materials_from_claims
from src.bilun.domain.billing.claim_audit_exposure import compute_audit_exposure_from_claims
from src.bilun.domain.billing.claim_blood_uplift import recommend_blood_uplift_from_claims
from src.bilun.domain.billing.claim_care_setting_review import (
    recommend_care_setting_review_from_claims,
)
from src.bilun.domain.billing.claim_procedure_addon_uplift import (
    recommend_procedure_addon_uplift_from_claims,
)
from src.bilun.domain.billing.claim_procedure_capture_gap import (
    recommend_procedure_capture_gap_from_claims,
)
from src.bilun.domain.billing.claim_drg_package_adequacy import (
    recommend_drg_package_adequacy_from_claims,
)
from src.bilun.domain.billing.claim_gazette_repricing import (
    recommend_gazette_repricing_from_claims,
)
from src.bilun.domain.billing.claim_medula_rejection import (
    recommend_medula_rejection_playbook_from_claims,
)
from src.bilun.domain.billing.claim_material_uplift import recommend_material_uplift_from_claims
from src.bilun.domain.billing.claim_drg_uplift import recommend_drg_uplift_from_claims
from src.bilun.domain.billing.claim_session_uplift import recommend_session_uplift_from_claims
from src.bilun.domain.billing.claim_strategy import recommend_billing_strategy_from_claims
from .claim_lab import _optimize_lab_billing_from_claims
from src.bilun.domain.constants import SUT_REQUIRE_CLAIM_LINES

if TYPE_CHECKING:
    from src.bilun.domain.claims.loader import SUTClaimDataset
    from src.bilun.domain.claims.patient_context import PatientClaimContext

logger = logging.getLogger("ilay.sut_billing_optimizer")


def _block_exactness_status(block: Any) -> str:
    status = str(
        getattr(block, "exactness_status", EXACTNESS_STATUS_MISSING_INPUTS) or ""
    ).strip()
    return status or EXACTNESS_STATUS_MISSING_INPUTS


def _exemption_gap_try(report: BillingActionReport) -> float:
    """Patient katılım payı exemption gap when copay block is exact."""
    copay = report.copay
    if _block_exactness_status(copay) != EXACTNESS_STATUS_EXACT or not copay.is_exempt:
        return 0.0
    waived = float(getattr(copay, "patient_copay_waived_total_try", 0.0) or 0.0)
    if waived <= 0:
        waived = copay.total_copay_savings_try + copay.rx_copay_savings_try
    return round(waived, 2)


def _total_opportunity_try(report: BillingActionReport) -> float:
    """Hospital SGK recoverable plus exemption gap (cohort ranking / directory display)."""
    return round(report.total_recoverable_try + _exemption_gap_try(report), 2)


def _sum_compliance_adjustment_try(report: BillingActionReport) -> float:
    """Over-billing corrections (e.g. lab hemogram bundling) — not SGK uplift."""
    if _block_exactness_status(report.lab) != EXACTNESS_STATUS_EXACT:
        return 0.0
    return round(report.lab.total_savings, 2)


def _sum_strategy_uplift_try(report: BillingActionReport) -> float:
    if _block_exactness_status(report.billing_strategy) != EXACTNESS_STATUS_EXACT:
        return 0.0
    return report.billing_strategy.uplift_savings_try


def _sum_session_uplift_try(report: BillingActionReport) -> float:
    if _block_exactness_status(report.session_uplift) != EXACTNESS_STATUS_EXACT:
        return 0.0
    return report.session_uplift.confirmed_uplift_try


def _sum_drg_uplift_try(report: BillingActionReport) -> float:
    if _block_exactness_status(report.drg_uplift) != EXACTNESS_STATUS_EXACT:
        return 0.0
    return report.drg_uplift.confirmed_uplift_try


def _sum_blood_uplift_try(report: BillingActionReport) -> float:
    if _block_exactness_status(report.blood_uplift) != EXACTNESS_STATUS_EXACT:
        return 0.0
    return report.blood_uplift.confirmed_uplift_try


def _sum_material_uplift_try(report: BillingActionReport) -> float:
    if _block_exactness_status(report.material_uplift) != EXACTNESS_STATUS_EXACT:
        return 0.0
    return report.material_uplift.confirmed_uplift_try


def _sum_procedure_addon_uplift_try(report: BillingActionReport) -> float:
    if _block_exactness_status(report.procedure_addon_uplift) != EXACTNESS_STATUS_EXACT:
        return 0.0
    return report.procedure_addon_uplift.confirmed_uplift_try


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


def _dedupe_addon_against_capture(
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


def _sum_sgk_uplift_try(report: BillingActionReport) -> float:
    """Legitimate Kurum ödemesi uplift; excludes compliance lab savings."""
    total = (
        _sum_strategy_uplift_try(report)
        + _sum_session_uplift_try(report)
        + _sum_drg_uplift_try(report)
        + _sum_blood_uplift_try(report)
        + _sum_material_uplift_try(report)
        + _sum_procedure_addon_uplift_try(report)
    )
    return round(total, 2)


def _sum_exact_recoverable_try(report: BillingActionReport) -> float:
    """Alias for ``sgk_uplift_try`` (backward-compatible headline)."""
    return _sum_sgk_uplift_try(report)


def _finalize_report_totals(
    report: BillingActionReport,
    *,
    claim_context: PatientClaimContext | None = None,
) -> None:
    report.compliance_adjustment_try = _sum_compliance_adjustment_try(report)
    report.sgk_uplift_try = _sum_sgk_uplift_try(report)
    report.total_recoverable_try = report.sgk_uplift_try
    if claim_context is not None and claim_context.procedure_lines:
        report.audit_exposure_try = compute_audit_exposure_from_claims(claim_context)
    else:
        report.audit_exposure_try = 0.0
    if (
        _block_exactness_status(report.procedure_capture_gap) == EXACTNESS_STATUS_EXACT
    ):
        report.capture_gap_try = report.procedure_capture_gap.confirmed_gap_try
    else:
        report.capture_gap_try = 0.0
    if (
        _block_exactness_status(report.drg_package_adequacy) == EXACTNESS_STATUS_EXACT
    ):
        report.package_adequacy_review_try = (
            report.drg_package_adequacy.review_uplift_try
        )
    else:
        report.package_adequacy_review_try = 0.0
    if _block_exactness_status(report.gazette_repricing) == EXACTNESS_STATUS_EXACT:
        report.gazette_repricing_try = report.gazette_repricing.review_repricing_try
    else:
        report.gazette_repricing_try = 0.0
    if (
        _block_exactness_status(report.medula_rejection_playbook)
        == EXACTNESS_STATUS_EXACT
    ):
        report.medula_playbook_entry_count = (
            report.medula_rejection_playbook.entry_count
        )
    else:
        report.medula_playbook_entry_count = 0


def _collect_required_inputs(blocks: list[Any]) -> list[str]:
    ordered: list[str] = []
    for block in blocks:
        for name in getattr(block, "required_inputs_missing", []) or []:
            if name not in ordered:
                ordered.append(name)
    return ordered


def _finalize_report_exactness(report: BillingActionReport) -> None:
    blocks = [
        report.lab,
        report.copay,
        report.billing_strategy,
        report.session_uplift,
        report.drg_uplift,
        report.blood_uplift,
        report.material_uplift,
        report.care_setting_review,
        report.procedure_addon_uplift,
        report.procedure_capture_gap,
        report.drg_package_adequacy,
        report.gazette_repricing,
        report.medula_rejection_playbook,
        report.materials,
    ]
    non_exact_blocks = [
        block
        for block in blocks
        if _block_exactness_status(block)
        not in (EXACTNESS_STATUS_EXACT, EXACTNESS_STATUS_NOT_APPLICABLE)
    ]
    if not non_exact_blocks:
        report.exactness_status = EXACTNESS_STATUS_EXACT
        report.unavailable_reason = None
        report.required_inputs_missing = []
        return

    if all(
        _block_exactness_status(block) == EXACTNESS_STATUS_MISSING_INPUTS
        for block in non_exact_blocks
    ):
        report.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
        report.unavailable_reason = getattr(
            non_exact_blocks[0], "unavailable_reason", None
        )
        report.required_inputs_missing = _collect_required_inputs(non_exact_blocks)
        return

    report.exactness_status = EXACTNESS_STATUS_PARTIAL
    report.unavailable_reason = BILLING_REPORT_PARTIAL_REASON
    report.required_inputs_missing = _collect_required_inputs(non_exact_blocks)
    if not report.required_inputs_missing:
        report.required_inputs_missing = [
            f"{getattr(block, '__class__', type(block)).__name__}.required_inputs_missing"
            for block in non_exact_blocks
        ]


def _finalize_summary_exactness(
    summary: CohortRecoverySummary,
    reports: dict[str, BillingActionReport],
) -> None:
    non_exact_reports = [
        report
        for report in reports.values()
        if _block_exactness_status(report) != EXACTNESS_STATUS_EXACT
    ]
    if not non_exact_reports:
        summary.exactness_status = EXACTNESS_STATUS_EXACT
        summary.unavailable_reason = None
        summary.required_inputs_missing = []
        return

    if all(
        _block_exactness_status(report) == EXACTNESS_STATUS_MISSING_INPUTS
        for report in non_exact_reports
    ):
        summary.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
        summary.unavailable_reason = getattr(
            non_exact_reports[0], "unavailable_reason", None
        )
        summary.required_inputs_missing = _collect_required_inputs(non_exact_reports)
        return

    summary.exactness_status = EXACTNESS_STATUS_PARTIAL
    summary.unavailable_reason = COHORT_RECOVERY_PARTIAL_REASON
    summary.required_inputs_missing = _collect_required_inputs(non_exact_reports)
    if not summary.required_inputs_missing:
        summary.required_inputs_missing = ["cohort_billing_report.required_inputs_missing"]


def _set_missing_inputs_report(report: BillingActionReport) -> None:
    """Mark every billing block as missing exact inputs when claim context is absent.

    No heuristic ₺ amounts are produced. The report shape is preserved so the
    frontend can still render empty sections.
    """
    report.lab.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
    report.lab.unavailable_reason = (
        "Lab optimization requires exact billed procedure claim lines."
    )
    report.lab.required_inputs_missing = ["procedure_claim_lines"]

    report.copay.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
    report.copay.unavailable_reason = COPAY_UNAVAILABLE_REASON
    report.copay.required_inputs_missing = list(COPAY_REQUIRED_INPUTS)

    report.billing_strategy.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
    report.billing_strategy.unavailable_reason = BILLING_STRATEGY_UNAVAILABLE_REASON
    report.billing_strategy.required_inputs_missing = list(BILLING_STRATEGY_REQUIRED_INPUTS)

    report.materials.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
    report.materials.unavailable_reason = MATERIALS_PARTIAL_REASON
    report.materials.required_inputs_missing = list(MATERIALS_REQUIRED_INPUTS)

    report.session_uplift.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
    report.session_uplift.unavailable_reason = SESSION_UPLIFT_UNAVAILABLE_REASON
    report.session_uplift.required_inputs_missing = list(SESSION_UPLIFT_REQUIRED_INPUTS)

    report.drg_uplift.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
    report.drg_uplift.unavailable_reason = DRG_UPLIFT_UNAVAILABLE_REASON
    report.drg_uplift.required_inputs_missing = list(DRG_UPLIFT_REQUIRED_INPUTS)

    report.blood_uplift.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
    report.blood_uplift.unavailable_reason = BLOOD_UPLIFT_UNAVAILABLE_REASON
    report.blood_uplift.required_inputs_missing = list(BLOOD_UPLIFT_REQUIRED_INPUTS)

    report.material_uplift.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
    report.material_uplift.unavailable_reason = MATERIAL_UPLIFT_UNAVAILABLE_REASON
    report.material_uplift.required_inputs_missing = list(MATERIAL_UPLIFT_REQUIRED_INPUTS)

    report.care_setting_review.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
    report.care_setting_review.unavailable_reason = CARE_SETTING_REVIEW_UNAVAILABLE_REASON
    report.care_setting_review.required_inputs_missing = list(CARE_SETTING_REVIEW_REQUIRED_INPUTS)

    report.procedure_addon_uplift.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
    report.procedure_addon_uplift.unavailable_reason = PROCEDURE_ADDON_UPLIFT_UNAVAILABLE_REASON
    report.procedure_addon_uplift.required_inputs_missing = list(PROCEDURE_ADDON_UPLIFT_REQUIRED_INPUTS)

    report.procedure_capture_gap.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
    report.procedure_capture_gap.unavailable_reason = PROCEDURE_CAPTURE_GAP_UNAVAILABLE_REASON
    report.procedure_capture_gap.required_inputs_missing = list(PROCEDURE_CAPTURE_GAP_REQUIRED_INPUTS)

    report.drg_package_adequacy.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
    report.drg_package_adequacy.unavailable_reason = DRG_PACKAGE_ADEQUACY_UNAVAILABLE_REASON
    report.drg_package_adequacy.required_inputs_missing = list(DRG_PACKAGE_ADEQUACY_REQUIRED_INPUTS)

    report.gazette_repricing.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
    report.gazette_repricing.unavailable_reason = GAZETTE_REPRICING_UNAVAILABLE_REASON
    report.gazette_repricing.required_inputs_missing = list(GAZETTE_REPRICING_REQUIRED_INPUTS)

    report.medula_rejection_playbook.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
    report.medula_rejection_playbook.unavailable_reason = MEDULA_PLAYBOOK_UNAVAILABLE_REASON
    report.medula_rejection_playbook.required_inputs_missing = list(MEDULA_PLAYBOOK_REQUIRED_INPUTS)


def compute_patient_billing_report(
    pid: str,
    *,
    claim_context: PatientClaimContext | None = None,
    copay_exemption: dict[str, Any] | None = None,
    chapters: set[str] | None = None,
    lab_df_pl: pl.DataFrame | None = None,
) -> BillingActionReport:
    """Compute a full billing action report for a single patient or bill.

    Lab optimization requires claim lines (procedure_category == "laboratuvar");
    if no claim_context is provided the lab block remains empty.

    Args:
        pid: Patient identifier.
        claim_context: Patient-level or bill-level claim context. Required for
            exact lab, copay, strategy, and uplift algorithms.
        copay_exemption: Pre-computed copay exemption result.
        chapters: Pre-computed ICD-10 chapter set (ignored when claim lines are
            required; kept for backward-compatible signatures).
        lab_df_pl: Normalized clinical lab feed for lab capture-gap detection.

    Returns:
        BillingActionReport with all algorithm results.
    """
    _ = chapters
    report = BillingActionReport(patient_id=pid)

    if claim_context is None:
        if SUT_REQUIRE_CLAIM_LINES:
            _set_missing_inputs_report(report)
            _finalize_report_totals(report, claim_context=None)
            _finalize_report_exactness(report)
            return report
        raise NotImplementedError(
            "Legacy estimate-based billing report path removed. "
            "Provide claim_context or set SUT_REQUIRE_CLAIM_LINES=False."
        )

    report.lab, report.procedure_capture_gap = _compute_lab_and_capture_gap_from_claims(
        claim_context,
        lab_df_pl=lab_df_pl,
    )

    exemption = copay_exemption or {
        "exempt": False,
        "n_qualifying": 0,
        "qualifying_diagnoses": [],
    }

    if claim_context.procedure_lines or claim_context.drug_lines:
        report.copay = optimize_copay_from_claims(claim_context, exemption)

    if claim_context.claims:
        report.billing_strategy = recommend_billing_strategy_from_claims(claim_context)

    if claim_context.procedure_lines:
        report.session_uplift = recommend_session_uplift_from_claims(claim_context)
        report.drg_uplift = recommend_drg_uplift_from_claims(
            claim_context,
            session_opportunities=report.session_uplift.opportunities,
            strategy_recommendations=report.billing_strategy.recommendations,
        )
        report.blood_uplift = recommend_blood_uplift_from_claims(claim_context)
        report.material_uplift = recommend_material_uplift_from_claims(claim_context)
        report.care_setting_review = recommend_care_setting_review_from_claims(
            claim_context
        )
        report.drg_package_adequacy = recommend_drg_package_adequacy_from_claims(
            claim_context
        )
        report.gazette_repricing = recommend_gazette_repricing_from_claims(
            claim_context
        )
        report.procedure_addon_uplift = _dedupe_addon_against_capture(
            recommend_procedure_addon_uplift_from_claims(
                claim_context,
                session_uplift_opportunities=report.session_uplift.opportunities,
            ),
            report.procedure_capture_gap,
        )

    report.medula_rejection_playbook = (
        recommend_medula_rejection_playbook_from_claims(claim_context)
    )
    report.medula_rejection_ingest_available = (
        claim_context.medula_rejection_ingest_available
    )
    report.materials = precheck_materials_from_claims(claim_context)

    _finalize_report_totals(report, claim_context=claim_context)

    actions = (
        len(report.lab.flagged_tests)
        + (1 if report.copay.is_exempt else 0)
        + len(report.billing_strategy.recommendations)
        + len(report.session_uplift.opportunities)
        + len(report.drg_uplift.opportunities)
        + len(report.blood_uplift.opportunities)
        + len(report.material_uplift.opportunities)
        + len(report.care_setting_review.opportunities)
        + len(report.procedure_addon_uplift.opportunities)
        + len(report.procedure_capture_gap.opportunities)
        + len(report.drg_package_adequacy.opportunities)
        + len(report.gazette_repricing.opportunities)
        + len(report.medula_rejection_playbook.entries)
        + len(getattr(report.materials, "pre_auth_required", []))
        + len(getattr(report.materials, "miat_restricted", []))
        + len(getattr(report.materials, "bundled_separate_billing", []))
        + len(getattr(report.materials, "miat_interval_violations", []))
        + len(getattr(report.materials, "prose_bundling_violations", []))
        + len(getattr(report.materials, "specialty_prose_violations", []))
    )
    report.action_count = actions

    _finalize_report_exactness(report)

    return report


def _group_lab_by_patient_visit(
    lab_df_pl: pl.DataFrame,
) -> dict[str, dict[str | None, tuple[list[str], list[str | None] | None, list[str | None] | None]]]:
    """Group the normalized lab feed by (patient_id, visit_id).

    ``visit_id`` equals ``episode_id`` (see ``cache/loaders._normalize_lab``).
    Returns patient_id -> visit_id -> (tests, dates, visit_ids).
    """
    out: dict[str, dict[str | None, tuple]] = {}
    if (
        lab_df_pl.is_empty()
        or "patient_id" not in lab_df_pl.columns
        or "test_name" not in lab_df_pl.columns
    ):
        return out
    has_visit = "visit_id" in lab_df_pl.columns
    date_col = next(
        (c for c in ("date", "test_date", "tarih") if c in lab_df_pl.columns), None
    )
    group_cols = ["patient_id"] + (["visit_id"] if has_visit else [])
    agg_exprs = [pl.col("test_name").cast(pl.Utf8).fill_null("").alias("tests")]
    if date_col:
        agg_exprs.append(pl.col(date_col).cast(pl.Utf8).fill_null("").alias("dates"))
    if has_visit:
        agg_exprs.append(pl.col("visit_id").cast(pl.Utf8).fill_null("").alias("vids"))
    grouped = lab_df_pl.group_by(group_cols).agg(agg_exprs)
    for row in grouped.iter_rows(named=True):
        pid = row["patient_id"]
        vid = row.get("visit_id") if has_visit else None
        out.setdefault(pid, {})[vid] = (
            row["tests"],
            row.get("dates") if date_col else None,
            row.get("vids") if has_visit else None,
        )
    return out


def _compute_lab_and_capture_gap_from_claims(
    claim_context: PatientClaimContext,
    lab_df_pl: pl.DataFrame | None,
) -> tuple[LabOptimization, ProcedureCaptureGap]:
    """Compute lab optimization and capture gap by summing per-bill results.

    Each claim is treated as its own bill for lab purposes. Lab optimization
    uses billed lab claim lines; capture gap compares the clinical lab feed
    against those billed lines per episode.
    """
    merged_lab = LabOptimization()
    merged_gap = ProcedureCaptureGap()

    if not claim_context.claims:
        return merged_lab, merged_gap

    # Index lab feed by visit_id for quick per-episode scoping.
    lab_by_visit: dict[str | None, pl.DataFrame] = {}
    if lab_df_pl is not None and not lab_df_pl.is_empty() and "visit_id" in lab_df_pl.columns:
        for vid, group in lab_df_pl.group_by("visit_id"):
            lab_by_visit[str(vid[0]) if isinstance(vid, tuple) else str(vid)] = group

    for claim in claim_context.claims:
        bill_context = PatientClaimContext(
            patient_id=claim_context.patient_id,
            claims=(claim,),
            procedure_lines=tuple(
                p for p in claim_context.procedure_lines if p.claim_id == claim.claim_id
            ),
            material_lines=tuple(
                m for m in claim_context.material_lines if m.claim_id == claim.claim_id
            ),
            drug_lines=tuple(
                d for d in claim_context.drug_lines if d.claim_id == claim.claim_id
            ),
            diagnoses=tuple(
                dg for dg in claim_context.diagnoses if dg.claim_id == claim.claim_id
            ),
            performed_procedure_lines=tuple(
                p for p in claim_context.performed_procedure_lines if p.claim_id == claim.claim_id
            ),
            medula_rejection_events=tuple(
                e for e in claim_context.medula_rejection_events if e.claim_id == claim.claim_id
            ),
        )

        lab_result = _optimize_lab_billing_from_claims(bill_context)
        merged_lab.normative_cost_try = round(
            merged_lab.normative_cost_try + lab_result.normative_cost_try, 2
        )
        merged_lab.session_fraction_savings = round(
            merged_lab.session_fraction_savings + lab_result.session_fraction_savings, 2
        )
        merged_lab.hemogram_bundling_savings = round(
            merged_lab.hemogram_bundling_savings + lab_result.hemogram_bundling_savings, 2
        )
        merged_lab.flagged_tests.extend(lab_result.flagged_tests)

        lab_for_claim = lab_by_visit.get(claim.episode_id)
        if lab_for_claim is not None or bill_context.performed_procedure_lines:
            gap_result = recommend_procedure_capture_gap_from_claims(
                bill_context,
                lab_df_pl=lab_for_claim,
            )
            merged_gap.opportunities.extend(gap_result.opportunities)

    # Preserve exactness metadata when any source contributed.
    if merged_lab.flagged_tests or merged_gap.opportunities:
        merged_lab.exactness_status = EXACTNESS_STATUS_EXACT
        merged_gap.exactness_status = EXACTNESS_STATUS_EXACT

    return merged_lab, merged_gap


def _assign_priority_by_percentile(reports: list[BillingActionReport]) -> None:
    """Tier reports high/medium/low by sgk_uplift percentile (in place)."""
    recoverables = sorted(r.sgk_uplift_try for r in reports if r.sgk_uplift_try > 0)
    if not recoverables:
        return
    n = len(recoverables)
    p75 = recoverables[min(n - 1, int(n * 0.75))]
    p50 = recoverables[min(n - 1, int(n * 0.50))]
    for report in reports:
        opportunity = report.sgk_uplift_try
        if opportunity >= p75:
            report.priority = "high"
        elif opportunity >= p50:
            report.priority = "medium"
        else:
            report.priority = "low"


def compute_all_bill_billing_reports(
    cache: dict[str, Any],
    *,
    max_workers: int = 1,
) -> dict[str, BillingActionReport]:
    """Compute one billing report per (patient, claim) bill.

    Mirrors :func:`compute_all_billing_reports` but scopes each report to a
    single ``claim_id`` via ``build_bill_claim_context``, with the clinical lab
    feed filtered to the claim's episode (``visit_id``). Reuses the same
    patient-level ``copay_exemption`` (exemption is a patient property). Keyed
    by ``f"{patient_id}::{claim_id}"`` so it stores in the generic payload-rows
    table. Returns ``{}`` when no claim dataset is present.
    """
    claim_dataset: SUTClaimDataset | None = cache.get("sut_claim_dataset")
    if claim_dataset is None:
        return {}

    alerts_cache = cache.get("patient_alerts_cache", {})
    lab_df_pl: pl.DataFrame = cache.get("lab_df_pl", pl.DataFrame())
    alerts_by_pid = {a["patient_id"]: a for a in alerts_cache.get("patients", [])}
    lab_by_pid_visit = _group_lab_by_patient_visit(lab_df_pl)

    tasks: list[tuple[str, str, str]] = [
        (pid, claim.claim_id, claim.episode_id)
        for pid, claims in claim_dataset.claims_by_patient.items()
        for claim in claims
    ]
    if not tasks:
        return {}

    def _one(task: tuple[str, str, str]) -> tuple[str, BillingActionReport | None]:
        pid, claim_id, episode_id = task
        key = f"{pid}::{claim_id}"
        bill_context = build_bill_claim_context(pid, claim_id, claim_dataset)
        if bill_context is None:
            return key, None
        alert = alerts_by_pid.get(pid, {})
        copay_exemption = alert.get(
            "copay_exemption",
            {"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []},
        )
        chapters = set(alert.get("icd10_chapters", []))
        report = compute_patient_billing_report(
            pid,
            claim_context=bill_context,
            copay_exemption=copay_exemption,
            chapters=chapters,
            lab_df_pl=lab_df_pl,
        )
        return key, report

    worker_count = max(1, min(int(max_workers), len(tasks)))
    if worker_count == 1:
        results = [_one(task) for task in tasks]
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            results = list(executor.map(_one, tasks))

    reports = {key: report for key, report in results if report is not None}
    _assign_priority_by_percentile(list(reports.values()))
    return reports


def compute_all_billing_reports(
    cache: dict[str, Any],
    *,
    max_workers: int = 1,
) -> tuple[dict[str, BillingActionReport], CohortRecoverySummary]:
    """Compute billing reports for all patients using pre-cached pipeline data.

    This is the main entry point called from pipeline.py after all SUT
    data is pre-computed.

    Args:
        cache: The _pipeline_cache dict containing:
            - sut_by_pid: optional exact SUT claim-total payloads keyed by patient
            - patient_alerts_cache: dict with "patients" list
            - lab_df_pl: Polars DataFrame of lab tests
    Returns:
        Tuple of (billing_reports_by_pid, cohort_summary).
    """
    t0 = time.perf_counter()

    sut_by_pid = cache.get("sut_by_pid", {})
    claim_dataset: SUTClaimDataset | None = cache.get("sut_claim_dataset")
    alerts_cache = cache.get("patient_alerts_cache", {})
    lab_df_pl: pl.DataFrame = cache.get("lab_df_pl", pl.DataFrame())

    alerts_by_pid: dict[str, dict[str, Any]] = {}
    for alert in alerts_cache.get("patients", []):
        alerts_by_pid[alert["patient_id"]] = alert

    reports: dict[str, BillingActionReport] = {}
    patient_id_set = set(sut_by_pid.keys()) if hasattr(sut_by_pid, "keys") else set()
    patient_id_set.update(alerts_by_pid.keys())
    if not lab_df_pl.is_empty() and "patient_id" in lab_df_pl.columns:
        patient_id_set.update(lab_df_pl["patient_id"].unique().to_list())
    patient_ids = sorted(patient_id_set)
    if not patient_ids:
        logger.warning("No SUT patient inputs in cache — billing reports will be empty")
        return {}, CohortRecoverySummary()

    worker_count = max(1, min(int(max_workers), max(1, len(patient_ids))))

    logger.info(
        "Computing billing reports for %d patients (workers=%d)...",
        len(patient_ids),
        worker_count,
    )

    def _build_report(pid: str) -> BillingActionReport:
        alert = alerts_by_pid.get(pid, {})
        copay_exemption = alert.get(
            "copay_exemption",
            {"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []},
        )
        chapters_list = alert.get("icd10_chapters", [])
        chapters = set(chapters_list)

        claim_context = None
        if claim_dataset is not None:
            claim_context = build_patient_claim_context(pid, claim_dataset)

        report = compute_patient_billing_report(
            pid,
            claim_context=claim_context,
            copay_exemption=copay_exemption,
            chapters=chapters,
            lab_df_pl=lab_df_pl,
        )
        return report

    if worker_count == 1:
        report_list = [_build_report(pid) for pid in patient_ids]
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            report_list = list(executor.map(_build_report, patient_ids))

    for pid, report in zip(patient_ids, report_list, strict=True):
        reports[pid] = report

    recoverables = sorted(
        [r.sgk_uplift_try for r in reports.values() if r.sgk_uplift_try > 0]
    )
    if recoverables:
        n = len(recoverables)
        p75 = recoverables[min(n - 1, int(n * 0.75))]
        p50 = recoverables[min(n - 1, int(n * 0.50))]
        for report in reports.values():
            opportunity = report.sgk_uplift_try
            if opportunity >= p75:
                report.priority = "high"
            elif opportunity >= p50:
                report.priority = "medium"
            else:
                report.priority = "low"

    summary = CohortRecoverySummary()
    summary.n_patients = len(reports)
    summary.medula_rejection_ingest_available = bool(
        claim_dataset is not None and claim_dataset.medula_rejection_ingest_available
    )

    priority_dist: dict[str, int] = {"high": 0, "medium": 0, "low": 0}

    for report in reports.values():
        if _block_exactness_status(report.lab) == EXACTNESS_STATUS_EXACT:
            summary.total_lab_savings += report.lab.total_savings
            summary.total_compliance_adjustment += report.compliance_adjustment_try
        if _block_exactness_status(report.billing_strategy) == EXACTNESS_STATUS_EXACT:
            uplift = report.billing_strategy.uplift_savings_try
            summary.total_strategy_savings += uplift
            summary.total_strategy_uplift += uplift
            override_uplift = report.billing_strategy.optional_override_uplift_try
            summary.total_optional_override_uplift += override_uplift
            if override_uplift > 0:
                summary.n_optional_override_patients += 1
        if _block_exactness_status(report.session_uplift) == EXACTNESS_STATUS_EXACT:
            summary.total_session_uplift += report.session_uplift.confirmed_uplift_try
        if _block_exactness_status(report.drg_uplift) == EXACTNESS_STATUS_EXACT:
            drg_uplift = report.drg_uplift.confirmed_uplift_try
            summary.total_drg_uplift += drg_uplift
            if drg_uplift > 0:
                summary.n_drg_uplift_patients += 1
        if _block_exactness_status(report.blood_uplift) == EXACTNESS_STATUS_EXACT:
            blood_uplift = report.blood_uplift.confirmed_uplift_try
            summary.total_blood_uplift += blood_uplift
            if blood_uplift > 0:
                summary.n_blood_uplift_patients += 1
        if _block_exactness_status(report.material_uplift) == EXACTNESS_STATUS_EXACT:
            material_uplift = report.material_uplift.confirmed_uplift_try
            summary.total_material_uplift += material_uplift
            if material_uplift > 0:
                summary.n_material_uplift_patients += 1
        if _block_exactness_status(report.procedure_addon_uplift) == EXACTNESS_STATUS_EXACT:
            addon_uplift = report.procedure_addon_uplift.confirmed_uplift_try
            summary.total_procedure_addon_uplift += addon_uplift
            if addon_uplift > 0:
                summary.n_procedure_addon_patients += 1
        if _block_exactness_status(report.copay) == EXACTNESS_STATUS_EXACT:
            waived_total = float(
                getattr(report.copay, "patient_copay_waived_total_try", 0.0) or 0.0
            )
            if waived_total <= 0:
                waived_total = (
                    report.copay.total_copay_savings_try
                    + report.copay.rx_copay_savings_try
                )
            summary.total_copay_savings += waived_total
        summary.total_audit_exposure += report.audit_exposure_try
        if (
            _block_exactness_status(report.procedure_capture_gap)
            == EXACTNESS_STATUS_EXACT
        ):
            summary.total_capture_gap += report.capture_gap_try
        if (
            _block_exactness_status(report.drg_package_adequacy)
            == EXACTNESS_STATUS_EXACT
        ):
            summary.total_package_adequacy_review += report.package_adequacy_review_try
        if _block_exactness_status(report.gazette_repricing) == EXACTNESS_STATUS_EXACT:
            summary.total_gazette_repricing += report.gazette_repricing_try
        if (
            _block_exactness_status(report.medula_rejection_playbook)
            == EXACTNESS_STATUS_EXACT
        ):
            summary.total_medula_playbook_entries += report.medula_playbook_entry_count
        summary.total_material_flags += (
            len(getattr(report.materials, "pre_auth_required", []))
            + len(getattr(report.materials, "miat_restricted", []))
            + len(getattr(report.materials, "bundled_separate_billing", []))
            + len(getattr(report.materials, "miat_interval_violations", []))
            + len(getattr(report.materials, "prose_bundling_violations", []))
            + len(getattr(report.materials, "specialty_prose_violations", []))
        )
        priority_dist[report.priority] = priority_dist.get(report.priority, 0) + 1

    summary.total_lab_savings = round(summary.total_lab_savings, 2)
    summary.total_copay_savings = round(summary.total_copay_savings, 2)
    summary.total_strategy_savings = round(summary.total_strategy_savings, 2)
    summary.total_session_uplift = round(summary.total_session_uplift, 2)
    summary.total_drg_uplift = round(summary.total_drg_uplift, 2)
    summary.total_blood_uplift = round(summary.total_blood_uplift, 2)
    summary.total_material_uplift = round(summary.total_material_uplift, 2)
    summary.total_procedure_addon_uplift = round(summary.total_procedure_addon_uplift, 2)
    summary.total_optional_override_uplift = round(summary.total_optional_override_uplift, 2)
    summary.total_strategy_uplift = round(summary.total_strategy_uplift, 2)
    summary.total_compliance_adjustment = round(summary.total_compliance_adjustment, 2)
    summary.total_sgk_uplift = round(
        sum(r.sgk_uplift_try for r in reports.values()),
        2,
    )
    summary.total_audit_exposure = round(summary.total_audit_exposure, 2)
    summary.total_capture_gap = round(summary.total_capture_gap, 2)
    summary.total_package_adequacy_review = round(
        summary.total_package_adequacy_review, 2
    )
    summary.grand_total_recoverable = summary.total_sgk_uplift
    summary.priority_distribution = priority_dist

    sorted_reports = sorted(
        reports.values(), key=_total_opportunity_try, reverse=True
    )
    summary.patient_summaries = [
        patient_recovery_summary_entry(r) for r in sorted_reports
    ]
    summary.top_patients = summary.patient_summaries[:10]

    summary.savings_by_category = {
        "sgk_uplift": summary.total_sgk_uplift,
        "session_uplift": summary.total_session_uplift,
        "drg_uplift": summary.total_drg_uplift,
        "blood_uplift": summary.total_blood_uplift,
        "material_uplift": summary.total_material_uplift,
        "procedure_addon_uplift": summary.total_procedure_addon_uplift,
        "optional_override": summary.total_optional_override_uplift,
        "strategy_uplift": summary.total_strategy_uplift,
        "compliance": summary.total_compliance_adjustment,
        "copay_waiver": summary.total_copay_savings,
        "audit_exposure": summary.total_audit_exposure,
        "capture_gap": summary.total_capture_gap,
        "package_adequacy_review": summary.total_package_adequacy_review,
        "gazette_repricing": summary.total_gazette_repricing,
        "lab": summary.total_compliance_adjustment,
        "copay": summary.total_copay_savings,
        "strategy": summary.total_strategy_uplift,
    }
    _finalize_summary_exactness(summary, reports)

    elapsed = time.perf_counter() - t0
    logger.info(
        "Billing reports computed for %d patients in %.1fs — "
        "total recoverable: %.0f TRY",
        len(reports),
        elapsed,
        summary.grand_total_recoverable,
    )

    return reports, summary


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
    gap = _exemption_gap_try(report)
    return {
        "patient_id": report.patient_id,
        "total_recoverable_try": report.total_recoverable_try,
        "sgk_uplift_try": report.sgk_uplift_try,
        "compliance_adjustment_try": report.compliance_adjustment_try,
        "exemption_gap_try": gap,
        "total_opportunity_try": _total_opportunity_try(report),
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

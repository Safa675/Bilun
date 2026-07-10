"""Single-patient billing report assembly."""

from __future__ import annotations

from typing import Any

import polars as pl

from src.bilun.domain.billing.claim_blood_uplift import recommend_blood_uplift_from_claims
from src.bilun.domain.billing.claim_yatak_puani import recommend_yatak_puani_from_claims
from src.bilun.domain.billing.claim_care_setting_review import (
    recommend_care_setting_review_from_claims,
)
from src.bilun.domain.billing.claim_copay import optimize_copay_from_claims
from src.bilun.domain.billing.claim_drg_package_adequacy import (
    recommend_drg_package_adequacy_from_claims,
)
from src.bilun.domain.billing.claim_drg_uplift import recommend_drg_uplift_from_claims
from src.bilun.domain.billing.claim_drug_indication import validate_drug_indication_from_claims
from src.bilun.domain.billing.claim_gazette_repricing import (
    recommend_gazette_repricing_from_claims,
)
from src.bilun.domain.billing.claim_material_uplift import recommend_material_uplift_from_claims
from src.bilun.domain.billing.claim_materials import precheck_materials_from_claims
from src.bilun.domain.billing.claim_medula_rejection import (
    recommend_medula_rejection_playbook_from_claims,
)
from src.bilun.domain.billing.claim_submission_checklist import (
    recommend_claim_submission_checklist_from_claims,
)
from src.bilun.domain.billing.claim_procedure_addon_uplift import (
    recommend_procedure_addon_uplift_from_claims,
)
from src.bilun.domain.billing.claim_session_uplift import recommend_session_uplift_from_claims
from src.bilun.domain.billing.claim_strategy import recommend_billing_strategy_from_claims
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.constants import SUT_REQUIRE_CLAIM_LINES

from .lab_bill_merge import compute_lab_and_capture_gap_from_claims
from .procedure_dedup import dedupe_addon_against_capture
from .billing_actions import collect_billing_actions
from .report_exactness import finalize_report_exactness, set_missing_inputs_report
from .report_totals import finalize_report_totals
from .types import BillingActionReport


def compute_patient_billing_report(
    pid: str,
    *,
    claim_context: PatientClaimContext | None = None,
    copay_exemption: dict[str, Any] | None = None,
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
        lab_df_pl: Normalized clinical lab feed for lab capture-gap detection.

    Returns:
        BillingActionReport with all algorithm results.
    """
    report = BillingActionReport(patient_id=pid)

    if claim_context is None:
        if SUT_REQUIRE_CLAIM_LINES:
            set_missing_inputs_report(report)
            finalize_report_totals(report, claim_context=None)
            finalize_report_exactness(report)
            return report

    assert claim_context is not None

    report.lab, report.procedure_capture_gap = compute_lab_and_capture_gap_from_claims(
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
        report.yatak_puani = recommend_yatak_puani_from_claims(claim_context)
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
        report.procedure_addon_uplift = dedupe_addon_against_capture(
            recommend_procedure_addon_uplift_from_claims(
                claim_context,
                session_uplift_opportunities=report.session_uplift.opportunities,
            ),
            report.procedure_capture_gap,
        )

    report.medula_rejection_playbook = (
        recommend_medula_rejection_playbook_from_claims(claim_context)
    )
    report.claim_submission_checklist = recommend_claim_submission_checklist_from_claims(
        claim_context
    )
    report.drug_indication = validate_drug_indication_from_claims(claim_context)
    report.medula_rejection_ingest_available = (
        claim_context.medula_rejection_ingest_available
    )
    report.materials = precheck_materials_from_claims(claim_context)

    finalize_report_totals(report, claim_context=claim_context)
    report.recommended_actions = collect_billing_actions(report)
    report.action_count = len(report.recommended_actions)
    finalize_report_exactness(report)

    return report

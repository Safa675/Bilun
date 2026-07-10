"""Declarative metadata for billing report blocks."""

from __future__ import annotations

from dataclasses import dataclass

from .types import (
    BILLING_STRATEGY_REQUIRED_INPUTS,
    BILLING_STRATEGY_UNAVAILABLE_REASON,
    BLOOD_UPLIFT_REQUIRED_INPUTS,
    BLOOD_UPLIFT_UNAVAILABLE_REASON,
    YATAK_PUANI_REQUIRED_INPUTS,
    YATAK_PUANI_UNAVAILABLE_REASON,
    CARE_SETTING_REVIEW_REQUIRED_INPUTS,
    CARE_SETTING_REVIEW_UNAVAILABLE_REASON,
    COPAY_REQUIRED_INPUTS,
    COPAY_UNAVAILABLE_REASON,
    DRG_PACKAGE_ADEQUACY_REQUIRED_INPUTS,
    DRG_PACKAGE_ADEQUACY_UNAVAILABLE_REASON,
    DRG_UPLIFT_REQUIRED_INPUTS,
    DRG_UPLIFT_UNAVAILABLE_REASON,
    DRUG_INDICATION_REQUIRED_INPUTS,
    DRUG_INDICATION_UNAVAILABLE_REASON,
    GAZETTE_REPRICING_REQUIRED_INPUTS,
    GAZETTE_REPRICING_UNAVAILABLE_REASON,
    MATERIAL_UPLIFT_REQUIRED_INPUTS,
    MATERIAL_UPLIFT_UNAVAILABLE_REASON,
    MATERIALS_PARTIAL_REASON,
    MATERIALS_REQUIRED_INPUTS,
    MEDULA_PLAYBOOK_REQUIRED_INPUTS,
    MEDULA_PLAYBOOK_UNAVAILABLE_REASON,
    CLAIM_SUBMISSION_CHECKLIST_REQUIRED_INPUTS,
    CLAIM_SUBMISSION_CHECKLIST_UNAVAILABLE_REASON,
    PROCEDURE_ADDON_UPLIFT_REQUIRED_INPUTS,
    PROCEDURE_ADDON_UPLIFT_UNAVAILABLE_REASON,
    PROCEDURE_CAPTURE_GAP_REQUIRED_INPUTS,
    PROCEDURE_CAPTURE_GAP_UNAVAILABLE_REASON,
    SESSION_UPLIFT_REQUIRED_INPUTS,
    SESSION_UPLIFT_UNAVAILABLE_REASON,
)

LAB_MISSING_INPUTS = ("procedure_claim_lines",)
LAB_UNAVAILABLE_REASON = (
    "Lab optimization requires exact billed procedure claim lines."
)


@dataclass(frozen=True)
class BillingBlockSpec:
    """Metadata for one ``BillingActionReport`` algorithm block."""

    attr: str
    required_inputs: tuple[str, ...]
    unavailable_reason: str
    uplift_field: str | None = None
    report_scalar: str | None = None
    block_scalar: str | None = None
    scalar_default: float | int = 0
    cohort_total_field: str | None = None
    cohort_patient_counter_field: str | None = None
    cohort_value_from_report: str | None = None


BILLING_BLOCK_SPECS: tuple[BillingBlockSpec, ...] = (
    BillingBlockSpec(
        attr="lab",
        required_inputs=LAB_MISSING_INPUTS,
        unavailable_reason=LAB_UNAVAILABLE_REASON,
    ),
    BillingBlockSpec(
        attr="copay",
        required_inputs=COPAY_REQUIRED_INPUTS,
        unavailable_reason=COPAY_UNAVAILABLE_REASON,
    ),
    BillingBlockSpec(
        attr="billing_strategy",
        required_inputs=BILLING_STRATEGY_REQUIRED_INPUTS,
        unavailable_reason=BILLING_STRATEGY_UNAVAILABLE_REASON,
        uplift_field="uplift_savings_try",
        cohort_total_field="total_strategy_uplift",
    ),
    BillingBlockSpec(
        attr="session_uplift",
        required_inputs=SESSION_UPLIFT_REQUIRED_INPUTS,
        unavailable_reason=SESSION_UPLIFT_UNAVAILABLE_REASON,
        uplift_field="confirmed_uplift_try",
        cohort_total_field="total_session_uplift",
    ),
    BillingBlockSpec(
        attr="drg_uplift",
        required_inputs=DRG_UPLIFT_REQUIRED_INPUTS,
        unavailable_reason=DRG_UPLIFT_UNAVAILABLE_REASON,
        uplift_field="confirmed_uplift_try",
        cohort_total_field="total_drg_uplift",
        cohort_patient_counter_field="n_drg_uplift_patients",
    ),
    BillingBlockSpec(
        attr="blood_uplift",
        required_inputs=BLOOD_UPLIFT_REQUIRED_INPUTS,
        unavailable_reason=BLOOD_UPLIFT_UNAVAILABLE_REASON,
        uplift_field="confirmed_uplift_try",
        cohort_total_field="total_blood_uplift",
        cohort_patient_counter_field="n_blood_uplift_patients",
    ),
    BillingBlockSpec(
        attr="yatak_puani",
        required_inputs=YATAK_PUANI_REQUIRED_INPUTS,
        unavailable_reason=YATAK_PUANI_UNAVAILABLE_REASON,
        uplift_field="confirmed_yatak_try",
        cohort_total_field="total_yatak_puani",
        cohort_patient_counter_field="n_yatak_puani_patients",
    ),
    BillingBlockSpec(
        attr="icu_puani",
        required_inputs=YATAK_PUANI_REQUIRED_INPUTS,
        unavailable_reason=YATAK_PUANI_UNAVAILABLE_REASON,
        uplift_field="confirmed_icu_try",
        cohort_total_field="total_icu_puani",
        cohort_patient_counter_field="n_icu_puani_patients",
    ),
    BillingBlockSpec(
        attr="yenidogan_yatak",
        required_inputs=YATAK_PUANI_REQUIRED_INPUTS,
        unavailable_reason=YATAK_PUANI_UNAVAILABLE_REASON,
        uplift_field="confirmed_yenidogan_yatak_try",
        cohort_total_field="total_yenidogan_yatak",
        cohort_patient_counter_field="n_yenidogan_yatak_patients",
    ),
    BillingBlockSpec(
        attr="refakatci",
        required_inputs=YATAK_PUANI_REQUIRED_INPUTS,
        unavailable_reason=YATAK_PUANI_UNAVAILABLE_REASON,
        uplift_field="confirmed_refakat_try",
        cohort_total_field="total_refakatci",
        cohort_patient_counter_field="n_refakatci_patients",
    ),
    BillingBlockSpec(
        attr="material_uplift",
        required_inputs=MATERIAL_UPLIFT_REQUIRED_INPUTS,
        unavailable_reason=MATERIAL_UPLIFT_UNAVAILABLE_REASON,
        uplift_field="confirmed_uplift_try",
        cohort_total_field="total_material_uplift",
        cohort_patient_counter_field="n_material_uplift_patients",
    ),
    BillingBlockSpec(
        attr="care_setting_review",
        required_inputs=CARE_SETTING_REVIEW_REQUIRED_INPUTS,
        unavailable_reason=CARE_SETTING_REVIEW_UNAVAILABLE_REASON,
    ),
    BillingBlockSpec(
        attr="procedure_addon_uplift",
        required_inputs=PROCEDURE_ADDON_UPLIFT_REQUIRED_INPUTS,
        unavailable_reason=PROCEDURE_ADDON_UPLIFT_UNAVAILABLE_REASON,
        uplift_field="confirmed_uplift_try",
        cohort_total_field="total_procedure_addon_uplift",
        cohort_patient_counter_field="n_procedure_addon_patients",
    ),
    BillingBlockSpec(
        attr="procedure_capture_gap",
        required_inputs=PROCEDURE_CAPTURE_GAP_REQUIRED_INPUTS,
        unavailable_reason=PROCEDURE_CAPTURE_GAP_UNAVAILABLE_REASON,
        report_scalar="capture_gap_try",
        block_scalar="confirmed_gap_try",
        cohort_total_field="total_capture_gap",
        cohort_value_from_report="capture_gap_try",
    ),
    BillingBlockSpec(
        attr="drg_package_adequacy",
        required_inputs=DRG_PACKAGE_ADEQUACY_REQUIRED_INPUTS,
        unavailable_reason=DRG_PACKAGE_ADEQUACY_UNAVAILABLE_REASON,
        report_scalar="package_adequacy_review_try",
        block_scalar="review_uplift_try",
        cohort_total_field="total_package_adequacy_review",
        cohort_value_from_report="package_adequacy_review_try",
    ),
    BillingBlockSpec(
        attr="gazette_repricing",
        required_inputs=GAZETTE_REPRICING_REQUIRED_INPUTS,
        unavailable_reason=GAZETTE_REPRICING_UNAVAILABLE_REASON,
        report_scalar="gazette_repricing_try",
        block_scalar="review_repricing_try",
        cohort_total_field="total_gazette_repricing",
        cohort_value_from_report="gazette_repricing_try",
    ),
    BillingBlockSpec(
        attr="medula_rejection_playbook",
        required_inputs=MEDULA_PLAYBOOK_REQUIRED_INPUTS,
        unavailable_reason=MEDULA_PLAYBOOK_UNAVAILABLE_REASON,
        report_scalar="medula_playbook_entry_count",
        block_scalar="entry_count",
        scalar_default=0,
        cohort_total_field="total_medula_playbook_entries",
        cohort_value_from_report="medula_playbook_entry_count",
    ),
    BillingBlockSpec(
        attr="claim_submission_checklist",
        required_inputs=CLAIM_SUBMISSION_CHECKLIST_REQUIRED_INPUTS,
        unavailable_reason=CLAIM_SUBMISSION_CHECKLIST_UNAVAILABLE_REASON,
        report_scalar="claim_submission_checklist_count",
        block_scalar="item_count",
        scalar_default=0,
    ),
    BillingBlockSpec(
        attr="materials",
        required_inputs=MATERIALS_REQUIRED_INPUTS,
        unavailable_reason=MATERIALS_PARTIAL_REASON,
    ),
    BillingBlockSpec(
        attr="drug_indication",
        required_inputs=DRUG_INDICATION_REQUIRED_INPUTS,
        unavailable_reason=DRUG_INDICATION_UNAVAILABLE_REASON,
        report_scalar="drug_indication_violation_count",
        block_scalar="violation_count",
        scalar_default=0,
    ),
)

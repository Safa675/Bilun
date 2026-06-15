"""
src/bilun/domain/billing/types.py
Dataclasses for billing optimization results.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.bilun.domain.materials.coverage_scope import material_bundling_coverage_scope
from src.bilun.domain.materials.specialty_coverage_scope import specialty_materials_coverage_scope
from typing import Any

EXACTNESS_STATUS_EXACT = "exact"
EXACTNESS_STATUS_PARTIAL = "partial_exact"
EXACTNESS_STATUS_MISSING_INPUTS = "missing_exact_inputs"
EXACTNESS_STATUS_NOT_APPLICABLE = "not_applicable"

COPAY_REQUIRED_INPUTS = (
    "billed_procedure_codes",
    "procedure_claim_dates",
    "dispensed_drug_claim_lines",
    "billed_drug_amounts",
)
COPAY_UNAVAILABLE_REASON = (
    "Copay optimization requires exact billed procedure codes, claim dates, "
    "dispensed drug claim lines, and billed amounts, which are not available "
    "in the active SUT runtime inputs."
)
MATERIALS_REQUIRED_INPUTS = (
    "billed_material_codes",
)
MATERIALS_PARTIAL_REASON = (
    "EK-3C-1 pre-authorization and EK-3C-2 MIAT require billed material claim lines. "
    "Partial mode shows EK-3 specialty price benchmarks (P90) only — not catalog "
    "pre-auth or MIAT flags."
)
BILLING_REPORT_PARTIAL_REASON = (
    "Billing report totals combine exact and non-exact sections. Use section-"
    "level exactness metadata before treating aggregate savings as exact."
)
COHORT_RECOVERY_PARTIAL_REASON = (
    "Revenue recovery totals aggregate billing reports that include non-exact "
    "sections. Treat cohort savings as mixed exactness unless every patient "
    "report is exact."
)
SESSION_UPLIFT_REQUIRED_INPUTS = (
    "procedure_claim_lines",
    "billed_procedure_amounts",
)
SESSION_UPLIFT_UNAVAILABLE_REASON = (
    "Session pricing uplift requires exact billed procedure claim lines with "
    "amounts, which are not available in the active SUT runtime inputs."
)
DRG_UPLIFT_REQUIRED_INPUTS = (
    "procedure_claim_lines",
    "billed_procedure_amounts",
)
DRG_UPLIFT_UNAVAILABLE_REASON = (
    "DRG itemized-vs-package uplift requires exact billed procedure claim lines "
    "with amounts, which are not available in the active SUT runtime inputs."
)
BLOOD_UPLIFT_REQUIRED_INPUTS = (
    "procedure_claim_lines",
    "billed_procedure_amounts",
)
BLOOD_UPLIFT_UNAVAILABLE_REASON = (
    "Blood component uplift requires exact billed procedure claim lines with "
    "amounts, which are not available in the active SUT runtime inputs."
)
MATERIAL_UPLIFT_REQUIRED_INPUTS = (
    "procedure_claim_lines",
    "material_claim_lines",
)
MATERIAL_UPLIFT_UNAVAILABLE_REASON = (
    "Missing billable material uplift requires exact procedure claim lines; "
    "material lines may be absent when uplift is detected."
)
CARE_SETTING_REVIEW_REQUIRED_INPUTS = (
    "procedure_claim_lines",
    "claim_type",
)
CARE_SETTING_REVIEW_UNAVAILABLE_REASON = (
    "Care-setting review requires exact procedure claim lines and claim type "
    "metadata, which are not available in the active SUT runtime inputs."
)
PROCEDURE_ADDON_UPLIFT_REQUIRED_INPUTS = (
    "procedure_claim_lines",
    "billed_procedure_amounts",
)
PROCEDURE_ADDON_UPLIFT_UNAVAILABLE_REASON = (
    "Procedure add-on uplift requires exact billed procedure claim lines with "
    "amounts, which are not available in the active SUT runtime inputs."
)
PROCEDURE_CAPTURE_GAP_REQUIRED_INPUTS = (
    "performed_procedure_lines",
)
PROCEDURE_CAPTURE_GAP_UNAVAILABLE_REASON = (
    "Procedure capture gap requires optional EMR/OR performed procedure log rows."
)
DRG_PACKAGE_ADEQUACY_REQUIRED_INPUTS = (
    "procedure_claim_lines",
    "package_candidate",
    "primary_icd10",
)
DRG_PACKAGE_ADEQUACY_UNAVAILABLE_REASON = (
    "Package adequacy review requires exact procedure claim lines with package "
    "candidate flags and primary ICD-10."
)
GAZETTE_REPRICING_REQUIRED_INPUTS = (
    "procedure_claim_lines",
    "procedure_dates",
    "expected_payable_try",
)
GAZETTE_REPRICING_UNAVAILABLE_REASON = (
    "Gazette repricing review requires exact procedure claim lines with service "
    "dates and payable amounts."
)
MEDULA_PLAYBOOK_REQUIRED_INPUTS = (
    "medula_rejection_events",
)
MEDULA_PLAYBOOK_UNAVAILABLE_REASON = (
    "MEDULA rebill playbook requires optional MEDULA rejection event ingest rows."
)


@dataclass
class LabOptimization:
    """Normative lab billing analysis for a single patient."""

    normative_cost_try: float = 0.0
    hemogram_bundling_savings: float = 0.0
    session_fraction_savings: float = 0.0
    flagged_tests: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_EXACT
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(default_factory=list)
    rule_source: str = (
        "EK-2B L107020 hemogram bundling; SUT §2.2.2.B / §2.2.2.A(5) session point factors"
    )

    @property
    def total_savings(self) -> float:
        """Recoverable TRY from hemogram bundling and session-fraction over-billing."""
        return round(self.hemogram_bundling_savings + self.session_fraction_savings, 2)


COPAY_SAVINGS_BENEFICIARY_PATIENT_AND_SGK = "patient_and_sgk"
"""Exemption gap: patient katılım waiver + SGK payable correction when flag was missing."""

COPAY_GAP_KIND_EXEMPTION_CORRECTION = "exemption_correction"


@dataclass
class CopayOptimization:
    """Copayment exemption review for a single patient.

    Monetary fields measure the **exemption gap** (billed − payable on claim lines)
    when exemption may apply: corrects patient katılım payı and SGK payable if
    ``katilimPayindanMuaf`` was missing in MEDULA — compliance correction, not repricing.
    """

    is_exempt: bool = False
    exemption_disease: str = ""
    exemption_range: str = ""
    savings_beneficiary: str = COPAY_SAVINGS_BENEFICIARY_PATIENT_AND_SGK
    gap_kind: str = COPAY_GAP_KIND_EXEMPTION_CORRECTION
    visit_copay_savings_try: float = 0.0  # procedure-line exemption gap (legacy name)
    rx_copay_savings_try: float = 0.0  # prescription exemption gap (legacy name)
    total_copay_savings_try: float = 0.0  # procedure gap only (legacy field name)
    patient_copay_waived_total_try: float = 0.0  # total exemption gap (visit + rx)
    rate_corrections: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = COPAY_UNAVAILABLE_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(COPAY_REQUIRED_INPUTS)
    )
    rule_source: str = "EK-1A chronic disease copay exemptions (98 ICD-10 ranges)"


@dataclass
class BillingStrategyRecommendation:
    """Per-chapter package vs. itemized billing recommendation."""

    recommendations: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_EXACT
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(default_factory=list)
    rule_source: str = "EK-2C DRG package pricing, EK-2B fee-for-service pricing"

    @property
    def total_savings(self) -> float:
        """Sum of all recommendation savings_try values (includes legacy rows)."""
        total = 0.0
        for recommendation in self.recommendations:
            savings = recommendation.get("savings_try")
            if savings is not None:
                total += float(savings)
        return total

    @property
    def optional_override_opportunities(self) -> list[dict[str, Any]]:
        """§2.2.2(2) rows with recoverable uplift (higher legal method not yet billed)."""
        return [
            recommendation
            for recommendation in self.recommendations
            if recommendation.get("recommendation_kind") == "optional_override"
            and float(recommendation.get("savings_try") or 0.0) > 0
        ]

    @property
    def optional_override_uplift_try(self) -> float:
        return round(
            sum(
                float(row.get("savings_try") or 0.0)
                for row in self.optional_override_opportunities
            ),
            2,
        )

    @property
    def uplift_savings_try(self) -> float:
        """SGK uplift from claim-level strategy rows with positive corrective/override savings."""
        total = 0.0
        for recommendation in self.recommendations:
            if recommendation.get("type") == "compliance_violation":
                continue
            if not recommendation.get("recommendation_kind"):
                continue
            if recommendation.get("included_in_sgk_total") is False:
                continue
            savings = recommendation.get("savings_try")
            if savings is None:
                continue
            amount = float(savings)
            if amount > 0:
                total += amount
        return round(total, 2)


@dataclass
class SessionPricingUplift:
    """Recoverable SGK uplift from same-session point-factor under-billing."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = SESSION_UPLIFT_UNAVAILABLE_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(SESSION_UPLIFT_REQUIRED_INPUTS)
    )
    rule_source: str = "SUT §2.2.2.B session point factors — under-billing"

    @property
    def total_uplift_try(self) -> float:
        """Rule-calculated uplift across all opportunities (including review rows)."""
        return round(
            sum(float(row.get("recoverable_uplift_try") or 0.0) for row in self.opportunities),
            2,
        )

    @property
    def confirmed_uplift_try(self) -> float:
        """Uplift counted in SGK headline (excludes needs_clinical_review)."""
        return round(
            sum(
                float(row.get("recoverable_uplift_try") or 0.0)
                for row in self.opportunities
                if row.get("included_in_sgk_total", True)
            ),
            2,
        )

    @property
    def review_uplift_try(self) -> float:
        return round(self.total_uplift_try - self.confirmed_uplift_try, 2)

    @property
    def review_opportunity_count(self) -> int:
        return sum(
            1
            for row in self.opportunities
            if row.get("review_kind") == "needs_clinical_review"
        )


@dataclass
class MaterialPreCheck:
    """Material reimbursability pre-check for a single patient."""

    pre_auth_required: list[dict[str, Any]] = field(default_factory=list)
    miat_restricted: list[dict[str, Any]] = field(default_factory=list)
    miat_interval_violations: list[dict[str, Any]] = field(default_factory=list)
    bundled_separate_billing: list[dict[str, Any]] = field(default_factory=list)
    prose_bundling_violations: list[dict[str, Any]] = field(default_factory=list)
    specialty_prose_violations: list[dict[str, Any]] = field(default_factory=list)
    specialty_coverage_scope: dict[str, Any] = field(
        default_factory=specialty_materials_coverage_scope
    )
    kdv_price_reviews: list[dict[str, Any]] = field(default_factory=list)
    gazette_ceiling_by_specialty: dict[str, float] = field(default_factory=dict)
    exactness_status: str = EXACTNESS_STATUS_PARTIAL
    unavailable_reason: str | None = MATERIALS_PARTIAL_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(MATERIALS_REQUIRED_INPUTS)
    )
    rule_source: str = (
        "EK-3 specialty price benchmarks (partial); EK-3C-1/2 on exact claim lines"
    )
    coverage_scope: dict[str, Any] = field(default_factory=material_bundling_coverage_scope)


@dataclass
class BloodComponentUplift:
    """Recoverable SGK uplift from blood component fraction under-billing."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = BLOOD_UPLIFT_UNAVAILABLE_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(BLOOD_UPLIFT_REQUIRED_INPUTS)
    )
    rule_source: str = "SUT §2.2.2.B-1.e blood component fraction — under-billing"

    @property
    def confirmed_uplift_try(self) -> float:
        return round(
            sum(
                float(row.get("recoverable_uplift_try") or 0.0)
                for row in self.opportunities
                if row.get("included_in_sgk_total", True)
            ),
            2,
        )

    @property
    def total_uplift_try(self) -> float:
        return round(
            sum(float(row.get("recoverable_uplift_try") or 0.0) for row in self.opportunities),
            2,
        )


@dataclass
class MaterialUplift:
    """Recoverable SGK uplift from missing separately billable materials."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = MATERIAL_UPLIFT_UNAVAILABLE_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(MATERIAL_UPLIFT_REQUIRED_INPUTS)
    )
    rule_source: str = "SUT §3.1 missing billable material pairing — uplift-only"

    @property
    def confirmed_uplift_try(self) -> float:
        return round(
            sum(
                float(row.get("recoverable_uplift_try") or 0.0)
                for row in self.opportunities
                if row.get("included_in_sgk_total", True)
            ),
            2,
        )

    @property
    def total_uplift_try(self) -> float:
        return round(
            sum(float(row.get("recoverable_uplift_try") or 0.0) for row in self.opportunities),
            2,
        )


@dataclass
class ProcedureAddonUplift:
    """Recoverable SGK uplift from missing same-session procedure add-ons."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = PROCEDURE_ADDON_UPLIFT_UNAVAILABLE_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(PROCEDURE_ADDON_UPLIFT_REQUIRED_INPUTS)
    )
    rule_source: str = "SUT §2.2.2 procedure add-on pairing — uplift-only"

    @property
    def confirmed_uplift_try(self) -> float:
        return round(
            sum(
                float(row.get("recoverable_uplift_try") or 0.0)
                for row in self.opportunities
                if row.get("included_in_sgk_total", True)
            ),
            2,
        )

    @property
    def total_uplift_try(self) -> float:
        return round(
            sum(float(row.get("recoverable_uplift_try") or 0.0) for row in self.opportunities),
            2,
        )


@dataclass
class GazetteRepricingOpportunity:
    """Prospective repricing when a post-service tebliğ raised gazette list prices."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_EXACT
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(default_factory=list)
    rule_source: str = "EK-2B/EK-2C gazette amendment repricing — prospective"

    @property
    def total_repricing_try(self) -> float:
        return round(
            sum(
                float(row.get("recoverable_repricing_try") or 0.0)
                for row in self.opportunities
            ),
            2,
        )

    @property
    def confirmed_repricing_try(self) -> float:
        return round(
            sum(
                float(row.get("recoverable_repricing_try") or 0.0)
                for row in self.opportunities
                if row.get("included_in_sgk_total", True)
            ),
            2,
        )

    @property
    def review_repricing_try(self) -> float:
        return round(self.total_repricing_try - self.confirmed_repricing_try, 2)


@dataclass
class DrgPackageAdequacyReview:
    """Advisory review when billed EK-2/C package may be under-coded."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_EXACT
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(DRG_PACKAGE_ADEQUACY_REQUIRED_INPUTS)
    )
    rule_source: str = "SUT §2.2.1.B package adequacy — documentation review"

    @property
    def total_uplift_try(self) -> float:
        return round(
            sum(float(row.get("recoverable_uplift_try") or 0.0) for row in self.opportunities),
            2,
        )

    @property
    def confirmed_uplift_try(self) -> float:
        return round(
            sum(
                float(row.get("recoverable_uplift_try") or 0.0)
                for row in self.opportunities
                if row.get("included_in_sgk_total", True)
            ),
            2,
        )

    @property
    def review_uplift_try(self) -> float:
        return round(self.total_uplift_try - self.confirmed_uplift_try, 2)

    @property
    def review_opportunity_count(self) -> int:
        return sum(
            1
            for row in self.opportunities
            if row.get("review_kind") == "needs_coding_review"
        )


@dataclass
class MedulaRejectionPlaybook:
    """Operational corrective rebill templates for ingested MEDULA rejections."""

    entries: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_EXACT
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(default_factory=list)
    rule_source: str = "MEDULA rejection playbook — corrective template"

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    @property
    def rebill_permitted_count(self) -> int:
        return sum(1 for row in self.entries if row.get("rebill_permitted"))


@dataclass
class ProcedureCaptureGap:
    """Display-only gap when EMR shows performed procedures not on the claim."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_EXACT
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(default_factory=list)
    rule_source: str = "EMR/OR performed procedure log — capture gap"

    @property
    def total_gap_try(self) -> float:
        return round(
            sum(float(row.get("recoverable_gap_try") or 0.0) for row in self.opportunities),
            2,
        )

    @property
    def confirmed_gap_try(self) -> float:
        return round(
            sum(
                float(row.get("recoverable_gap_try") or 0.0)
                for row in self.opportunities
                if not row.get("included_in_sgk_total", True)
            ),
            2,
        )


@dataclass
class CareSettingReview:
    """Advisory coding-review uplift from inpatient vs outpatient ambiguity."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = CARE_SETTING_REVIEW_UNAVAILABLE_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(CARE_SETTING_REVIEW_REQUIRED_INPUTS)
    )
    rule_source: str = "SUT §2.2.1.B / §2.2.2 care-setting ambiguity — advisory"

    @property
    def total_uplift_try(self) -> float:
        return round(
            sum(float(row.get("recoverable_uplift_try") or 0.0) for row in self.opportunities),
            2,
        )

    @property
    def confirmed_uplift_try(self) -> float:
        return round(
            sum(
                float(row.get("recoverable_uplift_try") or 0.0)
                for row in self.opportunities
                if row.get("included_in_sgk_total", True)
            ),
            2,
        )

    @property
    def review_uplift_try(self) -> float:
        return round(self.total_uplift_try - self.confirmed_uplift_try, 2)

    @property
    def review_opportunity_count(self) -> int:
        return sum(
            1
            for row in self.opportunities
            if row.get("review_kind") == "needs_clinical_review"
        )


@dataclass
class DrgUpliftRecommendation:
    """Recoverable SGK uplift from itemized vs package billing comparison."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = DRG_UPLIFT_UNAVAILABLE_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(DRG_UPLIFT_REQUIRED_INPUTS)
    )
    rule_source: str = "SUT §2.2.2 itemized vs package — uplift-only"

    @property
    def confirmed_uplift_try(self) -> float:
        return round(
            sum(
                float(row.get("recoverable_uplift_try") or 0.0)
                for row in self.opportunities
                if row.get("included_in_sgk_total", True)
            ),
            2,
        )

    @property
    def total_uplift_try(self) -> float:
        return round(
            sum(float(row.get("recoverable_uplift_try") or 0.0) for row in self.opportunities),
            2,
        )


@dataclass
class BillingActionReport:
    """Complete billing action report for a single patient."""

    patient_id: str = ""
    lab: LabOptimization = field(default_factory=LabOptimization)
    copay: CopayOptimization = field(default_factory=CopayOptimization)
    billing_strategy: BillingStrategyRecommendation = field(
        default_factory=BillingStrategyRecommendation
    )
    materials: MaterialPreCheck = field(default_factory=MaterialPreCheck)
    session_uplift: SessionPricingUplift = field(default_factory=SessionPricingUplift)
    drg_uplift: DrgUpliftRecommendation = field(default_factory=DrgUpliftRecommendation)
    blood_uplift: BloodComponentUplift = field(default_factory=BloodComponentUplift)
    material_uplift: MaterialUplift = field(default_factory=MaterialUplift)
    care_setting_review: CareSettingReview = field(default_factory=CareSettingReview)
    procedure_addon_uplift: ProcedureAddonUplift = field(
        default_factory=ProcedureAddonUplift
    )
    procedure_capture_gap: ProcedureCaptureGap = field(
        default_factory=ProcedureCaptureGap
    )
    drg_package_adequacy: DrgPackageAdequacyReview = field(
        default_factory=DrgPackageAdequacyReview
    )
    gazette_repricing: GazetteRepricingOpportunity = field(
        default_factory=GazetteRepricingOpportunity
    )
    medula_rejection_playbook: MedulaRejectionPlaybook = field(
        default_factory=MedulaRejectionPlaybook
    )
    medula_rejection_ingest_available: bool = False
    sgk_uplift_try: float = 0.0
    compliance_adjustment_try: float = 0.0
    audit_exposure_try: float = 0.0
    capture_gap_try: float = 0.0
    package_adequacy_review_try: float = 0.0
    gazette_repricing_try: float = 0.0
    medula_playbook_entry_count: int = 0
    total_recoverable_try: float = 0.0
    action_count: int = 0
    priority: str = "low"
    exactness_status: str = EXACTNESS_STATUS_EXACT
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(default_factory=list)


@dataclass
class CohortRecoverySummary:
    """Cohort-level revenue recovery aggregation."""

    n_patients: int = 0
    total_lab_savings: float = 0.0
    total_copay_savings: float = 0.0
    total_strategy_savings: float = 0.0
    total_session_uplift: float = 0.0
    total_drg_uplift: float = 0.0
    total_blood_uplift: float = 0.0
    total_optional_override_uplift: float = 0.0
    n_optional_override_patients: int = 0
    n_drg_uplift_patients: int = 0
    n_blood_uplift_patients: int = 0
    total_material_uplift: float = 0.0
    n_material_uplift_patients: int = 0
    total_procedure_addon_uplift: float = 0.0
    n_procedure_addon_patients: int = 0
    total_strategy_uplift: float = 0.0
    total_compliance_adjustment: float = 0.0
    total_sgk_uplift: float = 0.0
    total_audit_exposure: float = 0.0
    total_capture_gap: float = 0.0
    total_package_adequacy_review: float = 0.0
    total_gazette_repricing: float = 0.0
    total_medula_playbook_entries: int = 0
    medula_rejection_ingest_available: bool = False
    total_material_flags: int = 0
    grand_total_recoverable: float = 0.0
    top_patients: list[dict[str, Any]] = field(default_factory=list)
    patient_summaries: list[dict[str, Any]] = field(default_factory=list)
    savings_by_category: dict[str, float] = field(default_factory=dict)
    priority_distribution: dict[str, int] = field(default_factory=dict)
    exactness_status: str = EXACTNESS_STATUS_EXACT
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(default_factory=list)

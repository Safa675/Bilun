"""
src/bilun/domain/billing/types.py
Dataclasses for billing optimization results.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.bilun.domain.materials.coverage_scope import material_bundling_coverage_scope
from src.bilun.domain.materials.specialty_coverage_scope import specialty_materials_coverage_scope
from typing import Any

from .drug_indication_findings import (
    DrugIndicationFinding,
    DrugIndicationLineEvaluation,
)
from .wavea_evidence import WaveAEvidenceBlock

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
BILLING_STRATEGY_REQUIRED_INPUTS = (
    "itemized_billed_procedure_lines",
    "episode_package_eligibility_context",
    "admission_dates",
)
BILLING_STRATEGY_UNAVAILABLE_REASON = (
    "Billing strategy comparison requires exact itemized billed procedure lines, "
    "package eligibility context, and admission dates, which are not available "
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
YATAK_PUANI_REQUIRED_INPUTS = (
    "inpatient_claims_with_dates",
    "procedure_claim_lines",
)
YATAK_PUANI_UNAVAILABLE_REASON = (
    "Yatak puanı requires inpatient claims with admission/discharge dates and "
    "procedure claim lines, which are not available in the active SUT runtime inputs."
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
MEDULA_PLAYBOOK_REQUIRED_INPUTS = (
    "medula_rejection_events",
)
MEDULA_PLAYBOOK_UNAVAILABLE_REASON = (
    "MEDULA rebill playbook requires optional MEDULA rejection event ingest rows."
)
CLAIM_SUBMISSION_CHECKLIST_REQUIRED_INPUTS = (
    "procedure_claim_lines",
    "material_claim_lines",
    "dispensed_drug_claim_lines",
)
CLAIM_SUBMISSION_CHECKLIST_UNAVAILABLE_REASON = (
    "Claim submission checklist requires exact claim lines with optional report and "
    "registration flags."
)
DRUG_INDICATION_REQUIRED_INPUTS = (
    "dispensed_drug_claim_lines",
    "claim_primary_icd10",
)
DRUG_INDICATION_UNAVAILABLE_REASON = (
    "Drug indication validation requires exact dispensed drug claim lines with "
    "primary ICD-10 context, which are not available in the active SUT runtime inputs."
)
DRUG_INDICATION_CORPUS_UNAVAILABLE_REASON = (
    "Drug is not covered by the encoded Drug Indication corpus; manual SUT review "
    "is required and no financial value is inferred."
)


class _UpliftBlockMixin:
    """Shared uplift-sum properties for dataclasses with ``opportunities: list[dict]``.

    Eliminates the 7× copy-pasted ``confirmed_uplift_try`` / ``total_uplift_try``
    pattern across SessionPricingUplift, BloodComponentUplift, MaterialUplift,
    ProcedureAddonUplift, DrgPackageAdequacyReview, CareSettingReview, and
    DrgUpliftRecommendation. Each carries ``opportunities`` as a list of dicts
    with ``recoverable_uplift_try``, ``included_in_sgk_total``, and optionally
    ``review_uplift_try`` / ``review_kind`` keys.
    """

    @property
    def confirmed_uplift_try(self) -> float:
        """Uplift counted in SGK headline (rows where ``included_in_sgk_total`` is True)."""
        return round(
            sum(
                float(row.get("recoverable_uplift_try") or 0.0)
                for row in self.opportunities  # type: ignore[attr-defined]
                if row.get("included_in_sgk_total", True)
            ),
            2,
        )

    @property
    def total_uplift_try(self) -> float:
        """Total uplift across ALL opportunity rows (including non-SGK-counted)."""
        return round(
            sum(
                float(row.get("recoverable_uplift_try") or 0.0)
                for row in self.opportunities  # type: ignore[attr-defined]
            ),
            2,
        )


class _ReviewableUpliftBlockMixin(_UpliftBlockMixin):
    """Adds clinical-review properties for blocks that carry review-kind rows.

    Used by the 3 blocks (SessionPricingUplift, DrgPackageAdequacyReview,
    CareSettingReview) whose ``total_uplift_try`` includes review-flagged rows
    and that surface ``review_uplift_try`` + ``review_opportunity_count``.
    """

    @property
    def total_uplift_try(self) -> float:
        """Total = confirmed + review (audit total including clinical-review rows)."""
        return round(self.confirmed_uplift_try + self.review_uplift_try, 2)

    @property
    def review_uplift_try(self) -> float:
        return round(
            sum(
                float(row.get("review_uplift_try") or 0.0)
                for row in self.opportunities  # type: ignore[attr-defined]
            ),
            2,
        )

    @property
    def review_opportunity_count(self) -> int:
        return sum(
            1
            for row in self.opportunities  # type: ignore[attr-defined]
            if row.get("review_kind") == "needs_clinical_review"
        )


@dataclass
class LabOptimization:
    """Normative lab billing analysis for a single patient."""

    normative_cost_try: float | None = None
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
    exemption_sources: list[dict[str, Any]] = field(default_factory=list)
    categories_not_evaluated: list[dict[str, Any]] = field(default_factory=list)
    primary_exemption_category: str | None = None
    copay_primary_outcome: str = "none"
    savings_beneficiary: str = COPAY_SAVINGS_BENEFICIARY_PATIENT_AND_SGK
    gap_kind: str = COPAY_GAP_KIND_EXEMPTION_CORRECTION
    visit_copay_savings_try: float | None = None  # procedure-line exemption gap (legacy name)
    rx_copay_savings_try: float | None = None  # prescription exemption gap (legacy name)
    total_copay_savings_try: float | None = None  # procedure gap only (legacy field name)
    patient_copay_waived_total_try: float | None = None  # total exemption gap (visit + rx)
    patient_copay_try: float | None = None  # total katılım payı before waiver
    ilave_ucret_total_try: float | None = None  # total ilave ücret (never waived)
    line_decomposition_status: str = "missing_inputs"
    rx_copay_savings_by_ground: dict[str, float] = field(default_factory=dict)
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
class SessionPricingUplift(_ReviewableUpliftBlockMixin):
    """Recoverable SGK uplift from same-session point-factor under-billing."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = SESSION_UPLIFT_UNAVAILABLE_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(SESSION_UPLIFT_REQUIRED_INPUTS)
    )
    rule_source: str = "SUT §2.2.2.B session point factors — under-billing"


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
class BloodComponentUplift(_UpliftBlockMixin):
    """Recoverable SGK uplift from blood component fraction under-billing."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = BLOOD_UPLIFT_UNAVAILABLE_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(BLOOD_UPLIFT_REQUIRED_INPUTS)
    )
    rule_source: str = "SUT §2.2.2.B-1.e blood component fraction — under-billing"


@dataclass
class YatakPuaniReview:
    """Expected bed-day (yatak puanı) charges for inpatient claims."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = YATAK_PUANI_UNAVAILABLE_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(YATAK_PUANI_REQUIRED_INPUTS)
    )
    rule_source: str = (
        "SUT §2.2.2 standard bed tariff (510010) — inclusive LOS × price_try"
    )

    @property
    def confirmed_yatak_try(self) -> float:
        return round(
            sum(
                float(
                    row["recoverable_uplift_try"]
                    if row.get("recoverable_uplift_try") is not None
                    else (row.get("expected_yatak_try") or 0.0)
                )
                for row in self.opportunities
                if row.get("included_in_sgk_total", True)
            ),
            2,
        )


@dataclass
class IcuPuaniReview:
    """Expected ICU (yoğun bakım) charges — dual day-rate + package model."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(default_factory=list)
    rule_source: str = (
        "SUT §2.4.4.H ICU dual-charging — 510090 (first/last day) + "
        "P55200x (intermediate days)"
    )

    @property
    def confirmed_icu_try(self) -> float:
        return round(
            sum(
                float(
                    row["recoverable_uplift_try"]
                    if row.get("recoverable_uplift_try") is not None
                    else (row.get("total_try") or 0.0)
                )
                for row in self.opportunities
                if row.get("included_in_sgk_total", True)
            ),
            2,
        )


@dataclass
class YenidoganYatakReview:
    """Expected newborn bed charges (Kuvöz/Kot) for newborn inpatient claims."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(default_factory=list)
    rule_source: str = (
        "EK-2B 510070 (Kuvöz) / 510081 (Kot) — newborn inpatient bed charges"
    )

    @property
    def confirmed_yenidogan_yatak_try(self) -> float:
        return round(
            sum(
                float(row.get("expected_try") or 0.0)
                for row in self.opportunities
                if row.get("included_in_sgk_total", True)
            ),
            2,
        )


@dataclass
class RefakatciReview:
    """Expected companion (refakatçi) bed charges for inpatient claims."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(default_factory=list)
    rule_source: str = (
        "SUT §2.6.3 + EK-2B 510121 (Refakat) — companion bed charges"
    )

    @property
    def confirmed_refakat_try(self) -> float:
        return round(
            sum(
                float(
                    row["recoverable_uplift_try"]
                    if row.get("recoverable_uplift_try") is not None
                    else (row.get("expected_try") or 0.0)
                )
                for row in self.opportunities
                if row.get("included_in_sgk_total", True)
            ),
            2,
        )


@dataclass
class AnesteziPuaniReview:
    """Expected anesthesia (anestezi puanı) charges for inpatient surgical procedures."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(default_factory=list)
    rule_source: str = (
        "SUT §2.2.2.A + EK-2/B §4 anestezi — surgical puan range → group puan (550130-550260)"
    )

    @property
    def confirmed_anestezi_try(self) -> float:
        return round(
            sum(
                float(
                    row["recoverable_uplift_try"]
                    if row.get("recoverable_uplift_try") is not None
                    else (row.get("expected_try") or 0.0)
                )
                for row in self.opportunities
                if row.get("included_in_sgk_total", True)
            ),
            2,
        )


@dataclass
class MaterialUplift(_UpliftBlockMixin):
    """Recoverable SGK uplift from missing separately billable materials."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = MATERIAL_UPLIFT_UNAVAILABLE_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(MATERIAL_UPLIFT_REQUIRED_INPUTS)
    )
    rule_source: str = "SUT §3.1 missing billable material pairing — uplift-only"


@dataclass
class ProcedureAddonUplift(_UpliftBlockMixin):
    """Recoverable SGK uplift from missing same-session procedure add-ons."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = PROCEDURE_ADDON_UPLIFT_UNAVAILABLE_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(PROCEDURE_ADDON_UPLIFT_REQUIRED_INPUTS)
    )
    rule_source: str = "SUT §2.2.2 procedure add-on pairing — uplift-only"


@dataclass
class DrgPackageAdequacyReview(_UpliftBlockMixin):
    """Advisory review when billed EK-2/C package may be under-coded."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_EXACT
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(DRG_PACKAGE_ADEQUACY_REQUIRED_INPUTS)
    )
    rule_source: str = "SUT §2.2.1.B package adequacy — documentation review"

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
class ClaimSubmissionChecklist:
    """Proactive MEDULA rejection-risk reminders before submission."""

    items: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_EXACT
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(default_factory=list)
    rule_source: str = (
        "Claim submission checklist — proactive MEDULA risk triggers (Sprint 4)"
    )

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def error_count(self) -> int:
        return sum(1 for row in self.items if row.get("severity") == "error")


@dataclass
class DrugIndicationReview:
    """§4.2 pilot indication / report checks on exact drug claim lines."""

    violations: list[dict[str, Any]] = field(default_factory=list)
    findings: list[DrugIndicationFinding] = field(default_factory=list)
    evaluations: list[DrugIndicationLineEvaluation] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = DRUG_INDICATION_UNAVAILABLE_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(DRUG_INDICATION_REQUIRED_INPUTS)
    )
    rule_source: str = "SUT §4.2 drug indication prose — Phase 2 corpus"
    coverage_scope: dict[str, Any] = field(default_factory=dict)

    @property
    def violation_count(self) -> int:
        return len(self.findings) if self.findings else len(self.violations)

    @property
    def error_count(self) -> int:
        if self.findings:
            return sum(1 for finding in self.findings if finding.severity == "error")
        return sum(1 for row in self.violations if row.get("severity") == "error")

    def to_dict(self) -> dict[str, Any]:
        """Return the same derived-count contract used by the API serializer."""
        return {
            "violations": list(self.violations),
            "findings": [finding.to_dict() for finding in self.findings],
            "evaluations": [evaluation.to_dict() for evaluation in self.evaluations],
            "exactness_status": self.exactness_status,
            "unavailable_reason": self.unavailable_reason,
            "required_inputs_missing": list(self.required_inputs_missing),
            "rule_source": self.rule_source,
            "coverage_scope": dict(self.coverage_scope),
            "violation_count": self.violation_count,
            "error_count": self.error_count,
        }


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
class CareSettingReview(_UpliftBlockMixin):
    """Advisory coding-review uplift from inpatient vs outpatient ambiguity."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = CARE_SETTING_REVIEW_UNAVAILABLE_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(CARE_SETTING_REVIEW_REQUIRED_INPUTS)
    )
    rule_source: str = "SUT §2.2.1.B / §2.2.2 care-setting ambiguity — advisory"

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
class DrgUpliftRecommendation(_UpliftBlockMixin):
    """Recoverable SGK uplift from itemized vs package billing comparison."""

    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = DRG_UPLIFT_UNAVAILABLE_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(DRG_UPLIFT_REQUIRED_INPUTS)
    )
    rule_source: str = "SUT §2.2.2 itemized vs package — uplift-only"


@dataclass
class ClaimCompliance:
    findings: list[dict[str, Any]] = field(default_factory=list)
    evaluations: list[dict[str, Any]] = field(default_factory=list)


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
    yatak_puani: YatakPuaniReview = field(default_factory=YatakPuaniReview)
    icu_puani: IcuPuaniReview = field(default_factory=IcuPuaniReview)
    yenidogan_yatak: YenidoganYatakReview = field(default_factory=YenidoganYatakReview)
    refakatci: RefakatciReview = field(default_factory=RefakatciReview)
    anestezi_puani: AnesteziPuaniReview = field(default_factory=AnesteziPuaniReview)
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
    medula_rejection_playbook: MedulaRejectionPlaybook = field(
        default_factory=MedulaRejectionPlaybook
    )
    claim_submission_checklist: ClaimSubmissionChecklist = field(
        default_factory=ClaimSubmissionChecklist
    )
    drug_indication: DrugIndicationReview = field(default_factory=DrugIndicationReview)
    medula_rejection_ingest_available: bool = False
    sgk_uplift_try: float | None = None
    compliance_adjustment_try: float | None = None
    audit_exposure_try: float | None = None
    capture_gap_try: float | None = None
    package_adequacy_review_try: float | None = None
    medula_playbook_entry_count: int = 0
    claim_submission_checklist_count: int = 0
    drug_indication_violation_count: int = 0
    total_recoverable_try: float | None = None
    # The entries behind ``audit_exposure_try`` that carry risk (session factor, blood
    # component, bundled lines); ``collect_billing_actions`` makes ``audit_exposure`` rows.
    audit_exposure_rows: list[dict[str, Any]] = field(default_factory=list)
    recommended_actions: list[dict[str, Any]] = field(default_factory=list)
    action_count: int = 0
    priority: str = "low"
    exactness_status: str = EXACTNESS_STATUS_EXACT
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(default_factory=list)
    claim_compliance: ClaimCompliance = field(default_factory=ClaimCompliance)
    claim_reviews: WaveAEvidenceBlock = field(default_factory=WaveAEvidenceBlock)
    claim_advisories: WaveAEvidenceBlock = field(default_factory=WaveAEvidenceBlock)
    financial_findings: WaveAEvidenceBlock = field(default_factory=WaveAEvidenceBlock)
    wavea_coverage: dict[str, Any] | None = None
    # Kept only until cache build writes the separate patient detail table.
    # Default report/API serialization must remove this exhaustive payload.
    wavea_evidence_detail: dict[str, Any] | None = field(default=None, repr=False)


@dataclass
class CohortRecoverySummary:
    """Cohort-level revenue recovery aggregation."""

    n_patients: int = 0
    n_patients_with_actions: int = 0
    total_lab_savings: float = 0.0
    total_copay_savings: float = 0.0
    total_strategy_savings: float = 0.0
    total_session_uplift: float = 0.0
    total_drg_uplift: float = 0.0
    total_blood_uplift: float = 0.0
    total_yatak_puani: float = 0.0
    total_icu_puani: float = 0.0
    total_yenidogan_yatak: float = 0.0
    total_refakatci: float = 0.0
    total_anestezi_puani: float = 0.0
    total_optional_override_uplift: float = 0.0
    n_optional_override_patients: int = 0
    n_drg_uplift_patients: int = 0
    n_blood_uplift_patients: int = 0
    n_yatak_puani_patients: int = 0
    n_icu_puani_patients: int = 0
    n_yenidogan_yatak_patients: int = 0
    n_refakatci_patients: int = 0
    n_anestezi_puani_patients: int = 0
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

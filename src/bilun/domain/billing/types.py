"""
src/bilun/domain/billing/types.py
Dataclasses for billing optimization results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EXACTNESS_STATUS_EXACT = "exact"
EXACTNESS_STATUS_PARTIAL = "partial_exact"
EXACTNESS_STATUS_MISSING_INPUTS = "missing_exact_inputs"

DRUG_REQUIRED_INPUTS = (
    "dispensed_drug_claim_lines",
    "drug_claim_dates",
    "billed_drug_amounts",
)
DRUG_UNAVAILABLE_REASON = (
    "Drug optimization savings remain estimate-based until exact dispensed drug "
    "claim lines and billed drug amounts are available in the active SUT "
    "runtime inputs."
)
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
    "Materials pre-check findings mix exact pre-authorization and MIAT rules "
    "with non-exact ceiling heuristics, so the section should not be treated "
    "as fully exact."
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


@dataclass
class LabOptimization:
    """Normative lab billing analysis for a single patient."""

    normative_cost_try: float = 0.0
    hemogram_bundling_savings: float = 0.0
    duplicate_test_savings: float = 0.0
    flagged_tests: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_EXACT
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(default_factory=list)
    rule_source: str = "EK-2B hemogram bundling hierarchy, EK-2B duplicate test rules"

    @property
    def total_savings(self) -> float:
        return self.hemogram_bundling_savings + self.duplicate_test_savings


@dataclass
class DrugOptimization:
    """Drug cost optimization analysis for a single patient."""

    generic_substitution_savings: float = 0.0
    n_generics_available: int = 0
    passivated_drug_count: int = 0
    drug_recommendations: list[dict[str, Any]] = field(default_factory=list)
    exactness_status: str = EXACTNESS_STATUS_MISSING_INPUTS
    unavailable_reason: str | None = DRUG_UNAVAILABLE_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(DRUG_REQUIRED_INPUTS)
    )
    rule_source: str = "EK-4A drug equivalence groups and discount tiers"

    @property
    def total_savings(self) -> float:
        return self.generic_substitution_savings


@dataclass
class CopayOptimization:
    """Copayment optimization analysis for a single patient."""

    is_exempt: bool = False
    exemption_disease: str = ""
    exemption_range: str = ""
    visit_copay_savings_try: float = 0.0
    rx_copay_savings_try: float = 0.0
    total_copay_savings_try: float = 0.0  # procedure/visit copay only; rx tracked separately
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
        total = 0.0
        for recommendation in self.recommendations:
            savings = recommendation.get("savings_try")
            if savings is not None:
                total += float(savings)
        return total


@dataclass
class MaterialPreCheck:
    """Material reimbursability pre-check for a single patient."""

    pre_auth_required: list[dict[str, Any]] = field(default_factory=list)
    miat_restricted: list[dict[str, Any]] = field(default_factory=list)
    gazette_ceiling_by_specialty: dict[str, float] = field(default_factory=dict)
    exactness_status: str = EXACTNESS_STATUS_PARTIAL
    unavailable_reason: str | None = MATERIALS_PARTIAL_REASON
    required_inputs_missing: list[str] = field(
        default_factory=lambda: list(MATERIALS_REQUIRED_INPUTS)
    )
    rule_source: str = "EK-3C-1 sağlık kurulu pre-authorization, EK-3C-2 MIAT intervals"


@dataclass
class BillingActionReport:
    """Complete billing action report for a single patient."""

    patient_id: str = ""
    lab: LabOptimization = field(default_factory=LabOptimization)
    drug: DrugOptimization = field(default_factory=DrugOptimization)
    copay: CopayOptimization = field(default_factory=CopayOptimization)
    billing_strategy: BillingStrategyRecommendation = field(
        default_factory=BillingStrategyRecommendation
    )
    materials: MaterialPreCheck = field(default_factory=MaterialPreCheck)
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
    total_drug_savings: float = 0.0
    total_copay_savings: float = 0.0
    total_strategy_savings: float = 0.0
    total_material_flags: int = 0
    grand_total_recoverable: float = 0.0
    top_patients: list[dict[str, Any]] = field(default_factory=list)
    patient_summaries: list[dict[str, Any]] = field(default_factory=list)
    savings_by_category: dict[str, float] = field(default_factory=dict)
    priority_distribution: dict[str, int] = field(default_factory=dict)
    exactness_status: str = EXACTNESS_STATUS_EXACT
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = field(default_factory=list)

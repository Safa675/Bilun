"""
src/bilun/domain/billing package.

Normative billing optimization engine — claim-backed algorithms + cohort aggregator.

Transforms SUT claim lines into actionable, TRY-denominated
per-patient revenue leakage/recovery recommendations.

Modules:
- types: Dataclasses for billing optimization results
- block_registry: Declarative billing block metadata
- claim_lab: Algorithm 1 — Lab hemogram bundling from claim lines (EK-2B L107020)
- claim_copay: Algorithm 2 — Copay savings calculator from claim lines
- claim_strategy: Algorithm 3 — Package vs itemized recommender from claim lines
- claim_materials: Algorithm 4 — Material reimbursability pre-check from claim lines
- patient_report: Single-patient report assembly
- cohort_runner: Parallel cohort billing runners
- orchestrator: Thin facade re-exporting public entry points

Re-exports for backward compatibility.
"""

import logging

logger = logging.getLogger("ilay.sut_billing_optimizer")

from .types import (
    LabOptimization,
    CopayOptimization,
    BillingStrategyRecommendation,
    MaterialPreCheck,
    SessionPricingUplift,
    BillingActionReport,
    CohortRecoverySummary,
)

from .orchestrator import (
    compute_patient_billing_report,
    compute_all_billing_reports,
    compute_all_bill_billing_reports,
    _get_top_action_type,
)

__all__ = [
    "LabOptimization",
    "CopayOptimization",
    "BillingStrategyRecommendation",
    "MaterialPreCheck",
    "SessionPricingUplift",
    "BillingActionReport",
    "CohortRecoverySummary",
    "compute_patient_billing_report",
    "compute_all_billing_reports",
    "compute_all_bill_billing_reports",
    "_get_top_action_type",
]

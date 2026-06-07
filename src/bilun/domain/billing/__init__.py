"""
src/bilun/domain/billing package.

Normative billing optimization engine — 4 algorithms + cohort aggregator.

Transforms descriptive SUT cost ranges into actionable, TRY-denominated
per-patient revenue leakage/recovery recommendations.

Modules:
- types: Dataclasses for billing optimization results
- lab: Algorithm 1 — Lab hemogram bundling (EK-2B L107020)
- copay: Algorithm 2 — Copay savings calculator
- strategy: Algorithm 3 — Package vs itemized recommender
- materials: Algorithm 4 — Material reimbursability pre-check
- orchestrator: Main entry points compute_patient_billing_report, compute_all_billing_reports

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

from .lab import _optimize_lab_billing, _get_gazette_lab_prices

from .copay import _optimize_copay

from .strategy import _recommend_billing_strategy

from .materials import (
    _precheck_materials,
    _get_specialty_price_stats,
    _get_ek3c1_preauth,
    _get_ek3c2_miat,
)

from .orchestrator import (
    compute_patient_billing_report,
    compute_all_billing_reports,
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
    "_optimize_lab_billing",
    "_get_gazette_lab_prices",
    "_optimize_copay",
    "_recommend_billing_strategy",
    "_precheck_materials",
    "_get_specialty_price_stats",
    "_get_ek3c1_preauth",
    "_get_ek3c2_miat",
    "_get_top_action_type",
]

"""
src/bilun/domain/billing package.

Normative billing optimization engine — 5 algorithms + cohort aggregator.

Transforms descriptive SUT cost ranges into actionable, TRY-denominated
per-patient revenue leakage/recovery recommendations.

Modules:
- types: Dataclasses for billing optimization results
- lab: Algorithm 1 — Lab billing optimizer
- drug: Algorithm 2 — Drug cost optimizer
- copay: Algorithm 3 — Copay savings calculator
- strategy: Algorithm 4 — Package vs itemized recommender
- materials: Algorithm 5 — Material reimbursability pre-check
- orchestrator: Main entry points compute_patient_billing_report, compute_all_billing_reports

Re-exports for backward compatibility.
"""

import logging

logger = logging.getLogger("ilay.sut_billing_optimizer")

from .types import (
    LabOptimization,
    DrugOptimization,
    CopayOptimization,
    BillingStrategyRecommendation,
    MaterialPreCheck,
    BillingActionReport,
    CohortRecoverySummary,
)

from .lab import _optimize_lab_billing, _get_gazette_lab_prices

from .drug import _optimize_drug_costs, _get_ek4a_by_equiv_group

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
    "DrugOptimization",
    "CopayOptimization",
    "BillingStrategyRecommendation",
    "MaterialPreCheck",
    "BillingActionReport",
    "CohortRecoverySummary",
    "compute_patient_billing_report",
    "compute_all_billing_reports",
    "_optimize_lab_billing",
    "_get_gazette_lab_prices",
    "_optimize_drug_costs",
    "_get_ek4a_by_equiv_group",
    "_optimize_copay",
    "_recommend_billing_strategy",
    "_precheck_materials",
    "_get_specialty_price_stats",
    "_get_ek3c1_preauth",
    "_get_ek3c2_miat",
    "_get_top_action_type",
]
"""
src/bilun/domain/optimization package.

Rule engines for SUT revenue optimization features.

Modules:
- shared: Shared helper functions and constants
- copay_exemptions: Feature 1 — EK-1A chronic disease exemptions
- surcharge: Feature 2 — EK-2G surcharge exposure
- copay_rates: Feature 3 — EK-2C-1 copay rate exposure
- temporal: Feature 4 — EK-2B/2C temporal audit
- unbundling: Feature 5 — DRG unbundling detection
- aggregator: Cohort-level aggregation

Re-exports for backward compatibility.
"""

import logging

logger = logging.getLogger("bilun.domain.optimization")

from .shared import (
    _is_blank,
    _icd10_in_range,
    _extract_diagnoses_bulk_pl,
    _extract_patient_icd10_chapters,
    _ICD10_CHAPTER_TO_PROCEDURE_PREFIXES,
)

from .copay_exemptions import (
    check_copay_exemptions,
    evaluate_copay_exemption,
)
from .copay_exemption_rules.ek1a import (
    _get_ek1a_by_letter,
    _precompute_exemption_map,
)

from .surcharge import analyze_surcharge_exposure

from .copay_rates import analyze_copay_rate_exposure

from .temporal import audit_temporal_prices, _temporal_audit_cache

from .unbundling import detect_drg_unbundling

from .aggregator import compute_optimization_summary

__all__ = [
    "_is_blank",
    "_icd10_in_range",
    "_extract_diagnoses_bulk_pl",
    "_extract_patient_icd10_chapters",
    "_ICD10_CHAPTER_TO_PROCEDURE_PREFIXES",
    "check_copay_exemptions",
    "evaluate_copay_exemption",
    "_get_ek1a_by_letter",
    "_precompute_exemption_map",
    "analyze_surcharge_exposure",
    "analyze_copay_rate_exposure",
    "audit_temporal_prices",
    "_temporal_audit_cache",
    "detect_drg_unbundling",
    "compute_optimization_summary",
]

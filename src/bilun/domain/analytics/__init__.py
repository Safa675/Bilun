"""
src/bilun/domain/analytics package.

Advanced SUT analytics modules:
- drg: DRG episode cost modeling
- materials: Material cost estimation
- shared: Shared helper functions

Re-exports for backward compatibility.
"""

import logging

logger = logging.getLogger("ilay.sut_pricing")

from .shared import _select_patient_rows

from .drg import DRGEpisode, DRGSummary, compute_drg_summary

from .materials import MaterialCostEstimate, estimate_material_costs

__all__ = [
    "_select_patient_rows",
    "DRGEpisode",
    "DRGSummary",
    "compute_drg_summary",
    "MaterialCostEstimate",
    "estimate_material_costs",
]

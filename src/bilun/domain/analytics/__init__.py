"""
src/bilun/domain/analytics package.

Advanced SUT analytics modules:
- drg: DRG episode cost modeling
- materials: Claim-line material pricing
- shared: Shared helper functions

Re-exports for backward compatibility.
"""

import logging

logger = logging.getLogger("ilay.sut_pricing")

from .shared import _select_patient_rows

from .drg import DRGEpisode, DRGSummary, compute_drg_summary
from .drg_payload import (
    normalize_cached_drg_summary_payload,
    serialize_drg_summary,
)

from .materials import MaterialLinePricing, price_material_lines

__all__ = [
    "_select_patient_rows",
    "DRGEpisode",
    "DRGSummary",
    "compute_drg_summary",
    "MaterialLinePricing",
    "normalize_cached_drg_summary_payload",
    "price_material_lines",
    "serialize_drg_summary",
]

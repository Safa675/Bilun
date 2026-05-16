"""
src/bilun/domain/materials package.

EK-3 materials, EK-3B exclusions, and EK-4A drug functions.

Modules:
- cardiac: EK-3H and EK-3I cardiac materials
- specialty: All EK-3 specialty catalogs
- exclusions: EK-3B-1 bundled consumables, EK-3B-2 non-reimbursable
- drugs: EK-4A drug reimbursement data

Re-exports for backward compatibility.
"""

import logging

logger = logging.getLogger("ilay.sut_catalog")

from .cardiac import (
    get_ek3_cardiology_materials,
    get_ek3_cv_surgery_materials,
    get_cardiac_material_price_range,
)

from .specialty import get_all_specialty_materials

from .exclusions import (
    get_non_reimbursable_materials,
    get_bundled_consumables,
    is_material_reimbursable,
    is_consumable_bundled,
)

from .drugs import (
    get_ek4a_drugs,
    lookup_drug,
    lookup_drug_bulk,
    classify_drug_tier,
)

__all__ = [
    "get_ek3_cardiology_materials",
    "get_ek3_cv_surgery_materials",
    "get_cardiac_material_price_range",
    "get_all_specialty_materials",
    "get_non_reimbursable_materials",
    "get_bundled_consumables",
    "is_material_reimbursable",
    "is_consumable_bundled",
    "get_ek4a_drugs",
    "lookup_drug",
    "lookup_drug_bulk",
    "classify_drug_tier",
]
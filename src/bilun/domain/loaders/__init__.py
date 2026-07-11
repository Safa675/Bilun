"""
src/bilun/domain/loaders package.

Compatibility facade for historical `src.bilun.domain.loaders` imports while splitting
loader responsibilities by source-specific modules.
"""

from .checkup import (
    _build_checkup_lab_index,
    _build_checkup_procedure_index,
    _load_checkup_json,
)
from .gazette import (
    _load_curated_ek2b_by_asof,
    _load_curated_ek2c_by_asof,
    _load_curated_ek2c_dental_by_asof,
    _load_ek2a,
    _load_ek3_materials_parquet,
    _load_gazette_lab_prices,
    _load_gazette_visit_prices,
    get_cached_ek2a,
    get_cached_ek3h,
    get_cached_ek3i,
)
from .legacy import (
    _load_ek1a_exemptions,
    _load_ek2c1_copay_rates,
    _load_ek2g_no_surcharge,
)

__all__ = [
    "_build_checkup_lab_index",
    "_build_checkup_procedure_index",
    "_load_checkup_json",
    "_load_curated_ek2b_by_asof",
    "_load_curated_ek2c_by_asof",
    "_load_curated_ek2c_dental_by_asof",
    "_load_ek1a_exemptions",
    "_load_ek2a",
    "_load_ek2c1_copay_rates",
    "_load_ek2g_no_surcharge",
    "_load_ek3_materials_parquet",
    "_load_gazette_lab_prices",
    "_load_gazette_visit_prices",
    "get_cached_ek2a",
    "get_cached_ek3h",
    "get_cached_ek3i",
]

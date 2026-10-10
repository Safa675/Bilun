"""
Curated SUT catalog specs, grouped by extractor family.

Each submodule exposes:
  - the family's extractor functions and any shared helpers they use
  - a local SPECS list of CatalogSpec entries for the annexes in that family

This __init__ assembles them into a single flat CATALOG_SPECS list consumed by
`scripts/sut/build_curated_catalogs.py`.
"""

from __future__ import annotations

from scripts.sut.catalogs.ek4a_history import SPECS as EK4A_HISTORY_SPECS
from scripts.sut.catalogs.hierarchical_materials import SPECS as HIERARCHICAL_SPECS
from scripts.sut.catalogs.optimization import SPECS as OPTIMIZATION_SPECS
from scripts.sut.catalogs.orthopedic_materials import SPECS as ORTHOPEDIC_SPECS
from scripts.sut.catalogs.price_history import SPECS as PRICE_HISTORY_SPECS
from scripts.sut.catalogs.simple_materials import SPECS as SIMPLE_SPECS
from scripts.sut.catalogs.vision_materials import SPECS as VISION_SPECS

CATALOG_SPECS: list[dict] = (
    PRICE_HISTORY_SPECS
    + SIMPLE_SPECS
    + EK4A_HISTORY_SPECS
    + HIERARCHICAL_SPECS
    + ORTHOPEDIC_SPECS
    + VISION_SPECS
    + OPTIMIZATION_SPECS
)

__all__ = ["CATALOG_SPECS"]

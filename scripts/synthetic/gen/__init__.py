"""Synthetic data generation package (split from generators.py)."""

from gen.claim_lines import ClaimEpisodeContext
from gen.materials_flags import MATERIAL_PROSE_FLAG_COLUMNS, SPECIALTY_PROSE_FLAG_COLUMNS
from gen.specs import (
    PAYMENT_METHOD_COMPLIANCE_DEMO_TAG,
    _CLAIM_READINESS_DEMO_SPECS,
    _MEDULA_DEMO_SPECS,
)
from gen.workbook import build_workbook_tables

__all__ = [
    "ClaimEpisodeContext",
    "MATERIAL_PROSE_FLAG_COLUMNS",
    "SPECIALTY_PROSE_FLAG_COLUMNS",
    "PAYMENT_METHOD_COMPLIANCE_DEMO_TAG",
    "_CLAIM_READINESS_DEMO_SPECS",
    "_MEDULA_DEMO_SPECS",
    "build_workbook_tables",
]

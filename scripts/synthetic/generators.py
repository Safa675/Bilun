"""Backward-compatible shim — import from gen/ implementation."""

from gen import (  # noqa: F401
    MATERIAL_PROSE_FLAG_COLUMNS,
    SPECIALTY_PROSE_FLAG_COLUMNS,
    PAYMENT_METHOD_COMPLIANCE_DEMO_TAG,
    ClaimEpisodeContext,
    _CLAIM_READINESS_DEMO_SPECS,
    _MEDULA_DEMO_SPECS,
    build_workbook_tables,
)

__all__ = [
    "MATERIAL_PROSE_FLAG_COLUMNS",
    "SPECIALTY_PROSE_FLAG_COLUMNS",
    "PAYMENT_METHOD_COMPLIANCE_DEMO_TAG",
    "ClaimEpisodeContext",
    "_CLAIM_READINESS_DEMO_SPECS",
    "_MEDULA_DEMO_SPECS",
    "build_workbook_tables",
]

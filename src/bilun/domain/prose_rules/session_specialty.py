"""§2.2.2.A(5) / §2.2.2.B(3) cross-specialty (+25 points) detection from claim lines."""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine


def normalize_specialty_key(raw: str) -> str:
    """Stable key for comparing procedure specialties (branch codes or names)."""
    text = str(raw or "").strip().casefold()
    if not text:
        return ""
    folded = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in folded if not unicodedata.combining(ch)).replace(" ", "_")


def resolve_procedure_specialty_key(line: ProcedureClaimLine) -> str:
    """Specialty (uzmanlık dalı) key of one procedure line; empty when unknown.

    Only the line's own ``procedure_specialty_code`` (branch) counts. The EK-2/C
    ``group`` is the işlem grubu (A1–E: price group and package window), not a
    specialty (#264); claim-level ``department`` would give every line one
    specialty and hide cross-specialty sessions.
    """
    return normalize_specialty_key(str(getattr(line, "procedure_specialty_code", "") or ""))


def detect_cross_specialty_session(
    lines: list[ProcedureClaimLine],
    claim: ClaimHeader | None = None,
) -> bool:
    """True when two or more procedures carry different known branches.

    The 25 points apply when the operations were done "farklı uzmanlık
    dallarında" (C000662, C000674); two known branches that differ establish
    that, and the percentages rise for the whole session. A line without a
    branch is unknown: it neither adds a specialty nor cancels a known
    difference, so two lines need a branch on both (#264). ``claim`` is
    accepted for callers' signature and is not used.
    """
    known = {key for key in (resolve_procedure_specialty_key(line) for line in lines) if key}
    return len(known) >= 2

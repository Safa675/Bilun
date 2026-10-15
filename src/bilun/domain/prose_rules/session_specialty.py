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
    """True when every procedure in the session has a branch and two or more differ.

    The 25 points apply only when the operations were done "farklı uzmanlık
    dallarında"; a line without a branch leaves that unknown, so it never adds
    them (#264). ``claim`` is accepted for callers' signature and is not used.
    """
    keys = [resolve_procedure_specialty_key(line) for line in lines]
    if not all(keys):
        return False
    return len(set(keys)) >= 2

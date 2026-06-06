"""§2.2.2.B cross-specialty (+25pp) detection from claim lines and catalogs."""

from __future__ import annotations

import unicodedata
from datetime import date
from typing import TYPE_CHECKING

from .catalog_membership import get_ek2c_entry, normalize_procedure_code

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine


def normalize_specialty_key(raw: str) -> str:
    """Stable key for comparing procedure specialties (EK-2/C group, branch code, etc.)."""
    text = str(raw or "").strip().casefold()
    if not text:
        return ""
    folded = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in folded if not unicodedata.combining(ch)).replace(" ", "_")


def _line_as_of_date(
    line: ProcedureClaimLine,
    claim: ClaimHeader | None,
) -> date | None:
    if line.procedure_date is not None:
        return line.procedure_date
    if claim is None:
        return None
    return claim.admission_date or claim.claim_start_date


def resolve_procedure_specialty_key(
    line: ProcedureClaimLine,
    claim: ClaimHeader | None = None,
    *,
    as_of_date: date | None = None,
) -> str:
    """Best-effort specialty key for one procedure (empty when unknown).

    Priority: explicit ``procedure_specialty_code`` on the line, EK-2/C ``group``,
    then EK-2/B catalog ``group``. Claim-level ``department`` is intentionally not used —
    it would assign one specialty to every line and hide cross-specialty sessions.
    """
    explicit = normalize_specialty_key(
        str(getattr(line, "procedure_specialty_code", "") or "")
    )
    if explicit:
        return explicit

    as_of = as_of_date if as_of_date is not None else _line_as_of_date(line, claim)
    normalized_code = normalize_procedure_code(line.procedure_code)
    if not normalized_code:
        return ""

    ek2c = get_ek2c_entry(normalized_code, as_of_date=as_of)
    if ek2c:
        group_key = normalize_specialty_key(str(ek2c.get("group") or ""))
        if group_key:
            return group_key

    try:
        from ..catalog import lookup_procedure_code

        lookup = lookup_procedure_code(normalized_code, visit_date=as_of)
        entry = lookup.get("entry") if lookup else None
        if entry:
            group_key = normalize_specialty_key(str(entry.get("group") or ""))
            if group_key:
                return group_key
    except Exception:
        pass

    return ""


def detect_cross_specialty_session(
    lines: list[ProcedureClaimLine],
    claim: ClaimHeader | None = None,
) -> bool:
    """True when two or more procedures in the session resolve to different specialty keys."""
    keys: set[str] = set()
    for line in lines:
        key = resolve_procedure_specialty_key(line, claim)
        if key:
            keys.add(key)
    return len(keys) >= 2

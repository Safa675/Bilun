"""Shared helpers for prose rule evaluation on claim lines."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine


def infer_care_setting(claim: ClaimHeader) -> str:
    claim_type = str(getattr(claim, "claim_type", "") or "").casefold()
    if "yatarak" in claim_type or "inpatient" in claim_type:
        return "inpatient"
    if "ayakta" in claim_type or "outpatient" in claim_type:
        return "outpatient"
    return "inpatient"


def group_procedure_lines_by_session(
    lines: Iterable[ProcedureClaimLine],
) -> dict[date, list[ProcedureClaimLine]]:
    grouped: dict[date, list[ProcedureClaimLine]] = defaultdict(list)
    for line in lines:
        grouped[line.procedure_date].append(line)
    return dict(grouped)

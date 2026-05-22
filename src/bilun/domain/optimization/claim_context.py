"""Exact claim-line contexts for SUT optimization rules."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from src.bilun.domain.claims.models import ProcedureClaimLine


@dataclass(frozen=True)
class SurchargeClaimContext:
    """Exact procedure-line inputs for per-patient surcharge compliance."""

    patient_id: str
    procedures: tuple[ProcedureClaimLine, ...]


@dataclass(frozen=True)
class CopayRateClaimContext:
    """Exact procedure-line inputs for per-patient copay-rate compliance."""

    patient_id: str
    procedures: tuple[ProcedureClaimLine, ...]


def build_surcharge_claim_context(
    patient_id: str,
    procedure_lines: Iterable[ProcedureClaimLine] | None,
) -> SurchargeClaimContext | None:
    """Return exact surcharge context when dated procedure lines are present."""

    procedures = _sorted_procedure_lines(procedure_lines)
    if not procedures:
        return None
    return SurchargeClaimContext(patient_id=patient_id, procedures=procedures)


def build_copay_rate_claim_context(
    patient_id: str,
    procedure_lines: Iterable[ProcedureClaimLine] | None,
) -> CopayRateClaimContext | None:
    """Return exact copay-rate context when dated procedure lines are present."""

    procedures = _sorted_procedure_lines(procedure_lines)
    if not procedures:
        return None
    return CopayRateClaimContext(patient_id=patient_id, procedures=procedures)


def procedure_rate_pct(line: ProcedureClaimLine) -> Decimal:
    """Calculate the exact payable/billed percentage encoded on a claim line."""

    if line.billed_amount_try == 0:
        return Decimal("0.00")
    return (line.expected_payable_try / line.billed_amount_try * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _sorted_procedure_lines(
    procedure_lines: Iterable[ProcedureClaimLine] | None,
) -> tuple[ProcedureClaimLine, ...]:
    if procedure_lines is None:
        return ()
    return tuple(
        sorted(
            procedure_lines,
            key=lambda line: (
                str(line.procedure_date),
                str(line.procedure_code),
                str(line.procedure_line_id),
            ),
        )
    )

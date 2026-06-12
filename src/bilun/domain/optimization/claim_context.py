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


def procedure_sgk_share_pct(line: ProcedureClaimLine) -> Decimal:
    """SGK payable share of billed amount (capped at 100%)."""

    if line.billed_amount_try == 0:
        return Decimal("0.00")
    share = line.expected_payable_try / line.billed_amount_try * Decimal("100")
    if share > Decimal("100"):
        share = Decimal("100")
    return share.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def procedure_implied_copay_rate_pct(line: ProcedureClaimLine) -> Decimal:
    """Implied patient copay % from billed vs SGK payable (100 - SGK share)."""

    return (Decimal("100") - procedure_sgk_share_pct(line)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def procedure_rate_pct(line: ProcedureClaimLine) -> Decimal:
    """Backward-compatible alias for SGK payable share percentage."""

    return procedure_sgk_share_pct(line)


def copay_rate_evaluable_line(line: ProcedureClaimLine) -> bool:
    """EK-2C-1 rate/flag checks apply only to billable, non-package lines."""

    return not line.is_package_included and line.billed_amount_try > 0


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

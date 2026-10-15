"""
src/bilun/domain/billing/claim_lab.py
Claim-line based lab billing optimizer.

Uses ``procedure_claim_lines`` with ``procedure_category == "laboratuvar"`` as the
source of truth for lab corrections. Currently this only covers hemogram (CBC)
bundling (EK-2B L107020). Session-fraction / seans kesir oranı rules are **not**
applied to lab tests because SUT §2.2.2.A(5) / §2.2.2.B speak of surgical/medical
"işlemler" with "kesi" (incision), not laboratory "tetkikler".
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..pricing.temporal import get_ek2b_price_for_date
from ..constants import HEMOGRAM_TESTS
from ..utils import turkish_lower
from .types import LabOptimization

if TYPE_CHECKING:
    from src.bilun.domain.claims.patient_context import PatientClaimContext


# EK-2B has no per-parameter CBC codes: the hemogram is the single line L107020, and
# L103120 "Hematokrit (Manuel)" is the only separately coded CBC test.
_CBC_CODES = frozenset({"L107020", "L103120"})


def _fold_lab_name(name: Any) -> str:
    """Case-fold a lab name for exact equality; Turkish İ, I, ı and i all fold to "i"."""
    return turkish_lower(str(name or "").strip()).replace("ı", "i")


# Exact BILUN CBC parameter names, never substrings: catalog tests such as
# "Glike hemoglobin (Hb A1c)" or "Folat (Eritrosit)" are not CBC lines (#270).
_CBC_PARAMETER_NAMES = frozenset(_fold_lab_name(name) for name in HEMOGRAM_TESTS)


def _is_hemogram_subtest_line(line: Any) -> bool:
    """Return True when a lab claim line is a CBC line, by code or exact parameter name."""
    return (
        line.procedure_code in _CBC_CODES
        or _fold_lab_name(line.procedure_name) in _CBC_PARAMETER_NAMES
    )


def _hemogram_gazette_price(service_date: Any | None = None) -> float:
    """Gazette price for one hemogram (L107020) as of the service date."""
    if service_date is None:
        return 0.0
    try:
        price = get_ek2b_price_for_date("L107020", service_date)
    except FileNotFoundError:
        return 0.0
    return float(price) if price is not None else 0.0


def _optimize_lab_billing_from_claims(
    claim_context: PatientClaimContext,
) -> LabOptimization:
    """Compute lab optimization from billed lab claim lines.

    Each lab claim line is treated as one billed test. Raw clinical lab result
    rows are intentionally ignored here; missing-billed-lab detection belongs in
    the capture-gap module.
    """
    result = LabOptimization()

    lab_lines = [
        line
        for line in claim_context.procedure_lines
        if line.procedure_category == "laboratuvar"
    ]
    if not lab_lines:
        return result

    # Each dated bill/visit has its own panel allowance and tariff.
    by_episode: dict[tuple[str, str, str], list[Any]] = {}
    for line in lab_lines:
        key = (line.claim_id, line.episode_id, str(line.procedure_date))
        by_episode.setdefault(key, []).append(line)

    total_hemogram_savings = 0.0
    flagged: list[dict[str, Any]] = []

    for (_claim_id, episode_id, service_date), lines in by_episode.items():
        hemogram_lines = [ln for ln in lines if _is_hemogram_subtest_line(ln)]
        # A single L107020 line is the correct bundle; unbundling only applies
        # when multiple CBC component lines are billed separately.
        if len(hemogram_lines) < 2:
            continue

        hemogram_price = _hemogram_gazette_price(service_date)
        if hemogram_price <= 0:
            # No dated tariff is evidence of no price, not a zero-price panel.
            continue
        hemogram_billed_total = sum(float(ln.billed_amount_try) for ln in hemogram_lines)
        # Correct billing: one hemogram panel. Overbilling = total billed - one panel price.
        hemogram_savings = round(hemogram_billed_total - hemogram_price, 2)
        if hemogram_savings > 0:
            total_hemogram_savings += hemogram_savings
            flagged.append(
                {
                    "test_name": "Hemogram (CBC) Bundle",
                    "sut_code": "L107020",
                    "gazette_price": round(hemogram_price, 2),
                    "flag_type": "hemogram_unbundling",
                    "savings_try": hemogram_savings,
                    "detail": (
                        f"{len(hemogram_lines)} CBC component line(s) billed in "
                        f"{episode_id} on {service_date}; should be billed as one hemogram (L107020)"
                    ),
                }
            )

    result.hemogram_bundling_savings = round(total_hemogram_savings, 2)
    result.flagged_tests = flagged
    return result

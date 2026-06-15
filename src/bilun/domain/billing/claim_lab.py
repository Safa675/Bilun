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

from ..catalog import get_lab_price
from ..constants import HEMOGRAM_TESTS
from .types import LabOptimization

if TYPE_CHECKING:
    from src.bilun.domain.claims.patient_context import PatientClaimContext


# Lower-case hemogram subtest keywords for matching against SUT procedure names.
_HEMOGRAM_NAME_KEYWORDS = frozenset(name.lower() for name in HEMOGRAM_TESTS)


def _is_hemogram_subtest_line(line: Any) -> bool:
    """Return True when a lab claim line looks like a CBC subtest."""
    name = str(line.procedure_name or "").lower()
    # Direct keyword match against BILUN hemogram test names.
    if any(keyword in name for keyword in _HEMOGRAM_NAME_KEYWORDS):
        return True
    # SUT code match: all BILUN hemogram subtests map to L107020 in this catalog.
    if line.procedure_code == "L107020":
        return True
    return False


def _hemogram_gazette_price(service_date: Any | None = None) -> float:
    """Gazette price for one hemogram (L107020) as of the service date."""
    price = get_lab_price("Hemoglobin", visit_date=service_date)
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

    # Group by episode/visit for hemogram bundling.
    by_episode: dict[str, list[Any]] = {}
    for line in lab_lines:
        by_episode.setdefault(line.episode_id, []).append(line)

    total_hemogram_savings = 0.0
    flagged: list[dict[str, Any]] = []

    for episode_id, lines in by_episode.items():
        service_date = str(lines[0].procedure_date) if lines else None

        hemogram_lines = [ln for ln in lines if _is_hemogram_subtest_line(ln)]
        # A single L107020 line is the correct bundle; unbundling only applies
        # when multiple CBC component lines are billed separately.
        if len(hemogram_lines) < 2:
            continue

        hemogram_price = _hemogram_gazette_price(service_date)
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
                        f"{episode_id}; should be billed as one hemogram (L107020)"
                    ),
                }
            )

    result.hemogram_bundling_savings = round(total_hemogram_savings, 2)
    result.flagged_tests = flagged
    return result

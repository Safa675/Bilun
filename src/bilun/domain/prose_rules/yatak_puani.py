"""SUT §2.2.2 standard bed-day (yatak puanı) billing for inpatient claims.

Phase 1: 510010 Standart yatak tarifesi only. Computes expected bed-day
charge = inclusive LOS × EK-2B price_try (already puan × katsayı).

Day counting: inclusive LOS = ``(discharge - admission).days + 1`` — the
discharge day IS billed per the Turkish SUT convention ("standart yatak
gönderilmelidir" = must be submitted on the discharge day). Matches the
existing ``drg.py:225`` LOS convention.

See plans/refactor/rule-encoding-gap-closure-roadmap.md + the approved
yatak-puani plan.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.bilun.domain.catalog import lookup_procedure_code
from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules.claim_utils import infer_care_setting
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_SGK_UPLIFT,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader

_OPPORTUNITY_TYPE = "yatak_puani_standard_bed"
_BED_CODE = "510010"


def _daily_rate() -> float:
    """Look up the current 510010 price_try (already puan × katsayı)."""
    result = lookup_procedure_code(_BED_CODE)
    entry = (result or {}).get("entry") or {}
    return float(entry.get("price_try") or 0.0)


def detect_yatak_puani_opportunities(
    claims: list[ClaimHeader],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Detect expected bed-day charges for inpatient claims.

    For each inpatient claim with non-null admission + discharge dates,
    computes inclusive LOS × daily_rate and returns an opportunity dict.

    Args:
        claims: ClaimHeaders to evaluate.
        claim_ids_with_procs: Optional filter — only emit opportunities for
            claims that also have procedure lines (matches the patient_report
            wiring gate ``if claim_context.procedure_lines``).
    """
    daily_rate = _daily_rate()
    if daily_rate <= 0:
        return []

    opportunities: list[dict[str, Any]] = []

    for claim in claims:
        # Gate on inpatient.
        if infer_care_setting(claim) != "inpatient":
            continue

        # Gate on procedure lines present (if filter provided).
        if claim_ids_with_procs is not None and claim.claim_id not in claim_ids_with_procs:
            continue

        # Must have both dates.
        if claim.admission_date is None or claim.discharge_date is None:
            continue

        # Inclusive LOS: discharge day IS billed (+1).
        days = (claim.discharge_date - claim.admission_date).days + 1
        if days <= 0:
            continue

        expected = _money(days * daily_rate)
        same_day = days == 1 and claim.admission_date == claim.discharge_date

        detail_parts = [
            f"Standart yatak (510010): {days} bed-day(s) at {daily_rate:.2f} TRY/day",
            f"= {expected:.2f} TRY (inclusive LOS, discharge day billed).",
        ]
        if same_day:
            detail_parts.append(
                "Same-day admission/discharge — consider 510120 (gündüz yatak) "
                "instead of 510010 for <24h stays."
            )

        opportunities.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim.claim_id,
                "bed_code": _BED_CODE,
                "bed_days": days,
                "daily_rate_try": daily_rate,
                "expected_yatak_try": expected,
                "recoverable_uplift_try": expected,
                "same_day_stay": same_day,
                "included_in_sgk_total": True,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "sut_section_id": "2.2.2",
                "rule_id": "yatak_puani_510010",
                "detail": " ".join(detail_parts),
            }
        )

    return opportunities

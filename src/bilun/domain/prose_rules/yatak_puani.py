"""SUT §2.2.2 standard bed-day (yatak puanı) billing for inpatient claims.

510010 Standart yatak tarifesi only. Computes expected bed-day
charge = inclusive LOS × EK-2B price_try (already puan × katsayı).

Day counting: inclusive LOS = ``(discharge - admission).days + 1`` — the
discharge day IS billed per the Turkish SUT convention ("standart yatak
gönderilmelidir" = must be submitted on the discharge day). Matches the
existing ``drg.py:225`` LOS convention.

**Package-bundling rule (El Kitabı Tablo 23):** When a claim carries an
EK-2C package procedure (paket category), the **surgery-day** bed fee is
included in the package ("Yatak ve malzemeler P610130 kodlu işleme
dahildir"). The surgery day is identified as the ``procedure_date`` of
the package procedure line, and one day is subtracted from the inclusive
LOS before multiplying by the daily rate. Non-surgery bed-days remain
separately billable.

See plans/refactor/rule-encoding-gap-closure-roadmap.md + the approved
yatak-puani plan.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from src.bilun.domain.catalog import lookup_procedure_code
from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules.claim_utils import infer_care_setting
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_SGK_UPLIFT,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_OPPORTUNITY_TYPE = "yatak_puani_standard_bed"
_BED_CODE = "510010"


def _daily_rate() -> float:
    """Look up the current 510010 price_try (already puan × katsayı)."""
    result = lookup_procedure_code(_BED_CODE)
    entry = (result or {}).get("entry") or {}
    return float(entry.get("price_try") or 0.0)


def _find_package_surgery_day(
    procedure_lines: list[ProcedureClaimLine],
) -> date | None:
    """Return the surgery date if the claim has an EK-2C package procedure.

    Per El Kitabı Tablo 23: "Yatak ve malzemeler P610130 kodlu işleme
    dahildir" — when an EK-2/C package procedure (paket category) is
    performed, the surgery-day bed fee is bundled into the package. We
    identify the surgery day as the ``procedure_date`` of the first
    ``paket``-category procedure line. Returns ``None`` when no package
    line is present (standard non-package inpatient billing — all days
    billed).
    """
    for line in procedure_lines:
        if (line.procedure_category or "").strip().lower() == "paket":
            return line.procedure_date
    return None


def detect_yatak_puani_opportunities(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine] | None = None,
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Detect expected bed-day charges for inpatient claims.

    For each inpatient claim with non-null admission + discharge dates,
    computes inclusive LOS × daily_rate and returns an opportunity dict.

    **Package-bundling (El Kitabı Tablo 23):** When a claim has an EK-2C
    package procedure (paket category), the surgery-day bed fee is bundled
    into the package. ``procedure_lines`` is used to detect this — when a
    paket line is found on the claim, its ``procedure_date`` is treated as
    the surgery day and excluded from the LOS. Without ``procedure_lines``,
    all days are billed (backwards-compatible default).

    Args:
        claims: ClaimHeaders to evaluate.
        procedure_lines: Optional procedure lines used to detect package
            bundling. When a ``paket``-category line is found on a claim,
            its surgery day is excluded from the bed-day count.
        claim_ids_with_procs: Optional filter — only emit opportunities for
            claims that also have procedure lines (matches the patient_report
            wiring gate ``if claim_context.procedure_lines``).
    """
    daily_rate = _daily_rate()
    if daily_rate <= 0:
        return []

    # Group procedure lines by claim for package-bundling detection.
    procedures_by_claim: dict[str, list[ProcedureClaimLine]] = {}
    if procedure_lines:
        for line in procedure_lines:
            procedures_by_claim.setdefault(line.claim_id, []).append(line)

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
        gross_days = (claim.discharge_date - claim.admission_date).days + 1
        if gross_days <= 0:
            continue

        # Package-bundling: if the claim has an EK-2C package procedure,
        # the surgery-day bed fee is bundled into the package (El Kitabı
        # Tablo 23: "Yatak ve malzemeler P610130 kodlu işleme dahildir").
        claim_procs = procedures_by_claim.get(claim.claim_id, [])
        surgery_day = _find_package_surgery_day(claim_procs)
        surgery_day_bundled = surgery_day is not None
        bundled_days = (
            1
            if surgery_day_bundled
            and claim.admission_date <= surgery_day <= claim.discharge_date
            else 0
        )
        days = max(gross_days - bundled_days, 0)

        expected = _money(days * daily_rate)
        same_day = gross_days == 1 and claim.admission_date == claim.discharge_date

        detail_parts = [
            f"Standart yatak (510010): {days} billable bed-day(s) "
            f"(gross LOS {gross_days} day(s) at {daily_rate:.2f} TRY/day",
        ]
        if surgery_day_bundled:
            detail_parts[0] += (
                f", surgery day {surgery_day} bundled into EK-2/C package"
            )
        detail_parts[0] += ")"
        detail_parts.append(f"= {expected:.2f} TRY (inclusive LOS, discharge day billed).")
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
                "gross_bed_days": gross_days,
                "surgery_day_bundled": surgery_day_bundled,
                "bundled_days": bundled_days,
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

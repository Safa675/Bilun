"""SUT §2.2.2 standard bed-day (yatak puanı) billing for inpatient claims.

510010 Standart yatak tarifesi only. Computes expected bed-day
charge = inclusive LOS × EK-2B price_try (already puan × katsayı).

Day counting: inclusive LOS = ``(discharge - admission).days + 1`` — the
discharge day IS billed per the Turkish SUT convention ("standart yatak
gönderilmelidir" = must be submitted on the discharge day). Matches the
existing ``drg.py:225`` LOS convention.

**Package-bundling rule (SUT §2.2.2.B-1(1)(h), (3)-(4) & El Kitabı Tablo 23):**
When an inpatient claim carries an EK-2/C package procedure (``paket``
category), bed and companion fees from inpatient admission through the end
of the package group's window (A1/A2/A3=15, B=10, C=8, D=5, E=3 calendar
days starting on ``procedure_date``) are included in the package price. Only
days after the package window are separately billable under EK-2/B 510010.

See plans/refactor/rule-encoding-gap-closure-roadmap.md + the approved
yatak-puani plan.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from src.bilun.domain.catalog import lookup_procedure_code
from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules.catalog_membership import get_ek2c_entry
from src.bilun.domain.prose_rules.claim_utils import infer_care_setting
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_SGK_UPLIFT,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_OPPORTUNITY_TYPE = "yatak_puani_standard_bed"
_BED_CODE = "510010"

# SUT §2.2.2.B-1(3) EK-2/C package window lengths (inclusive calendar days
# starting on the package procedure date).
PACKAGE_WINDOW_DAYS: dict[str, int] = {
    "A1": 15,
    "A2": 15,
    "A3": 15,
    "A": 15,
    "B": 10,
    "C": 8,
    "D": 5,
    "E": 3,
}


def _daily_rate(visit_date: date | str | None = None) -> float:
    """Look up the 510010 price_try (already puan × katsayı) as of visit_date."""
    result = lookup_procedure_code(_BED_CODE, visit_date=visit_date)
    entry = (result or {}).get("entry") or {}
    return float(entry.get("price_try") or 0.0)


def _resolve_package_window_days(
    line: ProcedureClaimLine,
    *,
    fallback_date: date | None = None,
) -> int:
    """Return the §2.2.2.B-1(3) window length in days for a paket line."""
    as_of = line.procedure_date or fallback_date
    entry = get_ek2c_entry(line.procedure_code, as_of_date=as_of)
    if entry is None and getattr(line, "package_code", ""):
        entry = get_ek2c_entry(line.package_code, as_of_date=as_of)
    group = str(
        (entry or {}).get("group") or getattr(line, "ek2c_group", "") or ""
    ).strip().upper()
    return PACKAGE_WINDOW_DAYS.get(group, 1)


def _find_package_surgery_day(
    procedure_lines: list[ProcedureClaimLine],
) -> date | None:
    """Return the surgery date if the claim has an EK-2C package procedure."""
    for line in procedure_lines:
        if (line.procedure_category or "").strip().lower() == "paket":
            return line.procedure_date
    return None


def _find_package_window_end(
    procedure_lines: list[ProcedureClaimLine],
    *,
    admission_date: date | None = None,
    discharge_date: date | None = None,
) -> date | None:
    """Return the last calendar date covered by any EK-2/C package on the claim.

    Per SUT §2.2.2.B-1(1) ("takip alındıktan sonraki") and §2.2.2.B-1(3)-(4),
    an EK-2/C package bundles bed and companion fees from admission through
    ``procedure_date + timedelta(days=window_days - 1)``. When multiple
    package lines exist on a claim, the latest window end governs.
    """
    window_end: date | None = None
    for line in procedure_lines:
        if (line.procedure_category or "").strip().lower() != "paket":
            continue
        p_date = line.procedure_date or admission_date
        if p_date is None:
            continue
        if admission_date is not None and p_date < admission_date:
            continue
        if discharge_date is not None and p_date > discharge_date:
            continue
        w_days = _resolve_package_window_days(line, fallback_date=admission_date)
        candidate_end = p_date + timedelta(days=w_days - 1)
        if window_end is None or candidate_end > window_end:
            window_end = candidate_end
    return window_end


def detect_yatak_puani_opportunities(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine] | None = None,
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Detect expected bed-day charges for inpatient claims.

    For each inpatient claim with non-null admission + discharge dates,
    computes inclusive LOS × daily_rate and returns an opportunity dict.

    **Package-bundling (SUT §2.2.2.B-1(1), (3)-(4)):** When a claim has an
    EK-2/C package procedure (``paket`` category), bed days from admission
    through the end of the package group's window (A1/A2/A3=15, B=10, C=8,
    D=5, E=3 days from ``procedure_date``) are bundled into the package;
    only post-window days are billed. Without ``procedure_lines``, all days
    are billed (backwards-compatible default).
    """
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

        visit_date = claim.admission_date or claim.claim_start_date
        daily_rate = _daily_rate(visit_date)
        if daily_rate <= 0:
            continue

        # Inclusive LOS: discharge day IS billed (+1).
        gross_days = (claim.discharge_date - claim.admission_date).days + 1
        if gross_days <= 0:
            continue

        # Package-bundling (§2.2.2.B-1(1), (3)-(4)): when the claim carries an
        # EK-2/C package procedure, all bed days from admission through the
        # package group's window end are bundled into the package.
        claim_procs = procedures_by_claim.get(claim.claim_id, [])
        surgery_day = _find_package_surgery_day(claim_procs)
        window_end = _find_package_window_end(
            claim_procs,
            admission_date=claim.admission_date,
            discharge_date=claim.discharge_date,
        )
        surgery_day_bundled = window_end is not None
        if window_end is not None:
            days = max((claim.discharge_date - window_end).days, 0)
            bundled_days = gross_days - days
        else:
            days = gross_days
            bundled_days = 0

        expected = _money(days * daily_rate)
        same_day = gross_days == 1 and claim.admission_date == claim.discharge_date

        # Net out actual billed bed-day amounts (510010) so recoverable
        # uplift reflects only the UNBILLED portion.
        actual_billed_try = _money(
            sum(
                float(p.billed_amount_try)
                for p in claim_procs
                if str(p.procedure_code).strip() == _BED_CODE
            )
        )
        recoverable_try = _money(max(0.0, expected - actual_billed_try))

        detail_parts = [
            f"Standart yatak (510010): {days} billable bed-day(s) "
            f"(gross LOS {gross_days} day(s) at {daily_rate:.2f} TRY/day",
        ]
        if surgery_day_bundled:
            detail_parts[0] += (
                f", {bundled_days} day(s) bundled into EK-2/C package window "
                f"(surgery {surgery_day}, window through {window_end})"
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
                "actual_billed_try": actual_billed_try,
                "recoverable_uplift_try": recoverable_try,
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

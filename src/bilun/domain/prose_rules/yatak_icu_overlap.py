"""SUT §2.4.4.H + §2.2.2 YB→servis geçiş günü yatak koordinasyonu.

EK-2B defines both **510010** (Standart yatak) and **510090** (Yoğun bakım)
as covering *"Yemek, yatak, hasta vizit hizmetlerini kapsar"*. When a
patient is discharged/transferred from intensive care (ICU) on calendar day
D, the ICU claim bills **510090** for day D (last ICU day, hizmet başı) and
that charge already includes the bed. Billing the service bed **510010** on
the same day D — on the same claim or on a follow-on service claim — is
therefore double-billing.

This module provides two coordinated paths:

1. **reconcile_yatak_bed_days** (recoverable-uplift path, post-processing):
   drops ICU discharge/transfer days that fall inside a service-bed claim's
   inclusive LOS from the yatak bed-day count, so BILUN never recommends
   recovering a bed day that 510090 already paid (invoice correction).

2. **detect_yatak_icu_overlap** (audit-exposure path): flags positively billed **510010**
   procedure line whose ``procedure_date`` is an ICU discharge/transfer day
   (the last day of a claim carrying 510090/P55200x ICU codes) as a
   double-billing violation, mirroring the ``icu_bundled_leakage`` detector
   pattern.

The two paths are disjoint by trigger: the reconcile adjusts *expected*
billable days regardless of what was actually billed; the detector fires
only on *actually billed* 510010 lines dated on an ICU last day. No TRY is
counted in both paths.

**ICU day model:** mirrors ``icu_puani`` — when a claim carries ICU
indicator codes (510090 or P552001-008), the ICU span is the claim span and
the LAST ICU day (510090) is the claim's ``discharge_date``.

**Package-bundling (El Kitabı Tablo 23):** the surgery-day bed fee is
already excluded by ``yatak_puani`` for EK-2C package claims. The reconcile
never double-subtracts: if the ICU last day coincides with the package
surgery day, it is already excluded and no additional day is dropped.

Scope note: the mirror transition (service→ICU, i.e. the ICU *first* day) is
intentionally NOT in scope here — the YB→servis discharge/transfer day is
the reported double-billing scenario.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules.claim_utils import infer_care_setting
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_AUDIT_EXPOSURE,
)
from src.bilun.domain.prose_rules.yatak_puani import claim_package_window

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_OPPORTUNITY_TYPE = "yatak_icu_overlap_double_billing"
_SUT_SECTION_ID = "2.4.4.H"
_RULE_ID = "yatak_icu_overlap_510010"

_BED_CODE = "510010"  # Standart yatak (EK-2B)
_ICU_DAY_RATE_CODE = "510090"  # Yoğun bakım, hizmet başı (EK-2B)
# ICU intermediate packages (EK-2C) — also mark a claim as ICU.
_ICU_PACKAGE_PREFIXES = ("552001", "552002", "552003", "552006", "552007", "552008")


def _normalize_code(raw: str) -> str:
    """Normalize a procedure code for matching (mirrors icu_puani helpers).

    Strips a leading P/p (MEDULA package prefix), removes punctuation, and
    upper-cases so that ``"p510010"``, ``"510.010"``, ``"510 010"`` all
    collapse to ``"510010"``.
    """
    cleaned = (
        str(raw or "")
        .strip()
        .replace(".", "")
        .replace(" ", "")
        .replace("-", "")
        .upper()
    )
    return cleaned[1:] if cleaned.startswith("P") else cleaned


def _is_icu_code(normalized: str) -> bool:
    """True for 510090 or any P55200x package code (mirrors icu_puani)."""
    stripped = normalized[1:] if normalized.startswith("P") else normalized
    if stripped == _ICU_DAY_RATE_CODE:
        return True
    return stripped in _ICU_PACKAGE_PREFIXES


def _collect_icu_discharge_claims(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
) -> dict[date, list[str]]:
    """Qualifying ICU claim IDs grouped by discharge/transfer date.

    Per the ``icu_puani`` day model, when a claim carries 510090 or a
    P55200x package on its procedure lines, the ICU span is the claim span
    and 510090 is billed on the first AND last day. The last (discharge /
    transfer) day is therefore ``claim.discharge_date`` — the day on which a
    service bed (510010) cannot be separately billed.
    """
    procedures_by_claim: dict[str, list[ProcedureClaimLine]] = {}
    for line in procedure_lines:
        procedures_by_claim.setdefault(line.claim_id, []).append(line)

    icu_discharge_claims: dict[date, list[str]] = {}
    for claim in claims:
        if infer_care_setting(claim) != "inpatient":
            continue
        if claim.admission_date is None or claim.discharge_date is None:
            continue
        claim_procs = procedures_by_claim.get(claim.claim_id, [])
        if not any(
            _is_icu_code(_normalize_code(line.procedure_code))
            for line in claim_procs
        ):
            continue
        icu_discharge_claims.setdefault(claim.discharge_date, []).append(claim.claim_id)
    return icu_discharge_claims


def collect_icu_last_days(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
) -> set[date]:
    """The ICU discharge/transfer days of the claims (the project's claim-span ICU model).

    The ICU span is the claim span, so the last ICU day is the claim's ``discharge_date``, which the model
    treats as a 510090 day (EK-2B: it covers yemek + yatak + vizit) even when no 510090 line carries that date.
    Used by the standard-bed reconciliation and, as ``icu_last_days``, by the newborn bed motor.
    """
    return set(_collect_icu_discharge_claims(claims, procedure_lines))


def detect_yatak_icu_overlap(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine] | None = None,
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Detect service bed (510010) billed on an ICU discharge/transfer day.

    For each positively billed **510010** procedure line whose ``procedure_date`` equals the
    discharge/transfer day of a claim that carries ICU indicator codes
    (510090 / P55200x), emit an audit-exposure violation: the ICU day-rate
    already pays for the bed (EK-2B "Yemek, yatak, hasta vizit hizmetlerini
    kapsar"), so billing 510010 again the same day is double-billing.

    Args:
        claims: ClaimHeaders to evaluate (all of the patient's claims).
        procedure_lines: Procedure claim lines grouped by ``claim_id``. When
            omitted (or empty), ICU last days cannot be confirmed, so no
            violations are emitted.
        claim_ids_with_procs: Optional filter — only emit violations for
            claims that also have procedure lines (matches the
            ``patient_report`` wiring gate used by the other prose motors).

    Returns:
        Violation dicts with: ``type``, ``claim_id``, ``rule_id``,
        ``procedure_code``, ``procedure_name``, ``procedure_line_id``,
        ``overlap_date``, ``icu_claim_id``, ``risk_amount_try``, ``detail``
        (Turkish), ``sut_section_id``, ``savings_category``,
        ``savings_basis``, ``severity``.
    """
    if not procedure_lines:
        return []

    icu_discharge_claims = _collect_icu_discharge_claims(claims, procedure_lines)
    if not icu_discharge_claims:
        return []

    violations: list[dict[str, Any]] = []
    for line in procedure_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        if _normalize_code(line.procedure_code) != _BED_CODE:
            continue
        if line.billed_amount_try <= 0:
            continue
        if line.procedure_date not in icu_discharge_claims:
            continue

        icu_claim_ids = icu_discharge_claims.get(line.procedure_date, [])
        icu_claim_ref = ",".join(icu_claim_ids) if icu_claim_ids else "?"
        detail = (
            f"Servis yatağı (510010) YB çıkış/transfer günüyle aynı takvim "
            f"gününde faturalandı: {line.procedure_date.isoformat()} — 510090 "
            f"(yoğun bakım, hizmet başı) 'Yemek, yatak, hasta vizit "
            f"hizmetlerini kapsar' (EK-2B); yatak o gün zaten ödendiği için "
            f"510010 ayrı faturalanamaz (çift faturalama). İlgili YB takibi: "
            f"{icu_claim_ref}."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": line.claim_id,
                "rule_id": _RULE_ID,
                "procedure_code": line.procedure_code,
                "procedure_name": line.procedure_name,
                "procedure_line_id": line.procedure_line_id,
                "overlap_date": line.procedure_date.isoformat(),
                "icu_claim_id": icu_claim_ref,
                "risk_amount_try": _money(float(line.billed_amount_try or 0.0)),
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "savings_category": SAVINGS_CATEGORY_AUDIT_EXPOSURE,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "error",
            }
        )

    return violations


def reconcile_yatak_bed_days(
    yatak_opportunities: list[dict[str, Any]],
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine] | None = None,
) -> list[dict[str, Any]]:
    """Drop ICU discharge/transfer days from yatak bed-day expectations.

    Post-processing over ``yatak_puani.detect_yatak_puani_opportunities``
    output: for each service-bed opportunity (510010), any ICU last day
    (discharge/transfer day of an ICU-coded claim) that falls inside the
    claim's inclusive LOS is already paid by 510090 and is subtracted from
    the billable bed-day count. ``expected_yatak_try`` and
    ``recoverable_uplift_try`` are recomputed, and ``icu_overlap_days`` /
    ``icu_overlap_dates`` are recorded on the adjusted opportunity.

    Days already excluded by the EK-2C package-surgery bundling
    (``yatak_puani`` :126-138) are never double-subtracted: if the ICU last
    day coincides with the package surgery day, no additional day is
    dropped.

    Args:
        yatak_opportunities: Output of the yatak detector (unchanged when no
            overlap exists).
        claims: All of the patient's ClaimHeaders.
        procedure_lines: All of the patient's procedure lines — used both to
            confirm ICU last days and to recompute the package surgery day.

    Returns:
        A new list where overlapped opportunities are adjusted copies;
        when no opportunity overlaps an ICU last day, the ORIGINAL list is
        returned unchanged (identity), so callers can rely on
        ``result is yatak_opportunities`` to detect a no-op.
    """
    if not yatak_opportunities or not procedure_lines:
        return yatak_opportunities

    icu_last_days = collect_icu_last_days(claims, procedure_lines)
    if not icu_last_days:
        return yatak_opportunities

    # claim_id → procedure lines (for package surgery-day recomputation).
    procedures_by_claim: dict[str, list[ProcedureClaimLine]] = {}
    for line in procedure_lines:
        procedures_by_claim.setdefault(line.claim_id, []).append(line)

    claims_with_dates: dict[str, ClaimHeader] = {
        claim.claim_id: claim
        for claim in claims
        if claim.admission_date is not None and claim.discharge_date is not None
    }

    adjusted: list[dict[str, Any]] = []
    changed = False
    for opp in yatak_opportunities:
        claim = claims_with_dates.get(opp.get("claim_id", ""))
        if claim is None:
            adjusted.append(opp)
            continue
        admission, discharge = claim.admission_date, claim.discharge_date

        # Days already excluded by package-window bundling (yatak_puani
        # §2.2.2.B-1(1), (3)-(4)) — never double-subtract them. The same
        # window as yatak_puani: a billed package, or a mandated one.
        window = claim_package_window(
            claim, procedures_by_claim.get(claim.claim_id, []),
        )
        window_end = window.end if window is not None else None

        overlapping = sorted(
            d
            for d in icu_last_days
            if admission <= d <= discharge and (window_end is None or d > window_end)
        )
        if not overlapping:
            adjusted.append(opp)
            continue

        changed = True
        daily_rate = float(opp.get("daily_rate_try") or 0.0)
        days = int(opp.get("bed_days") or 0)
        new_days = max(days - len(overlapping), 0)

        expected = _money(new_days * daily_rate)
        actual_billed_try = float(opp.get("actual_billed_try") or 0.0)
        recoverable = _money(min(expected, max(0.0, expected - actual_billed_try)))

        new_opp = dict(opp)
        new_opp["bed_days"] = new_days
        new_opp["expected_yatak_try"] = expected
        new_opp["recoverable_uplift_try"] = recoverable
        new_opp["icu_overlap_days"] = len(overlapping)
        new_opp["icu_overlap_dates"] = [d.isoformat() for d in overlapping]
        new_opp["detail"] = (
            str(opp.get("detail", ""))
            + " ICU çıkış/transfer günü ("
            + ", ".join(d.isoformat() for d in overlapping)
            + ") 510090'da yatak zaten ödendiği için servis yatağından "
            + "düşüldü (EK-2B: 'Yemek, yatak, hasta vizit hizmetlerini "
            + "kapsar')."
        )
        adjusted.append(new_opp)

    if not changed:
        return yatak_opportunities
    return adjusted

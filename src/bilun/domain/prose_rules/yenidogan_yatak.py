"""SUT EK-2B newborn bed (yenidoğan yatağı) billing for inpatient claims.

Two mutually exclusive non-ICU newborn ward bed codes:

* **510070 Kuvöz (Incubator)** — 743.65 puan. The higher-tier newborn bed.
  Bundles yemek + yatak + vizit (same bundle as standart yatak 510010).
  Cannot be billed together with 510081.
* **510081 Kot (Cradle/Bassinet)** — 524.95 puan. Same bundle. Cannot be
  billed with 510070, and CANNOT be billed for rooming-in babies
  ("Anne yanında izlenen bebekler için faturalandırılmaz").

These are NON-ICU newborn ward beds. Newborn ICU uses P552006/7/8, which is
handled by the ICU motor — not here.

Day counting: inclusive LOS = ``(discharge - admission).days + 1`` — the
discharge day IS billed, matching the yatak puani convention.

Detection: a claim is "newborn" when its diagnoses contain an ICD-10 code
starting with ``Z38`` (liveborn) or in the ``P00–P96`` perinatal range, OR
when the claim ``department`` names a newborn/pediatric ward. With no
detection signal the claim is honestly skipped.

Bed selection: Kuvöz (510070) is the default higher-tier bed for an
identified newborn inpatient stay. Kot (510081) is emitted only when the
caller explicitly marks the baby as rooming-in via ``rooming_in_claim_ids``;
for rooming-in babies Kot is suppressed (not billable) and Kuvöz is offered
only when ``emit_kuvoz_for_rooming_in`` is set — default False, per the SUT
prohibition on billing rooming-in bassinet stays.
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
    from src.bilun.domain.claims.models import ClaimDiagnosis, ClaimHeader

_OPPORTUNITY_TYPE = "yenidogan_yatak"
_BED_KUVOZ = "510070"  # Kuvöz (Incubator) — 743.65 puan
_BED_KOT = "510081"  # Kot (Cradle/Bassinet) — 524.95 puan
_SUT_SECTION_ID = "2.2.2"  # EK-2B newborn bed tariff row

# ICD-10 prefixes/ranges that mark a claim as a newborn episode.
_NEWBORN_DX_PREFIXES = ("Z38",)  # Z38.* — liveborn infants
_PERINATAL_RANGE = ("P00", "P96")  # P00–P96 — perinatal conditions
# Department name fragments that indicate a newborn/pediatric ward.
_NEWBORN_DEPT_TOKENS = ("yenidoğan", "yenedogan", "çocuk", "cocuk", "neonatal", "newborn", "pediatri")


def _daily_rate(bed_code: str) -> float:
    """Look up the current newborn bed ``price_try`` (already puan × katsayı)."""
    result = lookup_procedure_code(bed_code)
    entry = (result or {}).get("entry") or {}
    return float(entry.get("price_try") or 0.0)


def _is_newborn_icd10(code: str) -> bool:
    """True for Z38.* (liveborn) or P00–P96 (perinatal) ICD-10 codes."""
    c = (code or "").strip().upper()
    if not c:
        return False
    if c.startswith(_NEWBORN_DX_PREFIXES):
        return True
    # P00–P96 range check (3-char alpha-numeric comparison is safe here).
    if len(c) >= 3 and c[0] == "P" and c[:3] >= _PERINATAL_RANGE[0] and c[:3] <= _PERINATAL_RANGE[1]:
        return True
    return False


def _claim_diagnoses(claim: ClaimHeader, diagnoses: list[ClaimDiagnosis]) -> list[str]:
    """Return ICD-10 codes attached to ``claim.claim_id`` plus the header's primary."""
    codes: list[str] = []
    primary = getattr(claim, "primary_icd10", "") or ""
    if primary:
        codes.append(primary)
    for dx in diagnoses or ():
        if getattr(dx, "claim_id", "") == claim.claim_id:
            codes.append(getattr(dx, "icd10_code", "") or "")
    return codes


def _department_is_newborn(department: str) -> bool:
    dept = (department or "").casefold()
    return any(token in dept for token in _NEWBORN_DEPT_TOKENS)


def detect_yenidogan_yatak_opportunities(
    claims: list[ClaimHeader],
    diagnoses: list[ClaimDiagnosis] = (),
    *,
    claim_ids_with_procs: set[str] | None = None,
    rooming_in_claim_ids: set[str] | None = None,
    emit_kuvoz_for_rooming_in: bool = False,
) -> list[dict[str, Any]]:
    """Detect expected newborn bed charges for newborn inpatient claims.

    For each inpatient claim whose diagnoses or department mark it as a
    newborn episode (Z38.* / P00–P96, or a yenidoğan/çocuk department),
    computes inclusive LOS × daily_rate for the appropriate bed code and
    returns an opportunity dict.

    Args:
        claims: ClaimHeaders to evaluate.
        diagnoses: ClaimDiagnosis rows (any patient; filtered by claim_id).
        claim_ids_with_procs: Optional filter — only emit opportunities for
            claims that also have procedure lines (matches the patient_report
            wiring gate ``if claim_context.procedure_lines``).
        rooming_in_claim_ids: Claim ids documented as rooming-in
            ("anne yanında"). For these claims Kot (510081) is suppressed per
            SUT; Kuvöz (510070) is only emitted when
            ``emit_kuvoz_for_rooming_in`` is True.
        emit_kuvoz_for_rooming_in: If True, emit a Kuvöz (510070) opportunity
            for rooming-in claims instead of suppressing all bed charges.

    Returns:
        Opportunity dicts with: type, claim_id, bed_code (510070 or 510081),
        days, puan, expected_try, sut_section_id, rule_id, detail.
    """
    kuvoz_rate = _daily_rate(_BED_KUVOZ)
    kot_rate = _daily_rate(_BED_KOT)
    if kuvoz_rate <= 0 and kot_rate <= 0:
        return []

    rooming_in = rooming_in_claim_ids or set()
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

        # Newborn detection: ICD-10 (Z38 / P00–P96) or department name.
        dx_codes = _claim_diagnoses(claim, list(diagnoses))
        is_newborn_dx = any(_is_newborn_icd10(code) for code in dx_codes)
        is_newborn_dept = _department_is_newborn(getattr(claim, "department", "") or "")
        if not (is_newborn_dx or is_newborn_dept):
            # No detection signal → honest skip.
            continue

        # Inclusive LOS: discharge day IS billed (+1), matching yatak puani.
        days = (claim.discharge_date - claim.admission_date).days + 1
        if days <= 0:
            continue

        # Mutually exclusive bed selection.
        # Default = Kuvöz (510070, higher tier). Kot (510081) is NEVER billed
        # for rooming-in babies per SUT; Kuvöz for rooming-in is opt-in.
        is_rooming_in = claim.claim_id in rooming_in
        if is_rooming_in:
            if emit_kuvoz_for_rooming_in and kuvoz_rate > 0:
                bed_code, rate = _BED_KUVOZ, kuvoz_rate
            else:
                # Rooming-in: Kot suppressed, Kuvöz not opted in → skip.
                continue
        else:
            bed_code, rate = _BED_KUVOZ, kuvoz_rate

        if rate <= 0:
            continue

        expected = _money(days * rate)
        same_day = days == 1 and claim.admission_date == claim.discharge_date

        detail_parts = [
            f"Yenidoğan yatağı ({bed_code}): {days} bed-day(s) at {rate:.2f} TRY/day",
            f"= {expected:.2f} TRY (inclusive LOS, discharge day billed).",
        ]
        if is_rooming_in:
            detail_parts.append(
                "Rooming-in ('anne yanında') episode — Kot (510081) is not "
                "billable per SUT; Kuvöz (510070) billed per opt-in."
            )
        if bed_code == _BED_KUVOZ:
            detail_parts.append(
                "Kuvöz (510070) and Kot (510081) are mutually exclusive; only "
                "one newborn bed may be billed per day."
            )
        if same_day:
            detail_parts.append(
                "Same-day admission/discharge — confirm newborn ward admission "
                "criteria are documented."
            )

        opportunities.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim.claim_id,
                "bed_code": bed_code,
                "days": days,
                "puan": _puan_for(bed_code),
                "expected_try": expected,
                "recoverable_uplift_try": expected,
                "same_day_stay": same_day,
                "rooming_in": is_rooming_in,
                "included_in_sgk_total": True,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "sut_section_id": _SUT_SECTION_ID,
                "rule_id": f"yenidogan_yatak_{bed_code}",
                "detail": " ".join(detail_parts),
            }
        )

    return opportunities


def _puan_for(bed_code: str) -> float:
    """Return the raw EK-2B puan (pre-katsayı) for a newborn bed code."""
    result = lookup_procedure_code(bed_code)
    entry = (result or {}).get("entry") or {}
    return float(entry.get("puan") or 0.0)

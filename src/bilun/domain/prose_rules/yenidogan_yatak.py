"""SUT EK-2B newborn bed (yenidoğan yatağı) billing for inpatient claims.

Two mutually exclusive non-ICU newborn ward bed codes:

* **510070 Kuvöz (Incubator)** — 743.65 puan. The higher-tier newborn bed.
  Bundles yemek + yatak + vizit (same bundle as standart yatak 510010).
  Cannot be billed together with 510081.
* **510081 Kot (Cradle/Bassinet)** — 524.95 puan. Same bundle. Cannot be
  billed with 510070, and CANNOT be billed for rooming-in babies
  ("Anne yanında izlenen bebekler için faturalandırılmaz").

These are NON-ICU newborn ward beds. Newborn ICU uses P552006/7/8, which is
handled by the ICU motor — not here: a claim that carries an ICU indicator code
(510090 / P55200x, the ICU motor's own gate) or whose department names an
intensive care unit is skipped.

Billed lines are netted: ``actual_billed_try`` is the sum of the claim's 510070
and 510081 lines and ``recoverable_uplift_try = min(expected, max(0, expected -
actual))`` (the ICU and standard-bed motors net the same way since #13; the cap
keeps a credit line from recovering more than the charge). The same days are
not expected as standard bed by the standard-bed motor
(``claim_yatak_newborn_overlap``).

The billed bed is the only evidence of the bed type (nothing in the claim says
whether the baby lay in an incubator): each billed Kot day (sum of the quantity
of the 510081 lines, at most the stay) is priced at the Kot rate, never
"upgraded" to Kuvöz; every other day at the Kuvöz default below. A claim that
bills the standard bed (510010) and no newborn bed line has stated its bed: this
motor stands down and the standard-bed motor keeps the stay.

Day counting: inclusive LOS = ``(discharge - admission).days + 1`` — the
discharge day IS billed, matching the yatak puani convention. Days inside an
EK-2/C package window (SUT §2.2.2.B-1(1), (3)-(4): the package includes the bed
from admission through its window) are not expected: ``claim_package_window`` of
the standard-bed motor decides them, so both bed motors agree on the days.

Detection: a claim is "newborn" when its diagnoses contain an ICD-10 code
starting with ``Z38`` (liveborn) or in the ``P00–P96`` perinatal range, OR
when the claim ``department`` names a newborn/pediatric ward. With no
detection signal the claim is honestly skipped.

Bed selection: Kuvöz (510070) is the default higher-tier bed for an
identified newborn inpatient stay, for every day no Kot line covers. Kot (510081)
is priced only for the days a billed Kot line covers; with the caller marking the
baby as rooming-in via ``rooming_in_claim_ids`` Kot is suppressed (not
billable) and Kuvöz is offered only when ``emit_kuvoz_for_rooming_in`` is set —
default False, per the SUT prohibition on billing rooming-in bassinet stays.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import TYPE_CHECKING, Any

from src.bilun.domain.catalog import lookup_procedure_code
from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code
from src.bilun.domain.prose_rules.claim_utils import infer_care_setting
from src.bilun.domain.prose_rules.icu_puani import claim_has_icu_code
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_SGK_UPLIFT,
)
from src.bilun.domain.prose_rules.yatak_puani import (
    claim_package_window,
    counts_against_expected_days,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import (
        ClaimDiagnosis,
        ClaimHeader,
        ProcedureClaimLine,
    )

_OPPORTUNITY_TYPE = "yenidogan_yatak"
_BED_KUVOZ = "510070"  # Kuvöz (Incubator) — 743.65 puan
_BED_KOT = "510081"  # Kot (Cradle/Bassinet) — 524.95 puan
_SUT_SECTION_ID = "2.2.2"  # EK-2B newborn bed tariff row

# ICD-10 prefixes/ranges that mark a claim as a newborn episode.
_NEWBORN_DX_PREFIXES = ("Z38",)  # Z38.* — liveborn infants
_PERINATAL_RANGE = ("P00", "P96")  # P00–P96 — perinatal conditions
# Department name fragments that indicate a newborn/pediatric ward.
_NEWBORN_DEPT_TOKENS = ("yenidoğan", "yenedogan", "çocuk", "cocuk", "neonatal", "newborn", "pediatri")
# The two codes this motor recommends and nets (EK-2/B: never billed together, one per day).
_NEWBORN_BED_CODES = frozenset({_BED_KUVOZ, _BED_KOT})
# The standard bed: a claim that bills it (and no newborn bed) has stated its bed; the standard-bed motor owns it.
_STANDARD_BED_CODE = "510010"
# Whole words that name an intensive care unit (YB, YYBÜ = yenidoğan yoğun bakım ünitesi, NICU, ICU).
_ICU_DEPT_WORDS = frozenset({"yb", "yybu", "nicu", "icu"})


def _daily_rate(bed_code: str, visit_date: date | str | None = None) -> float:
    """Look up the newborn bed ``price_try`` (already puan × katsayı) as of visit_date."""
    result = lookup_procedure_code(bed_code, visit_date=visit_date)
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


def _department_names_icu(department: str) -> bool:
    """True for a department that names an intensive care unit.

    Turkish-folded ("YOĞUN BAKIM", ASCII spellings), spaces ignored ("Yoğunbakım", double space) and the whole
    words YB / YYBÜ / NICU / ICU. A ward named by what it is not ("Yoğun Bakım Dışı ...") also reads as ICU.
    """
    folded = unicodedata.normalize("NFKD", (department or "").casefold().replace("ı", "i"))
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    words = re.findall(r"[a-z0-9]+", folded)
    return "yogunbakim" in "".join(words) or any(word in _ICU_DEPT_WORDS for word in words)


def detect_yenidogan_yatak_opportunities(
    claims: list[ClaimHeader],
    diagnoses: list[ClaimDiagnosis] = (),
    *,
    procedure_lines: list[ProcedureClaimLine] | None = None,
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
        procedure_lines: Procedure lines (any claim; filtered by claim_id). They
            net the billed 510070 / 510081 lines out of the charge and mark an
            ICU stay (510090 / P55200x), which this motor leaves to the ICU
            motor. Without them nothing is netted and no ICU code is seen.
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
        Opportunity dicts with: type, claim_id, bed_code (510070, or 510081 when
        every day is a billed Kot day), days (billable: after any package
        window), bundled_days, puan, expected_try (the full charge),
        actual_billed_try (billed 510070 / 510081 lines), recoverable_uplift_try
        (what they leave, at most the full charge), same_day_stay, rooming_in,
        included_in_sgk_total, savings_category, savings_basis, sut_section_id,
        rule_id, detail.
    """
    rooming_in = rooming_in_claim_ids or set()
    opportunities: list[dict[str, Any]] = []
    procedures_by_claim: dict[str, list[ProcedureClaimLine]] = {}
    for line in procedure_lines or ():
        procedures_by_claim.setdefault(line.claim_id, []).append(line)

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

        # An ICU stay is the ICU motor's (510090 + P552006/7/8): a Kuvöz is not
        # billed on top of it, and a unit that is not a ward is no Kuvöz stay.
        claim_procs = procedures_by_claim.get(claim.claim_id, [])
        if claim_has_icu_code(claim_procs) or _department_names_icu(
            getattr(claim, "department", "") or ""
        ):
            continue

        # The newborn bed lines already billed on this claim: they net the charge
        # and, as the only evidence of the bed type, price the Kot days below.
        bed_lines = [
            line
            for line in claim_procs
            if normalize_procedure_code(line.procedure_code) in _NEWBORN_BED_CODES
        ]
        # A claim that bills the standard bed and no newborn bed has stated its
        # bed: the standard-bed motor owns the stay and nets its own lines.
        if not bed_lines and any(
            normalize_procedure_code(line.procedure_code) == _STANDARD_BED_CODE
            for line in claim_procs
        ):
            continue

        # Inclusive LOS: discharge day IS billed (+1), matching yatak puani.
        gross_days = (claim.discharge_date - claim.admission_date).days + 1
        if gross_days <= 0:
            continue

        # Package bundling (§2.2.2.B-1(1), (3)-(4)), read as the standard-bed motor
        # reads it: only the days after the package window are newborn bed days.
        window = claim_package_window(claim, claim_procs)
        days = (
            max((claim.discharge_date - window.end).days, 0)
            if window is not None
            else gross_days
        )
        bundled_days = gross_days - days

        visit_date = claim.admission_date or claim.claim_start_date
        kuvoz_rate = _daily_rate(_BED_KUVOZ, visit_date)
        kot_rate = _daily_rate(_BED_KOT, visit_date)
        if kuvoz_rate <= 0 and kot_rate <= 0:
            continue

        # Net out the billed newborn bed lines (510070 + 510081), like the ICU and
        # standard-bed motors; lines inside a mandated package window belong to the package.
        counted_lines = [line for line in bed_lines if counts_against_expected_days(line, window)]

        # Mutually exclusive bed selection.
        # Default = Kuvöz (510070, higher tier). Kot (510081) is NEVER billed
        # for rooming-in babies per SUT; Kuvöz for rooming-in is opt-in. A billed
        # Kot day is priced as a Kot day, every other day as Kuvöz.
        is_rooming_in = claim.claim_id in rooming_in
        if is_rooming_in:
            if not (emit_kuvoz_for_rooming_in and kuvoz_rate > 0):
                # Rooming-in: Kot suppressed, Kuvöz not opted in → skip.
                continue
            kot_days = 0
        else:
            kot_units = sum(
                max(int(getattr(line, "quantity", 1) or 1), 1)
                for line in counted_lines
                if normalize_procedure_code(line.procedure_code) == _BED_KOT
            )
            kot_days = min(kot_units, days) if kot_rate > 0 else 0
        kuvoz_days = days - kot_days
        if kuvoz_days > 0 and kuvoz_rate <= 0:
            continue
        bed_code = _BED_KOT if days > 0 and kuvoz_days == 0 else _BED_KUVOZ
        rate = kot_rate if bed_code == _BED_KOT else kuvoz_rate

        expected = _money(kot_days * kot_rate + kuvoz_days * kuvoz_rate)
        actual_billed_try = _money(sum(float(line.billed_amount_try) for line in counted_lines))
        # Never more than the charge, whatever credit lines the bill carries.
        recoverable_try = _money(min(expected, max(0.0, expected - actual_billed_try)))
        same_day = days == 1 and claim.admission_date == claim.discharge_date

        if 0 < kot_days < days:
            charge = (
                f"{days} bed-day(s) = {kuvoz_days} at {kuvoz_rate:.2f} + "
                f"{kot_days} billed Kot day(s) at {kot_rate:.2f} TRY/day"
            )
        else:
            charge = f"{days} bed-day(s) at {rate:.2f} TRY/day"
        detail_parts = [
            f"Yenidoğan yatağı ({bed_code}): {charge}",
            f"= {expected:.2f} TRY (inclusive LOS, discharge day billed).",
        ]
        if window is not None:
            detail_parts.append(
                f"{bundled_days} of {gross_days} day(s) are bundled into the "
                f"{'mandated ' if window.mandated else ''}EK-2/C package window "
                f"(package {window.start}, window through {window.end}); only the "
                "days after it are newborn bed days."
            )
        if is_rooming_in:
            detail_parts.append(
                "Rooming-in ('anne yanında') episode — Kot (510081) is not "
                "billable per SUT; Kuvöz (510070) billed per opt-in."
            )
        detail_parts.append(
            "Kuvöz (510070) and Kot (510081) are mutually exclusive; only "
            "one newborn bed may be billed per day."
        )
        if bed_code == _BED_KOT:
            detail_parts.append(
                "A Kot (510081) line is billed on this claim: priced at the Kot "
                "rate, not upgraded to Kuvöz."
            )
        if procedure_lines is not None and not bed_lines and not is_rooming_in:
            detail_parts.append(
                "No newborn bed line (510070 / 510081) is billed on this claim: "
                "Kuvöz (510070) is assumed — confirm the bed type in the stay record."
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
                "bundled_days": bundled_days,
                "puan": _puan_for(bed_code, visit_date),
                "expected_try": expected,
                "actual_billed_try": actual_billed_try,
                "recoverable_uplift_try": recoverable_try,
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


def _puan_for(bed_code: str, visit_date: date | str | None = None) -> float:
    """Return the raw EK-2B puan (pre-katsayı) for a newborn bed code as of visit_date."""
    result = lookup_procedure_code(bed_code, visit_date=visit_date)
    entry = (result or {}).get("entry") or {}
    return float(entry.get("puan") or 0.0)

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
A claim billed hizmet başı whose package is mandated (§2.2.2(1)) is treated
the same way (``claim_package_window``): it must be billed as that package,
so the package's components add no itemized uplift inside the window.

**Stays under 24 hours (SUT §2.2.2.(3), EK-2/B 510120):** "24 saatten kısa süreli
yatışlarda yatak bedeli, gündüz yatak bedeli üzerinden faturalandırılır." The claim
has dates, no times, so a stay whose admission date equals its discharge date (always
under 24 hours) is priced at the day bed 510120 (Gündüz yatak tarifesi, 74.96 puan
against 374.97 for 510010) instead of a full 510010 day, and a billed 510120 line nets it like a 510010
line (on such a stay only: a 510120 line pays no standard-bed day of a longer stay).
An overnight stay under 24 hours spans two dates and cannot be seen.

**Days whose bed is already paid, or whose day bed the SUT forbids** (``bed_days_not_expected``, read by this motor,
the newborn bed motor and the ICU reconciliation): EK-2/B 530000 (Acil serviste kritik hasta yatak ve takibi), 510100
(Steril oda) and 510110 (İzole radyoaktif tedavi odası) "Yatak, yemek, hasta vizit hizmetlerini kapsar" — the days
such a line is billed for are not bed days to expect, as for 510090 on the ICU transfer day. The day bed of a stay of
one date is not billed beside 530000 (EK-2/B: "510120, 530003 ile birlikte faturalandırılmaz") or inside a
hemodialysis price (SUT §2.4.4.D-1.(11): "gündüz yatak ücreti fiyata dâhil"; 704210, 704230): no day is expected
there. A day case (it may cross midnight and has no admission, §2.1.2.B.(1)) that bills an EK-2/C procedure has no
bed to bill (§2.2.2.(4) forbids its day bed): none of its days is expected, whatever its dates.

**The ICU stay of the claim's own lines:** EK-2/B 510090 (Yoğun bakım) says, in every list since 2018, "Yemek, yatak, hasta
vizit hizmetlerini kapsar". The EK-2/C ICU packages (P552001-3, P552006-8) carry no text of their own (empty Açıklama and
işlem grubu): §2.4.4.H.(2) bills "Yoğun bakım tedavileri" on EK-2/C points, EK-2/C points include "Yatak bedeli" unless the
Açıklama column states an exception (§2.2.2.B-1.(1).a, (2)), and none is stated for the ICU packages (other per-day
EK-2/C packages do say it, either way: psychiatry includes the bed, FTR §2.4.4.F-2.(9) bills it separately). So the bed is
read as included: an inference from those clauses, not a quote. §2.4.4.H.(8) bills the first and the exit day hizmet başı
(510090); the days between are read as the package days of the same stay (inference from (2) and (8)). A line of either
pays the days its quantity covers, a 510090 line of quantity exactly 2 is the first and the exit day in one line (as the
ICU motor reads it), and the days between the first and the last such day are the stay, so none of them is a standard-bed
day. Ward days of the same claim before or after the stay are expected as before; the claim's own last day is still
dropped by ``yatak_icu_overlap``.

See plans/refactor/rule-encoding-gap-closure-roadmap.md + the approved
yatak-puani plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from src.bilun.domain.catalog import lookup_procedure_code
from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules.catalog_membership import (
    get_ek2c_entry,
    normalize_procedure_code,
)
from src.bilun.domain.prose_rules.claim_utils import (
    claim_is_day_case,
    group_procedure_lines_by_session,
    infer_care_setting,
)
from src.bilun.domain.prose_rules.payment_method import check_payment_method_compliance
from src.bilun.domain.prose_rules.session_pricing import compute_session_point_factors
from src.bilun.domain.prose_rules.session_scope import (
    billed_without_session_rules,
    line_billed_as_package,
    session_operation_lines,
)
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_SGK_UPLIFT,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_OPPORTUNITY_TYPE = "yatak_puani_standard_bed"
_BED_CODE = "510010"
# EK-2/B 510120 Gündüz yatak tarifesi: the bed of a stay under 24 hours (SUT §2.2.2.(3)); also read by the
# newborn bed motor and the standard-bed / newborn-bed reconciliation.
DAY_BED_CODE = "510120"
# EK-2/B codes whose price covers the patient's bed ("Yatak, yemek, hasta vizit hizmetlerini kapsar"): 530000 Acil
# serviste kritik hasta yatak ve takibi (billed once a day; "510120, 530003 ile birlikte faturalandırılmaz"), 510100
# Steril oda, 510110 İzole radyoaktif tedavi odası. The same sentence the project reads as "the bed is paid" for 510090
# (yatak_icu_overlap) and for 510070 / 510081 (claim_yatak_newborn_overlap).
ER_CRITICAL_BED_CODE = "530000"
BED_INCLUDING_CODES = frozenset({ER_CRITICAL_BED_CODE, "510100", "510110"})
# SUT §2.4.4.D-1.(11) (C000969): for a hemodialysis treatment "gündüz yatak ücreti fiyata dâhil olup ayrıca
# faturalandırılmayacaktır": 704210 Acil hemodiyaliz, 704230 Hemodiyaliz (not 704233 home hemodialysis, D-1-1).
HEMODIALYSIS_CODES = frozenset({"704210", "704230"})
# EK-2/B 510090 Yoğun bakım ("Yemek, yatak, hasta vizit hizmetlerini kapsar") and the EK-2/C ICU packages P552001-3 (adult)
# and P552006-8 (newborn), read without the P: the codes the ICU motor's own gate (``icu_puani.claim_has_icu_code``) takes
# as an ICU claim (``yatak_icu_overlap`` reads this set too). They carry a second rule beside the days their quantity
# covers (the days between the first and the last are the stay), so they are not in ``BED_INCLUDING_CODES``.
ICU_DAY_RATE_CODE = "510090"
ICU_BED_CODES = frozenset({ICU_DAY_RATE_CODE, "552001", "552002", "552003", "552006", "552007", "552008"})

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


def _daily_rate(visit_date: date | str | None = None, bed_code: str = _BED_CODE) -> float:
    """Look up the ``bed_code`` (default 510010) price_try (already puan × katsayı) as of visit_date."""
    result = lookup_procedure_code(bed_code, visit_date=visit_date)
    entry = (result or {}).get("entry") or {}
    return float(entry.get("price_try") or 0.0)


def _is_billed_bed_line(line: ProcedureClaimLine, *, same_day: bool) -> bool:
    """A billed bed line that nets the expected charge: 510010 (the exact code, as ever) and, on a
    stay under 24 hours, 510120. The day bed is read like the newborn motor's stand-down reads it
    (spacing, dots, hyphens), because that motor hands such a claim over for a billed 510120 line."""
    if str(line.procedure_code).strip() == _BED_CODE:
        return True
    return same_day and normalize_procedure_code(line.procedure_code) == DAY_BED_CODE


def _resolve_package_window_days(
    line: ProcedureClaimLine,
    *,
    fallback_date: date | None = None,
) -> int:
    """Return the §2.2.2.B-1(3) window length for a billed or mandated package line."""
    as_of = line.procedure_date or fallback_date
    entry = get_ek2c_entry(line.procedure_code, as_of_date=as_of)
    if entry is None and getattr(line, "package_code", ""):
        entry = get_ek2c_entry(line.package_code, as_of_date=as_of)
    group = str(
        (entry or {}).get("group") or getattr(line, "ek2c_group", "") or ""
    ).strip().upper()
    return PACKAGE_WINDOW_DAYS.get(group, 1)


@dataclass(frozen=True)
class PackageWindow:
    """An inpatient claim's EK-2/C package window (SUT §2.2.2.B-1(1), (3)).

    The package includes bed, companion and anaesthesia from admission
    ("takip alındıktan sonraki") through ``end``, the procedure date plus the
    group's days minus one; ``start`` is the first package line's procedure
    date. ``mandated`` marks a claim that bills no package line although one
    of its lines must be billed as a package (§2.2.2(1)).
    """

    start: date | None
    end: date
    mandated: bool = False


def _package_window_end(
    package_lines: list[ProcedureClaimLine],
    *,
    admission_date: date | None = None,
    discharge_date: date | None = None,
) -> date | None:
    """Return the last calendar date covered by the claim's EK-2/C packages.

    Per SUT §2.2.2.B-1(1) ("takip alındıktan sonraki") and §2.2.2.B-1(3)-(4),
    an EK-2/C package bundles bed and companion fees from admission through
    ``procedure_date + timedelta(days=window_days - 1)``. When multiple
    package lines exist on a claim, the latest window end governs.
    """
    window_end: date | None = None
    for line in package_lines:
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


def must_be_billed_as_package(claim: ClaimHeader, line: ProcedureClaimLine) -> bool:
    """Billed hizmet başı though SUT mandates its EK-2/C package on its procedure date.

    ``check_payment_method_compliance`` at the claim's care setting and facility
    tier (§2.2.2(1), §2.2.1.B-1(a)), the test of the payment-method row.
    """
    if line_billed_as_package(line) or float(line.billed_amount_try) <= 0:
        return False
    compliance = check_payment_method_compliance(
        normalize_procedure_code(line.procedure_code),
        billed_as_package=False,
        care_setting=infer_care_setting(claim),  # type: ignore[arg-type]
        facility_tier=claim.facility_tier,
        provider_type=claim.provider_type,
        as_of_date=line.procedure_date or claim.admission_date or claim.claim_start_date,
        day_case=claim_is_day_case(claim),
    )
    return not compliance.is_compliant and compliance.mandated_method == "package"


def c000672_hizmet_basi_lines(
    claim: ClaimHeader,
    claim_procs: list[ProcedureClaimLine],
) -> list[ProcedureClaimLine]:
    """Must-package lines that §2.2.2.B(3)(c)/(ç) lets the hospital bill hizmet başı.

    C000672 / C000673: "ancak SUT eki EK-2/B Listesinde yer alan işlemin puanının
    diğer işlemlerden yüksek olması durumunda tüm işlemler 2.2.2.A(5) fıkrası göz
    önünde bulundurularak hizmet başına ödeme yöntemiyle". When an operation billed
    hizmet başı outranks every package of its session, the session's
    must-package operations are billed hizmet başı too.
    """
    billed = [
        line for line in claim_procs
        if line.claim_id == claim.claim_id
        and not line.is_package_included
        and float(line.billed_amount_try) > 0
    ]
    exempt: list[ProcedureClaimLine] = []
    for session_date, session_lines in group_procedure_lines_by_session(billed).items():
        operations = [
            line for line in session_operation_lines(session_lines)
            if normalize_procedure_code(line.procedure_code)
        ]
        packages = [
            line_billed_as_package(line) or must_be_billed_as_package(claim, line)
            for line in operations
        ]
        if len(operations) < 2 or all(packages) or not any(packages):
            continue
        session = compute_session_point_factors(
            [line.procedure_code for line in operations],
            same_incision=True,
            as_of_date=session_date,
            billed_as_package=packages,
        )
        if session.rule_id == "2.2.2.A.(5)":
            exempt.extend(
                line for line, package in zip(operations, packages, strict=True)
                if package and not line_billed_as_package(line)
            )
    return exempt


def mandated_package_lines(
    claim: ClaimHeader,
    claim_procs: list[ProcedureClaimLine],
) -> list[ProcedureClaimLine]:
    """Lines billed hizmet başı that must be billed as an EK-2/C package (§2.2.2(1)).

    Read from the codes, never from the ``package_candidate`` header flag,
    which only the synthetic generator sets. A line qualifies when:

    - it is billed (> 0) and not as a package (``line_billed_as_package``: the
      ``paket`` category or a ``P`` code), and no package line for its code is on
      the claim;
    - ``must_be_billed_as_package``: "must use package billing" at the claim's
      facility tier on its procedure date, and C000672 does not bill its
      session hizmet başı (``c000672_hizmet_basi_lines``);
    - it is no neuromonitoring or neuronavigation line, which is billed next to
      its operation and carries no stay (C001389, C001413);
    - its EK-2/C package has a price and an işlem grubu (A1–E) that day.
    """
    package_codes = {
        normalize_procedure_code(code)
        for line in claim_procs
        if line_billed_as_package(line)
        for code in (line.procedure_code, line.package_code)
        if code
    }
    exempt = {id(line) for line in c000672_hizmet_basi_lines(claim, claim_procs)}
    mandated: list[ProcedureClaimLine] = []
    for line in claim_procs:
        if line.claim_id != claim.claim_id or line.is_package_included or id(line) in exempt:
            continue
        code = normalize_procedure_code(line.procedure_code)
        if not code or code in package_codes or billed_without_session_rules(code):
            continue
        if not must_be_billed_as_package(claim, line):
            continue
        as_of = line.procedure_date or claim.admission_date or claim.claim_start_date
        entry = get_ek2c_entry(code, as_of_date=as_of) or {}
        group = str(entry.get("group") or "").strip().upper()
        if float(entry.get("price_try") or 0.0) <= 0 or group not in PACKAGE_WINDOW_DAYS:
            continue
        mandated.append(line)
    return mandated


def claim_package_window(
    claim: ClaimHeader,
    claim_procs: list[ProcedureClaimLine],
) -> PackageWindow | None:
    """The claim's EK-2/C package window, or ``None``.

    Every package on the claim opens it: the lines billed as a package (#259)
    and the lines that must be billed as one but were billed hizmet başı
    (``mandated_package_lines``), each with its EK-2/C group in force on its
    procedure date. A claim of the second kind only is treated like a package
    claim, so the components the package includes add no itemized uplift
    inside the window.
    """
    billed = [line for line in claim_procs if line_billed_as_package(line)]
    lines = billed + mandated_package_lines(claim, claim_procs)
    end = _package_window_end(
        lines, admission_date=claim.admission_date, discharge_date=claim.discharge_date,
    )
    if end is None:
        return None
    return PackageWindow(start=lines[0].procedure_date, end=end, mandated=not billed)


def counts_against_expected_days(
    line: ProcedureClaimLine,
    window: PackageWindow | None,
) -> bool:
    """Whether a billed bed or companion line pays for days the detector expects.

    On a bill that should have been a package (``window.mandated``), a line
    whose days all fall inside the window belongs to the package, not to the
    days after it (§2.2.2.B-1(4)); a line reaching past the window still
    counts, so a stay billed on one multi-day line is never expected twice. On
    any other claim every billed line counts.
    """
    if window is None or not window.mandated or line.procedure_date is None:
        return True
    last_day = line.procedure_date + timedelta(days=max(int(line.quantity or 1), 1) - 1)
    return last_day > window.end


def _units(line: ProcedureClaimLine) -> int:
    """Days a bed-including line covers: its quantity, at least 1; a missing or unreadable one (None, NaN) counts one."""
    try:
        return max(int(line.quantity or 1), 1)
    except (TypeError, ValueError, OverflowError):
        return 1


def _stay_days_covered(line: ProcedureClaimLine, admission: date, discharge: date) -> list[date]:
    """The days of the stay a bed-including line pays: from its date (the admission date when undated) for its quantity in
    days, clipped to the stay, so a line dated outside the stay covers only what its quantity runs into."""
    start = line.procedure_date or admission
    # The quantity in days from the line's date, clipped at the discharge (no overflow for a huge quantity); a line dated
    # after the discharge gets no unit left and covers nothing.
    units = min(_units(line), (discharge - start).days + 1)
    last = start + timedelta(days=units - 1)
    first = max(start, admission)
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


def _icu_line_days(code: str, line: ProcedureClaimLine, admission: date, discharge: date) -> list[date]:
    """The days of the stay an ICU line pays. An EK-2/C ICU package pays its quantity in days from its date, like any
    bed-including line, and so does a 510090 line of quantity 1 (its own day) or of quantity 3 or more (§2.4.4.H.(8)
    knows two hizmet başı days only, so more units than that are a daily billing). A 510090 line of quantity exactly 2 is
    read as the ICU motor reads it (``icu_puani``: two day-rate units are the first and the exit day, not two consecutive
    days): either date can sit on the line, and the claim-span model of this project puts the other end on the claim's
    first or last day, so the stay runs from the line's date through the discharge, or, for a line dated on the
    discharge date itself, from the admission."""
    days = _stay_days_covered(line, admission, discharge)
    if days and code == ICU_DAY_RATE_CODE and _units(line) == 2:
        first = admission if line.procedure_date == discharge else days[0]
        return [first + timedelta(days=offset) for offset in range((discharge - first).days + 1)]
    return days


@dataclass(frozen=True)
class BedNotExpected:
    """Days of a stay on which no bed is expected, and why (one sentence per cause, for the row's ``detail``).

    ``dates`` are days of the stay after any package window: those the window takes are explained by it.
    """

    dates: frozenset[date] = frozenset()
    reasons: tuple[str, ...] = ()


def bed_days_not_expected(
    claim: ClaimHeader,
    claim_procs: list[ProcedureClaimLine],
    window: PackageWindow | None = None,
) -> BedNotExpected:
    """The days of the stay whose bed the SUT says is already paid, or whose day bed it forbids billing.

    Read from the claim's own lines, and only from billed ones: a credit line (a reversal) withdraws a charge and
    says nothing about the stay's bed, as for a newborn bed line.

    1. **Days a bed-including line pays** (``BED_INCLUDING_CODES``; EK-2/B "Yatak, yemek, hasta vizit hizmetlerini
       kapsar"): from the line's date for its quantity in days (an undated line sits on the admission date, as
       ``_package_window_end`` places an undated package line), clipped to the stay: only the days of the stay the
       quantity reaches are covered, so a line dated outside the stay covers nothing unless its quantity runs into it.
    2. **The day bed of a stay of one date** (a stay under 24 hours, §2.2.2.(3), priced at 510120) is not billable
       when the claim bills 530000 anywhere (EK-2/B: "510120, 530003 ile birlikte faturalandırılmaz", a claim-level
       exclusion, so its date and quantity do not matter) or hemodialysis 704210 / 704230 (§2.4.4.D-1.(11): "gündüz
       yatak ücreti fiyata dâhil olup ayrıca faturalandırılmayacaktır"). A stay of several dates bills 510010, which
       neither names: nothing is taken out there.
    3. **A day case** (``claim_is_day_case``: "within 24 hours" and "without admission", §2.1.2.B.(1), so it may cross
       midnight and has no ward bed) **that bills an EK-2/C procedure** has no bed to bill: its only bed is the day
       bed, which §2.2.2.(4) forbids for those procedures. Every day of such a claim (after any package window) is
       not expected, whatever its dates.
    4. **The ICU stay of the claim's own lines** (``ICU_BED_CODES``: 510090 and the EK-2/C ICU packages; 510090 says
       "Yemek, yatak, hasta vizit hizmetlerini kapsar"; the packages are the EK-2/C points of "Yoğun bakım tedavileri",
       §2.4.4.H.(2), and EK-2/C points include "Yatak bedeli", §2.2.2.B-1.(1).a, with no exception stated for them: the
       bed is read as included, an inference). A line pays the days its quantity covers (as for cause 1; see
       ``_icu_line_days`` for a 510090 line of quantity 2); the days between the first and the last covered day
       are the stay itself (§2.4.4.H.(8): the first and the exit day are hizmet başı, the days between are read as
       package days, billed or not: a missing package is an ICU matter, never a bed day), so none is expected. Days of
       the claim before the first and after the last ICU line are ward days and stay expected. A ward interval between
       two separate ICU stays of ONE claim is not told apart from package days and is read as part of the stay: silence,
       never a false recoverable.

    The package window takes its days first (never subtracted twice); the ICU reconciliation and the newborn bed
    motor skip the days this returns.
    """
    admission, discharge = claim.admission_date, claim.discharge_date
    if admission is None or discharge is None or discharge < admission:
        return BedNotExpected()
    first = admission if window is None else max(admission, window.end + timedelta(days=1))
    if first > discharge:
        return BedNotExpected()
    one_date = admission == discharge

    lines = [
        (normalize_procedure_code(line.procedure_code), line)
        for line in claim_procs
        if line.claim_id == claim.claim_id and float(line.billed_amount_try) >= 0
    ]
    codes = {code for code, _ in lines}
    dates: set[date] = set()
    reasons: list[str] = []

    paid_by: dict[str, set[date]] = {}
    for code, line in lines:
        # On a stay of one date 530000 is the claim-level cause below, whatever its date.
        if code not in BED_INCLUDING_CODES or (one_date and code == ER_CRITICAL_BED_CODE):
            continue
        for day in _stay_days_covered(line, admission, discharge):
            if day >= first:
                paid_by.setdefault(code, set()).add(day)
    if paid_by:
        covered = sorted(set().union(*paid_by.values()))
        dates.update(covered)
        reasons.append(
            f"{len(covered)} day(s) ({', '.join(day.isoformat() for day in covered)}) are paid by "
            f"{' / '.join(sorted(paid_by))} (EK-2/B: it covers yatak, yemek, hasta vizit) and are not expected as "
            "bed days."
        )

    # The ICU stay of the claim's own lines: the days the lines cover and, between the first and the last of them, the
    # days of the stay itself (nothing in the stay is a standard-bed day). The window's days are explained by the window.
    icu_covered: dict[str, set[date]] = {}
    for code, line in lines:
        if code in ICU_BED_CODES:
            for day in _icu_line_days(code, line, admission, discharge):
                icu_covered.setdefault(code, set()).add(day)
    if icu_covered:
        stay_first = min(min(days) for days in icu_covered.values())
        stay_last = max(max(days) for days in icu_covered.values())
        stay = (stay_first + timedelta(days=offset) for offset in range((stay_last - stay_first).days + 1))
        icu_days = [day for day in stay if day >= first]
        if icu_days:
            dates.update(icu_days)
            reasons.append(
                f"{len(icu_days)} day(s) ({', '.join(day.isoformat() for day in icu_days)}) lie inside the ICU stay shown "
                f"by the claim's {' / '.join(sorted(icu_covered))} line(s): EK-2/B 510090 covers yatak, yemek, hasta vizit; "
                "the EK-2/C ICU packages are EK-2/C points, which include the bed (SUT §2.2.2.B-1.(1).a, no exception stated "
                "for them); the first and the exit day are 510090 and the days between the package (§2.4.4.H.(2), (8)), so "
                "no standard bed is expected on them."
            )

    day_case_ek2c: list[str] = []
    if claim_is_day_case(claim):
        day_case_ek2c = sorted(
            {
                code
                for code, line in lines
                if get_ek2c_entry(code, as_of_date=line.procedure_date or admission) is not None
            }
        )

    if one_date:
        causes: list[str] = []
        if ER_CRITICAL_BED_CODE in codes:
            causes.append(
                "530000 (Acil serviste kritik hasta yatak ve takibi) is billed on this claim and covers yatak, yemek "
                f"and vizit; EK-2/B does not bill {DAY_BED_CODE} together with it."
            )
        dialysis = sorted(codes & HEMODIALYSIS_CODES)
        if dialysis:
            causes.append(
                f"hemodialysis ({' / '.join(dialysis)}) is billed on this claim and its price includes the day bed "
                "fee, which is not billed separately (SUT §2.4.4.D-1.(11))."
            )
        if day_case_ek2c:
            causes.append(
                f"a day case (günübirlik) bills EK-2/C procedure(s) ({' / '.join(day_case_ek2c)}), and SUT §2.2.2.(4) "
                "does not bill the day bed for them."
            )
        if causes:
            dates.add(admission)
            reasons.extend(f"No day bed ({DAY_BED_CODE}) is expected: {cause}" for cause in causes)
    elif day_case_ek2c:
        dates.update(first + timedelta(days=offset) for offset in range((discharge - first).days + 1))
        reasons.append(
            f"No bed day is expected: a day case (günübirlik) bills EK-2/C procedure(s) ({' / '.join(day_case_ek2c)}); "
            "SUT §2.2.2.(4) does not bill the day bed for them, and a day case has no admission (§2.1.2.B.(1)), so it "
            "has no other bed."
        )

    return BedNotExpected(dates=frozenset(dates), reasons=tuple(reasons))


def detect_yatak_puani_opportunities(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine] | None = None,
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Detect expected bed-day charges for inpatient claims.

    For each inpatient claim with non-null admission + discharge dates,
    computes inclusive LOS × daily_rate and returns an opportunity dict.

    **Stays under 24 hours (SUT §2.2.2.(3)):** a stay whose admission date equals
    its discharge date is priced at the day bed 510120, not a full 510010 day; its
    ``bed_code`` / ``daily_rate_try`` are the day bed's, and 510120 lines net it too.

    **Bed already paid / day bed forbidden (``bed_days_not_expected``):** the days a 530000, 510100 or 510110 line
    pays, the only day of a stay of one date that bills 530000 or hemodialysis, every day of a day case that bills
    an EK-2/C procedure, and the ICU stay of the claim's own 510090 / EK-2/C ICU package lines, are not expected:
    ``bed_days`` and the money fall, ``gross_bed_days`` / ``bundled_days`` keep their meaning, and ``detail`` says why.

    **Package-bundling (SUT §2.2.2.B-1(1), (3)-(4)):** When a claim has an
    EK-2/C package procedure (``paket`` category), or is billed hizmet başı
    while its package is mandated, bed days from admission through the end
    of the package group's window (A1/A2/A3=15, B=10, C=8, D=5, E=3 days
    from ``procedure_date``) are bundled into the package; only post-window
    days are billed. Without ``procedure_lines``, all days are billed
    (backwards-compatible default).
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

        # Inclusive LOS: discharge day IS billed (+1).
        gross_days = (claim.discharge_date - claim.admission_date).days + 1
        if gross_days <= 0:
            continue

        # SUT §2.2.2.(3): a stay under 24 hours (here: one date) is billed at the day bed.
        same_day = gross_days == 1 and claim.admission_date == claim.discharge_date
        bed_code = DAY_BED_CODE if same_day else _BED_CODE
        daily_rate = _daily_rate(visit_date, bed_code)
        if daily_rate <= 0:
            continue

        # Package-bundling (§2.2.2.B-1(1), (3)-(4)): when the claim carries an
        # EK-2/C package procedure, or must be billed as one, all bed days from
        # admission through the package group's window end are bundled into
        # the package.
        claim_procs = procedures_by_claim.get(claim.claim_id, [])
        window = claim_package_window(claim, claim_procs)
        surgery_day_bundled = window is not None
        if window is not None:
            days = max((claim.discharge_date - window.end).days, 0)
            bundled_days = gross_days - days
        else:
            days = gross_days
            bundled_days = 0

        # Days whose bed is already paid (530000, 510100, 510110, the claim's ICU lines) or whose day bed the SUT forbids
        # (530000, hemodialysis, a day case's EK-2/C procedures): not expected. They lie after the package window, so
        # nothing is taken twice.
        not_expected = bed_days_not_expected(claim, claim_procs, window)
        days -= len(not_expected.dates)

        expected = _money(days * daily_rate)

        # Net out actual billed bed-day amounts (510010; on a stay under 24 hours also
        # 510120) so recoverable uplift reflects only the UNBILLED portion.
        actual_billed_try = _money(
            sum(
                float(p.billed_amount_try)
                for p in claim_procs
                if _is_billed_bed_line(p, same_day=same_day)
                and counts_against_expected_days(p, window)
            )
        )
        # Never more than the expected charge: a credit line (negative amount) must not recover extra.
        recoverable_try = _money(min(expected, max(0.0, expected - actual_billed_try)))

        label = "Gündüz yatak" if same_day else "Standart yatak"
        detail_parts = [
            f"{label} ({bed_code}): {days} billable bed-day(s) "
            f"(gross LOS {gross_days} day(s) at {daily_rate:.2f} TRY/day",
        ]
        if window is not None and window.mandated:
            detail_parts[0] += (
                f", {bundled_days} day(s) bundled into the mandated EK-2/C package "
                f"window (operation {window.start}, window through {window.end}; "
                f"510010 lines inside it belong to the package)"
            )
        elif window is not None:
            detail_parts[0] += (
                f", {bundled_days} day(s) bundled into EK-2/C package window "
                f"(surgery {window.start}, window through {window.end})"
            )
        detail_parts[0] += ")"
        detail_parts.append(f"= {expected:.2f} TRY (inclusive LOS, discharge day billed).")
        if same_day:
            detail_parts.append(
                "Same-day admission/discharge (under 24 hours): SUT §2.2.2.(3) bills the bed "
                f"at the day bed ({DAY_BED_CODE}, Gündüz yatak tarifesi), not as a full "
                f"{_BED_CODE} day."
            )
        detail_parts.extend(not_expected.reasons)

        opportunities.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim.claim_id,
                "bed_code": bed_code,
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

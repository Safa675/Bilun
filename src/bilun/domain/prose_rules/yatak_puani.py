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
        daily_rate = _daily_rate(visit_date)
        if daily_rate <= 0:
            continue

        # Inclusive LOS: discharge day IS billed (+1).
        gross_days = (claim.discharge_date - claim.admission_date).days + 1
        if gross_days <= 0:
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

        expected = _money(days * daily_rate)
        same_day = gross_days == 1 and claim.admission_date == claim.discharge_date

        # Net out actual billed bed-day amounts (510010) so recoverable
        # uplift reflects only the UNBILLED portion.
        actual_billed_try = _money(
            sum(
                float(p.billed_amount_try)
                for p in claim_procs
                if str(p.procedure_code).strip() == _BED_CODE
                and counts_against_expected_days(p, window)
            )
        )
        recoverable_try = _money(max(0.0, expected - actual_billed_try))

        detail_parts = [
            f"Standart yatak (510010): {days} billable bed-day(s) "
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

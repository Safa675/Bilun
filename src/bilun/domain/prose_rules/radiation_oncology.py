"""Source-backed radiation billing candidates with unconfirmed financial risk.

Authority: current EK-2/B §8.1 explanatory cells, not SUT §2.4.4.C (the
stereotactic EK-2/C rules). Ministry El Kitabı pp87–89 / Tablo 30 illustrates
these rules but does not create a blanket one-per-family restriction.

A claim is not a verified treatment course; a procedure date is not a session
identifier; quantity can include several treatment days. SGK Fatura İnceleme
Usul ve Esasları, common criterion18, permits such grouped billing when the
supporting dates satisfy daily limits. The current input has no course/session,
date-allocation, clinical entitlement, or adjudication evidence. Consequently
returned participants are review-only, with null risk and the actual billed
amount kept separately. No first/highest/cheapest line is chosen for payment.

The legacy callable, family keys and historical rule IDs remain compatibility
identifiers, not confirmed decisions. An empty result is not complete clinical
or course validation. In particular, no hyperthermia daily-family predicate is
asserted without resolving its scope, and course checks do not span claims.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import TYPE_CHECKING, Any

from src.bilun.domain.money import money_round_half_up as _money

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_OPPORTUNITY_TYPE = "radiation_oncology"
_RULE_SET_ID = "radiation_oncology"
_SOURCE_URL = (
    "https://karabuk.sgk.gov.tr/Download/DownloadFile?"
    "f=9afde55e-9207-4432-a54e-3b441f11e70c.zip&d=658f4ba1-b0e8-4dfb-8504-fa0b09e353e0"
)
_SOURCE_DOCUMENT = "2026-08-29 consolidated SUT / EK-2B (effective 2026-07-07)"

# ---------------------------------------------------------------------------
# Radiation oncology code families.
#
# Catalog families retain their legacy identity/scope for callers. Only the
# two design families share a uniform cap. Actual source predicates below
# distinguish alternatives, per-code limits, plan counts and session evidence.
# The historical "same_day" identity does not certify a same-session event.
# Catalog names identify groups; they are not the authority for exclusions:
#   800070–800110  Eksternal radyoterapi tasarımı (external RT design)
#   800111–800114  Brakiterapi tasarımı (brachytherapy design)
#   800120–800160  Radyoterapi planlama (RT planning/simulation)
#   800170–800230  Eksternal radyoterapi doz hesapları (external RT dose calc)
#   800235–800260  Brakiterapi doz hesapları (brachytherapy dose calc)
#   800270–800300  Özel dozimetre / tedavi aletleri (special devices)
#   800330–800370  Eksternal radyoterapi uygulaması (conventional RT application)
#   800380–800440  Lineer akseleratör radyoterapi uygulaması (linac RT application)
#   800450–800490  Hipertermi (hyperthermia)
#   800500–800550  Intrakaviter/Intertisiyel brakiterapi uygulaması
#   800560–800590  After-loading brakiterapi uygulaması
# ---------------------------------------------------------------------------

_FAMILY_EXTERNAL_DESIGN = (
    "external_rt_design",
    "External RT design (tasarım)",
    ("800070", "800080", "800090", "800100", "800110"),
    "course",
    1,
)
_FAMILY_BRACHY_DESIGN = (
    "brachytherapy_design",
    "Brachytherapy design (tasarım)",
    ("800111", "800112", "800113", "800114"),
    "course",
    1,
)
_FAMILY_PLANNING = (
    "rt_planning",
    "RT planning/simulation (planlama)",
    ("800120", "800130", "800140", "800150", "800160"),
    "course",
    None,
)
_FAMILY_EXTERNAL_DOSE = (
    "external_rt_dose",
    "External RT dose calculation (doz hesabı)",
    ("800170", "800180", "800190", "800200", "800210", "800220", "800230"),
    "course",
    None,
)
_FAMILY_BRACHY_DOSE = (
    "brachytherapy_dose",
    "Brachytherapy dose calculation (doz hesabı)",
    ("800235", "800240", "800250", "800260"),
    "course",
    None,
)
_FAMILY_SPECIAL_DEVICES = (
    "special_devices",
    "Special services & auxiliary devices (özel hizmetler)",
    ("800270", "800280", "800290", "800300"),
    "course",
    None,
)
_FAMILY_RT_APPLICATION = (
    "rt_application",
    "Conventional RT application (eksternal uygulama)",
    ("800330", "800340", "800350", "800360", "800370"),
    "same_day",
    None,
)
_FAMILY_LINAC_APPLICATION = (
    "linac_application",
    "Linac RT application (lineer akseleratör uygulama)",
    ("800380", "800390", "800400", "800410", "800420", "800430", "800440"),
    "same_day",
    None,
)
_FAMILY_HYPERTHERMIA = (
    "hyperthermia",
    "Hyperthermia (hipertermi)",
    ("800450", "800460", "800470", "800480", "800490"),
    "same_day",
    None,
)
_FAMILY_BRACHY_APPLICATION = (
    "brachy_application",
    "Intracavitary/interstitial brachytherapy application",
    ("800500", "800510", "800520", "800530", "800540", "800550"),
    "same_day",
    None,
)
_FAMILY_AFTERLOADING = (
    "afterloading",
    "After-loading brachytherapy application",
    ("800560", "800570", "800580", "800590"),
    "same_day",
    None,
)

# (family_key, family_name, member_codes, scope, course_cap_or_None)
_FAMILIES: tuple[tuple[str, str, tuple[str, ...], str, int | None], ...] = (
    _FAMILY_EXTERNAL_DESIGN,
    _FAMILY_BRACHY_DESIGN,
    _FAMILY_PLANNING,
    _FAMILY_EXTERNAL_DOSE,
    _FAMILY_BRACHY_DOSE,
    _FAMILY_SPECIAL_DEVICES,
    _FAMILY_RT_APPLICATION,
    _FAMILY_LINAC_APPLICATION,
    _FAMILY_HYPERTHERMIA,
    _FAMILY_BRACHY_APPLICATION,
    _FAMILY_AFTERLOADING,
)

# Pre-computed lookup: code -> (family_key, family_name, scope, course_cap)
_CODE_TO_FAMILY: dict[str, tuple[str, str, str, int | None]] = {}
for _fkey, _fname, _codes, _scope, _cap in _FAMILIES:
    for _c in _codes:
        _CODE_TO_FAMILY[_c] = (_fkey, _fname, _scope, _cap)


def _is_radiation_code(code: str) -> bool:
    """True for any 800xxx procedure code present in a radiation family."""
    return (code or "").strip() in _CODE_TO_FAMILY


def _line_billed(line: ProcedureClaimLine) -> float:
    return float(getattr(line, "billed_amount_try", 0.0) or 0.0)


def _family_for_code(code: str) -> tuple[str, str, str, int | None] | None:
    return _CODE_TO_FAMILY.get((code or "").strip())


def _group_lines_by_claim(
    procedure_lines: list[ProcedureClaimLine],
) -> dict[str, list[ProcedureClaimLine]]:
    """Group procedure lines by claim_id (ignoring lines with no claim)."""
    grouped: dict[str, list[ProcedureClaimLine]] = defaultdict(list)
    for line in procedure_lines:
        claim_id = getattr(line, "claim_id", "") or ""
        if not claim_id:
            continue
        grouped[claim_id].append(line)
    return dict(grouped)


_COURSE_SOURCES = {
    "external_rt_design": ("8.1.2.A", "EK-2B!C3644"),
    "brachytherapy_design": ("8.1.2.B", "EK-2B!C3650"),
    "rt_planning": ("8.1.3", "EK-2B!C3655"),
    "external_rt_dose": ("8.1.4.A", "EK-2B!C3661"),
    "brachytherapy_dose": ("8.1.4.B", "EK-2B!C3669"),
    "special_devices": ("8.1.4.C", "EK-2B!C3675:C3678"),
}


def _detect_course_cap_violations(
    claim: ClaimHeader,
    lines: list[ProcedureClaimLine],
) -> list[dict[str, Any]]:
    """Apply only the alternatives/quantity conditions stated in EK-2/B.

    A repeated item can be legitimate on distinct courses. Advanced planning
    can repeat up to three times with justification, and advanced dose counts
    depend on plan counts. Those missing facts are never silently defaulted.
    """
    reviews: list[dict[str, Any]] = []
    for family, _name, codes, scope, _cap in _FAMILIES:
        if scope != "course":
            continue
        members = [line for line in lines if line.procedure_code.strip() in codes]
        by_code: dict[str, list[int]] = defaultdict(list)
        for index, line in enumerate(members):
            by_code[line.procedure_code.strip()].append(index)
        exclusive = set(codes)
        once = set(codes)
        if family == "external_rt_dose":
            exclusive = {"800180", "800190", "800200"}
            once = exclusive | {"800170"}
        elif family == "brachytherapy_dose":
            # C3669 excludes b/c/d together, but limits each a/b/c/d once;
            # basic 800235 is independent, not unlimited within a course.
            exclusive = {"800240", "800250", "800260"}
        elif family == "special_devices":
            exclusive = set()
        elif family == "rt_planning":
            # C3655 first excludes a/b/c/d/e together. Its next sentence
            # permits justified repeats of d/e up to three, not a cap of one.
            once = {"800120", "800130", "800140"}

        selected: set[int] = set()
        missing = {"treatment_course_id", "payable_procedure_code"}
        basis = "course_quantity"
        details: list[str] = []
        alternatives = exclusive.intersection(by_code)
        if len(alternatives) > 1:
            selected.update(index for code in alternatives for index in by_code[code])
            basis = "course_alternatives"
            details.append("These billed alternatives cannot coexist within one treatment course.")

        for code, indexes in by_code.items():
            quantity = sum(members[index].quantity for index in indexes)
            if quantity <= 1:
                continue
            if code in once:
                selected.update(indexes)
                details.append(f"{code} has an individual treatment-course quantity restriction.")
                if code in {"800290", "800300"}:
                    missing.add("device_material_identity")
                    basis = "device_material_identity"
                if code == "800270":
                    missing.add("treatment_indication")
            elif code in {"800150", "800160"}:
                selected.update(indexes)
                missing.add("planning_justification")
                if len(alternatives) <= 1:
                    basis = "planning_justification"
                details.append(
                    "Advanced planning permits up to three with documented justification."
                )
            elif code in {"800210", "800220"}:
                selected.update(indexes)
                missing.add("planning_count")
                if len(alternatives) <= 1:
                    basis = "planning_count"
                details.append("This dose-calculation quantity is linked to the planning count.")

        if selected:
            section, locator = _COURSE_SOURCES[family]
            reviews.extend(
                _review_rows(
                    claim,
                    [members[index] for index in sorted(selected)],
                    rule_kind="course_cap",
                    section=section,
                    locator=locator,
                    basis=basis,
                    missing=missing,
                    detail=" ".join(sorted(set(details)))
                    + " Claim identity does not establish course identity.",
                )
            )

    # Each special application has its own course restriction, even on
    # different days. Neither is represented by the daily-rule identity.
    for code, section, locator in (
        ("800370", "8.1.5.A", "EK-2B!C3688"),
        ("800430", "8.1.5.B", "EK-2B!C3695"),
    ):
        special = [line for line in lines if line.procedure_code.strip() == code]
        if sum(line.quantity for line in special) > 1:
            reviews.extend(
                _review_rows(
                    claim,
                    special,
                    rule_kind="course_cap",
                    section=section,
                    locator=locator,
                    basis="course_quantity",
                    missing={"treatment_course_id", "payable_procedure_code"},
                    detail=f"{code} permits one per treatment course; claim identity does not establish a course.",
                )
            )
    return reviews


def _detect_same_day_violations(
    claim: ClaimHeader,
    lines: list[ProcedureClaimLine],
) -> list[dict[str, Any]]:
    """Preserve daily/session review evidence without guessing application dates."""
    reviews: list[dict[str, Any]] = []
    groups = (
        ({"rt_application", "linac_application"}, "8.1.5", "EK-2B!C3682", False),
        ({"brachy_application"}, "8.1.5.D.1", "EK-2B!C3704", True),
        ({"afterloading"}, "8.1.5.D.2", "EK-2B!C3711", True),
    )
    for families, section, locator, needs_session in groups:
        by_date: dict[date | None, list[ProcedureClaimLine]] = defaultdict(list)
        for line in lines:
            family = _family_for_code(line.procedure_code)
            if family is not None and family[0] in families:
                day = line.procedure_date
                by_date[day if day and day != date.min else None].append(line)
        for day, members in by_date.items():
            if day is not None and sum(line.quantity for line in members) <= 1:
                continue
            missing = {"payable_procedure_code", "treatment_day_records"}
            basis = "application_daily_limit"
            detail = (
                "External radiotherapy applications share a daily limit across device families."
            )
            if day is None or any(line.quantity > 1 for line in members):
                missing.add("application_dates")
                basis = "application_date_allocation"
                detail = "Billed quantity does not establish the number of applications on one treatment day."
            if needs_session:
                missing.add("treatment_session_id")
                basis = "session_identity"
                detail = "These alternatives are restricted per session; a shared date does not establish a shared session."
            reviews.extend(
                _review_rows(
                    claim,
                    members,
                    rule_kind="same_day_collapse",
                    section=section,
                    locator=locator,
                    basis=basis,
                    missing=missing,
                    detail=detail,
                    service_date=day,
                )
            )
    return reviews


def _review_rows(
    claim: ClaimHeader,
    lines: list[ProcedureClaimLine],
    *,
    rule_kind: str,
    section: str,
    locator: str,
    basis: str,
    missing: set[str],
    detail: str,
    service_date: date | None = None,
) -> list[dict[str, Any]]:
    """Retain every participant, without selecting or pricing a denied charge."""
    records = []
    for line in lines:
        family = _family_for_code(line.procedure_code)
        assert family is not None
        family_key, family_name, _scope, _cap = family
        records.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim.claim_id,
                "patient_id": claim.patient_id,
                "episode_id": getattr(claim, "episode_id", "") or "",
                "procedure_line_id": getattr(line, "procedure_line_id", "") or "",
                "procedure_code": line.procedure_code,
                "procedure_name": getattr(line, "procedure_name", "") or "",
                "family_key": family_key,
                "family_name": family_name,
                "rule_kind": rule_kind,
                "rule_id": f"radiation_oncology.{rule_kind}.{family_key}",
                "rule_set_id": _RULE_SET_ID,
                "sut_section": f"EK-2/B {section}",
                "source_type": "sut_annex",
                "source_ref": {
                    "annex": "EK-2/B",
                    "section": section,
                    "locator": locator,
                    "document": _SOURCE_DOCUMENT,
                    "url": _SOURCE_URL,
                },
                "scenario_tag": getattr(claim, "scenario_tag", "") or "",
                "billed_quantity": line.quantity,
                "procedure_date": (
                    line.procedure_date.isoformat()
                    if line.procedure_date and line.procedure_date != date.min
                    else None
                ),
                "billed_amount_try": _money(_line_billed(line)),
                "risk_amount_try": None,
                "severity": "info",
                "candidate_classification": "review_only",
                "evaluation_status": "unavailable",
                "missing_inputs": sorted(missing),
                "review_basis": basis,
                "service_date": service_date.isoformat() if service_date else None,
                "related_procedure_line_ids": sorted(member.procedure_line_id for member in lines),
                "detail": (
                    f"EK-2/B {section}: {detail} "
                    "Review supporting records; payable entitlement and excess amount are unconfirmed. "
                    "El Kitabı Tablo 30 is an illustrative billing example."
                ),
                "included_in_sgk_total": False,
            }
        )
    return records


def detect_radiation_oncology_violations(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
) -> list[dict[str, Any]]:
    """Return source-backed review candidates via the legacy detector signature.

    Positive charges/quantities only; no credit allocation, treatment-course
    inference, cross-claim completeness, or exact financial excess is asserted.
    """
    if not claims or not procedure_lines:
        return []

    # Early-exit: if no line is a radiation code, nothing to do.
    if not any(_is_radiation_code(getattr(l, "procedure_code", "")) for l in procedure_lines):
        return []

    lines_by_claim = _group_lines_by_claim(procedure_lines)
    violations: list[dict[str, Any]] = []

    for claim in claims:
        claim_lines = lines_by_claim.get(claim.claim_id)
        if not claim_lines:
            continue
        # Restrict to radiation lines on this claim.
        rad_lines = [
            line
            for line in claim_lines
            if _is_radiation_code(line.procedure_code)
            and line.quantity > 0
            and _line_billed(line) > 0
        ]
        if not rad_lines:
            continue

        violations.extend(_detect_course_cap_violations(claim, rad_lines))
        violations.extend(_detect_same_day_violations(claim, rad_lines))

    return sorted(
        violations,
        key=lambda row: (
            row["claim_id"],
            row["rule_id"],
            row["procedure_line_id"],
        ),
    )

"""SUT §2.4.4.C / El Kitabı Tablo 30 — Radiation oncology (800xxx) billing rules.

Radiation oncology is **NOT** a single EK-2/C package. It is a bundle of
mutually-exclusive, course-capped EK-2/B line items in the 800xxx series.
This detector enforces the three rule families described in El Kitabı
Tablo 30 (Radyasyon Onkoloji Faturalandırması):

1. **Mutual exclusion within families** — Radiation therapy codes come in
   families (e.g. external-RT design 800070–800110). Only ONE code from
   each family may be billed per course of treatment.

2. **Course cap** — Certain codes are billable at most once per treatment
   course (the design / planning / dose-calculation / special-service
   families). We enforce this as: across the whole claim, the family may
   not appear more than ``course_cap`` times in total.

3. **Same-day collapse** — For the application families (treatment
   fractions), only one code may be billed per day; multiple fractions on
   the same day must collapse to a single bill.

Families are defined from the catalog names below (grouped by code prefix
and shared name stem). Codes outside the 800xxx series and outside any
defined family are ignored.

The detector takes ``claims`` and ``procedure_lines`` (the same shape the
other prose-rule detectors consume), groups 800xxx lines by claim and by
date, and emits one violation dict per offending family. The violation
dict mirrors the structure used by ``drg_unbundling`` (procedure_line_id,
procedure_code, procedure_name, rule_id, sut_section, detail, …).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import TYPE_CHECKING, Any

from src.bilun.domain.money import money_round_half_up as _money

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_OPPORTUNITY_TYPE = "radiation_oncology"
_SUT_SECTION = "2.4.4.C"
_RULE_SET_ID = "radiation_oncology"

# ---------------------------------------------------------------------------
# Radiation oncology code families.
#
# Each family is a tuple of (family_key, human-readable name, member codes,
# scope). ``scope`` is one of:
#   - "course":  mutual-exclusion + at-most-N-times-per-course (design /
#                planning / dose-calc / special-service families — these
#                are once-per-course).
#   - "same_day": only one code per family per service date (the RT
#                application families — multiple fractions same day
#                collapse to one bill).
#
# Families are derived directly from the SUT catalog names:
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

_FAMILY_EXTERNAL_DESIGN = ("external_rt_design", "External RT design (tasarım)",
                           ("800070", "800080", "800090", "800100", "800110"), "course", 1)
_FAMILY_BRACHY_DESIGN = ("brachytherapy_design", "Brachytherapy design (tasarım)",
                         ("800111", "800112", "800113", "800114"), "course", 1)
_FAMILY_PLANNING = ("rt_planning", "RT planning/simulation (planlama)",
                    ("800120", "800130", "800140", "800150", "800160"), "course", 1)
_FAMILY_EXTERNAL_DOSE = ("external_rt_dose", "External RT dose calculation (doz hesabı)",
                         ("800170", "800180", "800190", "800200", "800210", "800220", "800230"),
                         "course", 1)
_FAMILY_BRACHY_DOSE = ("brachytherapy_dose", "Brachytherapy dose calculation (doz hesabı)",
                       ("800235", "800240", "800250", "800260"), "course", 1)
_FAMILY_SPECIAL_DEVICES = ("special_devices", "Special services & auxiliary devices (özel hizmetler)",
                           ("800270", "800280", "800290", "800300"), "course", 1)
_FAMILY_RT_APPLICATION = ("rt_application", "Conventional RT application (eksternal uygulama)",
                          ("800330", "800340", "800350", "800360", "800370"), "same_day", None)
_FAMILY_LINAC_APPLICATION = ("linac_application", "Linac RT application (lineer akseleratör uygulama)",
                             ("800380", "800390", "800400", "800410", "800420", "800430", "800440"),
                             "same_day", None)
_FAMILY_HYPERTHERMIA = ("hyperthermia", "Hyperthermia (hipertermi)",
                        ("800450", "800460", "800470", "800480", "800490"), "same_day", None)
_FAMILY_BRACHY_APPLICATION = ("brachy_application",
                              "Intracavitary/interstitial brachytherapy application",
                              ("800500", "800510", "800520", "800530", "800540", "800550"),
                              "same_day", None)
_FAMILY_AFTERLOADING = ("afterloading", "After-loading brachytherapy application",
                        ("800560", "800570", "800580", "800590"), "same_day", None)

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


def _detect_course_cap_violations(
    claim: ClaimHeader,
    lines: list[ProcedureClaimLine],
) -> list[dict[str, Any]]:
    """Enforce at-most-N-per-course for course-scoped families.

    For each course-scoped family, if more than ``course_cap`` lines (by
    total quantity billed) from that family appear on the claim, emit one
    violation per line beyond the cap.
    """
    violations: list[dict[str, Any]] = []

    # family_key -> ordered list of (line, qty)
    by_family: dict[str, list[tuple[ProcedureClaimLine, int]]] = defaultdict(list)
    for line in lines:
        fam = _family_for_code(line.procedure_code)
        if fam is None:
            continue
        fkey, _fname, scope, _cap = fam
        if scope != "course":
            continue
        qty = int(getattr(line, "quantity", 1) or 1)
        by_family[fkey].append((line, qty))

    for fkey, members in by_family.items():
        cap = next(c for fk, _n, _codes, _s, c in _FAMILIES if fk == fkey)
        # Sort by line id for stable output, keep insertion order otherwise.
        total_qty = sum(q for _l, q in members)
        if total_qty <= cap:
            continue
        # Emit one violation per line in the family (each line participates
        # in the over-cap billing). The detail explains the rule.
        for line, _qty in members:
            _fname = next(n for fk, n, _codes, _s, _c in _FAMILIES if fk == fkey)
            violations.append(
                _build_violation(
                    claim=claim,
                    line=line,
                    family_key=fkey,
                    family_name=_fname,
                    rule_kind="course_cap",
                    detail=(
                        f"Radiation family '{_fname}' is capped at {cap} billing(s) "
                        f"per treatment course; {total_qty} billed on this claim. "
                        f"SUT §{_SUT_SECTION} / El Kitabı Tablo 30: only one code "
                        f"per family per course."
                    ),
                )
            )
    return violations


def _detect_same_day_violations(
    claim: ClaimHeader,
    lines: list[ProcedureClaimLine],
) -> list[dict[str, Any]]:
    """Enforce one-code-per-family-per-day for same_day-scoped families.

    For each service date, for each same-day family, if two or more lines
    from the family fall on the same date, emit a violation for each
    offending line after the first (the "collapsed" fraction).
    """
    violations: list[dict[str, Any]] = []

    # date -> family_key -> ordered list of lines
    by_date_family: dict[date, dict[str, list[ProcedureClaimLine]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for line in lines:
        fam = _family_for_code(line.procedure_code)
        if fam is None:
            continue
        _fkey, _fname, scope, _cap = fam
        if scope != "same_day":
            continue
        svc_date = getattr(line, "procedure_date", None)
        if svc_date is None or svc_date == date.min:
            # Undated lines cannot be same-day-grouped; skip (do not merge
            # unrelated undated lines — mirrors group_procedure_lines_by_session).
            continue
        by_date_family[svc_date][_fkey].append(line)

    for svc_date, fam_map in by_date_family.items():
        for fkey, fam_lines in fam_map.items():
            if len(fam_lines) < 2:
                continue
            _fname = next(n for fk, n, _codes, _s, _c in _FAMILIES if fk == fkey)
            for line in fam_lines:
                violations.append(
                    _build_violation(
                        claim=claim,
                        line=line,
                        family_key=fkey,
                        family_name=_fname,
                        rule_kind="same_day_collapse",
                        detail=(
                            f"Multiple codes from radiation family '{_fname}' billed "
                            f"on the same day ({svc_date.isoformat()}); only one "
                            f"application code per family per day is billable. "
                            f"SUT §{_SUT_SECTION} / El Kitabı Tablo 30: same-day "
                            f"fractions collapse to a single bill."
                        ),
                        extra={"service_date": svc_date.isoformat()},
                    )
                )
    return violations


def _build_violation(
    *,
    claim: ClaimHeader,
    line: ProcedureClaimLine,
    family_key: str,
    family_name: str,
    rule_kind: str,
    detail: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a violation dict in the standard prose-rule structure."""
    record: dict[str, Any] = {
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
        "sut_section": _SUT_SECTION,
        "scenario_tag": getattr(claim, "scenario_tag", "") or "",
        "billed_amount_try": _money(_line_billed(line)),
        "risk_amount_try": _money(_line_billed(line)),
        "detail": detail,
        "included_in_sgk_total": False,
    }
    if extra:
        record.update(extra)
    return record


def detect_radiation_oncology_violations(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
) -> list[dict[str, Any]]:
    """Detect radiation oncology (800xxx) mutual-exclusion / cap violations.

    Enforces, per claim:
      * **Mutual exclusion + course cap** — only one code from each
        course-scoped family (design / planning / dose-calc / special
        devices) may be billed per treatment course.
      * **Same-day collapse** — only one code from each application family
        may be billed per service date.

    Args:
        claims: ClaimHeaders to evaluate.
        procedure_lines: ProcedureClaimLine rows (any patient; filtered by
            claim_id).

    Returns:
        Violation dicts mirroring the prose-rule structure: type, claim_id,
        patient_id, procedure_line_id, procedure_code, family_key,
        family_name, rule_kind, rule_id, sut_section, detail,
        billed_amount_try, risk_amount_try, … One dict per offending line.
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
            line for line in claim_lines if _is_radiation_code(line.procedure_code)
        ]
        if not rad_lines:
            continue

        violations.extend(_detect_course_cap_violations(claim, rad_lines))
        violations.extend(_detect_same_day_violations(claim, rad_lines))

    return violations

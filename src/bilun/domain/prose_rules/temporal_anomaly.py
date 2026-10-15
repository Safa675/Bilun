"""Temporal-anomaly detectors (Workstream C — diagnosis-coding plan).

Two heuristics flag billing patterns that are physically or clinically
implausible and therefore almost always signal a coding / documentation
defect:

- **#8** Generic procedure time-overlap — two surgical-category procedures
  on the *same claim*, *same service date*, *same specialty* cannot both
  have been performed by one team in one room. Flagged as a review warning.
- **#9** LOS vs procedure density — too many procedures per inpatient day
  (ratio > 5) or a multi-day inpatient stay with zero billable procedures
  (ghost stay) are both temporal anomalies.

Each detector takes plain ``ClaimHeader`` / ``ProcedureClaimLine`` lists
plus an optional ``claim_ids_with_procs`` filter set (matching the wiring
gate used by the other prose-rule motors). Each emits violation dicts with
the uniform shape used across :mod:`common_billing_errors`:
``type``, ``claim_id``, ``rule_id``, ``detail`` (Turkish),
``sut_section_id``, ``savings_category``, ``savings_basis``, ``severity``.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from src.bilun.domain.prose_rules.claim_utils import (
    group_procedure_lines_by_session,
)
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_SGK_UPLIFT,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

# Temporal-anomaly detectors emit under their own opportunity type so the
# engine can route them separately from the Tablo-15 common-billing family.
_OPPORTUNITY_TYPE = "temporal_anomaly"
_SUT_SECTION_ID = "2.4"

# Error #8 — procedure_category keywords signalling an operative / surgical
# service. Two of these on the same date + same claim + same specialty
# cannot physically have been performed concurrently by the same team.
_SURGICAL_CATEGORY_KEYWORDS: tuple[str, ...] = (
    "cerrahi",
    "surgery",
    "operative",
    "ameliyat",
    "cerrahi_dis",
    "surgical",
)

# Error #8 — SUT procedure-code prefix range that is surgical (the 600xxx-
# 629xxx block in EK-2B and P600xxx-P629xxx in EK-2C). Used as a fallback
# when the category string does not carry a surgical keyword.
_SURGICAL_CODE_PREFIXES: tuple[str, ...] = ("60", "61", "62")
# EK-2B 51xxxx codes (510010–510121) are inpatient bed/stay tariffs, never
# surgical procedures even if a line's category was miscoded.
_BED_CODE_PREFIXES: tuple[str, ...] = ("51",)

# Error #9 — procedure_count / LOS_days threshold above which the billing
# pattern is implausible (too many concurrent procedures per inpatient day).
_PROCEDURE_DENSITY_RATIO_MAX = 5

# Error #9 — ghost-stay: an inpatient stay this long or longer with zero
# billable procedures is almost certainly a capture/documentation defect.
_GHOST_STAY_MIN_LOS_DAYS = 3


def _normalize_surgical_code(raw: str | None) -> str:
    code = (
        str(raw or "")
        .strip()
        .replace(".", "")
        .replace(" ", "")
        .replace("-", "")
        .upper()
    )
    if code.startswith("P") and len(code) > 1 and code[1:].isdigit():
        return code[1:]
    return code


def _is_surgical(line: ProcedureClaimLine) -> bool:
    """True when a procedure line is an operative / surgical service.

    Excludes EK-2B ``51xxxx`` bed/stay tariffs unconditionally, then checks
    whether ``procedure_category`` carries a surgical keyword
    (``cerrahi``/``surgery``/``operative``/``ameliyat``), falling back to
    the SUT ``600xxx``–``629xxx`` (and ``P600xxx``–``P629xxx``) surgical
    code-prefix range when the category is blank or non-descriptive.
    """
    code = _normalize_surgical_code(line.procedure_code)
    if code[:2] in _BED_CODE_PREFIXES:
        return False
    category = (line.procedure_category or "").casefold()
    if any(kw in category for kw in _SURGICAL_CATEGORY_KEYWORDS):
        return True
    return code[:2] in _SURGICAL_CODE_PREFIXES


def detect_procedure_time_overlap(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """#8: Two surgical procedures on the same claim, same date, same specialty.

    Two operative procedures performed by the *same specialty* on the
    *same service date* on the *same claim* cannot both have been carried
    out concurrently — one team / one room / one anaesthetic cannot service
    two surgeries at once. The pair is flagged for review (conservative:
    only same date + both surgical + same specialty counts).

    Date grouping uses :func:`group_procedure_lines_by_session`
    (the §2.2.2.B session helper), which isolates undated sentinel lines
    into their own sessions so unrelated procedures are not falsely paired.

    Honest skips: claim filtered out by ``claim_ids_with_procs``, fewer
    than two surgical procedures on a date, or no ``procedure_specialty_code``
    (cannot determine same-specialty without it).
    """
    # Group procedure lines by claim, then by service-date session.
    by_claim: dict[str, list[ProcedureClaimLine]] = defaultdict(list)
    for line in procedure_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        by_claim[line.claim_id].append(line)

    violations: list[dict[str, Any]] = []
    for claim in claims:
        lines = by_claim.get(claim.claim_id)
        if not lines:
            continue
        # group_procedure_lines_by_session keys sessions by service date.
        sessions = group_procedure_lines_by_session(lines)
        for session_date, session_lines in sessions.items():
            # Only surgical lines can physically overlap.
            surgical = [ln for ln in session_lines if _is_surgical(ln)]
            if len(surgical) < 2:
                continue
            # Same-specialty check — a line without a specialty code cannot
            # be safely paired, so it is excluded from the comparison.
            by_specialty: dict[str, list[ProcedureClaimLine]] = defaultdict(list)
            for ln in surgical:
                if ln.procedure_specialty_code:
                    by_specialty[ln.procedure_specialty_code].append(ln)
            for specialty, spec_lines in by_specialty.items():
                if len(spec_lines) < 2:
                    continue
                detail = (
                    f"Takip {claim.claim_id}: aynı branşta ({specialty}) iki cerrahi "
                    f"işlem {session_date} tarihinde aynı anda faturalandırılmış — "
                    f"aynı ekip/oda aynı anda iki ameliyatı aynı günde yapamaz "
                    f"(zaman çakışması, SUT §{_SUT_SECTION_ID})."
                )
                violations.append(
                    {
                        "type": _OPPORTUNITY_TYPE,
                        "claim_id": claim.claim_id,
                        "rule_id": "procedure_time_overlap",
                        "detail": detail,
                        "sut_section_id": _SUT_SECTION_ID,
                        "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                        "savings_basis": SAVINGS_BASIS_SOURCED,
                        "severity": "warning",
                        "procedure_date": session_date,
                        "procedure_specialty_code": specialty,
                        "procedure_codes": [ln.procedure_code for ln in spec_lines],
                        "procedure_line_ids": [
                            ln.procedure_line_id for ln in spec_lines
                        ],
                    }
                )
    return violations


def detect_los_procedure_density_anomaly(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """#9: LOS vs procedure-density anomaly (too many / zero procedures per day).

    Two sub-patterns, both review warnings:

    - **High density** — ``procedure_count / LOS_days > 5`` signals that the
      claim is over-loaded with procedures relative to the stay length
      (unbundling / upcoding嫌疑).
    - **Ghost stay** — an inpatient stay of ``> 3`` days with **zero**
      billable procedures is almost certainly a capture/documentation defect
      (the episode was billed as bed-days only).

    LOS is computed as ``(discharge_date - admission_date).days``.
    Outpatient claims (no ``admission_date`` or LOS <= 0) are skipped — the
    density rule is meaningful only for a real inpatient stay. One violation
    per claim (high-density takes precedence when both fire).

    Honest skips: claim filtered out by ``claim_ids_with_procs``, missing
    admission/discharge date, non-positive LOS, or LOS <= 0.
    """
    # Count procedure lines per claim (each line is one billed procedure).
    count_by_claim: dict[str, int] = defaultdict(int)
    for line in procedure_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        count_by_claim[line.claim_id] += 1

    violations: list[dict[str, Any]] = []
    for claim in claims:
        if claim_ids_with_procs is not None and claim.claim_id not in claim_ids_with_procs:
            continue
        if claim.admission_date is None or claim.discharge_date is None:
            continue
        los_days = (claim.discharge_date - claim.admission_date).days
        if los_days <= 0:
            continue
        proc_count = count_by_claim.get(claim.claim_id, 0)
        density = proc_count / los_days

        if density > _PROCEDURE_DENSITY_RATIO_MAX:
            detail = (
                f"Takip {claim.claim_id}: yatış süresi {los_days} gün için işlem "
                f"yoğunluğu çok yüksek ({proc_count} işlem, oran {density:.2f} > "
                f"{_PROCEDURE_DENSITY_RATIO_MAX}) — gün başına işlem sayısı "
                f"fiziksel olarak uygulanabilir değil (SUT §{_SUT_SECTION_ID})."
            )
            violations.append(
                {
                    "type": _OPPORTUNITY_TYPE,
                    "claim_id": claim.claim_id,
                    "rule_id": "los_procedure_density_anomaly",
                    "detail": detail,
                    "sut_section_id": _SUT_SECTION_ID,
                    "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                    "savings_basis": SAVINGS_BASIS_SOURCED,
                    "severity": "warning",
                    "anomaly_kind": "high_density",
                    "los_days": los_days,
                    "procedure_count": proc_count,
                    "density_ratio": round(density, 4),
                }
            )
            continue
        if proc_count == 0 and los_days > _GHOST_STAY_MIN_LOS_DAYS:
            detail = (
                f"Takip {claim.claim_id}: yatış süresi {los_days} gün ancak "
                f"hattında hiç faturalandırılabilir işlem yok — hayalet yatış "
                f"(sadece yatak günü faturalandırılmış, SUT §{_SUT_SECTION_ID})."
            )
            violations.append(
                {
                    "type": _OPPORTUNITY_TYPE,
                    "claim_id": claim.claim_id,
                    "rule_id": "los_procedure_density_anomaly",
                    "detail": detail,
                    "sut_section_id": _SUT_SECTION_ID,
                    "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                    "savings_basis": SAVINGS_BASIS_SOURCED,
                    "severity": "warning",
                    "anomaly_kind": "ghost_stay",
                    "los_days": los_days,
                    "procedure_count": proc_count,
                    "density_ratio": 0.0,
                }
            )
    return violations


def detect_procedure_time_overlap_for_context(ctx) -> list[dict[str, Any]]:
    """``PatientClaimContext`` adapter for :func:`detect_procedure_time_overlap`."""
    return detect_procedure_time_overlap(list(ctx.claims), list(ctx.procedure_lines))


def detect_los_procedure_density_anomaly_for_context(ctx) -> list[dict[str, Any]]:
    """``PatientClaimContext`` adapter for :func:`detect_los_procedure_density_anomaly`."""
    return detect_los_procedure_density_anomaly(
        list(ctx.claims), list(ctx.procedure_lines)
    )

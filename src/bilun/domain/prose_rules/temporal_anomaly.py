"""Temporal-anomaly detectors (Workstream C — diagnosis-coding plan).

Two heuristics for billing patterns that are physically or clinically
implausible and therefore almost always signal a coding / documentation
defect:

- **#8** Generic procedure time-overlap — honest skip. MEDULA procedure
  lines carry a service date but no start/end time, and two operations on
  the *same claim*, *same date*, *same branch* are the same-session case the
  SUT prices (§2.2.2.A(5), §2.2.2.B(3)), so a shared date is no overlap.
- **#9** LOS vs service density — too many services per inpatient night
  (ratio > 5) or a multi-night stay billed with daily bed/stay tariffs only
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

# Error #9 — the density ratio counts services, not every line (#263). EK-2B
# 51xxxx codes (510010 standard bed … 510121 companion) are daily bed/stay
# tariffs whose count tracks the stay length, and L-codes are laboratory-list
# tests billed one line per analyte; counting either pushed normal medical
# stays over the ratio. A stay billed with daily tariffs only is the ghost
# stay; a lab line still evidences care there.
_DAILY_TARIFF_CODE_PREFIXES: tuple[str, ...] = ("51",)
_LAB_CODE_PREFIXES: tuple[str, ...] = ("L",)

# Error #9 — procedure_count / LOS_days threshold above which the billing
# pattern is implausible (too many concurrent procedures per inpatient day).
_PROCEDURE_DENSITY_RATIO_MAX = 5

# Error #9 — ghost-stay: an inpatient stay longer than this (LOS > 3 nights)
# billed with daily tariffs only is almost certainly a capture/documentation
# defect.
_GHOST_STAY_MIN_LOS_DAYS = 3


def _normalize_code(raw: str | None) -> str:
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


def detect_procedure_time_overlap(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """#8: Procedure time-overlap — honest skip until lines carry times.

    An overlap needs a start/end time on both lines, and a MEDULA procedure
    line (``ProcedureClaimLine``) carries its service date only. Two
    operations on the same claim, date and branch are therefore one session
    with several operations, which the SUT prices at reduced rates rather
    than forbids (§2.2.2.A(5), §2.2.2.B(3)). Flagging a shared date warned
    on every legal multi-operation session (#263), so no violation is
    emitted; the signature stays for the engine wiring.
    """
    return []


def detect_los_procedure_density_anomaly(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """#9: LOS vs service-density anomaly (too many services / tariff-only stay).

    Two sub-patterns, both review warnings:

    - **High density** — ``service_count / LOS_days > 5`` signals that the
      claim is over-loaded with services relative to the stay length
      (suspected unbundling / upcoding). Daily bed/stay tariff lines
      (``51xxxx``) and laboratory L-code lines are not services here.
    - **Ghost stay** — an inpatient stay of ``> 3`` days billed with daily
      bed/stay tariff lines only (no service, no lab line) is almost
      certainly a capture/documentation defect.

    LOS is computed as ``(discharge_date - admission_date).days``.
    Outpatient claims (no ``admission_date`` or LOS <= 0) are skipped — the
    density rule is meaningful only for a real inpatient stay. One violation
    per claim (high-density takes precedence when both fire).

    Honest skips: claim filtered out by ``claim_ids_with_procs``, missing
    admission/discharge date, non-positive LOS, or LOS <= 0.
    """
    # Per claim: lines other than daily tariffs, and the services among them.
    non_tariff_by_claim: dict[str, int] = defaultdict(int)
    services_by_claim: dict[str, int] = defaultdict(int)
    for line in procedure_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        code = _normalize_code(line.procedure_code)
        if code.startswith(_DAILY_TARIFF_CODE_PREFIXES):
            continue
        non_tariff_by_claim[line.claim_id] += 1
        if not code.startswith(_LAB_CODE_PREFIXES):
            services_by_claim[line.claim_id] += 1

    violations: list[dict[str, Any]] = []
    for claim in claims:
        if claim_ids_with_procs is not None and claim.claim_id not in claim_ids_with_procs:
            continue
        if claim.admission_date is None or claim.discharge_date is None:
            continue
        los_days = (claim.discharge_date - claim.admission_date).days
        if los_days <= 0:
            continue
        proc_count = services_by_claim.get(claim.claim_id, 0)
        density = proc_count / los_days

        if density > _PROCEDURE_DENSITY_RATIO_MAX:
            detail = (
                f"Takip {claim.claim_id}: yatış süresi {los_days} gün için işlem "
                f"yoğunluğu çok yüksek ({proc_count} işlem; günlük yatak/refakat ve "
                f"laboratuvar satırları hariç, oran {density:.2f} > "
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
        tariff_only = non_tariff_by_claim.get(claim.claim_id, 0) == 0
        if tariff_only and los_days > _GHOST_STAY_MIN_LOS_DAYS:
            detail = (
                f"Takip {claim.claim_id}: yatış süresi {los_days} gün ancak "
                f"günlük yatak/refakat tarifesi dışında hiç işlem yok — hayalet "
                f"yatış (sadece yatak günü faturalandırılmış, SUT §{_SUT_SECTION_ID})."
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

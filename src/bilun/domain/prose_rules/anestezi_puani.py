"""SUT §2.2.2.A + EK-2/B §4 anesthesia (anestezi puanı) billing for inpatient claims.

Anesthesia is charged as a flat **group point** based on the surgical
procedure's point value (or total surgical point value when multiple surgeries
are performed in the same session). The mapping is a **point-range lookup** in
EK-2/B section "4. ANESTEZİ VE REANİMASYON" (in force from 2026-04-16):

    Surgical procedure puan >= 39001     → A1 group (550130 / multi 550200)
    Surgical procedure puan 18501-39000  → A2 group (550140 / multi 550210)
    Surgical procedure puan  9001-18500  → A3 group (550150 / multi 550220)
    Surgical procedure puan  6001-9000   → B  group (550160 / multi 550230)
    Surgical procedure puan  3005-6000   → C  group (550170 / multi 550240)
    Surgical procedure puan  1301-3004   → D  group (550180 / multi 550250)
    Surgical procedure puan     1-1300   → E  group (550190 / multi 550260)

Earlier service dates use the EK-2/B §4 point thresholds in force on that
date. Each table starts on the Yürürlük date of the amendment marker on its
rows in the raw EK-2/B lists (2018-02-15, 2022-08-04, 2024-08-07, 2026-04-16),
not on the date of the list that later consolidated it.

**Formula:** ``anestezi_charge_try = group_puan × katsayi``.
Already-billed surgical anesthesia lines (550130-550346) on the claim are
subtracted to compute ``recoverable_uplift_try``.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from src.bilun.domain.catalog import get_katsayi, lookup_procedure_code
from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules.claim_utils import infer_care_setting
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_SGK_UPLIFT,
)
from src.bilun.domain.prose_rules.session_scope import line_billed_as_package
from src.bilun.domain.prose_rules.yatak_puani import mandated_package_lines

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_OPPORTUNITY_TYPE = "anestezi_puani_group"
_SUT_SECTION_ID = "2.2.2.A"

# (min_puan, group_name, single_code, multi_code, fallback_single_puan, fallback_multi_puan)
_GroupBand = tuple[float, str, str, str, float, float]

# Değişik: RG-08/04/2026-33218/9-a md., Yürürlük 16/04/2026 (raw EK-2B list 2026-01-31).
_ANESTEZI_GROUPS_2026_04_16: tuple[_GroupBand, ...] = (
    (39001.0, "A1", "550130", "550200", 8942.14, 12338.02),
    (18501.0, "A2", "550140", "550210", 5589.58, 6706.36),
    (9001.0, "A3", "550150", "550220", 3353.79, 4024.47),
    (6001.0, "B", "550160", "550230", 1565.07, 1863.93),
    (3005.0, "C", "550170", "550240", 894.31, 1075.18),
    (1301.0, "D", "550180", "550250", 558.84, 670.68),
    (0.01, "E", "550190", "550260", 372.93, 447.12),
)

# Değişik: RG-05/08/2024-32623/10 md., Yürürlük 07/08/2024 (raw EK-2B list 2024-05-11).
_ANESTEZI_GROUPS_2024_08_07: tuple[_GroupBand, ...] = (
    (32561.0, "A1", "550130", "550200", 8942.14, 12338.02),
    (15401.0, "A2", "550140", "550210", 5589.58, 6706.36),
    (7584.0, "A3", "550150", "550220", 3353.79, 4024.47),
    (5001.0, "B", "550160", "550230", 1565.07, 1863.93),
    (2501.0, "C", "550170", "550240", 894.31, 1075.18),
    (943.0, "D", "550180", "550250", 558.84, 670.68),
    (0.01, "E", "550190", "550260", 372.93, 447.12),
)

# Değişik: RG-27/07/2022-31905/1-a md., Yürürlük 04/08/2022 (raw EK-2B list 2022-02-16).
_ANESTEZI_GROUPS_2022_08_04: tuple[_GroupBand, ...] = (
    (12001.0, "A1", "550130", "550200", 7451.79, 10281.69),
    (5201.0, "A2", "550140", "550210", 4657.99, 5588.64),
    (2351.0, "A3", "550150", "550220", 2794.83, 3353.73),
    (1451.0, "B", "550160", "550230", 1304.23, 1553.28),
    (751.0, "C", "550170", "550240", 745.26, 895.99),
    (301.0, "D", "550180", "550250", 465.70, 558.90),
    (0.01, "E", "550190", "550260", 310.78, 372.60),
)

# Değişik: RG-04/02/2018-30322/22-a md., Yürürlük 15/02/2018 (raw EK-2B list, date unknown).
_ANESTEZI_GROUPS_2018_02_15: tuple[_GroupBand, ...] = (
    (3000.0, "A1", "550130", "550200", 1594.57, 2200.12),
    (2000.0, "A2", "550140", "550210", 996.74, 1195.88),
    (900.0, "A3", "550150", "550220", 598.05, 717.65),
    (500.0, "B", "550160", "550230", 279.09, 332.38),
    (300.0, "C", "550170", "550240", 159.48, 191.73),
    (150.0, "D", "550180", "550250", 99.66, 119.60),
    (0.01, "E", "550190", "550260", 66.51, 79.73),
)

# Backwards-compatible module export for any external caller inspecting the
# current (2026-04-16) single-surgery table.
_ANESTEZI_GROUPS: list[tuple[float, float, str, str, float]] = [
    (39001.0, float("inf"), "A1", "550130", 8942.14),
    (18501.0, 39000.99, "A2", "550140", 5589.58),
    (9001.0, 18500.99, "A3", "550150", 3353.79),
    (6001.0, 9000.99, "B", "550160", 1565.07),
    (3005.0, 6000.99, "C", "550170", 894.31),
    (1301.0, 3004.99, "D", "550180", 558.84),
    (0.01, 1300.99, "E", "550190", 372.93),
]


def _normalize_code(raw_code: str) -> str:
    code = (
        str(raw_code or "")
        .strip()
        .replace(".", "")
        .replace(" ", "")
        .replace("-", "")
        .upper()
    )
    if code.startswith("P") and len(code) > 1 and code[1:].isdigit():
        code = code[1:]
    return code


def _is_surgical_code(raw_code: str) -> bool:
    """Return True only for EK-2B §6 surgical codes (600000–629999)."""
    code = _normalize_code(raw_code)
    if len(code) != 6 or not code.isdigit():
        return False
    return 600000 <= int(code) <= 629999


def _is_anestezi_group_code(raw_code: str) -> bool:
    """Return True for EK-2B §4 surgical anesthesia group codes (550130–550346)."""
    code = _normalize_code(raw_code)
    if len(code) != 6 or not code.isdigit():
        return False
    return 550130 <= int(code) <= 550346


def _group_table_for_date(visit_date: date | str | None) -> tuple[_GroupBand, ...]:
    if visit_date is None:
        return _ANESTEZI_GROUPS_2026_04_16
    as_of = visit_date.isoformat() if isinstance(visit_date, date) else str(visit_date)[:10]
    if as_of >= "2026-04-16":
        return _ANESTEZI_GROUPS_2026_04_16
    if as_of >= "2024-08-07":
        return _ANESTEZI_GROUPS_2024_08_07
    if as_of >= "2022-08-04":
        return _ANESTEZI_GROUPS_2022_08_04
    return _ANESTEZI_GROUPS_2018_02_15


def _resolve_anestezi_group(
    procedure_puan: float,
    *,
    visit_date: date | str | None = None,
    multiple_surgeries: bool = False,
) -> tuple[str, str, float] | None:
    """Given surgical puan, return ``(group_name, sut_code, fallback_anestezi_puan)``.

    Uses the EK-2/B §4 group table in force on ``visit_date`` (defaulting to the
    2026-04-16 table). When ``multiple_surgeries=True``, returns the increased
    multi-surgery anesthesia code (550200–550260) for the session's total
    surgical puan.
    """
    if procedure_puan <= 0:
        return None
    table = _group_table_for_date(visit_date)
    for (
        min_puan,
        group_name,
        single_code,
        multi_code,
        fallback_single,
        fallback_multi,
    ) in table:
        if procedure_puan >= min_puan:
            if multiple_surgeries:
                return group_name, multi_code, fallback_multi
            return group_name, single_code, fallback_single
    return None


def _surgical_puan(
    procedure_code: str, visit_date: date | str | None = None
) -> float | None:
    """Look up an EK-2B §6 surgical procedure's puan as of ``visit_date``.

    Returns ``None`` when ``procedure_code`` is not in EK-2B §6 (600000–629999),
    is not found in the catalog, or has no positive puan.
    """
    if not _is_surgical_code(procedure_code):
        return None
    result = lookup_procedure_code(procedure_code, visit_date=visit_date)
    entry = (result or {}).get("entry") or {}
    puan = entry.get("puan")
    if puan is None:
        return None
    try:
        val = float(puan)
    except (TypeError, ValueError):
        return None
    return val if val > 0 else None


def _anestezi_group_puan(
    anestezi_code: str,
    fallback_puan: float,
    visit_date: date | str | None = None,
) -> float:
    """Look up the anesthesia group code's EK-2B puan as of visit_date."""
    result = lookup_procedure_code(anestezi_code, visit_date=visit_date)
    entry = (result or {}).get("entry") or {}
    puan = entry.get("puan")
    if puan is None:
        return fallback_puan
    try:
        return float(puan)
    except (TypeError, ValueError):
        return fallback_puan


def detect_anestezi_puani_opportunities(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Detect expected anesthesia charges for inpatient surgical procedures.

    For each inpatient claim, groups non-package EK-2B §6 surgical procedure
    lines (600000–629999) by session date:
      - Single surgical procedure in session → 550130–550190 (A1–E) from that
        procedure's puan.
      - Multiple surgical procedures in session → one increased anesthesia row
        (550200–550260) from the session's total surgical puan.
      - Subtracts already-billed surgical anesthesia (550130–550346) on the
        claim from ``recoverable_uplift_try``.

    A line that must be billed as an EK-2/C package (§2.2.2(1)) on a bill
    sent hizmet başı counts as a package line: the package includes its
    anaesthesia (SUT §2.2.2.B-1(1)(g)).
    """
    claims_by_id: dict[str, ClaimHeader] = {c.claim_id: c for c in claims}
    lines_by_claim: dict[str, list[ProcedureClaimLine]] = {}
    for line in procedure_lines:
        lines_by_claim.setdefault(line.claim_id, []).append(line)
    mandated_by_claim: dict[str, list[ProcedureClaimLine]] = {}

    def _is_mandated_package_line(line: ProcedureClaimLine, claim: ClaimHeader) -> bool:
        if claim.claim_id not in mandated_by_claim:
            mandated_by_claim[claim.claim_id] = mandated_package_lines(
                claim, lines_by_claim.get(claim.claim_id, [])
            )
        return line in mandated_by_claim[claim.claim_id]

    # Sum already-billed anesthesia (550130-550346) per claim.
    remaining_billed_by_claim: dict[str, float] = {}
    for line in procedure_lines:
        if line_billed_as_package(line):
            continue
        if _is_anestezi_group_code(line.procedure_code):
            remaining_billed_by_claim[line.claim_id] = _money(
                remaining_billed_by_claim.get(line.claim_id, 0.0)
                + float(line.billed_amount_try or 0.0)
            )

    # Collect qualifying surgical lines grouped by (claim_id, session_date)
    # preserving encounter order.
    sessions: dict[tuple[str, date | None], list[tuple[ProcedureClaimLine, float]]] = {}
    for line in procedure_lines:
        claim = claims_by_id.get(line.claim_id)
        if claim is None:
            continue
        if infer_care_setting(claim) != "inpatient":
            continue
        if (
            claim_ids_with_procs is not None
            and line.claim_id not in claim_ids_with_procs
        ):
            continue
        if line_billed_as_package(line):
            continue

        visit_date = line.procedure_date or claim.admission_date or claim.claim_start_date
        procedure_puan = _surgical_puan(line.procedure_code, visit_date=visit_date)
        if procedure_puan is None:
            continue
        if _is_mandated_package_line(line, claim):
            continue

        session_key = (line.claim_id, visit_date)
        sessions.setdefault(session_key, []).append((line, procedure_puan))

    opportunities: list[dict[str, Any]] = []

    for (claim_id, visit_date), session_items in sessions.items():
        as_of_str = visit_date.isoformat() if isinstance(visit_date, date) else visit_date
        katsayi = get_katsayi(as_of=as_of_str)
        if katsayi <= 0:
            continue

        multiple_surgeries = len(session_items) > 1
        total_surgical_puan = round(sum(puan for _, puan in session_items), 2)
        primary_line, _ = max(session_items, key=lambda item: item[1])

        resolved = _resolve_anestezi_group(
            total_surgical_puan,
            visit_date=visit_date,
            multiple_surgeries=multiple_surgeries,
        )
        if resolved is None:
            continue
        group_name, anestezi_code, fallback_anestezi_puan = resolved
        anestezi_puan = _anestezi_group_puan(
            anestezi_code, fallback_anestezi_puan, visit_date=visit_date
        )

        expected = _money(anestezi_puan * katsayi)
        claim_billed = remaining_billed_by_claim.get(claim_id, 0.0)
        recoverable = _money(max(0.0, expected - claim_billed))
        remaining_billed_by_claim[claim_id] = _money(max(0.0, claim_billed - expected))

        if multiple_surgeries:
            codes_str = ", ".join(item.procedure_code for item, _ in session_items)
            detail = (
                f"Anestezi {group_name} grubu birden fazla ameliyat ({anestezi_code}): "
                f"surgical procedures [{codes_str}] (toplam puan {total_surgical_puan:.2f}) → "
                f"anestezi puan {anestezi_puan:.2f} × katsayı {katsayi:.3f} = {expected:.2f} TRY "
                f"(SUT §{_SUT_SECTION_ID}, EK-2/B §4)."
            )
        else:
            detail = (
                f"Anestezi {group_name} grubu ({anestezi_code}): surgical procedure "
                f"{primary_line.procedure_code} (puan {total_surgical_puan:.2f}) → anestezi puan "
                f"{anestezi_puan:.2f} × katsayı {katsayi:.3f} = {expected:.2f} TRY "
                f"(SUT §{_SUT_SECTION_ID}, EK-2/B §4)."
            )

        opportunities.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim_id,
                "procedure_code": primary_line.procedure_code,
                "procedure_puan": total_surgical_puan,
                "session_procedure_count": len(session_items),
                "anestezi_group": group_name,
                "anestezi_code": anestezi_code,
                "anestezi_puan": anestezi_puan,
                "katsayi": katsayi,
                "expected_try": expected,
                "actual_billed_try": claim_billed,
                "recoverable_uplift_try": recoverable,
                "included_in_sgk_total": recoverable > 0,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "sut_section_id": _SUT_SECTION_ID,
                "rule_id": "anestezi_puani_group_lookup",
                "detail": detail,
            }
        )

    return opportunities


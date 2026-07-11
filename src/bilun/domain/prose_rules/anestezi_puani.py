"""SUT §2.4.4.A anesthesia (anestezi puanı) billing for inpatient claims.

Anesthesia is charged as a flat **group point** based on the surgical
procedure's point value. The mapping is NOT per-procedure-code — it's a
**point-range lookup** (EK-2B section "5. ANESTEZİ VE REANİMASYON"):

    Surgical procedure puan 3000-5000 → A1 group (550130, puan=8942.14)
    Surgical procedure puan 2000-2999 → A2 group (550140, puan=5589.58)
    Surgical procedure puan 1000-1999 → A3 group (550150, puan=3353.79)
    Surgical procedure puan  500-999  → B  group (550160, puan=1565.07)
    Surgical procedure puan  250-499  → C  group (550170, puan=894.31)
    Surgical procedure puan  100-249  → D  group (550180, puan=558.84)
    Surgical procedure puan    1-99   → E  group (550190, puan=372.93)

The group ``puan`` values above are HARDCODED constants for Phase 1
(verified by reading the EK-2B parquet snapshot asof_2026-01-31). The
dynamic part is looking up the SURGICAL procedure's puan to determine
which anesthesia group applies.

**Formula:** ``anestezi_charge_try = group_puan × katsayi (0.593)``.

**Geriatrik/yenidoğan modifier (550270-550330):** For patients ≥75 years
old OR newborns (ASA 3-4), a higher group puan applies. Phase 1 SKIP —
the standard group puan is used only (see TODO in ``_resolve_anestezi_group``).

See plans/refactor/rule-encoding-gap-closure-roadmap.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.bilun.domain.catalog import get_katsayi, lookup_procedure_code
from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules.claim_utils import infer_care_setting
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_SGK_UPLIFT,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_OPPORTUNITY_TYPE = "anestezi_puani_group"
_SUT_SECTION_ID = "2.4.4.A"

# Hardcoded lookup table — surgical puan range → anesthesia group.
# (min_puan, max_puan, group_name, sut_code, anestezi_puan)
# The anestezi_puan values are the EK-2B group point values (verified
# from the asof_2026-01-31 snapshot). They are NOT looked up dynamically
# in Phase 1 — only the surgical procedure's puan is resolved dynamically.
_ANESTEZI_GROUPS: list[tuple[float, float, str, str, float]] = [
    (3000, 5000, "A1", "550130", 8942.14),
    (2000, 2999, "A2", "550140", 5589.58),
    (1000, 1999, "A3", "550150", 3353.79),
    (500, 999, "B", "550160", 1565.07),
    (250, 499, "C", "550170", 894.31),
    (100, 249, "D", "550180", 558.84),
    (1, 99, "E", "550190", 372.93),
]

# Upper bound of the standard anesthesia group table. Procedures with a
# puan above this threshold fall into the "birden fazla ameliyat"
# (550200-550260) bands which are out of Phase 1 scope — honest skip.
_TABLE_MAX_PUAN = 5000.0


def _resolve_anestezi_group(
    procedure_puan: float,
) -> tuple[str, str, float] | None:
    """Given a surgical procedure's puan, return ``(group_name, sut_code, anestezi_puan)``.

    Returns ``None`` when the puan falls outside the standard group table
    (puan < 1 or puan > 5000). Procedures above 5000 puan belong to the
    "birden fazla ameliyat" bands (550200-550260), not modelled in Phase 1.

    TODO(Phase 2): geriatrik/yenidoğan modifier (550270-550330) — patients
    ≥75 years old OR newborns (ASA 3-4) use a higher group puan. Requires
    patient age + ASA score inputs; not available in Phase 1.
    """
    for min_puan, max_puan, group_name, sut_code, anestezi_puan in _ANESTEZI_GROUPS:
        if min_puan <= procedure_puan <= max_puan:
            return group_name, sut_code, anestezi_puan
    return None


def _surgical_puan(procedure_code: str) -> float | None:
    """Look up a surgical procedure's puan via the EK-2B catalog.

    Returns ``None`` when the code is not found (non-surgical / unknown
    procedure) or has no puan.
    """
    result = lookup_procedure_code(procedure_code)
    entry = (result or {}).get("entry") or {}
    puan = entry.get("puan")
    if puan is None:
        return None
    try:
        return float(puan)
    except (TypeError, ValueError):
        return None


def detect_anestezi_puani_opportunities(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Detect expected anesthesia charges for inpatient surgical procedures.

    For each inpatient claim, walks its (non-package) procedure lines and,
    for each surgical procedure whose puan resolves to a standard anesthesia
    group, computes the anesthesia charge ``group_puan × katsayi``.

    Steps per procedure line:
      1. Claim must be inpatient (``infer_care_setting == "inpatient"``).
      2. Skip package-included lines (``procedure_category == "paket"``).
      3. Look up the procedure's puan via ``lookup_procedure_code``.
      4. Resolve the anesthesia group from the puan range.
      5. ``expected_try = group_puan × katsayi``.

    Skipped (honest, no opportunity emitted):
      - Outpatient claims.
      - Package-included procedure lines.
      - Procedures not in the catalog (puan lookup fails).
      - Procedures with puan > 5000 (beyond the standard table range;
        "birden fazla ameliyat" bands 550200-550260 are out of Phase 1 scope).

    Args:
        claims: ClaimHeaders to evaluate.
        procedure_lines: Procedure claim lines to evaluate against.
        claim_ids_with_procs: Optional filter — only emit opportunities for
            claims that also have procedure lines (matches the patient_report
            wiring gate ``if claim_context.procedure_lines``).

    Returns:
        Opportunity dicts with: type, claim_id, procedure_code, procedure_puan,
        anestezi_group, anestezi_code, anestezi_puan, expected_try,
        recoverable_uplift_try, sut_section_id, rule_id, detail.
    """
    katsayi = get_katsayi()
    if katsayi <= 0:
        return []

    claims_by_id: dict[str, ClaimHeader] = {c.claim_id: c for c in claims}

    opportunities: list[dict[str, Any]] = []

    for line in procedure_lines:
        claim = claims_by_id.get(line.claim_id)
        if claim is None:
            continue

        # Gate on inpatient.
        if infer_care_setting(claim) != "inpatient":
            continue

        # Gate on procedure lines present (if filter provided).
        if (
            claim_ids_with_procs is not None
            and line.claim_id not in claim_ids_with_procs
        ):
            continue

        # Skip package-included procedures — anesthesia for a paket procedure
        # is bundled into the package and not separately billable.
        if line.procedure_category == "paket":
            continue

        # Look up the surgical procedure's puan.
        procedure_puan = _surgical_puan(line.procedure_code)
        if procedure_puan is None:
            continue

        # Resolve the anesthesia group; skip when beyond the table range.
        resolved = _resolve_anestezi_group(procedure_puan)
        if resolved is None:
            continue
        group_name, anestezi_code, anestezi_puan = resolved

        expected = _money(anestezi_puan * katsayi)

        detail = (
            f"Anestezi {group_name} grubu ({anestezi_code}): surgical procedure "
            f"{line.procedure_code} (puan {procedure_puan:.2f}) → anestezi puan "
            f"{anestezi_puan:.2f} × katsayı {katsayi:.3f} = {expected:.2f} TRY "
            f"(§2.4.4.A)."
        )

        opportunities.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": line.claim_id,
                "procedure_code": line.procedure_code,
                "procedure_puan": procedure_puan,
                "anestezi_group": group_name,
                "anestezi_code": anestezi_code,
                "anestezi_puan": anestezi_puan,
                "katsayi": katsayi,
                "expected_try": expected,
                "recoverable_uplift_try": expected,
                "included_in_sgk_total": True,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "sut_section_id": _SUT_SECTION_ID,
                "rule_id": "anestezi_puani_group_lookup",
                "detail": detail,
            }
        )

    return opportunities

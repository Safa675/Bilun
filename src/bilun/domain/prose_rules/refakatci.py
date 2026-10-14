"""SUT §2.6.3 + §2.2.2.(5) companion bed (refakatçi) billing for inpatient claims.

Phase 1: 510121 Refakat (124.95 puan). Computes expected companion-bed
charge = companion days × puan × katsayı for inpatient claims that are
NOT day-case and NOT intensive-care.

Day counting: companion days = ``(discharge - admission).days`` — the
discharge day is excluded for the companion (the companion goes home on
discharge day, not billed as an extra day). Admission IN, discharge OUT.

Companion bed bundles ONLY yemek + yatak (NO vizit — the companion has
no medical visit). 510121 must NEVER be paid for günübirlik/day-case
stays (§2.2.2.(5)) and does NOT apply on ICU days (§2.6.3.(3)); on ICU
days a separate per-diem applies instead — Phase 1 suppresses 510121 and
notes the per-diem consideration.

See plans/refactor/rule-encoding-gap-closure-roadmap.md.
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

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_OPPORTUNITY_TYPE = "refakatci_companion_bed"
_REFAKATCI_CODE = "510121"
_REFAKATCI_PUAN = 124.95
# ICU indicator procedure codes — presence on a claim marks it as intensive
# care, where the companion bed (510121) is suppressed in favour of a
# separate per-diem (§2.6.3.(3)).
_ICU_PROCEDURE_CODES = frozenset({"510090", "P55200x"})


def _refakatci_puan(visit_date: date | str | None = None) -> float:
    """Look up the 510121 puan from the EK-2B catalog as of visit_date."""
    result = lookup_procedure_code(_REFAKATCI_CODE, visit_date=visit_date)
    entry = (result or {}).get("entry") or {}
    puan = entry.get("puan")
    if puan is None:
        # Fall back to the regulatory constant if the catalog is unavailable.
        return _REFAKATCI_PUAN
    return float(puan)


def _claim_is_icu(procedure_lines: list[ProcedureClaimLine]) -> bool:
    """True when any procedure line on the claim is an ICU indicator code."""
    codes = {
        line.procedure_code.strip().replace(".", "").replace(" ", "").replace("-", "")
        for line in procedure_lines
    }
    return any(code in _ICU_PROCEDURE_CODES for code in codes)


def detect_refakatci_opportunities(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine] = (),
) -> list[dict[str, Any]]:
    """Detect expected companion-bed (510121) charges for inpatient claims.

    For each inpatient claim with non-null admission + discharge dates:
      * Skip outpatient / day-case (<24h) stays with an informational note.
      * Skip ICU stays (510090 / P55200x) — companion per-diem applies
        instead (§2.6.3.(3)).
      * Otherwise compute companion days = ``(discharge - admission).days``
        and expected charge = days × 124.95 puan × katsayı.

    Args:
        claims: ClaimHeaders to evaluate.
        procedure_lines: Procedure claim lines used to detect ICU claims.
            Only lines belonging to a given claim are consulted for the ICU
            gate.

    Returns:
        Opportunity dicts with: type, claim_id, days, puan (124.95),
        expected_try, sut_section_id, rule_id, detail, suppression_notes.
    """
    # Group procedure lines by claim for the ICU gate.
    procedures_by_claim: dict[str, list[ProcedureClaimLine]] = {}
    for line in procedure_lines:
        procedures_by_claim.setdefault(line.claim_id, []).append(line)

    opportunities: list[dict[str, Any]] = []

    for claim in claims:
        # Gate on inpatient.
        if infer_care_setting(claim) != "inpatient":
            continue

        # Must have both dates.
        if claim.admission_date is None or claim.discharge_date is None:
            continue

        visit_date = claim.admission_date or claim.claim_start_date
        puan = _refakatci_puan(visit_date)
        if puan <= 0:
            continue

        as_of_str = visit_date.isoformat() if isinstance(visit_date, date) else visit_date
        katsayi = get_katsayi(as_of=as_of_str)
        if katsayi <= 0:
            continue

        daily_rate = _money(puan * katsayi)

        companion_days = (claim.discharge_date - claim.admission_date).days

        # Suppression rule 1 (§2.2.2.(5)): never paid for günübirlik /
        # day-case stays (<24h).
        if companion_days < 1:
            opportunities.append(
                {
                    "type": _OPPORTUNITY_TYPE,
                    "claim_id": claim.claim_id,
                    "days": 0,
                    "puan": puan,
                    "expected_try": 0.0,
                    "katsayi": katsayi,
                    "sut_section_id": "2.6.3",
                    "rule_id": "refakatci_510121",
                    "detail": (
                        f"Companion bed (510121) suppressed for same-day stay "
                        f"({claim.admission_date} → {claim.discharge_date}): "
                        f"günübirlik/day-case stays are not eligible for "
                        f"refakat per §2.2.2.(5)."
                    ),
                    "suppression_notes": [
                        "day_case_suppressed (§2.2.2.(5))",
                    ],
                    "included_in_sgk_total": False,
                    "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                    "savings_basis": SAVINGS_BASIS_SOURCED,
                }
            )
            continue

        # Suppression rule 2 (§2.6.3.(3)): ICU days → companion gets a
        # separate per-diem instead of 510121.
        claim_procs = procedures_by_claim.get(claim.claim_id, [])
        if _claim_is_icu(claim_procs):
            opportunities.append(
                {
                    "type": _OPPORTUNITY_TYPE,
                    "claim_id": claim.claim_id,
                    "days": companion_days,
                    "puan": puan,
                    "expected_try": 0.0,
                    "katsayi": katsayi,
                    "sut_section_id": "2.6.3",
                    "rule_id": "refakatci_510121",
                    "detail": (
                        f"Companion bed (510121) suppressed for ICU stay "
                        f"({companion_days} day(s), {claim.admission_date} → "
                        f"{claim.discharge_date}): on ICU days a separate "
                        f"companion per-diem applies instead of 510121 per "
                        f"§2.6.3.(3)."
                    ),
                    "suppression_notes": [
                        "icu_suppressed_per_diem_applies (§2.6.3.(3))",
                        "Verify medical indication/documentation (§2.6.3.(2)).",
                    ],
                    "included_in_sgk_total": False,
                    "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                    "savings_basis": SAVINGS_BASIS_SOURCED,
                }
            )
            continue

        expected = _money(companion_days * daily_rate)

        opportunities.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim.claim_id,
                "days": companion_days,
                "puan": puan,
                "expected_try": expected,
                "katsayi": katsayi,
                "sut_section_id": "2.6.3",
                "rule_id": "refakatci_510121",
                "detail": (
                    f"Refakat (510121): {companion_days} companion day(s) at "
                    f"{puan:.2f} puan × {katsayi:.3f} katsayı = "
                    f"{daily_rate:.2f} TRY/day → {expected:.2f} TRY "
                    f"(admission IN, discharge OUT)."
                ),
                "suppression_notes": [
                    "Verify companion actually stayed and is medically "
                    "indicated/documented (§2.6.3.(2)).",
                ],
                "included_in_sgk_total": True,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
            }
        )

    return opportunities

"""SUT §2.4.4.H intensive care (yoğun bakım) billing for inpatient claims.

Phase 1: base puan only (no EK-2C-1 ilave oran — that depends on facility
class and is tracked as a TODO below).

ICU uses a **dual-charging** model (verified from SUT §2.4.4.H + El Kitabı):

**A. Day-rate: 510090 "Yoğun bakım" (EK-2B, 1252.27 puan)**
- Used on the **FIRST and LAST ICU day** (hizmet başı ödeme yöntemi).
- First day = admission to ICU.
- Last day = death / discharge from ICU / transfer to another facility's ICU.
- Bundles monitoring, mechanical ventilation, nebulizer, oxygen therapy,
  deep tracheal suction — NOT separately billable on 510090 days.
- PACU (anesthesia recovery) is NEVER ICU (§2.4.4.H.(3)).

**B. Package: P552001-P552008 (EK-2C)**
- Used on **INTERMEDIATE days** ("ara günü") between first and last ICU day.
- P552001/P552006 = 1st basamak (3221.799 puan, adult/newborn)
- P552002/P552007 = 2nd basamak (6846.35 puan, adult/newborn)
- P552003/P552008 = 3rd basamak (12896.186 puan, adult/newborn)

**Day-counting (§2.4.4.H.(8)):**
- ICU days = ``(discharge - admission).days``.
- 1-day stay → first=last=same day → only 510090 once.
- 2-day stay → 510090 (first) + 510090 (last), no intermediate.
- 3+ day stay → 510090 (first) + P55200x × (days-2) intermediate + 510090 (last).

TODO(Phase 2): EK-2C-1 ilave oran — ICU packages P552001-008 attract a +60%
or +100% uplift depending on facility ICU class (1./2./3. basamak). The
uplift is applied to the intermediate package puan only (not 510090). This
requires the facility's ICU class, which is not modelled on ClaimHeader yet.

See plans/refactor/rule-encoding-gap-closure-roadmap.md + the approved
yatak-puani plan.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.bilun.domain.catalog import get_katsayi, lookup_procedure_code
from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules.catalog_membership import get_ek2c_entry
from src.bilun.domain.prose_rules.claim_utils import infer_care_setting
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_SGK_UPLIFT,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_OPPORTUNITY_TYPE = "icu_puani_yogun_bakim"
_DAY_RATE_CODE = "510090"  # Yoğun bakım (EK-2B, hizmet başı)
_SUT_SECTION_ID = "2.4.4.H"

# ICU indicator procedure codes — presence on a claim marks it as intensive
# care (matches refakatci._ICU_PROCEDURE_CODES convention).
_ICU_DAY_RATE_CODE = "510090"
_ICU_PACKAGE_PREFIXES = ("552001", "552002", "552003", "552006", "552007", "552008")

# Default intermediate package when a specific ICU basamak cannot be inferred
# from procedure lines. 3rd basamak adult (P552003) is the conservative
# (highest) default so we never under-state the recoverable amount.
_DEFAULT_INTERMEDIATE_CODE = "552003"


def _normalize_code(raw: str) -> str:
    return (
        str(raw or "")
        .strip()
        .replace(".", "")
        .replace(" ", "")
        .replace("-", "")
        .upper()
    )


def _is_icu_code(normalized: str) -> bool:
    """True for 510090 or any P55200x package code."""
    stripped = normalized[1:] if normalized.startswith("P") else normalized
    if stripped == _ICU_DAY_RATE_CODE:
        return True
    return stripped in _ICU_PACKAGE_PREFIXES


def _day_rate_puan() -> float:
    """Look up the 510090 puan (hizmet başı) from the EK-2B catalog."""
    result = lookup_procedure_code(_DAY_RATE_CODE)
    entry = (result or {}).get("entry") or {}
    puan = entry.get("puan")
    return float(puan) if puan is not None else 0.0


def _day_rate_price_try() -> float:
    """510090 price_try (already puan × katsayı)."""
    result = lookup_procedure_code(_DAY_RATE_CODE)
    entry = (result or {}).get("entry") or {}
    return float(entry.get("price_try") or 0.0)


def _intermediate_package_puan(package_code: str) -> float:
    """P55200x base puan from EK-2C (Phase 1: no ilave oran)."""
    entry = get_ek2c_entry(package_code)
    if entry is None:
        return 0.0
    puan = entry.get("puan")
    return float(puan) if puan is not None else 0.0


def _intermediate_package_price_try(package_code: str) -> float:
    """P55200x price_try (already puan × katsayı, base — no ilave oran)."""
    entry = get_ek2c_entry(package_code)
    if entry is None:
        return 0.0
    return float(entry.get("price_try") or 0.0)


def _claim_icu_package_code(
    procedure_lines: list[ProcedureClaimLine],
) -> str | None:
    """If the claim's procedure lines carry a P55200x code, return its code.

    This lets us pick the correct basamak (1./2./3.) and newborn vs adult
    variant from what the hospital actually submitted. Falls back to None
    when no package code is present (caller uses the default).
    """
    for line in procedure_lines:
        normalized = _normalize_code(line.procedure_code)
        stripped = normalized[1:] if normalized.startswith("P") else normalized
        if stripped in _ICU_PACKAGE_PREFIXES:
            return stripped
    return None


def _claim_has_icu_code(
    procedure_lines: list[ProcedureClaimLine],
) -> bool:
    """True when any procedure line on the claim is an ICU indicator code."""
    return any(
        _is_icu_code(_normalize_code(line.procedure_code))
        for line in procedure_lines
    )


def detect_icu_puani_opportunities(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine] | None = None,
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Detect expected ICU (yoğun bakım) charges for inpatient claims.

    For each inpatient claim with non-null admission + discharge dates AND at
    least one ICU indicator code (510090 / P55200x) on its procedure lines,
    computes the dual-charge expected total:

      - 510090 (first ICU day) + P55200x × (days-2) intermediate days
        + 510090 (last ICU day).

    Day counting: ICU days = ``(discharge - admission).days``. A 1-day stay
    is billed as a single 510090 (first=last). A 2-day stay is two 510090s
    with no intermediate.

    Args:
        claims: ClaimHeaders to evaluate.
        procedure_lines: Procedure claim lines used (a) to detect ICU
            presence and (b) to infer the submitted basamak package. When
            omitted, ICU presence cannot be confirmed and no opportunities
            are emitted.
        claim_ids_with_procs: Optional filter — only emit opportunities for
            claims that also have procedure lines (matches the
            patient_report wiring gate ``if claim_context.procedure_lines``).

    Returns:
        Opportunity dicts with: type, claim_id, icu_days, first_day_code,
        last_day_code, intermediate_package, intermediate_days, total_puan,
        total_try, recoverable_uplift_try, sut_section_id, rule_id, detail.
    """
    day_rate_puan = _day_rate_puan()
    if day_rate_puan <= 0:
        return []

    # Group procedure lines by claim for the ICU gate + basamak inference.
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

        claim_procs = procedures_by_claim.get(claim.claim_id, [])

        # Must have ICU codes present on the claim.
        if not _claim_has_icu_code(claim_procs):
            continue

        # Must have both dates.
        if claim.admission_date is None or claim.discharge_date is None:
            continue

        # ICU days = (discharge - admission).days — NOT inclusive (+0).
        # A same-day admission/discharge is a 0-day span; treat it as a
        # 1-day stay (single 510090) per §2.4.4.H.(8) first=last.
        raw_days = (claim.discharge_date - claim.admission_date).days
        icu_days = max(raw_days, 1)
        same_day = raw_days == 0

        # Intermediate (ara günü) days = days between first and last.
        # days=1 → 0 intermediate; days=2 → 0; days=3 → 1; days=n → n-2.
        intermediate_days = max(icu_days - 2, 0)

        # Pick the intermediate package basamak from submitted lines, else
        # fall back to the conservative default (3rd basamak adult).
        intermediate_code = (
            _claim_icu_package_code(claim_procs) or _DEFAULT_INTERMEDIATE_CODE
        )
        intermediate_puan = _intermediate_package_puan(intermediate_code)
        intermediate_price_try = _intermediate_package_price_try(intermediate_code)
        day_rate_price_try = _day_rate_price_try()

        # Puan totals: first 510090 + intermediate packages + last 510090.
        # For a 1-day stay first==last so only one 510090 is counted.
        first_last_count = 1 if icu_days == 1 else 2
        total_puan = _money(
            first_last_count * day_rate_puan
            + intermediate_days * intermediate_puan
        )
        total_try = _money(
            first_last_count * day_rate_price_try
            + intermediate_days * intermediate_price_try
        )

        # Build the human-readable charge breakdown.
        charge_lines = [
            f"510090 (yoğun bakım, hizmet başı): {first_last_count} day(s) × "
            f"{day_rate_puan:.2f} puan",
        ]
        if intermediate_days > 0 and intermediate_puan > 0:
            charge_lines.append(
                f"P{intermediate_code} (EK-2C ara günü): {intermediate_days} day(s) × "
                f"{intermediate_puan:.2f} puan"
            )
        charge_lines.append(
            f"= {total_puan:.2f} puan ({total_try:.2f} TRY), {icu_days} ICU day(s)."
        )
        detail = " ".join(
            [
                f"ICU dual-charge (§2.4.4.H):",
                *charge_lines,
                "Base puan only — EK-2C-1 ilave oran (+60%/+100%) pending "
                "facility ICU class (Phase 2 TODO).",
            ]
        )

        opportunities.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim.claim_id,
                "icu_days": icu_days,
                "same_day_stay": same_day,
                "first_day_code": _DAY_RATE_CODE,
                "last_day_code": _DAY_RATE_CODE,
                "intermediate_package": f"P{intermediate_code}",
                "intermediate_days": intermediate_days,
                "day_rate_puan": day_rate_puan,
                "intermediate_puan": intermediate_puan,
                "total_puan": total_puan,
                "total_try": total_try,
                "recoverable_uplift_try": total_try,
                "included_in_sgk_total": True,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "sut_section_id": _SUT_SECTION_ID,
                "rule_id": "icu_puani_510090_p55200x",
                "detail": detail,
            }
        )

    return opportunities

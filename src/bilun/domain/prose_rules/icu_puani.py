"""SUT §2.4.4.H intensive care (yoğun bakım) billing for inpatient claims.

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

**EK-2/C-1 ilave oran (Phase 2):** ICU packages P552001-008 attract a +100%
uplift (in-force as of 2026-01-31) when the procedure is performed by a
3rd-basamak (Sınıf-3) facility (SUT §2.2.(20): "3. basamak sağlık hizmeti
sunucularınca yapılması halinde"). The uplift is applied to the intermediate
package puan/price only — the 510090 day-rate (EK-2B hizmet başı) is not in
EK-2/C-1 and is never uplifted. The tier gate is resolved from the claim
header via ``normalize_facility_tier``; unresolved or non-3rd-basamak tiers
get no uplift (honest skip, not a default-apply). SUT 2.2.(20) (C000549) adds
the EK-2/C-1 rate to the procedure's points, so the rows of these packages are
no copay rate: the EK-2/C-1 copay-rate check does not read them
(``ICU_PACKAGE_CODES``).

See plans/billing/icu-ilave-oran-plan.md for the regulatory basis.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from src.bilun.domain.catalog import get_ek2c1_copay_rates, lookup_procedure_code
from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules.catalog_membership import get_ek2c_entry
from src.bilun.domain.prose_rules.claim_utils import (
    PackagePrefix,
    clean_procedure_code,
    infer_care_setting,
)
from src.bilun.domain.prose_rules.facility_tier import normalize_facility_tier
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_AUDIT_EXPOSURE,
    SAVINGS_CATEGORY_SGK_UPLIFT,
)
from src.bilun.domain.turkish_fold import TurkishFold, fold_turkish

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_OPPORTUNITY_TYPE = "icu_puani_yogun_bakim"
_TIER_OVERBILLING_TYPE = "icu_tier_overbilling"
_TIER_OVERBILLING_RULE_ID = "icu_tier_overbilling_2_4_4_H"
_DAY_RATE_CODE = "510090"  # Yoğun bakım (EK-2B, hizmet başı)
_SUT_SECTION_ID = "2.4.4.H"

# ICU indicator procedure codes — presence on a claim marks it as intensive
# care (matches refakatci._ICU_PROCEDURE_CODES convention).
_ICU_DAY_RATE_CODE = "510090"
_ICU_PACKAGE_PREFIXES = ("552001", "552002", "552003", "552006", "552007", "552008")
# The same codes as a set: the EK-2/C-1 copay-rate check (``optimization.catalog_join``) leaves their EK-2/C-1 rows to
# this motor, which reads the rate as the Sınıf-3 uplift (``_resolve_ilave_oran``), not as a copay rate.
ICU_PACKAGE_CODES = frozenset(_ICU_PACKAGE_PREFIXES)
_TIER_3_PACKAGE_CODES: dict[str, tuple[str, str]] = {
    "552003": ("552002", "552001"),  # Adult 3rd -> (2nd, 1st)
    "552008": ("552007", "552006"),  # Newborn 3rd -> (2nd, 1st)
}

# Separately billable procedure codes on EK-2/C ICU package days under
# SUT §2.4.4.H.(2) (C001234: EK-2/C A/B/C-group operations) and §2.4.4.H.(4)
# (C001236: continuous haemodiafiltration/haemofiltration, plasmapheresis,
# haemodialysis, therapeutic hypothermia). Included ICU care (mechanical
# ventilation 530130/530490, intubation 530800/550030/550110, CPR 550070) is
# not separately billable on package days, so its absence on the bill is never
# evidence of overbilling (#255).
_SEPARATELY_BILLABLE_EK2C_GROUPS: frozenset[str] = frozenset({"A1", "A2", "A3", "B", "C"})
_TIER_3_SUPPORT_PROCEDURE_CODES: frozenset[str] = frozenset(
    {
        "605960",  # Kardiyopulmoner by-pass cerrahi işlemi (EK-2/C A3)
        "605969",  # Sol ventriküle uzun süreli yardımcı cihaz ve sağ ventriküle ECMO (EK-2/C A2)
        "605975",  # Santral (Veno-arteriyel) VA-ECMO takılması veya çıkartılması (EK-2/C A3)
        "605976",  # Perkütan (Veno-arteriyel) VA-ECMO takılması veya çıkartılması (EK-2/C A3)
        "605977",  # Perkütan (Veno-venöz) VV-ECMO takılması veya çıkartılması (EK-2/C A3)
        "605978",  # Perkütan (Veno-arteriyel-venöz) VAV-ECMO takılması veya çıkartılması (EK-2/C A3)
        "605979",  # Arteriyal greft kullanılarak VA-ECMO takılması veya çıkartılması (EK-2/C A3)
        "704210",  # Acil hemodiyaliz (§2.4.4.H.(4))
        "704230",  # Hemodiyaliz (§2.4.4.H.(4))
        "704290",  # Sürekli hemodiafiltrasyon/hemofiltrasyon tedavisi (§2.4.4.H.(4))
        "704920",  # Aferez, Terapötik plazma değişimi (§2.4.4.H.(4))
    }
)

_TIER_3_SUPPORT_KEYWORDS: tuple[str, ...] = (
    "hemodiyaliz",
    "hemodiafiltrasyon",
    "hemofiltrasyon",
    "ecmo",
    "plazma degisimi",
    "plazmaferez",
    "terapotik hipotermi",
)


def _is_icu_code(normalized: str) -> bool:
    """True for 510090 or any P55200x package code."""
    stripped = clean_procedure_code(normalized, PackagePrefix.ALWAYS)
    if stripped == _ICU_DAY_RATE_CODE:
        return True
    return stripped in _ICU_PACKAGE_PREFIXES


def _is_day_rate_code(raw: str) -> bool:
    return clean_procedure_code(raw, PackagePrefix.ALWAYS) == _ICU_DAY_RATE_CODE


def _is_icu_package_code(raw: str) -> bool:
    return clean_procedure_code(raw, PackagePrefix.ALWAYS) in _ICU_PACKAGE_PREFIXES


def _day_rate_puan(visit_date: date | str | None = None) -> float:
    """Look up the 510090 puan (hizmet başı) from the EK-2B catalog as of visit_date."""
    result = lookup_procedure_code(_DAY_RATE_CODE, visit_date=visit_date)
    entry = (result or {}).get("entry") or {}
    puan = entry.get("puan")
    return float(puan) if puan is not None else 0.0


def _day_rate_price_try(visit_date: date | str | None = None) -> float:
    """510090 price_try (already puan × katsayı) as of visit_date."""
    result = lookup_procedure_code(_DAY_RATE_CODE, visit_date=visit_date)
    entry = (result or {}).get("entry") or {}
    return float(entry.get("price_try") or 0.0)


def _intermediate_package_puan(
    package_code: str, as_of_date: date | str | None = None
) -> float:
    """P55200x base puan from EK-2C (Phase 1: no ilave oran) as of as_of_date."""
    entry = get_ek2c_entry(package_code, as_of_date=as_of_date)
    if entry is None:
        return 0.0
    puan = entry.get("puan")
    return float(puan) if puan is not None else 0.0


def _intermediate_package_price_try(
    package_code: str, as_of_date: date | str | None = None
) -> float:
    """P55200x price_try (already puan × katsayı, base — no ilave oran) as of as_of_date."""
    entry = get_ek2c_entry(package_code, as_of_date=as_of_date)
    if entry is None:
        return 0.0
    return float(entry.get("price_try") or 0.0)


def _resolve_ilave_oran(
    claim: ClaimHeader, intermediate_code: str | None
) -> tuple[float, str]:
    """EK-2/C-1 ilave oran (%) for ICU intermediate days, gated on facility tier."""
    if not intermediate_code:
        return 0.0, "no_intermediate_package"
    tier = normalize_facility_tier(
        claim.facility_tier, provider_type=claim.provider_type
    )
    if not tier.resolved:
        return 0.0, "tier_unresolved"
    if not tier.is_third_tier:
        return 0.0, "not_sinif_3"
    row = get_ek2c1_copay_rates().get(f"P{intermediate_code}")
    if not row:
        return 0.0, "no_ek2c1_entry"
    oran = float(row.get("copay_rate_pct", 0.0))
    return oran, "sinif_3_uplift_applied"


def _claim_icu_package_code(
    procedure_lines: list[ProcedureClaimLine],
) -> str | None:
    """If the claim's procedure lines carry a P55200x code, return its code."""
    for line in procedure_lines:
        stripped = clean_procedure_code(line.procedure_code, PackagePrefix.ALWAYS)
        if stripped in _ICU_PACKAGE_PREFIXES:
            return stripped
    return None


def claim_has_icu_code(
    procedure_lines: list[ProcedureClaimLine],
) -> bool:
    """True when any procedure line on the claim is an ICU indicator code.

    The ICU motor's claim gate; the newborn bed motor uses the same test to
    leave a newborn ICU stay to this motor.
    """
    return any(_is_icu_code(line.procedure_code) for line in procedure_lines)


def _infer_billed_icu_days(
    claim_procs: list[ProcedureClaimLine],
    hospital_raw_days: int,
) -> tuple[int, int]:
    """Compute (icu_days, intermediate_days) from billed ICU procedure lines.

    Under SUT §2.4.4.H.(8), intermediate packages (P552001–P552008) are billed
    exclusively on days between the first ICU day (510090) and last ICU day
    (510090). Therefore:
      - When K >= 1 intermediate package units are billed, the ICU segment
        spans ``max(K + 2, D + K)`` days (bounded by the hospital stay), with
        ``intermediate_days = max(icu_days - 2, 0)``. A 14-day ward stay with
        a 3-day ICU segment (510090 + P552001 + 510090, D=2, K=1) yields 3 ICU
        days and 1 intermediate day rather than 14 ICU days.
      - When K == 0 (only 510090 is billed, no P55200x tier code), there are
        zero intermediate days (we never default to 3rd-level P552003). A
        same-day stay (hospital_raw_days == 0) is 1 ICU day; a 2-day stay
        without ward-bed (510010) lines or with D >= 2 is 2 ICU days; otherwise
        1 ICU day.
    """
    hospital_cap = max(hospital_raw_days, 1)
    day_rate_units = sum(
        max(int(getattr(p, "quantity", 1) or 1), 1)
        for p in claim_procs
        if _is_day_rate_code(p.procedure_code)
    )
    pkg_units = sum(
        max(int(getattr(p, "quantity", 1) or 1), 1)
        for p in claim_procs
        if _is_icu_package_code(p.procedure_code)
    )
    has_ward_bed = any(
        clean_procedure_code(p.procedure_code, PackagePrefix.ALWAYS) in ("510010", "510070", "510081")
        for p in claim_procs
    )

    if pkg_units > 0:
        icu_days = min(max(pkg_units + 2, day_rate_units + pkg_units), hospital_cap)
        intermediate_days = max(icu_days - 2, 0)
        return icu_days, intermediate_days

    if hospital_raw_days == 0:
        return 1, 0
    if day_rate_units >= 2 or (hospital_raw_days == 2 and not has_ward_bed):
        return min(2, hospital_cap), 0
    return 1, 0


def detect_icu_puani_opportunities(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine] | None = None,
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Detect expected ICU (yoğun bakım) charges for inpatient claims."""
    procedures_by_claim: dict[str, list[ProcedureClaimLine]] = {}
    if procedure_lines:
        for line in procedure_lines:
            procedures_by_claim.setdefault(line.claim_id, []).append(line)

    opportunities: list[dict[str, Any]] = []

    for claim in claims:
        if infer_care_setting(claim) != "inpatient":
            continue

        if claim_ids_with_procs is not None and claim.claim_id not in claim_ids_with_procs:
            continue

        claim_procs = procedures_by_claim.get(claim.claim_id, [])

        if not claim_has_icu_code(claim_procs):
            continue

        if claim.admission_date is None or claim.discharge_date is None:
            continue

        as_of_date = claim.admission_date or claim.claim_start_date
        day_rate_puan = _day_rate_puan(as_of_date)
        if day_rate_puan <= 0:
            continue

        raw_days = (claim.discharge_date - claim.admission_date).days
        same_day = raw_days == 0
        icu_days, intermediate_days = _infer_billed_icu_days(claim_procs, raw_days)

        # Pick the intermediate package basamak strictly from submitted lines;
        # never default to 3rd-basamak P552003 when no package code is present.
        intermediate_code = _claim_icu_package_code(claim_procs)
        if intermediate_code is not None:
            intermediate_puan_base = _intermediate_package_puan(
                intermediate_code, as_of_date
            )
            intermediate_price_try_base = _intermediate_package_price_try(
                intermediate_code, as_of_date
            )
        else:
            intermediate_days = 0
            intermediate_puan_base = 0.0
            intermediate_price_try_base = 0.0
        day_rate_price_try = _day_rate_price_try(as_of_date)

        ilave_oran_pct, ilave_oran_reason = _resolve_ilave_oran(
            claim, intermediate_code
        )
        ilave_oran_eligible = ilave_oran_pct > 0
        uplift_mult = 1 + ilave_oran_pct / 100
        intermediate_puan = intermediate_puan_base * uplift_mult
        intermediate_price_try = intermediate_price_try_base * uplift_mult

        first_last_count = 1 if icu_days == 1 else 2
        total_puan = _money(
            first_last_count * day_rate_puan
            + intermediate_days * intermediate_puan
        )
        total_try = _money(
            first_last_count * day_rate_price_try
            + intermediate_days * intermediate_price_try
        )

        actual_billed_try = _money(
            sum(
                float(p.billed_amount_try)
                for p in claim_procs
                if _is_icu_code(p.procedure_code)
            )
        )
        recoverable_try = _money(max(0.0, total_try - actual_billed_try))

        charge_lines = [
            f"510090 (yoğun bakım, hizmet başı): {first_last_count} day(s) × "
            f"{day_rate_puan:.2f} puan",
        ]
        if intermediate_days > 0 and intermediate_code and intermediate_puan_base > 0:
            charge_lines.append(
                f"P{intermediate_code} (EK-2C ara günü): {intermediate_days} day(s) × "
                f"{intermediate_puan_base:.2f} puan"
                + (f" × {uplift_mult:.2f}" if ilave_oran_eligible else "")
            )
        charge_lines.append(
            f"= {total_puan:.2f} puan ({total_try:.2f} TRY), {icu_days} ICU day(s)."
        )
        if ilave_oran_eligible:
            uplift_note = (
                f"EK-2/C-1 ilave oran +{ilave_oran_pct:.0f}% applied to "
                f"intermediate days (Sınıf-3 facility)."
            )
        else:
            uplift_note = f"No EK-2/C-1 ilave oran ({ilave_oran_reason})."
        detail = " ".join(
            [
                "ICU dual-charge (§2.4.4.H):",
                *charge_lines,
                uplift_note,
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
                "intermediate_package": (
                    f"P{intermediate_code}" if intermediate_code else None
                ),
                "intermediate_days": intermediate_days,
                "day_rate_puan": day_rate_puan,
                "intermediate_puan": intermediate_puan_base,
                "intermediate_puan_base": intermediate_puan_base,
                "intermediate_puan_uplifted": intermediate_puan,
                "ilave_oran_pct": ilave_oran_pct,
                "ilave_oran_eligible": ilave_oran_eligible,
                "ilave_oran_reason": ilave_oran_reason,
                "total_puan": total_puan,
                "total_try": total_try,
                "actual_billed_try": actual_billed_try,
                "recoverable_uplift_try": recoverable_try,
                "included_in_sgk_total": True,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "sut_section_id": _SUT_SECTION_ID,
                "rule_id": "icu_puani_510090_p55200x",
                "detail": detail,
            }
        )

    return opportunities


def _line_is_tier_3_support(
    line: ProcedureClaimLine,
    *,
    as_of_date: date | str | None = None,
) -> bool:
    """True when a line is a separately billable §2.4.4.H.(2)/(4) ICU support/A-B-C item."""
    code = clean_procedure_code(line.procedure_code, PackagePrefix.ALWAYS)
    if not code or code == _ICU_DAY_RATE_CODE or code.startswith(_ICU_PACKAGE_PREFIXES):
        return False
    if code in _TIER_3_SUPPORT_PROCEDURE_CODES:
        return True
    line_group = str(getattr(line, "ek2c_group", "") or "").strip().upper()
    if line_group in _SEPARATELY_BILLABLE_EK2C_GROUPS:
        return True
    entry = get_ek2c_entry(code, as_of_date=getattr(line, "procedure_date", None) or as_of_date)
    if entry and str(entry.get("group") or "").strip().upper() in _SEPARATELY_BILLABLE_EK2C_GROUPS:
        return True
    folded_name = fold_turkish(getattr(line, "procedure_name", "") or "", TurkishFold.ASCII)
    return any(kw in folded_name for kw in _TIER_3_SUPPORT_KEYWORDS)


def detect_icu_tier_overbilling(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine] | None = None,
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Review 3rd-level ICU packages (P552003 / P552008) without separately billed support.

    Under SUT §2.4.4.H.(1) (C001233), ICU bed standards and patient-level tier
    criteria follow Ministry of Health regulations. On EK-2/C ICU package days,
    only EK-2/C A/B/C-group operations (§2.4.4.H.(2), C001234) and the treatments
    listed in §2.4.4.H.(4) (C001236: continuous haemodiafiltration/haemofiltration,
    plasmapheresis, haemodialysis, therapeutic hypothermia) are billed separately;
    mechanical ventilation, intubation, and CPR are included in the ICU package.
    When a claim bills ``P552003`` or ``P552008`` with no separately billed
    §2.4.4.H.(2)/(4) item on the episode, this detector emits an informational
    review row ("tier evidence not on the bill") with 0.00 TL audit exposure so
    epikriz documentation can be checked without flagging included care as
    overbilling (#255).
    """
    if not procedure_lines:
        return []

    procedures_by_claim: dict[str, list[ProcedureClaimLine]] = {}
    procedures_by_episode: dict[str, list[ProcedureClaimLine]] = {}
    for line in procedure_lines:
        procedures_by_claim.setdefault(line.claim_id, []).append(line)
        ep_id = getattr(line, "episode_id", "") or ""
        if ep_id:
            procedures_by_episode.setdefault(ep_id, []).append(line)

    findings: list[dict[str, Any]] = []

    for claim in claims:
        if infer_care_setting(claim) != "inpatient":
            continue
        if claim_ids_with_procs is not None and claim.claim_id not in claim_ids_with_procs:
            continue

        claim_procs = procedures_by_claim.get(claim.claim_id, [])
        if not claim_procs:
            continue

        as_of_date = claim.admission_date or claim.claim_start_date
        ep_id = getattr(claim, "episode_id", "") or ""
        episode_procs = procedures_by_episode.get(ep_id, claim_procs) if ep_id else claim_procs
        if any(_line_is_tier_3_support(p, as_of_date=as_of_date) for p in episode_procs):
            continue

        for line in claim_procs:
            stripped = clean_procedure_code(line.procedure_code, PackagePrefix.ALWAYS)
            if stripped not in _TIER_3_PACKAGE_CODES:
                continue

            tier2_stripped, tier1_stripped = _TIER_3_PACKAGE_CODES[stripped]
            ilave_oran_pct, _ = _resolve_ilave_oran(claim, stripped)
            uplift_mult = 1.0 + ilave_oran_pct / 100.0
            qty = max(int(getattr(line, "quantity", 1) or 1), 1)

            tier3_unit = _money(
                _intermediate_package_price_try(stripped, as_of_date) * uplift_mult
            )
            tier2_unit = _money(
                _intermediate_package_price_try(tier2_stripped, as_of_date) * uplift_mult
            )
            tier1_unit = _money(
                _intermediate_package_price_try(tier1_stripped, as_of_date) * uplift_mult
            )

            tier3_total = _money(tier3_unit * qty)
            tier2_total = _money(tier2_unit * qty)
            tier1_total = _money(tier1_unit * qty)
            billed_try = _money(float(getattr(line, "billed_amount_try", 0.0) or 0.0))
            reference_top = billed_try if billed_try > 0 else tier3_total
            gap_to_tier2 = _money(max(0.0, reference_top - tier2_total))
            gap_to_tier1 = _money(max(0.0, reference_top - tier1_total))

            detail = (
                f"3. basamak yoğun bakım paketi (P{stripped}, {qty} gün) için "
                f"faturada ayrıca faturalandırılabilir A/B/C grubu işlem veya "
                f"diyaliz/hemodiafiltrasyon/plazmaferez/ECMO satırı yer almıyor; "
                f"basamak kriterleri epikriz ve Sağlık Bakanlığı düzenlemeleri "
                f"üzerinden teyit edilmelidir (SUT §2.4.4.H.(1), (2), (4)). "
                f"Referans P{tier2_stripped} (2. basamak) farkı: "
                f"{gap_to_tier2:.2f} TRY; P{tier1_stripped} (1. basamak) farkı: "
                f"{gap_to_tier1:.2f} TRY."
            )

            findings.append(
                {
                    "type": _TIER_OVERBILLING_TYPE,
                    "rule": _TIER_OVERBILLING_RULE_ID,
                    "rule_id": _TIER_OVERBILLING_RULE_ID,
                    "sut_section_id": _SUT_SECTION_ID,
                    "severity": "info",
                    "claim_id": claim.claim_id,
                    "procedure_line_id": line.procedure_line_id,
                    "procedure_code": f"P{stripped}",
                    "billed_tier": 3,
                    "recommended_tier_2_code": f"P{tier2_stripped}",
                    "recommended_tier_1_code": f"P{tier1_stripped}",
                    "quantity": qty,
                    "billed_amount_try": billed_try,
                    "tier_3_expected_try": tier3_total,
                    "tier_2_expected_try": tier2_total,
                    "tier_1_expected_try": tier1_total,
                    "price_gap_to_tier_2_try": gap_to_tier2,
                    "price_gap_to_tier_1_try": gap_to_tier1,
                    "at_risk_try": 0.0,
                    "savings_try": 0.0,
                    "risk_amount": 0.0,
                    "included_in_sgk_total": False,
                    "savings_category": SAVINGS_CATEGORY_AUDIT_EXPOSURE,
                    "savings_basis": SAVINGS_BASIS_SOURCED,
                    "message": detail,
                    "detail": detail,
                }
            )

    return findings

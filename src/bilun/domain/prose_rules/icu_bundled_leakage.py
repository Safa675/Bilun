"""SUT §2.4.4.H ICU bundled-service leakage detector.

The El Kitabı and SUT §2.4.4.H establish that on ICU days billed as
**510090** ("Yoğun bakım", EK-2B hizmet başı ödeme yöntemi), the following
services are **BUNDLED** into the 510090 charge and cannot be separately
billed on that day:

- Mechanical ventilation (mekanik ventilasyon)
- Non-invasive mechanical ventilation (non-invaziv mekanik ventilasyon)
- Ventilator follow-up (ventilatör ile takip)
- Oxygen therapy (oksijen inhalasyon tedavisi)
- Nebulizer treatment (nebulizatör ile ilaç uygulaması)
- Deep tracheal suction (derin trakeal aspirasyon)
- Patient monitoring (monitörizasyon)

BILUN's :mod:`icu_puani` module *documents* this bundling in its module
docstring but does **not** detect violations when these services are billed
separately on a 510090 day. This detector closes that gap: for each
inpatient claim that carries a 510090 procedure line, it scans the claim's
other procedure lines and emits a violation for every bundled service found.

**Scope notes:**
- The bundle applies on **510090 day-rate days only**. Intermediate ICU days
  billed as P552001-P552008 packages (EK-2C) are NOT in scope here — those
  packages bundle a different (broader) service set and are audited
  separately.
- Outpatient claims are skipped (ICU is an inpatient-only concept per
  §2.4.4.H.(3): PACU/anesthesia recovery is never ICU).
- Matching is by exact SUT code (``_BUNDLED_SERVICE_CODES``) plus a keyword
  fallback (``_BUNDLED_SERVICE_KEYWORDS``) so that variant/typo codes still
  surface, e.g. when a hospital submits a slightly renamed procedure.

SUT codes identified as bundled services (EK-2B, verified against the live
catalog — see ``_BUNDLED_SERVICE_CODES`` docstring for the regulatory
mapping of each code to its El Kitabı category).
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from src.bilun.domain.prose_rules.claim_utils import infer_care_setting
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_AUDIT_EXPOSURE,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_OPPORTUNITY_TYPE = "icu_bundled_service_leakage"
_SUT_SECTION_ID = "2.4.4.H"
_RULE_ID = "icu_bundled_leakage_510090"

# The 510090 day-rate code (yoğun bakım, hizmet başı) — mirrors icu_puani.
_ICU_DAY_RATE_CODE = "510090"

# SUT codes BUNDLED into the 510090 charge per El Kitabı / §2.4.4.H. Each is
# an EK-2B procedure that is otherwise billable on its own, but is subsumed
# by the ICU day-rate when billed on the same day as 510090.
#
# Regulatory mapping (verified against the live SUT catalog):
#   530130 "Hastanın mekanik ventilatöre bağlanması"        → mekanik ventilasyon
#   530490 "Ventilatör ile takip"                            → mekanik ventilasyon (devam)
#   530700 "Non invaziv mekanik ventilatör uygulaması"       → non-invaziv mekanik ventilasyon
#   530360 "Oksijen inhalasyon tedavisi, saatlik"            → oksijen tedavisi
#   530350 "Nebülizatör ile ilaç uygulaması"                 → nebulizasyon
#   551251 "Derin trakeal aspirasyon"                        → derin trakeal aspirasyon
#   530330 "Monitörizasyon"                                  → hasta monitorizasyonu
#   530960 "Yenidoğan monitörizasyonu"                       → hasta monitorizasyonu (yenidoğan)
_BUNDLED_SERVICE_CODES: frozenset[str] = frozenset(
    {
        "530130",  # mekanik ventilasyon (hastanın mekanik ventilatöre bağlanması)
        "530490",  # ventilatör ile takip (mekanik ventilasyon devam)
        "530700",  # non-invaziv mekanik ventilatör uygulaması
        "530360",  # oksijen inhalasyon tedavisi, saatlik
        "530350",  # nebulizatör ile ilaç uygulaması
        "551251",  # derin trakeal aspirasyon
        "530330",  # monitörizasyon
        "530960",  # yenidoğan monitörizasyonu
    }
)

# Turkish keyword fallback — catches variant/typo codes that name a bundled
# service but are not in the exact code set above. Matching is on the
# ASCII-folded, lower-cased procedure name (see ``_fold_tr``). Keywords are
# written in their folded form. Each keyword is specific enough to avoid
# false positives (e.g. "ventilasyon sintigrafisi" is a nuclear-medicine
# study, not ICU ventilation — we therefore key on "ventilator" rather than
# the broader "ventilasyon").
_BUNDLED_SERVICE_KEYWORDS: tuple[str, ...] = (
    "ventilator",
    "non invaziv mekanik ventil",
    "non-invaziv mekanik ventil",
    "nebulizator",
    "nebulizasyon",
    "oksijen inhalasyon",
    "derin trakeal aspirasyon",
    "trakeal aspirasyon",
    "monitorizasyon",
)


def _normalize_code(raw: str) -> str:
    """Normalize a procedure code for matching (mirrors icu_puani helpers).

    Strips a leading P/p (MEDULA package prefix), removes punctuation, and
    upper-cases so that ``"p530130"``, ``"530.130"``, ``"530 130"`` all
    collapse to ``"530130"``.
    """
    cleaned = (
        str(raw or "")
        .strip()
        .replace(".", "")
        .replace(" ", "")
        .replace("-", "")
        .upper()
    )
    return cleaned[1:] if cleaned.startswith("P") else cleaned


# Turkish diacritics → ASCII fold map. Used so that "Nebülizatör",
# "Monitörizasyon", and "Mekanik ventilatör" match their ASCII keyword forms
# regardless of whether the source string carries the dotted/dotless-i and
# umlaut forms (SUT catalog is inconsistent on this).
_TR_FOLD_MAP = str.maketrans(
    {
        "ç": "c", "Ç": "c",
        "ğ": "g", "Ğ": "g",
        "ı": "i", "I": "i",
        "İ": "i",
        "ö": "o", "Ö": "o",
        "ş": "s", "Ş": "s",
        "ü": "u", "Ü": "u",
    }
)


def _fold_tr(text: str) -> str:
    """Fold Turkish diacritics to ASCII and lower-case for keyword matching."""
    return str(text or "").translate(_TR_FOLD_MAP).lower()


def _is_bundled_service(code: str, name: str) -> bool:
    """True when a procedure line represents a service bundled into 510090.

    Matches first on the normalized code (exact), then falls back to a
    keyword scan of the procedure name so that variant/typo codes still
    surface. Keyword matching uses ``_fold_tr`` so Turkish diacritics
    (ü/ö/ş/ç/ı) do not cause misses.
    """
    normalized = _normalize_code(code)
    if normalized in _BUNDLED_SERVICE_CODES:
        return True
    name_folded = _fold_tr(name)
    if not name_folded:
        return False
    return any(kw in name_folded for kw in _BUNDLED_SERVICE_KEYWORDS)


def _bundled_category_for(code: str, name: str) -> str:
    """Map a matched bundled service to its El Kitabı category label (Turkish).

    Used to make the violation detail self-explanatory for an auditor.
    Falls back to the raw procedure name when no keyword matches.
    """
    normalized = _normalize_code(code)
    name_folded = _fold_tr(name)

    if normalized == "530130" or ("baglanmas" in name_folded) or ("ventilator" in name_folded and "non" not in name_folded and "invaziv" not in name_folded):
        # 530130 "hastanın mekanik ventilatöre bağlanması" + ventilator follow-up
        if "takip" in name_folded:
            return "Mekanik ventilasyon (ventilatör ile takip)"
        return "Mekanik ventilasyon"
    if normalized == "530700" or "non invaziv mekanik" in name_folded or "non-invaziv mekanik" in name_folded:
        return "Non-invaziv mekanik ventilasyon"
    if normalized == "530360" or "oksijen inhalasyon" in name_folded:
        return "Oksijen tedavisi"
    if normalized == "530350" or "nebulizator" in name_folded or "nebulizasyon" in name_folded:
        return "Nebülizasyon"
    if normalized == "551251" or "trakeal aspirasyon" in name_folded:
        return "Derin trakeal aspirasyon"
    if normalized in {"530330", "530960"} or "monitorizasyon" in name_folded:
        return "Hasta monitorizasyonu"
    return str(name or code)


def detect_icu_bundled_leakage(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine] | None = None,
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Detect bundled services billed separately on ICU (510090) days.

    For each **inpatient** claim that carries a ``510090`` procedure line,
    scan the claim's other procedure lines on the same date and emit one
    violation per line whose code (or name) matches a bundled service. A
    bundled service billed on a 510090 date is double-billing: the day-rate
    already pays for ventilation, oxygen, nebulization, suction, and
    monitoring (El Kitabı + SUT §2.4.4.H).

    Args:
        claims: ClaimHeaders to evaluate.
        procedure_lines: Procedure claim lines grouped by ``claim_id``. When
            omitted (or empty), no claims can be confirmed as 510090 days, so
            no violations are emitted.
        claim_ids_with_procs: Optional filter — only emit violations for
            claims that also have procedure lines (matches the
            ``patient_report`` wiring gate used by the other prose motors).

    Returns:
        Violation dicts with: ``type``, ``claim_id``, ``rule_id``,
        ``procedure_code``, ``procedure_name``, ``procedure_line_id``,
        ``bundled_category``, ``detail`` (Turkish), ``sut_section_id``,
        ``savings_category``, ``savings_basis``, ``severity``.
    """
    # Group procedure lines by claim.
    procedures_by_claim: dict[str, list[ProcedureClaimLine]] = {}
    if procedure_lines:
        for line in procedure_lines:
            procedures_by_claim.setdefault(line.claim_id, []).append(line)

    # Pre-compute the exact 510090 dates for each eligible inpatient claim.
    icu_days_by_claim: dict[str, set[date]] = {}
    for claim in claims:
        # Gate on inpatient — ICU is an inpatient-only concept (§2.4.4.H.(3)).
        if infer_care_setting(claim) != "inpatient":
            continue
        if claim_ids_with_procs is not None and claim.claim_id not in claim_ids_with_procs:
            continue
        claim_procs = procedures_by_claim.get(claim.claim_id, [])
        icu_days = {
            line.procedure_date
            for line in claim_procs
            if _normalize_code(line.procedure_code) == _ICU_DAY_RATE_CODE
        }
        if icu_days:
            icu_days_by_claim[claim.claim_id] = icu_days

    violations: list[dict[str, Any]] = []
    for claim_id, icu_days in icu_days_by_claim.items():
        claim_procs = procedures_by_claim.get(claim_id, [])
        for line in claim_procs:
            # Skip the 510090 line itself.
            if _normalize_code(line.procedure_code) == _ICU_DAY_RATE_CODE:
                continue
            if line.procedure_date not in icu_days:
                continue
            # Skip ICU intermediate-day packages (P552001-008) — those are a
            # separate bundled-service regime audited elsewhere; flagging them
            # here would conflate two different rules.
            normalized = _normalize_code(line.procedure_code)
            if normalized.startswith("55200") and len(normalized) == 6:
                continue
            if not _is_bundled_service(line.procedure_code, line.procedure_name):
                continue

            category = _bundled_category_for(line.procedure_code, line.procedure_name)
            detail = (
                f"Yoğun bakım günü (510090, hizmet başı) ile aynı tarihte ayrı "
                f"faturalandırılan paket hizmet: {line.procedure_code} "
                f"({line.procedure_name}) — {category}, 510090 içine dahildir "
                f"ve ayrı faturalanamaz (SUT §2.4.4.H, El Kitabı)."
            )
            violations.append(
                {
                    "type": _OPPORTUNITY_TYPE,
                    "claim_id": claim_id,
                    "rule_id": _RULE_ID,
                    "procedure_code": line.procedure_code,
                    "procedure_name": line.procedure_name,
                    "procedure_line_id": line.procedure_line_id,
                    "bundled_category": category,
                    "detail": detail,
                    "sut_section_id": _SUT_SECTION_ID,
                    "savings_category": SAVINGS_CATEGORY_AUDIT_EXPOSURE,
                    "savings_basis": SAVINGS_BASIS_SOURCED,
                    "severity": "error",
                }
            )

    return violations

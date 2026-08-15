"""ICD-10 diagnosis-coding quality detectors (El Kitabı diagnosis-coding rules).

Each detector encodes one diagnosis-coding quality rule sourced from the
Sağlık Bakanlığı Geri Ödeme El Kitabı, focusing on the three highest-value
coding-quality error classes observed in real Medula denials:

- **A1** Never-valid principal diagnosis codes          → ``detect_never_principal_diagnosis``
- **A2** Diagnosis ↔ procedure chapter mismatch         → ``detect_diagnosis_procedure_mismatch``
- **A3** Redundant symptom (R-code) additional diagnosis → ``detect_unnecessary_additional_diagnosis``

These detectors follow the same contract as the Tablo-15 detectors in
:mod:`common_billing_errors`: each takes plain ``ClaimHeader`` /
``ProcedureClaimLine`` / ``ClaimDiagnosis`` lists plus an optional
``claim_ids_with_procs`` filter set, and emits violation dicts with the
uniform shape (``type``, ``claim_id``, ``rule_id``, ``detail`` (Turkish),
``sut_section_id``, ``savings_category``, ``savings_basis``, ``severity``).

Matching is performed on the ICD-10 prefix (first letter) and the first
three characters of the code (the category, e.g. ``R69``). Code strings are
normalised (upper-cased, trimmed) before matching so that lowercase or
whitespace-padded dataset values are handled uniformly.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_SGK_UPLIFT,
)
from src.bilun.domain.sut.clause_reference import SOURCE_EL_KITABI, non_sut_reference

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimDiagnosis, ClaimHeader, ProcedureClaimLine

# Common violation-shape keys reused by every detector.
_OPPORTUNITY_TYPE = "diagnosis_quality"
_SUT_SECTION_ID = "elkitabi_diagnosis_coding"

# Provenance (Phase 2): diagnosis-coding quality rules are El Kitabı
# content, not a SUT clause — findings are labeled honestly instead of
# carrying an invented SUT cite. Resolved once at module load; every
# finding shares the same dict (clause_key stays empty).
_SOURCE_TYPE = SOURCE_EL_KITABI
_CLAUSE_REF = non_sut_reference(
    "El Kitabı — Tanı Kodlama Kalitesi", source_type=SOURCE_EL_KITABI
).to_dict()

# ---------------------------------------------------------------------------
# A1 — Never-valid principal diagnosis blocklists.
# ---------------------------------------------------------------------------

# R-codes (R00-R99): symptoms, signs and abnormal clinical/laboratory
# findings — not a definitive diagnosis and therefore never acceptable as a
# *principal* (birincil) diagnosis on a claim.
_NEVER_PRINCIPAL_PREFIXES: frozenset[str] = frozenset({"R"})

# Z-code categories that are "history of" (geçmiş hikaye) — a resolved
# condition, not the active reason for the encounter.
_Z_HISTORY_PREFIXES: frozenset[str] = frozenset(
    {
        "Z80", "Z81", "Z82", "Z83", "Z84", "Z85", "Z86", "Z87",
    }
)

# Z-code categories representing encounter/screening status (muayene/tarama
# sebebi) — they describe the *reason for the visit*, not an active disease.
_Z_ENCOUNTER_SCREENING_PREFIXES: frozenset[str] = frozenset(
    {
        # Z00-Z13 health examination / screening
        "Z00", "Z01", "Z02", "Z03", "Z04", "Z05", "Z06", "Z07", "Z08",
        "Z09", "Z10", "Z11", "Z12", "Z13",
        # Z32-Z36, Z39 pregnancy/prenatal encounter state
        "Z32", "Z33", "Z34", "Z35", "Z36", "Z39",
        # Z40-Z43, Z45-Z49, Z50, Z51 procedure/encounter aftercare & special
        # screenings (note: Z48.0 and Z51.5 / Z51.81 also called out explicitly
        # below as specific never-principal codes).
        "Z40", "Z41", "Z42", "Z43", "Z45", "Z46", "Z47", "Z48", "Z49",
        "Z50", "Z51",
        # Z71-Z76 health-service encounters for specific reasons
        "Z71", "Z72", "Z73", "Z74", "Z75", "Z76",
    }
)

# Specific never-principal codes called out individually in the El Kitabı.
_NEVER_PRINCIPAL_EXACT_CODES: frozenset[str] = frozenset(
    {
        "O09",  # supervision of high-risk pregnancy — never the principal dx
        "Z48.0",  # post-surgical aftercare follow-up
        "Z51.5",  # encounter for palliative care (aftercare)
        "Z51.81",  # encounter for therapeutic drug monitoring
    }
)

# External-cause / supplementary chapter codes (V01-Y98): they describe the
# *cause/mechanism* of an injury, never the principal diagnosis itself.
_EXTERNAL_CAUSE_PREFIXES: frozenset[str] = frozenset(
    {"V", "W", "X", "Y"}
)

# P00-P04 (newborn affected by maternal factors) is also never principal.
_NEVER_PRINCIPAL_P_PREFIXES: frozenset[str] = frozenset(
    {"P00", "P01", "P02", "P03", "P04"}
)


# ---------------------------------------------------------------------------
# A2 — Diagnosis ↔ procedure chapter mismatch maps.
# ---------------------------------------------------------------------------

# Procedure code prefixes that represent orthopedic surgery (SUT 60xxxx /
# 61xxxx family). An orthopedic operation billed under a mental-health (F-code)
# *principal* diagnosis is a gross mismatch.
_ORTHO_SURGERY_PROC_PREFIXES: tuple[str, ...] = ("60", "61")

# Procedure code prefixes that represent cardiac / cardiothoracic surgery
# (SUT 70xxxx family). Billed under a pregnancy (O-code) principal diagnosis is
# a gross mismatch (obstetric vs cardiac procedure chapter).
_CARDIAC_SURGERY_PROC_PREFIXES: tuple[str, ...] = ("70",)

# Procedure categories that represent routine screening / check-up services.
# A screening service under an injury (S/T-code) principal diagnosis is
# suspicious: an injury encounter is not a screening visit.
_SCREENING_PROC_CATEGORIES: frozenset[str] = frozenset(
    {"tarama", "checkup", "check_up", "muayene_kontrol", "kontrol"}
)


def _normalize_icd10(code: str | None) -> str:
    """Upper-case, strip and trim an ICD-10 code for prefix matching.

    Returns the empty string for ``None`` / blank input. Whitespace internal to
    a code is preserved (real ICD-10 codes have none), but leading/trailing
    spaces are removed.
    """
    return (code or "").strip().upper()


def _is_never_principal(icd10: str) -> tuple[bool, str]:
    """Classify a (non-empty, normalised) ICD-10 code as never-principal.

    Returns ``(True, reason)`` when the code must never be a principal
    diagnosis, otherwise ``(False, "")``. ``reason`` is a short Turkish tag
    used to build the violation detail text.
    """
    first = icd10[:1]
    cat3 = icd10[:3]

    # Specific codes first (longest match wins).
    if icd10 in _NEVER_PRINCIPAL_EXACT_CODES:
        return True, "spesifik asla birincil tanı olmayan kod"
    if cat3 == "O09":
        return True, "yüksek riskli gebelik takibi (O09)"
    # Z-code families.
    if first == "Z":
        if cat3 in _Z_HISTORY_PREFIXES:
            return True, "kişisel hastalık öyküsü (Z80-Z87)"
        if cat3 in _Z_ENCOUNTER_SCREENING_PREFIXES:
            return True, "karşılaşma/tarama durumu (Z muayene/tarama)"
        # Z48.0 / Z51.5 / Z51.81 already handled by the exact set, but defend
        # against the longer Z48.* / Z51.* aftercare families being principal.
        if cat3 in {"Z48", "Z51"}:
            return True, "karşılaşma sonrası bakım/izlem (Z48/Z51)"
    # R-codes (symptoms / signs).
    if first == "R":
        return True, "belirti/bulguya ait kod (R00-R99)"
    # External cause codes (V/W/X/Y).
    if first in _EXTERNAL_CAUSE_PREFIXES:
        return True, "dışsal neden/yaralanma kodu (V01-Y98)"
    # Newborn affected by maternal factors (P00-P04).
    if cat3 in _NEVER_PRINCIPAL_P_PREFIXES:
        return True, "yenidoğan anne faktörü kodu (P00-P04)"
    return False, ""


def detect_never_principal_diagnosis(
    claims: list[ClaimHeader],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """A1: ICD-10 codes that must never be coded as the principal diagnosis.

    Flags a claim whose ``primary_icd10`` falls into one of the never-principal
    families per the Sağlık Bakanlığı El Kitabı:

    - R-codes (R00-R99): symptoms/signs — not a definitive diagnosis.
    - Z-codes for personal history (Z80-Z87): resolved, not active disease.
    - Z-codes for encounter/screening status (Z00-Z13, Z32-Z36, Z39, Z40-Z43,
      Z45-Z49, Z50, Z51, Z71-Z76): describe the visit reason, not a disease.
    - External cause codes (V01-Y98, including W/X/Y): injury *causes*.
    - Specific codes: O09, P00-P04, Z48.0, Z51.5, Z51.81.

    Detection uses ICD-10 prefix/chapter matching (first letter + first three
    chars). Empty ``primary_icd10`` is skipped (the existing
    ``detect_missing_diagnosis`` covers that case).

    Args:
        claims: ClaimHeaders to evaluate.
        claim_ids_with_procs: Optional filter — only evaluate claims that also
            carry procedure lines (matches the ``patient_report`` wiring gate).
    """
    violations: list[dict[str, Any]] = []
    for claim in claims:
        if claim_ids_with_procs is not None and claim.claim_id not in claim_ids_with_procs:
            continue
        icd10 = _normalize_icd10(claim.primary_icd10)
        if not icd10:
            continue  # detect_missing_diagnosis owns the empty case
        is_blocklisted, reason = _is_never_principal(icd10)
        if not is_blocklisted:
            continue
        detail = (
            f"Takip {claim.claim_id} birincil tanısı '{claim.primary_icd10}' asla "
            f"birincil (ana) tanı olarak kodlanamaz — {reason}. Kesin tanı kodu "
            f"birincil tanı alanına yazılmalıdır (El Kitabı tanı kodlama kalitesi)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim.claim_id,
                "rule_id": "never_principal_diagnosis_blocklist",
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "error",
                "primary_icd10": claim.primary_icd10,
                "reason": reason,
            }
        )
    return violations


def detect_diagnosis_procedure_mismatch(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """A2: Clearly-impossible diagnosis ↔ procedure combinations.

    Conservative detector — only flags *gross* chapter-level mismatches, not
    "unusual but possible" pairings. Maps the ICD-10 chapter of the principal
    diagnosis to the SUT procedure code range on the same claim:

    - F-code (mental health) principal + orthopedic surgery (60xxxx / 61xxxx)
      procedures → flag.
    - O-code (pregnancy) principal + cardiac / cardiothoracic surgery
      (70xxxx) procedures → flag.
    - S/T-code (injury) principal + routine screening/check-up category
      procedures → flag.

    Procedure lines are grouped by ``claim_id``; only claims that have at least
    one procedure line are evaluated. One violation is emitted per claim
    (carrying the first mismatched procedure code); the rule is suspicious, not
    always wrong, hence severity ``warning``.
    """
    claims_by_id: dict[str, ClaimHeader] = {c.claim_id: c for c in claims}

    lines_by_claim: dict[str, list[ProcedureClaimLine]] = defaultdict(list)
    for line in procedure_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        lines_by_claim[line.claim_id].append(line)

    violations: list[dict[str, Any]] = []
    for claim_id, lines in lines_by_claim.items():
        claim = claims_by_id.get(claim_id)
        if claim is None:
            continue
        icd10 = _normalize_icd10(claim.primary_icd10)
        if not icd10:
            continue  # no principal dx to compare against
        first = icd10[:1]

        mismatched: list[ProcedureClaimLine] = []
        if first == "F":
            for line in lines:
                if any(
                    line.procedure_code.startswith(p)
                    for p in _ORTHO_SURGERY_PROC_PREFIXES
                ):
                    mismatched.append(line)
        elif first == "O":
            for line in lines:
                if any(
                    line.procedure_code.startswith(p)
                    for p in _CARDIAC_SURGERY_PROC_PREFIXES
                ):
                    mismatched.append(line)
        elif first in {"S", "T"}:
            for line in lines:
                cat = (line.procedure_category or "").casefold()
                if cat in _SCREENING_PROC_CATEGORIES:
                    mismatched.append(line)

        if not mismatched:
            continue
        # One violation per claim — surface the first offending line's code.
        offending = mismatched[0]
        detail = (
            f"Takip {claim_id}: birincil tanı '{claim.primary_icd10}' "
            f"({first}-kodu bölümü) ile işlem '{offending.procedure_code}' "
            f"({offending.procedure_category}) uyuşmuyor — tanı ile işlem "
            f"kategorileri mantıken imkansız kombinasyon (El Kitabı tanı-işlem "
            f"uyuşmazlığı)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim.claim_id,
                "rule_id": "dx_procedure_mismatch",
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "warning",
                "primary_icd10": claim.primary_icd10,
                "procedure_code": offending.procedure_code,
                "procedure_category": offending.procedure_category,
                "mismatched_line_count": len(mismatched),
            }
        )
    return violations


def _r_code_chapter_letters(icd10: str) -> frozenset[str]:
    """Map an R-code symptom category to the disease-chapter letters it covers.

    The ICD-10 R-chapter (R00-R99) groups symptoms/signs by body system. Each
    sub-block maps naturally to a definitive-diagnosis chapter letter (e.g.
    R10-R19 abdominal symptoms → K digestive, matching the plan's canonical
    K35.8 + R10.4 example). Returns the set of disease letters the R-code's
    body system belongs to; the empty set means the R-code is a general
    symptom (R50-R69) with no single chapter, which we never flag (conservative).
    """
    if not icd10.startswith("R") or len(icd10) < 3:
        return frozenset()
    # Group by the R-category range using the numeric band of R<NN>.
    try:
        band = int(icd10[1:3])
    except ValueError:
        return frozenset()
    if 0 <= band <= 9:           # R00-R09 circulatory & respiratory symptoms
        return frozenset({"I", "J"})
    if 10 <= band <= 19:         # R10-R19 digestive symptoms → K
        return frozenset({"K"})
    if 20 <= band <= 23:         # R20-R23 skin & subcutaneous → L
        return frozenset({"L"})
    if 25 <= band <= 29:         # R25-R29 nervous & musculoskeletal → G, M
        return frozenset({"G", "M"})
    if 30 <= band <= 39:         # R30-R39 urinary → N
        return frozenset({"N"})
    if 40 <= band <= 49:         # R40-R49 cognition/speech → G, F
        return frozenset({"G", "F"})
    return frozenset()           # R50-R69 general symptoms — never flag


def detect_unnecessary_additional_diagnosis(
    claims: list[ClaimHeader],
    diagnoses: list[ClaimDiagnosis],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """A3: Redundant symptom (R-code) additional diagnosis.

    Flags a claim where an R-code symptom diagnosis is coded *alongside* a
    definitive diagnosis in the SAME body-system chapter on the same claim.
    Example: K35.8 (appendicitis) + R10.4 (abdominal pain) — the abdominal-pain
    R-code is clinically subsumed by the appendicitis and is redundant; the
    symptom is implied by the definitive disease, so coding both adds no
    clinical information and inflates the dx list.

    Chapter pairing is resolved via :func:`_r_code_chapter_letters`: each
    R-category sub-block maps to the disease-chapter letter(s) it covers
    (R10-R19 → K digestive, R30-R39 → N genitourinary, etc.). An R-code is
    flagged only when a definitive diagnosis with one of those letters is
    present on the same claim. General R-symptoms (R50-R69) map to no chapter
    and are never flagged (conservative). When the symptom R-code's body system
    does not match any definitive dx chapter (e.g. J20 bronchitis + R10.4
    abdominal pain → J vs K), no violation is raised.

    ``ClaimDiagnosis`` rows are grouped by ``claim_id``; only claims carrying
    at least one R-code diagnosis AND a matching-chapter definitive dx are
    flagged. Severity is ``warning``.
    """
    claims_by_id: dict[str, ClaimHeader] = {c.claim_id: c for c in claims}

    dx_by_claim: dict[str, list[ClaimDiagnosis]] = defaultdict(list)
    for dx in diagnoses:
        if claim_ids_with_procs is not None and dx.claim_id not in claim_ids_with_procs:
            continue
        dx_by_claim[dx.claim_id].append(dx)

    violations: list[dict[str, Any]] = []
    for claim_id, dxs in dx_by_claim.items():
        claim = claims_by_id.get(claim_id)
        if claim is None:
            continue
        # Partition diagnoses into R-code symptoms vs definitive (non-R).
        r_code_rows: list[ClaimDiagnosis] = []
        definitive_by_letter: dict[str, list[ClaimDiagnosis]] = defaultdict(list)
        for dx in dxs:
            icd10 = _normalize_icd10(dx.icd10_code)
            if not icd10:
                continue
            if icd10[:1] == "R":
                r_code_rows.append(dx)
            else:
                definitive_by_letter[icd10[:1]].append(dx)

        if not r_code_rows or not definitive_by_letter:
            continue

        for r_row in r_code_rows:
            r_icd = _normalize_icd10(r_row.icd10_code)
            paired_letters = _r_code_chapter_letters(r_icd)
            if not paired_letters:
                continue  # general R-symptom with no chapter mapping
            paired: list[ClaimDiagnosis] = []
            for letter in paired_letters:
                paired.extend(definitive_by_letter.get(letter, ()))
            if not paired:
                continue  # definitive dx exists but in a different chapter
            paired_codes = ", ".join(
                _normalize_icd10(d.icd10_code) for d in paired
            )
            detail = (
                f"Takip {claim_id}: belirti/bulguya ait ek tanı '{r_icd}' "
                f"kesin tanı(lar) ile birlikte ({paired_codes}) kodlanmış — "
                f"belirti kesin tanı tarafından kapsandığı için gereksiz ek "
                f"tanıdır (El Kitabı gereksiz ek tanı)."
            )
            violations.append(
                {
                    "type": _OPPORTUNITY_TYPE,
                    "claim_id": claim.claim_id,
                    "rule_id": "unnecessary_additional_diagnosis",
                    "detail": detail,
                    "sut_section_id": _SUT_SECTION_ID,
                    "source_type": _SOURCE_TYPE,
                    "clause_ref": _CLAUSE_REF,
                    "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                    "savings_basis": SAVINGS_BASIS_SOURCED,
                    "severity": "warning",
                    "primary_icd10": claim.primary_icd10,
                    "redundant_icd10": r_row.icd10_code,
                    "paired_definitive_icd10": paired_codes,
                    "diagnosis_id": r_row.diagnosis_id,
                }
            )
    return violations


# ===========================================================================
# PatientClaimContext wrappers (mirror the SCT / drg_package_adequacy pattern).
# ===========================================================================


def detect_never_principal_diagnosis_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Run :func:`detect_never_principal_diagnosis` on a PatientClaimContext."""
    return detect_never_principal_diagnosis(list(ctx.claims))


def detect_diagnosis_procedure_mismatch_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Run :func:`detect_diagnosis_procedure_mismatch` on a PatientClaimContext."""
    return detect_diagnosis_procedure_mismatch(
        list(ctx.claims), list(ctx.procedure_lines)
    )


def detect_unnecessary_additional_diagnosis_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Run :func:`detect_unnecessary_additional_diagnosis` on a PatientClaimContext."""
    return detect_unnecessary_additional_diagnosis(
        list(ctx.claims), list(ctx.diagnoses)
    )

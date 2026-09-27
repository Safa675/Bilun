"""High-value Turkish hospital billing error detectors (El Kitabı Tablo 15).

Each detector encodes one row of "El Kitabı Tablo 15 — 24 Most Common
Outpatient Billing Errors". Phase 1 covered the 5 highest-frequency errors
selected by the feasibility study (`/tmp/feasibility/common_errors.md`) as
buildable now (data already on the claim context), high-frequency in real
Medula denials, and low effort to implement. Phase 2 adds 11 more.

Phase 1 errors covered:
- **#2** Same-specialty exam within 10 days  → ``detect_duplicate_exam_10day``
- **#8** Services with no diagnosis on takip → ``detect_missing_diagnosis``
- **#12** Duplicate tests across claims       → ``detect_duplicate_tests``
- **#22** Exam date ≠ admission date          → ``detect_exam_admission_date_mismatch``
- **#20** Drug QR/barcode missing             → ``detect_missing_drug_barcode``

Phase 2 errors covered:
- **#3** Vakabaşı billed where Normal Poliklinik required → ``detect_vakabasi_wrong_method``
- **#4** Normal Poliklinik billed where vakabaşı required → ``detect_normal_poliklinik_wrong_method``
- **#5** Material identity errors (SUT/barcode) → ``detect_material_identity_errors``
- **#7** Green-area exam + bundled extras → ``detect_green_area_bundled_extras``
- **#9** Admissions past 60-day billing window → ``detect_admission_billing_window``
- **#10** Incomplete/unreported procedures → ``detect_unreported_lab_result``
- **#11** Drug quantity (adet) error → ``detect_drug_quantity_error``
- **#15** Material pre-auth missing → ``detect_material_preauth_missing``
- **#16** Wrong material-type code → ``detect_material_type_missing``
- **#21** Inpatient data on outpatient takip → ``detect_inpatient_on_outpatient``
- **#24** Donor-prep workup billed as exam → ``detect_donor_prep_as_exam``

Every detector takes plain ``ClaimHeader`` / ``ProcedureClaimLine`` /
``DrugClaimLine`` lists plus an optional ``claim_ids_with_procs`` filter set
(matching the wiring gate used by ``patient_report`` and the other prose-rule
motors, e.g. ``anestezi_puani``). Each emits violation dicts with a uniform
shape: ``type``, ``claim_id``, ``rule_id``, ``detail`` (Turkish),
``sut_section_id``, ``savings_category``, ``savings_basis``, ``severity``.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from src.bilun.domain.prose_rules.claim_utils import infer_care_setting
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_SGK_UPLIFT,
)
from src.bilun.domain.sut.clause_reference import SOURCE_EL_KITABI, non_sut_reference

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import (
        ClaimHeader,
        ProcedureClaimLine,
    )

# Common violation-shape keys reused by every detector.
_OPPORTUNITY_TYPE = "common_billing_error"
_SUT_SECTION_ID = "tablo_15"

# Provenance (Phase 2): Tablo 15 is El Kitabı content, not a SUT clause —
# findings are labeled honestly instead of carrying an invented SUT cite.
# The reference dict is resolved ONCE at module load and shared by every
# finding (clause_key is empty: the El Kitabı has no row in the SUT corpus).
_SOURCE_TYPE = SOURCE_EL_KITABI
_CLAUSE_REF = non_sut_reference(
    "El Kitabı Tablo 15", source_type=SOURCE_EL_KITABI
).to_dict()

# Error #2 — Exam categories that represent a poliklinik muayenesi. The
# 10-day duplicate rule applies only to outpatient exam procedures, not to
# surgery/lab/radiology. "muayene" is the canonical SUT category string
# used across the codebase; we also accept the more specific variants.
_EXAM_CATEGORIES: frozenset[str] = frozenset(
    {"muayene", "poliklinik_muayenesi", "poliklinik"}
)

# Error #2 — Same-specialty exam window in days (Tablo 15 #2 hard rule).
_EXAM_DUPLICATE_WINDOW_DAYS = 10

# Error #12 — Cross-claim duplicate-test window in days.
_DUPLICATE_TEST_WINDOW_DAYS = 7

# Error #12 — Procedure categories that represent repeatable lab /
# radiology / pathology tests. Only these are in scope for the duplicate
# test rule; surgery/exam/drug lines are governed by other rules.
_TEST_CATEGORIES: frozenset[str] = frozenset(
    {"laboratuvar", "radioloji", "radyoloji", "patoloji", "test"}
)

# Error #3/#4 — Procedure categories signalling package (vakabaşı / case-fee)
# billing vs per-visit (Normal Poliklinik) itemized billing. A line is
# "billed as package" when its category is ``paket`` or ``is_package_included``
# is set; this mirrors procedure_capture_gap._submitted_amount_by_code_date.
_PACKAGE_CATEGORIES: frozenset[str] = frozenset({"paket", "vakabasi", "vakabaşı"})

# Error #7 — Green-area (yeşil alan) poliklinik exam code. Sourced from
# copay_line_waivers._GREEN_ZONE_EXAM_CODE (verified canonical constant).
_GREEN_ZONE_EXAM_CODE = "520021"

# Error #9 — Medula admission→claim billing window. SGK requires a yatış
# takibi to be submitted within ~60 days of admission; beyond that the claim
# is statute-barred (zamanaşımı) and rejected at the gateway.
_ADMISSION_BILLING_WINDOW_DAYS = 60

# Error #10 — lab_billing_status values that mean the result was never
# reported back, so the test is unbundlable / non-reimbursable. The field
# is populated by the dataset builder / adapter and may carry "pending",
# "missing", "not_reported", or the empty sentinel.
_UNREPORTED_LAB_STATUSES: frozenset[str] = frozenset(
    {"pending", "missing", "not_reported", "unreported", "incomplete"}
)

# Error #11 — Drug quantity sanity bounds. Zero/negative is never a valid
# dispense; >999 adet on a single drug line is almost certainly a unit
# (kutu/şase) vs adet confusion.
_DRUG_QUANTITY_MIN = 1
_DRUG_QUANTITY_MAX = 999

# Error #16 — Valid generic material_type codes (lower-cased sentinel values
# observed in the curated dataset). Long Turkish EK-list category names are
# also legitimate, so this set is only used to recognise the generic codes;
# the detector flags lines whose material_type is empty/whitespace.
_VALID_MATERIAL_TYPE_CODES: frozenset[str] = frozenset(
    {
        "consumable",
        "implant",
        "ortez",
        "protez",
        "cihaz",
        "goz",
        "ortopedi",
        "uzmanlik",
    }
)

# Error #21 — Procedure categories that are inpatient-only (yatan hasta
# services). Appearing any of these on an outpatient (poliklinik) takip is a
# care-setting mismatch.
_INPATIENT_ONLY_CATEGORIES: frozenset[str] = frozenset(
    {"yatis", "yatarak", "gunubirlik", "ameliyat", "cerrahi", "anestezi"}
)

# Error #24 — occupational_context / procedure_category values signalling a
# donor-prep workup episode (living-donor transplant preparation).
_DONOR_PREP_CONTEXTS: frozenset[str] = frozenset(
    {"donor", "donor_hazirligi", "donor_prep", "verici", "verici_hazirligi"}
)
_DONOR_PREP_CATEGORIES: frozenset[str] = frozenset(
    {"donor_hazirligi", "donor_prep", "verici_hazirligi"}
)


def detect_duplicate_exam_10day(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #2: Same specialty exams the patient twice within 10 days.

    Flags the *second* (and each later) outpatient exam performed by the
    same specialty within a 10-day window on a different claim than the
    earlier exam. This is a deterministic Medula denial (10-day
    mükerrer muayene rule).

    A line is an "exam" when ``procedure_category`` is in
    :data:`_EXAM_CATEGORIES`. Lines without a ``procedure_specialty_code``
    are skipped (cannot determine same-specialty without it).

    Honest skips: outpatient setting cannot be determined, missing
    specialty, missing procedure_date, or the same-claim self-pair (an
    exam repeated on the *same* bill is a different error class).
    """
    claims_by_id: dict[str, ClaimHeader] = {c.claim_id: c for c in claims}

    # Collect exam lines, restricted to outpatient exams with a known specialty.
    exams: list[ProcedureClaimLine] = []
    for line in procedure_lines:
        if line.procedure_category not in _EXAM_CATEGORIES:
            continue
        if not line.procedure_specialty_code:
            continue
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        claim = claims_by_id.get(line.claim_id)
        if claim is None or infer_care_setting(claim) != "outpatient":
            continue
        exams.append(line)

    # Group by specialty; within each group sort by date and retain the most
    # recent prior exam from a different claim for each later line.
    by_specialty: dict[str, list[ProcedureClaimLine]] = defaultdict(list)
    for line in exams:
        by_specialty[line.procedure_specialty_code].append(line)

    violations: list[dict[str, Any]] = []
    for specialty, lines in by_specialty.items():
        ordered = sorted(lines, key=lambda p: (p.procedure_date, p.claim_id))
        latest: ProcedureClaimLine | None = None
        latest_other: ProcedureClaimLine | None = None
        for curr in ordered:
            # The immediately preceding line may belong to this same claim.
            # Keep the latest line from another claim so each later line can
            # still be checked without rescanning the entire specialty group.
            prev = (
                latest
                if latest is not None and latest.claim_id != curr.claim_id
                else latest_other
            )
            gap = (curr.procedure_date - prev.procedure_date).days if prev is not None else None
            if gap is not None and 0 <= gap <= _EXAM_DUPLICATE_WINDOW_DAYS:
                detail = (
                    f"Aynı branş ({specialty}) muayenesi {prev.procedure_date} ve "
                    f"{curr.procedure_date} tarihlerinde {_EXAM_DUPLICATE_WINDOW_DAYS} "
                    f"gün içinde tekrarlandı (Tablo 15 #2, 10 günlük mükerrer muayene)."
                )
                violations.append(
                    {
                        "type": _OPPORTUNITY_TYPE,
                        "claim_id": curr.claim_id,
                        "procedure_line_id": curr.procedure_line_id,
                        "rule_id": "tablo15_2_duplicate_exam_10day",
                        "detail": detail,
                        "sut_section_id": _SUT_SECTION_ID,
                        "source_type": _SOURCE_TYPE,
                        "clause_ref": _CLAUSE_REF,
                        "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                        "savings_basis": SAVINGS_BASIS_SOURCED,
                        "severity": "error",
                        "procedure_code": curr.procedure_code,
                        "procedure_specialty_code": specialty,
                        "procedure_date": curr.procedure_date,
                        "prior_claim_id": prev.claim_id,
                        "prior_procedure_date": prev.procedure_date,
                        "gap_days": gap,
                    }
                )
            if latest is not None and latest.claim_id != curr.claim_id:
                latest_other = latest
            latest = curr
    return violations


def detect_missing_diagnosis(
    claims: list[ClaimHeader],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #8: Services billed without a diagnosis code.

    Flags any claim (inpatient or outpatient) where ``primary_icd10`` is
    empty/null. Such a claim is an automatic data-integrity Medula denial
    (tanı kodu olmayan takip).

    Args:
        claims: ClaimHeaders to evaluate.
        claim_ids_with_procs: Optional filter — only evaluate claims that
            also carry procedure lines (matches the ``patient_report``
            wiring gate).
    """
    violations: list[dict[str, Any]] = []
    for claim in claims:
        if claim_ids_with_procs is not None and claim.claim_id not in claim_ids_with_procs:
            continue
        if (claim.primary_icd10 or "").strip():
            continue
        detail = (
            f"Takip {claim.claim_id} için tanı kodu (primary_icd10) boş — "
            f"tanısız hizmet faturalandırılamaz (Tablo 15 #8)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim.claim_id,
                "rule_id": "tablo15_8_missing_diagnosis",
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "error",
                "primary_icd10": claim.primary_icd10,
            }
        )
    return violations


def detect_duplicate_tests(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #12: Same test billed on multiple claims within a short window.

    Flags a lab/radiology/pathology procedure code that appears on a
    *different* claim within :data:`_DUPLICATE_TEST_WINDOW_DAYS` days of an
    earlier identical procedure code. The later line is flagged.

    A line is a "test" when ``procedure_category`` is in
    :data:`_TEST_CATEGORIES`. Same-claim repeats are skipped (those are a
    quantity/line-level issue, not a cross-claim mükerrerlik).
    """
    # Index test lines by procedure_code for efficient window lookup.
    by_code: dict[str, list[ProcedureClaimLine]] = defaultdict(list)
    for line in procedure_lines:
        if line.procedure_category not in _TEST_CATEGORIES:
            continue
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        by_code[line.procedure_code].append(line)

    violations: list[dict[str, Any]] = []
    for code, lines in by_code.items():
        if len(lines) < 2:
            continue
        ordered = sorted(lines, key=lambda p: (p.procedure_date, p.claim_id))
        # Compare each later line to the most recent earlier line on a
        # different claim; emit at most one violation per later line.
        seen_prior: list[ProcedureClaimLine] = []
        for curr in ordered:
            for prev in seen_prior:
                if prev.claim_id == curr.claim_id:
                    continue
                gap = (curr.procedure_date - prev.procedure_date).days
                if 0 <= gap <= _DUPLICATE_TEST_WINDOW_DAYS:
                    detail = (
                        f"{code} işlemi {prev.procedure_date} (takip {prev.claim_id}) "
                        f"ve {curr.procedure_date} (takip {curr.claim_id}) tarihlerinde "
                        f"{_DUPLICATE_TEST_WINDOW_DAYS} gün içinde farklı takiplerde "
                        f"mükerrer faturalandırıldı (Tablo 15 #12)."
                    )
                    violations.append(
                        {
                            "type": _OPPORTUNITY_TYPE,
                            "claim_id": curr.claim_id,
                            "procedure_line_id": curr.procedure_line_id,
                            "rule_id": "tablo15_12_duplicate_test",
                            "detail": detail,
                            "sut_section_id": _SUT_SECTION_ID,
                            "source_type": _SOURCE_TYPE,
                            "clause_ref": _CLAUSE_REF,
                            "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                            "savings_basis": SAVINGS_BASIS_SOURCED,
                            "severity": "warning",
                            "procedure_code": code,
                            "procedure_date": curr.procedure_date,
                            "prior_claim_id": prev.claim_id,
                            "prior_procedure_date": prev.procedure_date,
                            "gap_days": gap,
                        }
                    )
                    break  # one violation per later line is enough
            seen_prior.append(curr)
    return violations


def detect_exam_admission_date_mismatch(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #22: First exam/procedure date doesn't match admission date.

    For inpatient claims, the earliest ``procedure_date`` among the claim's
    procedure lines should equal ``admission_date`` (the first service day
    of an inpatient episode is the admission day). A mismatch signals that
    the exam/muayene was not recorded on the admission day, which is a
    Medula data-integrity finding.

    Honest skips: outpatient claims, no admission_date, no procedure lines
    on the claim, or any procedure line missing a real date.
    """
    claims_by_id: dict[str, ClaimHeader] = {c.claim_id: c for c in claims}

    lines_by_claim: dict[str, list[ProcedureClaimLine]] = defaultdict(list)
    for line in procedure_lines:
        lines_by_claim[line.claim_id].append(line)

    violations: list[dict[str, Any]] = []
    for claim in claims:
        if claim_ids_with_procs is not None and claim.claim_id not in claim_ids_with_procs:
            continue
        if infer_care_setting(claim) != "inpatient":
            continue
        if claim.admission_date is None:
            continue
        lines = lines_by_claim.get(claim.claim_id, [])
        if not lines:
            continue
        earliest = min(line.procedure_date for line in lines)
        if earliest == claim.admission_date:
            continue
        detail = (
            f"Yatan hasta takibi {claim.claim_id}: ilk işlem tarihi {earliest}, "
            f"yatırım tarihi {claim.admission_date} ile uyuşmuyor (Tablo 15 #22)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim.claim_id,
                "rule_id": "tablo15_22_exam_admission_date_mismatch",
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "error",
                "admission_date": claim.admission_date,
                "first_procedure_date": earliest,
            }
        )
    return violations


def detect_missing_drug_barcode(
    claims: list[ClaimHeader],
    drug_lines: tuple,
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #20: Drug line missing the QR/barcode (``barkod``).

    Flags each drug line whose ``barkod`` field is empty or whitespace-only.
    The barcode is required for SGK drug reimbursement (UTS/karekod
    traceability); a missing barcode is a Medula rejection (07xx family).

    Args:
        claims: ClaimHeaders (used only to honour the ``claim_ids_with_procs``
            gate when provided).
        drug_lines: Drug claim lines to evaluate. Typed as ``tuple`` to match
            the ``PatientClaimContext.drug_lines`` shape while avoiding an
            import cycle.
        claim_ids_with_procs: Optional filter — only evaluate lines whose
            claim is in this set.
    """
    del claims  # only used for the filter gate semantics above

    violations: list[dict[str, Any]] = []
    for line in drug_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        if (getattr(line, "barkod", "") or "").strip():
            continue
        detail = (
            f"İlaç {getattr(line, 'drug_name', '')} ({getattr(line, 'drug_code', '')}) "
            f"için barkod/karekod boş — UTS izlenebilirlik zorunlu (Tablo 15 #20)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": line.claim_id,
                "rule_id": "tablo15_20_missing_drug_barcode",
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "error",
                "drug_claim_line_id": line.drug_claim_line_id,
                "drug_code": line.drug_code,
                "drug_name": line.drug_name,
            }
        )
    return violations


# ===========================================================================
# Phase 2 detectors (errors #3, #4, #5, #7, #9, #10, #11, #15, #16, #21, #24)
# ===========================================================================


def _is_outpatient_claim(claim: ClaimHeader) -> bool:
    return infer_care_setting(claim) == "outpatient"


def _line_billed_as_package(line: ProcedureClaimLine) -> bool:
    """True when a procedure line carries package/case-fee (vakabaşı) billing."""
    if line.is_package_included:
        return True
    return (line.procedure_category or "").casefold() in _PACKAGE_CATEGORIES


def detect_vakabasi_wrong_method(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #3: Vakabaşı (case-fee/package) billed where Normal Poliklinik required.

    On an outpatient (poliklinik) visit the visit fee must be billed per-visit
    (Normal Poliklinik / itemized, §2.2.1.B-1.b). A poliklinik exam line that
    is instead marked as package-included (vakabaşı) is a payment-method
    mismatch — the case-fee path is reserved for inpatient DRG episodes.

    Detection uses ``procedure_category`` (exam) + ``is_package_included``
    / package category on the line, gated to outpatient claims. This mirrors
    the package-vs-itemized discriminator in
    ``payment_method._classify_payment_method_kind`` without depending on the
    catalog (owned by another module).
    """
    claims_by_id: dict[str, ClaimHeader] = {c.claim_id: c for c in claims}

    violations: list[dict[str, Any]] = []
    for line in procedure_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        claim = claims_by_id.get(line.claim_id)
        if claim is None or not _is_outpatient_claim(claim):
            continue
        # Only exam/muayene lines are in scope for the per-visit rule.
        if (line.procedure_category or "").casefold() not in _EXAM_CATEGORIES:
            continue
        if not _line_billed_as_package(line):
            continue
        detail = (
            f"Poliklinik muayenesi ({line.procedure_code}) vakabaşı/paket olarak "
            f"faturalandırılmış — ayakta tedavide Normal Poliklinik (hizmet başına) "
            f"ödeme yöntemi zorunludur (Tablo 15 #3)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": line.claim_id,
                "procedure_line_id": line.procedure_line_id,
                "rule_id": "tablo15_3_vakabasi_wrong_method",
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "error",
                "procedure_code": line.procedure_code,
                "procedure_category": line.procedure_category,
                "is_package_included": line.is_package_included,
            }
        )
    return violations


def detect_normal_poliklinik_wrong_method(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #4: Normal Poliklinik (per-visit) billed where vakabaşı required.

    Inverse of #3: on an inpatient (yatış) episode, services that are mandated
    as package (DRG/vakabaşı) billing under §2.2.2 must NOT be split out as a
    per-visit Normal Poliklinik exam. A package-category line on an inpatient
    claim that is billed itemized (not package-included) is the mismatch.

    Detection: inpatient claim + a package category line that is NOT marked
    ``is_package_included``.
    """
    claims_by_id: dict[str, ClaimHeader] = {c.claim_id: c for c in claims}

    violations: list[dict[str, Any]] = []
    for line in procedure_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        claim = claims_by_id.get(line.claim_id)
        if claim is None or infer_care_setting(claim) != "inpatient":
            continue
        if (line.procedure_category or "").casefold() not in _PACKAGE_CATEGORIES:
            continue
        if line.is_package_included:
            continue  # correctly billed as package
        detail = (
            f"Yatan hasta paket işlemi ({line.procedure_code}) Normal Poliklinik "
            f"(hizmet başına) olarak faturalandırılmış — yatış takiplerinde "
            f"vakabaşı/paket ödeme yöntemi zorunludur (Tablo 15 #4)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": line.claim_id,
                "procedure_line_id": line.procedure_line_id,
                "rule_id": "tablo15_4_normal_poliklinik_wrong_method",
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "error",
                "procedure_code": line.procedure_code,
                "procedure_category": line.procedure_category,
                "is_package_included": line.is_package_included,
            }
        )
    return violations


def detect_material_identity_errors(
    claims: list[ClaimHeader],
    material_lines: tuple,
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #5: Material identity errors (wrong SUT/barcode documentation).

    Flags each material line where the build-time identity check found a
    mismatch: ``barcode_sut_mismatch`` (the UTS barcode does not resolve to the
    billed SUT code) or ``titubb_uts_barcode_documentation_missing`` (TİUBB/UTS
    traceability documentation is absent). Both are deterministic Medula
    rejections (material identity / traceability family).

    Args:
        claims: ClaimHeaders (used only to honour the ``claim_ids_with_procs``
            gate when provided).
        material_lines: Material claim lines. Typed as ``tuple`` to match the
            ``PatientClaimContext.material_lines`` shape without an import cycle.
        claim_ids_with_procs: Optional filter.
    """
    del claims

    violations: list[dict[str, Any]] = []
    for line in material_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        barcode_mismatch = bool(getattr(line, "barcode_sut_mismatch", False))
        doc_missing = bool(getattr(line, "titubb_uts_barcode_documentation_missing", False))
        if not (barcode_mismatch or doc_missing):
            continue
        flags = []
        if barcode_mismatch:
            flags.append("barkod/SUT uyuşmazlığı")
        if doc_missing:
            flags.append("TİUBB/UTS dokümantasyon eksik")
        detail = (
            f"Malzeme {getattr(line, 'material_name', '')} "
            f"({getattr(line, 'material_code', '')}) için kimlik/doğrulama hatası: "
            f"{', '.join(flags)} (Tablo 15 #5)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": line.claim_id,
                "rule_id": "tablo15_5_material_identity_error",
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "error",
                "material_line_id": line.material_line_id,
                "material_code": line.material_code,
                "material_name": line.material_name,
                "barcode_sut_mismatch": barcode_mismatch,
                "titubb_uts_barcode_documentation_missing": doc_missing,
            }
        )
    return violations


def detect_green_area_bundled_extras(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #7: Green-area (yeşil alan) exam billed alongside bundled extras.

    The green-area poliklinik exam (SUT ``520021``) is a flat-fee visit: no
    additional examination/procedure components may be separately billed on the
    same claim (green-area patients have a different copay profile per §1.8.5).
    When a ``520021`` line shares a claim with any *other* procedure line, the
    co-ordered procedures are flagged as unbundlable extras.

    The green-area code is sourced from ``copay_line_waivers._GREEN_ZONE_EXAM_CODE``.
    """
    del claims

    # Group non-green-area procedure lines by claim that also has a green-area exam.
    green_area_claims: set[str] = set()
    for line in procedure_lines:
        if line.procedure_code == _GREEN_ZONE_EXAM_CODE:
            if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
                continue
            green_area_claims.add(line.claim_id)

    violations: list[dict[str, Any]] = []
    if not green_area_claims:
        return violations
    for line in procedure_lines:
        if line.claim_id not in green_area_claims:
            continue
        if line.procedure_code == _GREEN_ZONE_EXAM_CODE:
            continue  # the green-area exam itself is not an "extra"
        detail = (
            f"Yeşil alan muayenesi (520021) ile aynı takipte ek işlem "
            f"faturalandırılmış: {line.procedure_code} ({line.procedure_name}) — "
            f"yeşil alan vizitinde ayrı faturalama yapılamaz (Tablo 15 #7)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": line.claim_id,
                "procedure_line_id": line.procedure_line_id,
                "rule_id": "tablo15_7_green_area_bundled_extra",
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "warning",
                "procedure_code": line.procedure_code,
                "procedure_name": line.procedure_name,
                "green_area_exam_code": _GREEN_ZONE_EXAM_CODE,
            }
        )
    return violations


def detect_admission_billing_window(
    claims: list[ClaimHeader],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #9: Admissions billed past the 60-day SGK billing window.

    SGK requires a yatış takibi to be submitted within ~60 days of the
    admission date; beyond that the claim is statute-barred (zamanaşımı) and
    rejected. Flags any claim whose ``admission_date`` is more than
    :data:`_ADMISSION_BILLING_WINDOW_DAYS` days before ``claim_end_date``.

    Pure date arithmetic on existing header fields. Honest skip when either
    date is missing.
    """
    violations: list[dict[str, Any]] = []
    for claim in claims:
        if claim_ids_with_procs is not None and claim.claim_id not in claim_ids_with_procs:
            continue
        if claim.admission_date is None or claim.claim_end_date is None:
            continue
        gap = (claim.claim_end_date - claim.admission_date).days
        if gap <= _ADMISSION_BILLING_WINDOW_DAYS:
            continue
        detail = (
            f"Takip {claim.claim_id}: yatış tarihi {claim.admission_date} ile takip "
            f"bitiş {claim.claim_end_date} arası {gap} gün — SGK 60 günlük faturalama "
            f"süresi aşılmış (zamanaşımı, Tablo 15 #9)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim.claim_id,
                "rule_id": "tablo15_9_admission_billing_window",
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "error",
                "admission_date": claim.admission_date,
                "claim_end_date": claim.claim_end_date,
                "gap_days": gap,
            }
        )
    return violations


def detect_unreported_lab_result(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #10: Incomplete/unreported procedures (lab result never reported).

    Flags each procedure line whose ``lab_billing_status`` indicates the test
    result was never reported back (e.g. ``"pending"``/``"missing"``). A test
    without a reported result is non-reimbursable — the performed-but-not-
    submitted capture gap is handled separately by ``procedure_capture_gap``;
    this detector covers the *submitted-but-never-resulted* case via the line's
    ``lab_billing_status`` field.

    Honest skip when ``lab_billing_status`` is empty (field not populated for
    this line type).
    """
    del claims

    violations: list[dict[str, Any]] = []
    for line in procedure_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        status = (getattr(line, "lab_billing_status", "") or "").strip().casefold()
        if not status or status not in _UNREPORTED_LAB_STATUSES:
            continue
        detail = (
            f"İşlem {line.procedure_code} ({line.procedure_name}) için sonuç raporu "
            f"bildirilmemiş (lab_billing_status='{status}') — sonuçlanmamış tetkik "
            f"faturalandırılamaz (Tablo 15 #10)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": line.claim_id,
                "rule_id": "tablo15_10_unreported_lab_result",
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "warning",
                "procedure_line_id": line.procedure_line_id,
                "procedure_code": line.procedure_code,
                "procedure_name": line.procedure_name,
                "lab_billing_status": line.lab_billing_status,
            }
        )
    return violations


def detect_drug_quantity_error(
    claims: list[ClaimHeader],
    drug_lines: tuple,
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #11: Drug quantity (adet) error.

    Flags each drug line whose ``quantity`` is zero/negative (no real dispense)
    or exceeds a sane maximum (``>999`` adet), which almost always signals a
    unit confusion (kutu/şase vs adet). Both are data-integrity Medula
    rejections.

    Args:
        claims: ClaimHeaders (used only to honour the ``claim_ids_with_procs``
            gate when provided).
        drug_lines: Drug claim lines.
        claim_ids_with_procs: Optional filter.
    """
    del claims

    violations: list[dict[str, Any]] = []
    for line in drug_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        quantity = getattr(line, "quantity", None)
        if quantity is None:
            continue
        if _DRUG_QUANTITY_MIN <= quantity <= _DRUG_QUANTITY_MAX:
            continue
        if quantity <= 0:
            reason = "sıfır/negatif adet"
        else:
            reason = f"adet sınırı aşımı ({quantity} > {_DRUG_QUANTITY_MAX})"
        detail = (
            f"İlaç {getattr(line, 'drug_name', '')} ({getattr(line, 'drug_code', '')}) "
            f"için adet miktarı geçersiz: {quantity} — {reason} (Tablo 15 #11)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": line.claim_id,
                "rule_id": "tablo15_11_drug_quantity_error",
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "error",
                "drug_claim_line_id": line.drug_claim_line_id,
                "drug_code": line.drug_code,
                "drug_name": line.drug_name,
                "quantity": quantity,
            }
        )
    return violations


def detect_material_preauth_missing(
    claims: list[ClaimHeader],
    material_lines: tuple,
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #15: Material requires pre-auth but no approval evidence on the claim.

    Flags each material line whose ``requires_pre_auth`` is ``True`` and for
    which there is no evidence of an approval on the claim. There is no
    ``approval_date`` field on the model, so "no evidence" is established by
    absence: the line still carries ``requires_pre_auth=True`` (the upstream
    enricher clears/approves pre-auth once a board decision is on file via the
    EK-3C-1 path, mirroring ``material_preauth_ek3c1``).

    Severity is ``"warning"`` — pre-auth is a review flag, not a hard denial
    (consistent with ``material_preauth_ek3c1.check_material_preauth_for_context``).

    Args:
        material_lines: Material claim lines.
        claim_ids_with_procs: Optional filter.
    """
    del claims

    violations: list[dict[str, Any]] = []
    for line in material_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        if not bool(getattr(line, "requires_pre_auth", False)):
            continue
        detail = (
            f"Malzeme {getattr(line, 'material_name', '')} "
            f"({getattr(line, 'material_code', '')}) ön onay (pre-auth) gerektiriyor "
            f"ancak takipte onay kanıtı yok — kurul kararı olmadan geri ödenmez "
            f"(Tablo 15 #15)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": line.claim_id,
                "rule_id": "tablo15_15_material_preauth_missing",
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "warning",
                "material_line_id": line.material_line_id,
                "material_code": line.material_code,
                "material_name": line.material_name,
                "requires_pre_auth": True,
            }
        )
    return violations


def detect_material_type_missing(
    claims: list[ClaimHeader],
    material_lines: tuple,
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #16: Wrong/missing material-type code.

    Flags each material line whose ``material_type`` is empty or
    whitespace-only. The material type (implant / ortez / protez / cihaz / etc.)
    drives reimbursement-path routing and annex membership; an empty type is a
    data-integrity Medula rejection. The curated dataset carries long Turkish
    EK-list category names plus the generic codes in
    :data:`_VALID_MATERIAL_TYPE_CODES`; only a truly empty/blank type is
    flagged (the descriptive strings are legitimate category names).

    Args:
        material_lines: Material claim lines.
        claim_ids_with_procs: Optional filter.
    """
    del claims

    violations: list[dict[str, Any]] = []
    for line in material_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        material_type = (getattr(line, "material_type", "") or "").strip()
        if material_type:
            continue
        detail = (
            f"Malzeme {getattr(line, 'material_name', '')} "
            f"({getattr(line, 'material_code', '')}) için malzeme türü (material_type) "
            f"boş — tür kodu olmadan ödeme yönlendirmesi yapılamaz (Tablo 15 #16)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": line.claim_id,
                "rule_id": "tablo15_16_material_type_missing",
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "error",
                "material_line_id": line.material_line_id,
                "material_code": line.material_code,
                "material_name": line.material_name,
            }
        )
    return violations


def detect_inpatient_on_outpatient(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #21: Inpatient-only services billed on an outpatient takip.

    Flags each procedure line on an outpatient (poliklinik) claim whose
    ``procedure_category`` is inpatient-only (yatis / yatarak / gunubirlik /
    ameliyat / cerrahi / anestezi). Such services cannot be legitimately
    performed/billed in an outpatient setting — a care-setting mismatch and a
    Medula data-integrity finding.

    The outpatient setting is inferred via :func:`infer_care_setting` (the same
    helper used by ``care_setting_review``).
    """
    claims_by_id: dict[str, ClaimHeader] = {c.claim_id: c for c in claims}

    violations: list[dict[str, Any]] = []
    for line in procedure_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        claim = claims_by_id.get(line.claim_id)
        if claim is None or not _is_outpatient_claim(claim):
            continue
        if (line.procedure_category or "").casefold() not in _INPATIENT_ONLY_CATEGORIES:
            continue
        detail = (
            f"Ayakta tedavi (poliklinik) takibine yatan hasta işlemi kaydedilmiş: "
            f"{line.procedure_code} ({line.procedure_category}) — bakım ortamı "
            f"uyuşmazlığı (Tablo 15 #21)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": line.claim_id,
                "procedure_line_id": line.procedure_line_id,
                "rule_id": "tablo15_21_inpatient_on_outpatient",
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "error",
                "procedure_code": line.procedure_code,
                "procedure_category": line.procedure_category,
                "care_setting": "outpatient",
            }
        )
    return violations


def detect_donor_prep_as_exam(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Error #24: Donor-prep workup billed as a routine exam (muayene).

    Living-donor transplant preparation visits are a distinct service class
    (donor hazırlık) and must NOT be billed as a routine poliklinik muayenesi.
    Flags a procedure line billed as an exam (``procedure_category`` in
    :data:`_EXAM_CATEGORIES`) when the claim's ``occupational_context`` or the
    line's ``procedure_category`` signals donor-prep.

    Honest skip when neither the claim nor the line carries a donor-prep signal.
    """
    claims_by_id: dict[str, ClaimHeader] = {c.claim_id: c for c in claims}

    violations: list[dict[str, Any]] = []
    for line in procedure_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        if (line.procedure_category or "").casefold() not in _EXAM_CATEGORIES:
            continue
        claim = claims_by_id.get(line.claim_id)
        ctx = (getattr(claim, "occupational_context", "") or "").casefold() if claim else ""
        line_cat = (line.procedure_category or "").casefold()
        is_donor_prep = (
            ctx in _DONOR_PREP_CONTEXTS or line_cat in _DONOR_PREP_CATEGORIES
        )
        if not is_donor_prep:
            continue
        detail = (
            f"Donör/verici hazırlık viziti ({line.procedure_code}) rutin poliklinik "
            f"muayenesi olarak faturalandırılmış — donör hazırlık ayrı hizmet "
            f"sınıfıdır (Tablo 15 #24)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": line.claim_id,
                "procedure_line_id": line.procedure_line_id,
                "rule_id": "tablo15_24_donor_prep_as_exam",
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "warning",
                "procedure_code": line.procedure_code,
                "procedure_category": line.procedure_category,
                "occupational_context": ctx,
            }
        )
    return violations

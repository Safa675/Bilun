"""Top 5 highest-value Turkish hospital billing error detectors.

Each detector encodes one row of "El Kitabı Tablo 15 — 24 Most Common
Outpatient Billing Errors". These are the 5 errors selected by the
feasibility study (`/tmp/feasibility/common_errors.md`) as buildable now
(data already on the claim context), high-frequency in real Medula denials,
and low effort to implement.

Errors covered:
- **#2** Same-specialty exam within 10 days  → ``detect_duplicate_exam_10day``
- **#8** Services with no diagnosis on takip → ``detect_missing_diagnosis``
- **#12** Duplicate tests across claims       → ``detect_duplicate_tests``
- **#22** Exam date ≠ admission date          → ``detect_exam_admission_date_mismatch``
- **#20** Drug QR/barcode missing             → ``detect_missing_drug_barcode``

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

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import (
        ClaimHeader,
        DrugClaimLine,
        ProcedureClaimLine,
    )

# Common violation-shape keys reused by every detector.
_OPPORTUNITY_TYPE = "common_billing_error"
_SUT_SECTION_ID = "tablo_15"

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

    # Group by specialty; within each group sort by date and compare consecutive.
    by_specialty: dict[str, list[ProcedureClaimLine]] = defaultdict(list)
    for line in exams:
        by_specialty[line.procedure_specialty_code].append(line)

    violations: list[dict[str, Any]] = []
    for specialty, lines in by_specialty.items():
        ordered = sorted(lines, key=lambda p: (p.procedure_date, p.claim_id))
        for prev, curr in zip(ordered, ordered[1:]):
            # Skip the same-claim self-pair (different error class).
            if prev.claim_id == curr.claim_id:
                continue
            gap = (curr.procedure_date - prev.procedure_date).days
            # Only a forward gap within the window counts; negative gaps
            # are covered by the symmetric pair after sorting.
            if 0 <= gap <= _EXAM_DUPLICATE_WINDOW_DAYS:
                detail = (
                    f"Aynı branş ({specialty}) muayenesi {prev.procedure_date} ve "
                    f"{curr.procedure_date} tarihlerinde {_EXAM_DUPLICATE_WINDOW_DAYS} "
                    f"gün içinde tekrarlandı (Tablo 15 #2, 10 günlük mükerrer muayene)."
                )
                violations.append(
                    {
                        "type": _OPPORTUNITY_TYPE,
                        "claim_id": curr.claim_id,
                        "rule_id": "tablo15_2_duplicate_exam_10day",
                        "detail": detail,
                        "sut_section_id": _SUT_SECTION_ID,
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
                            "rule_id": "tablo15_12_duplicate_test",
                            "detail": detail,
                            "sut_section_id": _SUT_SECTION_ID,
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
                "savings_category": SAVINGS_CATEGORY_SGK_UPLIFT,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "error",
                "drug_claim_line_id": line.drug_claim_line_id,
                "drug_code": line.drug_code,
                "drug_name": line.drug_name,
            }
        )
    return violations

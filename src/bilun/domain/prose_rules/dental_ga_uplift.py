"""SUT §2-04.1 Madde 4 — dental general-anesthesia +%30 billing rule.

When EK-2/Ç (EK-2Ç) dental procedures are performed under general anesthesia
(GA), the anesthesia fee is billed as **+%30 of the dental procedure total** —
NOT as a separate anesthesia procedure line. The +30% is the only correct
billing method for anesthesia in the dental context.

This detector therefore surfaces TWO violation classes:

1. **Double-billed anesthesia (over-billing / unbundling):** A dental claim
   performed under GA that ALSO carries a separate anesthesia procedure line
   (a ``550xxx`` group code). The anesthesia line is mutually exclusive with
   the +30% uplift — billing both is an error. Flagged at ``severity="error"``.

2. **Missing GA uplift (under-billing):** Dental procedures performed under GA
   where neither the +30% uplift NOR a separate anesthesia line is present.
   This is a capture gap (recoverable SGK uplift). Flagged at
   ``severity="info"`` because the detector can confirm GA was performed (an
   anesthesia line or ``procedure_category`` marker is present on a sibling
   line) but the +30% was never applied.

The expected GA fee is computed as::

    expected_ga_fee_try = sum(dental_line.billed_amount_try for the claim) × 0.30

Dental procedures are identified via the catalog — ``lookup_procedure_code``
returns ``entry.annex == "EK-2Ç"`` for every dental code (all 4xxxxx codes).
Anesthesia codes are the ``550xxx`` range (``catalog._categorize_code`` returns
``"anesthesia"`` for 550000–559999, which covers the SUT group codes
550130–550260).

GA detection signals (any one suffices):
  - A ``550xxx`` anesthesia line shares the claim (optionally the same
    ``procedure_date``) with a dental line — this is both the GA signal and,
    per the rule, the double-bill.
  - A dental line carries a ``procedure_category`` marker indicating GA /
    sedo-analgesia (e.g. ``"dental_ga"``, ``"ga_sedoanalgesia"``), mirroring
    the ``procedure_under_ga_or_sedoanalgesia`` flag used by the
    ``dental_2_4_1`` SUT rule encoding.

See the Algoritma Rehberi §2-04.1 Madde 4 and
``data/gazette/prose_rules/dental_2_4_1.json``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.bilun.domain.catalog import lookup_procedure_code
from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules.claim_utils import infer_care_setting
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_HEURISTIC,
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_AUDIT_EXPOSURE,
    SAVINGS_CATEGORY_CAPTURE_GAP,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_OPPORTUNITY_TYPE = "dental_ga_uplift"
_SUT_SECTION_ID = "2-04.1"

# Per Algoritma Rehberi §2-04.1 Madde 4, GA anesthesia for dental work is billed
# as +%30 of the dental procedure total (not a flat anesthesia group puan).
_GA_UPLIFT_RATE = 0.30

# Anesthesia procedure codes occupy the 550xxx range (SUT EK-2B groups A1–E and
# the "birden fazla ameliyat" bands 550200–550260). ``catalog._categorize_code``
# classifies 550000–559999 as ``"anesthesia"``.
_ANESTHESIA_PREFIX = "550"


def _is_dental_code(procedure_code: str) -> bool:
    """True when ``procedure_code`` is an EK-2Ç dental procedure.

    Authoritative source is the catalog: ``entry.annex == "EK-2Ç"``. The ``4``
    prefix is a resilient fallback for codes not yet loaded into the catalog
    (all dental codes start with 4 and never collide with EK-2B code space).
    """
    result = lookup_procedure_code(procedure_code)
    entry = (result or {}).get("entry") or {}
    annex = entry.get("annex")
    if annex:
        # Normalise the ç/Ç variants defensively.
        return str(annex).strip().casefold() in {"ek-2ç", "ek-2c"}
    return procedure_code.startswith("4") and len(procedure_code) >= 6


def _is_anesthesia_code(procedure_code: str) -> bool:
    """True when ``procedure_code`` is a separately-billable anesthesia line.

    These are the 550xxx group codes (550130–550260). The dental extraction
    code ``405010`` ("Diş çekimi, infiltrasyon anestezi ile") is a *dental*
    procedure (EK-2Ç) despite its name and is correctly classified as dental
    by ``_is_dental_code`` — it will never reach this check.
    """
    return (
        len(procedure_code) >= 3
        and procedure_code.startswith(_ANESTHESIA_PREFIX)
    )


# ``procedure_category`` values that, when set on a dental line, indicate the
# procedure was performed under general anesthesia / sedo-analgesia. Mirrors
# the ``procedure_under_ga_or_sedoanalgesia`` flag in dental_2_4_1.json.
_GA_CATEGORY_MARKERS: frozenset[str] = frozenset(
    {
        "dental_ga",
        "dental_ga_sedoanalgesia",
        "ga_sedoanalgesia",
        "general_anesthesia",
        "sedoanalgesia",
    }
)


def _line_is_ga_marked(line: ProcedureClaimLine) -> bool:
    """A dental line flagged as performed under GA via its ``procedure_category``."""
    category = str(getattr(line, "procedure_category", "") or "").casefold()
    return category in _GA_CATEGORY_MARKERS


def detect_dental_ga_uplift_violations(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Detect dental general-anesthesia +%30 billing violations.

    For each claim that contains dental (EK-2Ç) procedures performed under GA,
    this detector checks for the two rule violations:

    - **Double-billed anesthesia:** a ``550xxx`` line is billed alongside the
      dental work. The anesthesia line must be removed and replaced by the
      +%30 uplift (severity ``error``).
    - **Missing uplift:** GA was performed (anesthesia signal present) but
      neither the +30% uplift nor a separate anesthesia line was billed
      (severity ``info`` — recoverable SGK uplift / capture gap).

    When the claim carries dental work WITHOUT a GA signal, nothing is emitted
    (the +30% does not apply). Non-dental procedures under anesthesia are
    surgical-anesthesia territory (SUT §2.4.4.A, ``anestezi_puani``) and are
    deliberately left untouched here.

    Args:
        claims: ClaimHeaders to evaluate.
        procedure_lines: Procedure claim lines to evaluate against.
        claim_ids_with_procs: Optional filter — only emit violations for claims
            that also have procedure lines (mirrors the wiring gate used by the
            ``anestezi_puani`` detector).

    Returns:
        Violation dicts with the standard BILUN structure: ``type``,
        ``claim_id``, ``rule_id``, ``detail`` (Turkish), ``sut_section_id``,
        ``savings_category``, ``savings_basis``, ``severity``, plus the
        computed ``expected_ga_fee_try`` (= dental total × 0.30),
        ``dental_total_try``, ``ga_uplift_rate``, and the relevant procedure
        codes.
    """
    claims_by_id: dict[str, ClaimHeader] = {c.claim_id: c for c in claims}
    violations: list[dict[str, Any]] = []

    # Bucket lines per claim up front so GA detection and double-bill detection
    # can both reason about the full claim context.
    lines_by_claim: dict[str, list[ProcedureClaimLine]] = {}
    for line in procedure_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        lines_by_claim.setdefault(line.claim_id, []).append(line)

    for claim_id, claim_lines in lines_by_claim.items():
        claim = claims_by_id.get(claim_id)
        # Dental GA applies to both inpatient and outpatient dental work — dental
        # treatment is overwhelmingly performed outpatient (ayakta). We therefore
        # do NOT gate on care setting (unlike the surgical anestezi_puani motor,
        # which is inpatient-only). ``infer_care_setting`` is referenced only to
        # surface the setting in the detail string for the auditor.

        dental_lines = [
            ln for ln in claim_lines if _is_dental_code(ln.procedure_code)
        ]
        if not dental_lines:
            continue

        anesthesia_lines = [
            ln for ln in claim_lines if _is_anesthesia_code(ln.procedure_code)
        ]

        # GA was performed if (a) an anesthesia 550xxx line is present on the
        # claim, OR (b) any dental line carries a GA procedure_category marker.
        ga_performed = bool(anesthesia_lines) or any(
            _line_is_ga_marked(ln) for ln in dental_lines
        )
        if not ga_performed:
            continue

        # Sum the dental billed total for the claim (the +30% base).
        dental_total_try = _money(
            sum(float(ln.billed_amount_try) for ln in dental_lines)
        )
        expected_ga_fee_try = _money(dental_total_try * _GA_UPLIFT_RATE)

        care_setting = infer_care_setting(claim) if claim is not None else "unknown"
        dental_codes = sorted({ln.procedure_code for ln in dental_lines})
        anesthesia_codes = sorted(
            {ln.procedure_code for ln in anesthesia_lines}
        )

        if anesthesia_lines:
            # ── Violation type 1: double-billed anesthesia ─────────────────
            # The 550xxx line is mutually exclusive with the +30% uplift. The
            # correct billing is to DROP the anesthesia line and apply +%30 to
            # the dental total. This is over-billing / unbundling.
            codes_str = ", ".join(anesthesia_codes) or "?"
            detail = (
                f"GA altında yapılan diş tedavisinde ({', '.join(dental_codes)}) "
                f"ayrı anestezi işlem hattı faturalandırılmış ({codes_str}). "
                f"Kural (§2-04.1 Madde 4): anestezi bedeli ayrı hat olarak "
                f"değil, diş işlem toplamının +%30'u olarak faturalanmalıdır. "
                f"Beklenen GA bedeli = {dental_total_try:.2f} × %30 = "
                f"{expected_ga_fee_try:.2f} TRY ({care_setting})."
            )
            violations.append(
                {
                    "type": _OPPORTUNITY_TYPE,
                    "claim_id": claim_id,
                    "rule_id": "2-04.1.4_dental_ga_double_billed_anesthesia",
                    "detail": detail,
                    "sut_section_id": _SUT_SECTION_ID,
                    "savings_category": SAVINGS_CATEGORY_AUDIT_EXPOSURE,
                    "savings_basis": SAVINGS_BASIS_SOURCED,
                    "severity": "error",
                    "violation_kind": "double_billed_anesthesia",
                    "dental_procedure_codes": dental_codes,
                    "anesthesia_procedure_codes": anesthesia_codes,
                    "dental_total_try": dental_total_try,
                    "ga_uplift_rate": _GA_UPLIFT_RATE,
                    "expected_ga_fee_try": expected_ga_fee_try,
                }
            )
        else:
            # ── Violation type 2: missing uplift (under-billing) ───────────
            # GA was performed (signal via category marker) but neither the
            # +30% uplift nor a separate anesthesia line is on the claim. This
            # is a recoverable SGK capture gap — informational.
            detail = (
                f"GA altında yapılan diş tedavisinde ({', '.join(dental_codes)}) "
                f"%30 anestezi zamkı uygulanmamış ve ayrı anestezi hattı da yok. "
                f"Beklenen GA bedeli = {dental_total_try:.2f} × %30 = "
                f"{expected_ga_fee_try:.2f} TRY ({care_setting})."
            )
            violations.append(
                {
                    "type": _OPPORTUNITY_TYPE,
                    "claim_id": claim_id,
                    "rule_id": "2-04.1.4_dental_ga_missing_uplift",
                    "detail": detail,
                    "sut_section_id": _SUT_SECTION_ID,
                    "savings_category": SAVINGS_CATEGORY_CAPTURE_GAP,
                    "savings_basis": SAVINGS_BASIS_HEURISTIC,
                    "severity": "info",
                    "violation_kind": "missing_uplift",
                    "dental_procedure_codes": dental_codes,
                    "anesthesia_procedure_codes": [],
                    "dental_total_try": dental_total_try,
                    "ga_uplift_rate": _GA_UPLIFT_RATE,
                    "expected_ga_fee_try": expected_ga_fee_try,
                    "recoverable_uplift_try": expected_ga_fee_try,
                }
            )

    return violations

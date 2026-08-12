"""SUT §4.6 — ISBT 128 barcode requirement for blood component lines.

SUT §4.6 (encoded in ``drug_indication/4.6.yaml``) makes the ISBT 128
barcode a hard payment/recording condition for blood components:

- ``4.6.ek2b_blood_component_isbt_barcode_coverage`` (§4.6.(3)): EK-2/B-billed
  blood components are paid only **provided the epicrisis states the component
  name, count and ISBT 128 blood-barcode numbers**.
- ``4.6.ek2c_blood_component_drg_unbundling_must_bill`` (§4.6.(4)): all blood
  components must be **recorded in MEDULA with their ISBT 128 barcode
  numbers**; the 705371/705430/705440 (36%), 705372/705373 (24%), 705441 (20%),
  705442/705443 (28%) codes remain partially billable in EK-2/C package
  context (the ``blood_component_partial_bill`` tier map).

This detector closes the gap: for every procedure line whose code is one of
the eight blood components, it checks the MEDULA-recorded barcode
(``ProcedureClaimLine.isbt128_barcode``) and emits an audit-exposure
violation when the barcode is absent or not a valid ISBT 128 identifier.

**Scope notes:**

- Matching is by exact SUT code (the 8 blood components). Keyword fallback is
  deliberately NOT used — blood components have a small, stable code set and
  a keyword scan would risk flagging unrelated transfusion records.
- The barcode is read from ``isbt128_barcode`` — the field the MEDULA ingest
  layer populates. When the ingest does not carry the field yet, every
  blood-component line surfaces as *missing*: that is the honest state of the
  data, not a fabricated signal (SUT still demands the barcode be recorded).
- Missing/malformed barcode is a compliance/audit-exposure issue, NOT a
  recoverable uplift — no patient_report recoverable path is wired.
- Format validation is deliberately lenient: any ``=``- or ``A``-prefixed
  13-16 char alphanumeric core passes, so genuine ISBT 128 donation
  identifiers (flag + 5-char facility + 1-char year + 7-char serial + 2
  check digits) never false-positive. The detector's job is audit-exposure
  flagging, not barcode decoding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_SOURCED,
    SAVINGS_CATEGORY_AUDIT_EXPOSURE,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_OPPORTUNITY_TYPE = "blood_component_isbt128_barcode"
_SUT_SECTION_ID = "4.6"
_RULE_ID = "blood_component_isbt128_barcode"

# The 8 SUT §4.6 EK-2/C blood components — same set the session-pricing
# partial-bill tier map covers (session_pricing_2_2_2_B.json → fractions).
_BLOOD_COMPONENT_CODES: frozenset[str] = frozenset(
    {
        "705371",  # Eritrosit süspansiyonu
        "705430",  # Tam kan
        "705440",  # Trombosit süspansiyonu
        "705372",  # Eritrosit süspansiyonu (lökosit filtrelenmiş / diğer)
        "705373",  # Eritrosit süspansiyonu (yıkanmış / diğer)
        "705441",  # Trombosit süspansiyonu (aferez / diğer)
        "705442",  # Taze donmuş plazma
        "705443",  # Taze donmuş plazma (diğer)
    }
)

# Prose rules this detector implements (data/gazette/prose_rule_sources/
# drug_indication/4.6.yaml).
_PROSE_RULE_IDS: tuple[str, ...] = (
    "4.6.ek2b_blood_component_isbt_barcode_coverage",
    "4.6.ek2c_blood_component_drg_unbundling_must_bill",
)

# ISBT 128 barcodes start with the '=' flag character (DIN data structure)
# or the legacy Codabar 'A' prefix. Anything else is not an ISBT 128
# identifier.
_ISBT128_VALID_PREFIXES: tuple[str, ...] = ("=", "A")


def _normalize_code(raw: str) -> str:
    """Normalize a procedure code for matching (mirrors catalog_membership).

    Strips a leading P/p (MEDULA package prefix), removes punctuation, and
    upper-cases so ``"p705371"``, ``"705.371"``, ``"705 371"`` all collapse
    to ``"705371"``.
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


def is_valid_isbt128_barcode(raw: str) -> bool:
    """Lenient ISBT 128 identifier check (SUT §4.6).

    Accepts the canonical 16-char DIN — ``=`` flag + 5-char facility +
    1-char year + 7-char serial + 2 check digits — as well as the legacy
    ``A``-prefixed Codabar form. The check is deliberately loose: a non-empty
    value that starts with ``=``/``A`` and whose remainder is a 13-16 char
    alphanumeric core passes. Empty/whitespace values return ``False``
    (missing).
    """
    value = (raw or "").strip()
    if not value:
        return False
    if value[0].upper() not in _ISBT128_VALID_PREFIXES:
        return False
    core = value[1:].replace(" ", "")
    if not (13 <= len(core) <= 16):
        return False
    return core.isalnum()


def detect_blood_component_isbt128_violations(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine] | None = None,
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Flag blood-component procedure lines missing a valid ISBT 128 barcode.

    For each procedure line carrying one of the 8 blood-component codes,
    read ``ProcedureClaimLine.isbt128_barcode`` (the MEDULA-recorded ISBT 128
    number). Emit one audit-exposure violation when the barcode is empty
    (``barcode_status="missing"``) or fails the lenient ISBT 128 format check
    (``barcode_status="invalid_format"``). Lines whose code is not a blood
    component are never touched.

    Args:
        claims: ClaimHeaders (used only to honour the ``claim_ids_with_procs``
            gate semantics — see ``common_billing_errors`` barcode detectors).
        procedure_lines: Procedure claim lines to evaluate.
        claim_ids_with_procs: Optional filter — only evaluate lines whose
            claim is in this set (the ``patient_report`` wiring gate).

    Returns:
        Violation dicts with: ``type``, ``claim_id``, ``rule_id``,
        ``procedure_code``, ``procedure_name``, ``procedure_line_id``,
        ``barcode_status``, ``isbt128_barcode``, ``prose_rule_ids``,
        ``detail`` (Turkish), ``sut_section_id``, ``savings_category``,
        ``savings_basis``, ``severity``.
    """
    del claims  # gate semantics only; lines carry their own claim_id

    if not procedure_lines:
        return []

    violations: list[dict[str, Any]] = []
    for line in procedure_lines:
        if claim_ids_with_procs is not None and line.claim_id not in claim_ids_with_procs:
            continue
        if _normalize_code(line.procedure_code) not in _BLOOD_COMPONENT_CODES:
            continue

        barcode = (getattr(line, "isbt128_barcode", "") or "").strip()
        if not barcode:
            status = "missing"
        elif not is_valid_isbt128_barcode(barcode):
            status = "invalid_format"
        else:
            continue

        detail = (
            f"Kan bileşeni {line.procedure_code} ({line.procedure_name}) için "
            f"ISBT 128 barkod numarası MEDULA kaydında "
            f"{'bulunmuyor' if status == 'missing' else 'geçersiz formatta'} — "
            f"tüm kan bileşenlerinin ISBT 128 barkod numaralarıyla MEDULA'ya "
            f"kaydedilmesi zorunludur (SUT §4.6)."
        )
        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": line.claim_id,
                "rule_id": _RULE_ID,
                "procedure_code": line.procedure_code,
                "procedure_name": line.procedure_name,
                "procedure_line_id": line.procedure_line_id,
                "barcode_status": status,
                "isbt128_barcode": barcode,
                "prose_rule_ids": _PROSE_RULE_IDS,
                "detail": detail,
                "sut_section_id": _SUT_SECTION_ID,
                "savings_category": SAVINGS_CATEGORY_AUDIT_EXPOSURE,
                "savings_basis": SAVINGS_BASIS_SOURCED,
                "severity": "error",
            }
        )

    return violations

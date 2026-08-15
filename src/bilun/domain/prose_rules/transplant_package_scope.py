"""SUT transplant package-scope detector — flags separately billed surgical
procedures that are bundled into the liver transplant package P609080.

Per SUT, the P609080 "Karaciğer Transplantasyonu" package states
"Tüm cerrahi işlemler dahildir" (all surgical procedures are included).
Any surgical procedure (``procedure_category == "islem"``) billed separately
on a claim that also carries a P609080 package line is therefore an
unbundling violation, unless it appears on the explicit allow-list of
separately billable items (blood components per SUT §4.6.4, certain imaging,
etc.).

The allow-list is intentionally empty at creation and MUST be populated from
SUT before this detector produces sourced findings; until then every flag it
emits is a heuristic audit exposure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code
from src.bilun.domain.prose_rules.claim_utils import infer_care_setting
from src.bilun.domain.prose_rules.types import (
    SAVINGS_BASIS_HEURISTIC,
    SAVINGS_CATEGORY_AUDIT_EXPOSURE,
)
from src.bilun.domain.sut.clause_reference import SOURCE_REHBER, non_sut_reference

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

# Liver transplant package code. ``normalize_procedure_code`` strips the "P"
# prefix so "P609080" and "609080" collapse to the same key.
_LIVER_TRANSPLANT_CODE = normalize_procedure_code("P609080")

_RULE_SET_ID = "transplant_package_scope"
_RULE_ID = "transplant_bundled_surgical_procedure"
# Structured snake_case locator (Phase 2): the rule registry carries no
# transplant entry whose coordinate resolves in the coverage parquet, so a
# SUT cite would be invented — the finding keeps an honest package-scope
# locator with rehber provenance instead.
_SUT_SECTION_ID = "p609080_package_scope"
_OPPORTUNITY_TYPE = "transplant_bundled_violation"
_BILLING_TOLERANCE = 0.02

# Provenance (Phase 2): resolved once at module load; shared by every
# finding (clause_key stays empty — no SUT-corpus row behind this locator).
_SOURCE_TYPE = SOURCE_REHBER
_CLAUSE_REF = non_sut_reference(
    "P609080 package scope", source_type=SOURCE_REHBER
).to_dict()

# Procedure categories that count as "surgical procedures" for the purposes
# of the P609080 package scope. The package prose says all *surgical*
# procedures are included; the SGK claim taxonomy marks surgical procedures
# with ``procedure_category == "islem"`` (the package itself is "paket").
_SURGICAL_CATEGORIES = frozenset({"islem"})

# Allow-list of procedure codes that remain separately billable on a liver
# transplant claim despite the "all surgical procedures included" rule.
#
# Per SUT this includes (non-exhaustive — to be confirmed against SUT):
#   - blood components per SUT §4.6.4
#   - certain imaging / diagnostics explicitly carved out
#
# NOTE: This list is intentionally EMPTY. It must be populated from SUT
# before the detector's findings should be treated as anything stronger than
# a heuristic audit exposure. Each entry is a normalized procedure code.
ALLOWED_SEPARATELY_BILLABLE_CODES: frozenset[str] = frozenset()


def _line_billed(line: ProcedureClaimLine) -> float:
    return float(line.billed_amount_try)


def _is_liver_transplant_line(line: ProcedureClaimLine) -> bool:
    return normalize_procedure_code(line.procedure_code) == _LIVER_TRANSPLANT_CODE


def _claim_has_liver_transplant(lines: list[ProcedureClaimLine]) -> bool:
    return any(_is_liver_transplant_line(line) for line in lines)


def detect_transplant_package_scope_violations(
    claim: ClaimHeader,
    lines: list[ProcedureClaimLine],
) -> list[dict[str, Any]]:
    """Flag surgical procedures separately billed on a liver-transplant claim.

    A violation is emitted for every ``procedure_category == "islem"`` line on
    a claim that also carries a P609080 (liver transplant) package line, when:

      * the claim is inpatient (transplants are inpatient — ``infer_care_setting``
        gates this), and
      * the line is actually billed (``billed_amount_try > tolerance``), and
      * the line's procedure code is NOT on the allow-list of separately
        billable items, and
      * the line is not the P609080 package line itself.

    Returns a list of violation dicts using the standard opportunity schema
    (``type``, ``claim_id``, ``rule_id``, ``detail``, ``sut_section_id``,
    ``savings_category``, ``savings_basis``).
    """
    if not lines:
        return []

    # Transplants are inpatient; do not flag outpatient claims.
    care_setting = infer_care_setting(claim)
    if care_setting != "inpatient":
        return []

    # No P609080 package line → not a transplant claim under this detector.
    if not _claim_has_liver_transplant(lines):
        return []

    violations: list[dict[str, Any]] = []
    for line in lines:
        # Skip the transplant package line itself.
        if _is_liver_transplant_line(line):
            continue

        # Only surgical procedures are in scope of the package.
        if line.procedure_category not in _SURGICAL_CATEGORIES:
            continue

        # Only flag lines that were actually billed separately.
        if _line_billed(line) <= _BILLING_TOLERANCE:
            continue

        # Allow-listed items (blood components §4.6.4, carved-out imaging,
        # etc.) remain separately billable.
        code = normalize_procedure_code(line.procedure_code)
        if code and code in ALLOWED_SEPARATELY_BILLABLE_CODES:
            continue

        billed = _line_billed(line)
        detail = (
            f"Surgical procedure {line.procedure_code} ({line.procedure_name}) "
            f"billed separately at {billed:.2f} TRY on liver transplant claim "
            f"with P609080 package; SUT requires 'Tüm cerrahi işlemler "
            f"dahildir' (all surgical procedures included)."
        )

        violations.append(
            {
                "type": _OPPORTUNITY_TYPE,
                "claim_id": claim.claim_id,
                "procedure_line_id": line.procedure_line_id,
                "procedure_code": line.procedure_code,
                "procedure_name": line.procedure_name,
                "package_code": "P609080",
                "actual_billed_try": _money(billed),
                "risk_amount_try": _money(billed),
                "savings_category": SAVINGS_CATEGORY_AUDIT_EXPOSURE,
                # Heuristic until the allow-list is populated from SUT and the
                # finding is cross-checked against §2.2 prose.
                "savings_basis": SAVINGS_BASIS_HEURISTIC,
                "included_in_sgk_total": False,
                "sut_section_id": _SUT_SECTION_ID,
                "source_type": _SOURCE_TYPE,
                "clause_ref": _CLAUSE_REF,
                "rule_id": _RULE_ID,
                "rule_set_id": _RULE_SET_ID,
                "care_setting": care_setting,
                "detail": detail,
            }
        )

    return violations

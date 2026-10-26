"""Fatura İnceleme Usul ve Esasları — documentation checklist motor.

Companion to ``fatura_inceleme.py`` (the 91 algorithmic rules that fire as
violations). This motor covers the 63 DOCUMENTATION rules from the same SGK
fatura inceleme guideline (dayanak 5510 md. 63/73). Hierarchy: SUT > this
document. Conflicts → SUT wins.

Unlike the algorithmic rules, these do NOT produce violations. They surface
"required documents" as informational warnings.

Matching:
  - Rules with ``procedure_code_any``: billed-code overlap + branch gate
    (``fatura_inceleme._branch_matches``, the algorithmic rules' own gate).
  - Code-less rules: require ``relevance_signals`` (Option B). Missing/empty
    signals → hidden. Signals are claim-shape flags derived in the context
    bridge (TPN, EK-2/C, surgery/biopsy, outpatient, inpatient/ICU, etc.).

UI dayanak uses ``fatura_inceleme_ref`` (+ optional ``sut_section_label``),
never ``gate_b_sources`` / F000 / C000 corpus ids.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from src.bilun.domain.claims.claim_type import claim_type_kind, fold_claim_type

from ..constants import _PROSE_RULES_DIR
from .fatura_inceleme import _branch_matches

_RULES_PATH = _PROSE_RULES_DIR / "fatura_inceleme_checklist.json"

_TPN_CODES = frozenset({"530430", "530980", "P530430", "P530980"})
_TPN_NAME_RE = re.compile(r"\bTPN\b|parenteral\s+n[uü]trisyon|total\s+parenteral", re.I)
_SURGERY_BIOPSY_NAME_RE = re.compile(
    r"biyopsi|eksizyon|rezeksiyon|ameliyat|cerrah[iı]|operasyon|torakotom|lamin[eo]",
    re.I,
)
# The claim type is read through the one vocabulary (claims/claim_type.py, #335);
# these folded values are the checklist's own additions to it.
_OUTPATIENT_TYPES = frozenset({"muayene"})
_INPATIENT_DAYCASE_ICU_TYPES = frozenset({"yogun_bakim", "icu", "ybu"})
_ICU_CODE_PREFIXES = ("510090", "P55200", "P55201", "P55202", "P55203", "P55206", "P55207", "P55208")


@lru_cache(maxsize=1)
def load_fatura_inceleme_checklist_rules() -> dict[str, Any]:
    """Load and cache the documentation checklist ruleset JSON."""
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def format_fi_dayanak(rule_or_ref: dict[str, Any] | str) -> str:
    """Human-readable dayanak for UI — FI section, never F000/C000 corpus ids."""
    if isinstance(rule_or_ref, str):
        ref = rule_or_ref.strip()
        sut_label = ""
    else:
        ref = str(rule_or_ref.get("fatura_inceleme_ref") or "").strip()
        sut_label = str(rule_or_ref.get("sut_section_label") or "").strip()
    if not ref:
        return ""
    basis = f"Fatura İnceleme {ref}"
    if sut_label:
        basis = f"{basis} · {sut_label}"
    return basis


def _code_overlap(rule: dict[str, Any], context: dict[str, Any]) -> bool:
    required_codes = rule.get("procedure_code_any") or []
    if not required_codes:
        return False
    billed_codes = context.get("procedure_code_any")
    if not billed_codes:
        billed_codes = context.get("procedure_code")
    if not billed_codes:
        return False
    billed_set = (
        set(billed_codes)
        if isinstance(billed_codes, (list, tuple, set))
        else {billed_codes}
    )
    return bool(billed_set & set(required_codes))


def _relevance_matches(rule: dict[str, Any], context: dict[str, Any]) -> bool:
    """Option B: code-less rules need every listed relevance signal true."""
    signals = rule.get("relevance_signals") or []
    if not signals:
        return False
    flags = context.get("relevance_flags") or {}
    for signal in signals:
        if not flags.get(signal):
            return False
    return True


def _condition_matches(rule: dict[str, Any], context: dict[str, Any]) -> bool:
    """Code-gated rules use code overlap; code-less rules use relevance_signals."""
    required_codes = rule.get("procedure_code_any") or []
    if required_codes:
        return _code_overlap(rule, context)
    return _relevance_matches(rule, context)


def _requirement_from_rule(rule: dict[str, Any], ruleset_id: str) -> dict[str, Any]:
    """Build the informational requirement dict for a matched rule."""
    return {
        "procedure_code": sorted(rule.get("procedure_code_any") or []),
        "required_documents": list(rule.get("required_documents") or []),
        "rule_source": ruleset_id,
        "fatura_inceleme_ref": rule.get("fatura_inceleme_ref", ""),
        "sut_section_label": rule.get("sut_section_label") or "",
        "sut_anchor": format_fi_dayanak(rule),
        "message_tr": rule.get("message_tr", ""),
    }


def check_fatura_inceleme_checklist(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate the documentation checklist against a flat claim context dict."""
    if not _RULES_PATH.is_file():
        return []
    return _evaluate(load_fatura_inceleme_checklist_rules(), context)


def _evaluate(
    ruleset: dict[str, Any], context: dict[str, Any]
) -> list[dict[str, Any]]:
    ruleset_id = ruleset.get("rule_set_id", "")
    requirements: list[dict[str, Any]] = []
    for rule in ruleset.get("rules") or []:
        if not _branch_matches(rule.get("branch"), context):
            continue
        if not _condition_matches(rule, context):
            continue
        requirements.append(_requirement_from_rule(rule, ruleset_id))
    return requirements


def _fold_department(raw: str | None) -> str:
    text = (raw or "").strip().lower()
    return text.translate(
        str.maketrans(
            {
                "ı": "i",
                "ş": "s",
                "ğ": "g",
                "ü": "u",
                "ö": "o",
                "ç": "c",
            }
        )
    )


def _compute_relevance_flags(
    *,
    header: Any,
    procedure_lines: list[Any],
    drug_lines: list[Any] | None = None,
) -> dict[str, bool]:
    """Derive Option-B relevance flags from claim header + lines."""
    from src.bilun.domain.prose_rules.catalog_membership import procedure_annex_membership

    raw_claim_type = getattr(header, "claim_type", None)
    claim_type = fold_claim_type(raw_claim_type)
    kind = claim_type_kind(raw_claim_type)
    dept = (getattr(header, "department", None) or "").lower()
    discharge = getattr(header, "discharge_date", None)

    has_ek2b = False
    has_ek2c = False
    has_tpn = False
    has_surgery_or_biopsy = False
    has_icu_code = False
    discharge_day_with_ek2b = False

    for line in procedure_lines:
        code = str(getattr(line, "procedure_code", "") or "")
        name = str(getattr(line, "procedure_name", "") or "")
        category = str(getattr(line, "procedure_category", "") or "").lower()
        service_date = getattr(line, "procedure_date", None)
        as_of = service_date or getattr(header, "claim_start_date", None)

        if code in _TPN_CODES or _TPN_NAME_RE.search(name):
            has_tpn = True
        if any(code.startswith(prefix) for prefix in _ICU_CODE_PREFIXES):
            has_icu_code = True

        in_ek2b, in_ek2c = False, False
        if code:
            try:
                in_ek2b, in_ek2c = procedure_annex_membership(code, as_of_date=as_of)
            except (TypeError, ValueError, KeyError, AttributeError):
                in_ek2b, in_ek2c = False, False
        if in_ek2b:
            has_ek2b = True
        if in_ek2c or code.startswith("P"):
            has_ek2c = True

        if (
            in_ek2c
            or code.startswith("P")
            or category in {"paket", "ameliyat", "cerrahi"}
            or _SURGERY_BIOPSY_NAME_RE.search(name)
        ):
            has_surgery_or_biopsy = True

        if (
            discharge is not None
            and service_date is not None
            and service_date == discharge
            and (in_ek2b or (code and not in_ek2c))
        ):
            # Prefer explicit EK-2/B membership; fall back to non-package itemized.
            if in_ek2b:
                discharge_day_with_ek2b = True

    for line in drug_lines or []:
        name = str(getattr(line, "drug_name", "") or "")
        if _TPN_NAME_RE.search(name):
            has_tpn = True

    dept_folded = _fold_department(dept)
    # An ER visit (acil) is outpatient but not a polyclinic visit; a provision
    # ground (koruyucu, meslek_hastaligi) is neither.
    is_outpatient = (
        kind == "poliklinik" or claim_type in _OUTPATIENT_TYPES or "poliklinik" in dept_folded
    )
    is_inpatient_daycase_or_icu = (
        kind in ("yatis", "gunubirlik")
        or claim_type in _INPATIENT_DAYCASE_ICU_TYPES
        or has_icu_code
        or "yogun" in dept_folded
        or "ybu" in dept_folded
    )

    return {
        "is_outpatient_polyclinic": is_outpatient,
        "has_ek2c": has_ek2c,
        "has_ek2b": has_ek2b,
        "has_surgery_or_biopsy": has_surgery_or_biopsy,
        "has_tpn": has_tpn,
        "is_inpatient_daycase_or_icu": is_inpatient_daycase_or_icu,
        "discharge_day_with_ek2b": discharge_day_with_ek2b,
    }


def _build_fatura_inceleme_checklist_context(ctx: Any) -> dict[str, Any]:
    """Bridge a PatientClaimContext → flat dict for the checklist motor."""
    if not ctx.claims:
        return {}
    header = ctx.claims[0]
    claim_id = getattr(header, "claim_id", None)

    def _lines_for_claim(attr: str) -> list[Any]:
        return [
            line
            for line in (getattr(ctx, attr, ()) or ())
            if getattr(line, "claim_id", None) == claim_id
        ]

    procedure_lines = _lines_for_claim("procedure_lines")
    drug_lines = _lines_for_claim("drug_lines") if hasattr(ctx, "drug_lines") else []

    context: dict[str, Any] = {
        "department": header.department or "",
        "provider_specialty": getattr(header, "procedure_specialty_code", "") or "",
        "claim_type": getattr(header, "claim_type", "") or "",
        "relevance_flags": _compute_relevance_flags(
            header=header,
            procedure_lines=procedure_lines,
            drug_lines=drug_lines,
        ),
    }

    if procedure_lines:
        codes = {p.procedure_code for p in procedure_lines if p.procedure_code}
        if codes:
            context["procedure_code_any"] = sorted(codes)
            if len(codes) == 1:
                context["procedure_code"] = next(iter(codes))

    return context


def check_fatura_inceleme_checklist_for_context(
    ctx: Any,
) -> list[dict[str, Any]]:
    """Evaluate the documentation checklist against a PatientClaimContext."""
    context = _build_fatura_inceleme_checklist_context(ctx)
    if not context:
        return []
    return check_fatura_inceleme_checklist(context)

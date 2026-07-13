"""Fatura İnceleme Usul ve Esasları — documentation checklist motor.

Companion to ``fatura_inceleme.py`` (the 91 algorithmic rules that fire as
violations). This motor covers the 63 DOCUMENTATION rules from the same SGK
fatura inceleme guideline (dayanak 5510 md. 63/73). Hierarchy: SUT > this
document. Conflicts → SUT wins.

Unlike the algorithmic rules, these do NOT produce violations. They surface
"required documents" — epikriz/report presence checks — as informational
warnings so reviewers know which supporting documents (patoloji raporu,
ameliyat notu, fotoğraf, alış faturası, etc.) the inceleyici will request for
a given procedure.

The motor is intentionally simpler than ``gap_closing.py``'s 4-layer pattern:
matching is just ``procedure_code_any`` membership (with the same ORTAK/branch
gate as ``fatura_inceleme.py``). Rules with an empty ``procedure_code_any``
list are ORTAK/general and surface for any in-scope claim via their branch
gate (mostly null-branch ORTAK rules, plus a few branch-general rules that
name no specific code).
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from ..constants import _PROSE_RULES_DIR

_RULES_PATH = _PROSE_RULES_DIR / "fatura_inceleme_checklist.json"

# Reuse the same branch → keyword map as fatura_inceleme.py so the branch
# gate is consistent across both motors. Kept here (not imported) to keep the
# checklist motor self-contained and avoid a hard dependency on the algorithmic
# motor's internals.
_BRANCH_KEYWORDS: dict[str, list[str]] = {
    "ANESTEZİ VE REANİMASYON": ["anestezi", "reanimasyon"],
    "BEYİN VE SİNİR CERRAHİSİ": ["beyin", "sinir cerrahisi", "norosirurji"],
    "DERMATOLOJİ": ["dermatoloji"],
    "ÇOCUK SAĞLIĞI VE HASTALIKLARI": ["çocuk sağlığı", "çocuk hastalıkları", "pediatri"],
    "ÇOCUK CERRAHİSİ": ["çocuk cerrahisi"],
    "İÇ HASTALIKLARI": ["iç hastalıkları", "dahiliye"],
    "ENFEKSİYON HASTALIKLARI VE KLİNİK MİKROBİYOLOJİ": ["enfeksiyon", "mikrobiyoloji"],
    "FİZİK TEDAVİ VE REHABİLİTASYON": ["fizik tedavi", "rehabilitasyon", "ftr"],
    "GENEL CERRAHİ": ["genel cerrahi"],
    "GÖĞÜS CERRAHİSİ": ["göğüs cerrahisi", "toraks cerrahisi"],
    "GÖĞÜS HASTALIKLARI": ["göğüs hastalıkları", "göğüs", "toraks"],
    "GÖZ HASTALIKLARI": ["göz", "göz hastalıkları", "oftalmoloji"],
    "KARDİYOLOJİ": ["kardiyoloji"],
    "KALP VE DAMAR CERRAHİSİ": ["kalp damar cerrahisi", "kvc"],
    "KULAK BURUN BOĞAZ": ["kulak burun boğaz", "kbb", "ent"],
    "KADIN HASTALIKLARI VE DOĞUM": ["kadın hastalıkları", "doğum", "jinekoloji", "obstetri"],
    "NÖROLOJİ": ["nöroloji"],
    "ORTOPEDİ VE TRAVMATOLOJİ": ["ortopedi", "travmatoloji"],
    "PATOLOJİ": ["patoloji"],
    "PLASTİK VE REKONSTRÜKTİF CERRAHİ": ["plastik cerrahi", "rekonstrüktif"],
    "PSİKİYATRİ": ["psikiyatri"],
    "RADYASYON ONKOLOJİSİ": ["radyasyon onkolojisi", "radyoterapi"],
    "ÜROLOJİ": ["üroloji"],
    "RADYOLOJİ": ["radyoloji"],
    "NÜKLEER TIP": ["nükleer tıp"],
    "DİYALİZ": ["diyaliz"],
    "ACİL TIP HEKİMLİĞİ": ["acil tip", "acil servis", "emergency"],
}


@lru_cache(maxsize=1)
def load_fatura_inceleme_checklist_rules() -> dict[str, Any]:
    """Load and cache the documentation checklist ruleset JSON."""
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _branch_matches(rule_branch: str | None, context: dict[str, Any]) -> bool:
    """Check if a rule's branch matches the claim's department/specialty.

    ORTAK rules (branch=null) match all claims. Branch-specific rules match
    when the claim's department/specialty contains any of the branch's
    keywords. Same semantics as ``fatura_inceleme._branch_matches``.
    """
    if rule_branch is None:
        return True  # ORTAK — applies to all branches
    keywords = _BRANCH_KEYWORDS.get(rule_branch, [])
    if not keywords:
        return False  # Unknown branch — honest skip
    dept = (context.get("department") or "").lower()
    specialty = (context.get("provider_specialty") or "").lower()
    combined = f"{dept} {specialty}"
    return any(kw in combined for kw in keywords)


def _condition_matches(rule: dict[str, Any], context: dict[str, Any]) -> bool:
    """Evaluate a checklist rule's match condition.

    Simpler than ``gap_closing._condition_matches``: a rule matches when the
    claim's billed procedure codes overlap the rule's ``procedure_code_any``
    list. Rules with an empty ``procedure_code_any`` are general (matched
    purely on their branch gate) — they always match the code condition so
    the branch gate is the sole discriminator.
    """
    required_codes = rule.get("procedure_code_any") or []
    if not required_codes:
        return True  # General documentation rule — no code gate
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


def _requirement_from_rule(rule: dict[str, Any], ruleset_id: str) -> dict[str, Any]:
    """Build the informational requirement dict for a matched rule.

    This is NOT a violation — it surfaces which supporting documents the
    inceleyici will request, keyed to the originating Fatura İnceleme clause.
    """
    return {
        "procedure_code": sorted(rule.get("procedure_code_any") or []),
        "required_documents": list(rule.get("required_documents") or []),
        "rule_source": ruleset_id,
        "fatura_inceleme_ref": rule.get("fatura_inceleme_ref", ""),
        "message_tr": rule.get("message_tr", ""),
    }


def check_fatura_inceleme_checklist(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate the documentation checklist against a flat claim context dict.

    Returns a list of informational "required documents" entries. Does NOT
    produce violations — callers should treat these as advisory requirements,
    not denials.
    """
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


def _build_fatura_inceleme_checklist_context(ctx: Any) -> dict[str, Any]:
    """Bridge a PatientClaimContext → flat dict for the checklist motor.

    Reuses the same context-derivation shape as
    ``fatura_inceleme._build_fatura_inceleme_context`` (and gap_closing's
    pattern) but only surfaces the fields this motor actually consumes:
    ``procedure_code_any``, ``department`` and ``provider_specialty``.
    """
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

    context: dict[str, Any] = {
        "department": header.department or "",
        "provider_specialty": getattr(header, "procedure_specialty_code", "") or "",
    }

    procedure_lines = _lines_for_claim("procedure_lines")
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
    """Evaluate the documentation checklist against a PatientClaimContext.

    Bridges the checklist evaluator (which takes a flat dict) to the typed
    PatientClaimContext via ``_build_fatura_inceleme_checklist_context``.
    """
    context = _build_fatura_inceleme_checklist_context(ctx)
    if not context:
        return []
    return check_fatura_inceleme_checklist(context)

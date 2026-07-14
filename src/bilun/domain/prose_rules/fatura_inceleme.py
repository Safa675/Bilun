"""Fatura İnceleme Usul ve Esasları prose rules — SGK billing audit guideline.

NOT SUT. This is SGK's internal fatura inceleme rehberi (dayanak: 5510
md. 63/73). Hierarchy: SUT > this document. Conflicts → SUT wins.

91 algorithmic rules from 28 branches + Ortak Kriterler (common criteria).
Rules fire as violations when claim data matches denial conditions — e.g.
"acilde kontrol muayenesi ödenmez" fires when care_setting=emergency and
the procedure is a kontrol muayenesi.

The motor follows the gap_closing.py 4-layer pattern:
- ``load_fatura_inceleme_rules()`` — cached JSON loader
- ``_evaluate()`` — iterate rules, match conditions, collect violations
- ``_condition_matches()`` — predicate engine (bools, scalars, sets, annex)
- ``_build_fatura_inceleme_context()`` — PatientClaimContext → flat dict bridge

The ``branch`` field on each rule gates firing: ORTAK rules (branch=null)
fire for all claims; branch-specific rules only fire when the claim's
department/provider_specialty matches the rule's branch.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from ..constants import _PROSE_RULES_DIR
from .facility_tier import normalize_facility_tier
from .gap_closing import _condition_matches, _derive_payment_method_path

_RULES_PATH = _PROSE_RULES_DIR / "fatura_inceleme_prose.json"

# Branch name → normalized tokens for matching against department/specialty.
# The Fatura İnceleme document uses Turkish branch names; the claim header
# carries a free-text ``department`` field. We match on keyword overlap.
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
def load_fatura_inceleme_rules() -> dict[str, Any]:
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _branch_matches(rule_branch: str | None, context: dict[str, Any]) -> bool:
    """Check if a rule's branch matches the claim's department/specialty.

    ORTAK rules (branch=null) match all claims. Branch-specific rules
    match when the claim's department contains any of the branch's keywords.
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


def _violation_from_rule(
    rule: dict[str, Any],
    ruleset_id: str,
) -> dict[str, Any]:
    action = rule.get("action") or {}
    billable = bool(action.get("billable", True))
    message = (
        action.get("denial_tr")
        or action.get("payment_tr")
        or action.get("message_tr")
        or rule.get("rule_id", "")
    )
    return {
        "rule": ruleset_id,
        "severity": action.get("severity", "warning"),
        "message": message,
        "savings_try": 0.0,
        "risk_amount": 0.0,
        "sut_section": rule.get("sut_section", ""),
        "rule_id": rule.get("rule_id", ""),
        "billable": billable,
        "material_outcome": "must_bill" if billable else "no_pay",
        "annex_basis": action.get("annex_basis"),
        "details": {
            "prose_rule_set": ruleset_id,
            "fatura_inceleme_ref": rule.get("fatura_inceleme_ref", ""),
        },
    }


def check_fatura_inceleme(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate Fatura İnceleme rules against a claim context dict."""
    if not _RULES_PATH.is_file():
        return []
    return _evaluate(load_fatura_inceleme_rules(), context)


def _evaluate(ruleset: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    ruleset_id = ruleset.get("rule_set_id", "")
    violations: list[dict[str, Any]] = []
    for rule in ruleset.get("rules") or []:
        # Branch gate: skip rules whose branch doesn't match the claim's department
        if not _branch_matches(rule.get("branch"), context):
            continue
        condition = rule.get("condition") or {}
        if not _condition_matches(condition, context):
            continue
        violations.append(_violation_from_rule(rule, ruleset_id))
    return violations


def _build_fatura_inceleme_context(ctx: Any) -> dict[str, Any]:
    """Build the flat claim-context dict from a PatientClaimContext.

    Reuses gap_closing's context derivation pattern — same fields, same
    honesty guards — plus ``department`` and ``provider_specialty`` for
    the branch-matching gate.
    """
    if not ctx.claims:
        return {}
    header = ctx.claims[0]
    claim_id = getattr(header, "claim_id", None)

    def _lines_for_claim(attr: str) -> list[Any]:
        return [
            line for line in (getattr(ctx, attr, ()) or ())
            if getattr(line, "claim_id", None) == claim_id
        ]

    # procedure_specialty_code lives on ProcedureClaimLine, NOT ClaimHeader.
    # The first billed procedure line's specialty is the claim-level signal.
    proc_lines = _lines_for_claim("procedure_lines")
    provider_specialty = ""
    if proc_lines:
        provider_specialty = getattr(proc_lines[0], "procedure_specialty_code", "") or ""

    context: dict[str, Any] = {
        "facility_tier": header.facility_tier or "",
        "provider_type": header.provider_type or "",
        "claim_type": header.claim_type or "",
        "department": header.department or "",
        "provider_specialty": provider_specialty,
    }

    # Care setting
    claim_type_lower = (header.claim_type or "").lower()
    if "yatis" in claim_type_lower or "inpatient" in claim_type_lower:
        context["care_setting"] = "inpatient"
    elif (
        "ayakta" in claim_type_lower
        or "outpatient" in claim_type_lower
        or "poliklinik" in claim_type_lower
        or "gunubirlik" in claim_type_lower
    ):
        context["care_setting"] = "outpatient"
    else:
        context["care_setting"] = claim_type_lower or "outpatient"

    # Emergency detection
    dept = (header.department or "").lower()
    tag = (header.scenario_tag or "").lower()
    context["is_emergency"] = (
        "acil" in dept or "emergency" in dept or "acil" in tag or "emergency" in tag
    )

    # Facility contracting
    context["facility_uncontracted"] = header.provider_type in ("uncontracted", "sozlesmesiz")
    context["facility_contracted"] = header.provider_type not in ("uncontracted", "sozlesmesiz", "")

    # Procedure-derived fields
    procedure_lines = _lines_for_claim("procedure_lines")
    if procedure_lines:
        categories = {p.procedure_category for p in procedure_lines if p.procedure_category}
        codes = {p.procedure_code for p in procedure_lines if p.procedure_code}
        if categories:
            context["procedure_category_any"] = sorted(categories)
            if len(categories) == 1:
                context["procedure_category"] = next(iter(categories))
        if codes:
            context["procedure_code_any"] = sorted(codes)
            if len(codes) == 1:
                context["procedure_code"] = next(iter(codes))

    # Payment method
    payment_method = _derive_payment_method_path(
        header, procedure_lines, care_setting=context["care_setting"]
    )
    if payment_method is not None:
        context["payment_method"] = payment_method
        if payment_method == "fee_for_service":
            context["payment_method_path"] = "itemized"

    # Provider contract status
    if header.provider_type in ("sozlesmeli", "contracted", "private"):
        context["provider_contract_status"] = "contracted"
    elif header.provider_type in ("uncontracted", "sozlesmesiz"):
        context["provider_contract_status"] = "uncontracted"

    # Visit type
    if "gunubirlik" in claim_type_lower:
        context["visit_type"] = "gunubirlik"

    # Facility type
    provider_type_lower = (header.provider_type or "").lower()
    if any(
        token in provider_type_lower
        for token in ("universite", "egitim_arastirma", "training_research")
    ):
        context["facility_type"] = "training_research_hospital"

    # Facility tier basamak
    tier_context = normalize_facility_tier(
        header.facility_tier, provider_type=header.provider_type
    )
    if tier_context.basamak is not None:
        context["facility_tier_basamak"] = tier_context.basamak

    # Emergency excluded
    if context["is_emergency"]:
        context["emergency_excluded"] = True

    # Drug-derived fields
    drug_lines = _lines_for_claim("drug_lines")
    if drug_lines:
        reports = [d for d in drug_lines if d.drug_specialty_board_report_present]
        context["health_report_present"] = bool(reports)
        drug_categories = {getattr(d, "drug_category", None) or "" for d in drug_lines} - {""}
        if drug_categories:
            context["drug_category_any"] = sorted(drug_categories)
            if len(drug_categories) == 1:
                context["drug_category"] = next(iter(drug_categories))

    # Material-derived fields
    material_lines = _lines_for_claim("material_lines")
    if material_lines:
        material_categories = {m.specialty_category for m in material_lines if m.specialty_category}
        if material_categories:
            context["material_category_any"] = sorted(material_categories)
            if len(material_categories) == 1:
                context["material_category"] = next(iter(material_categories))

    return context


def check_fatura_inceleme_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Evaluate Fatura İnceleme rules against a PatientClaimContext.

    Bridges the fatura inceleme evaluator (which takes a flat dict) to the
    typed PatientClaimContext via ``_build_fatura_inceleme_context``.
    """
    context = _build_fatura_inceleme_context(ctx)
    if not context:
        return []
    return check_fatura_inceleme(context)

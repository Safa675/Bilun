"""SUT gap-closing prose rules — cross-section claim-context gates.

Two rule sets live here, both encoding whole-claim (not line-level) billing
gates that close coverage gaps across §1.5, §1.6, §1.8, §2.2, §2.3, §2.5:

- ``gap_closing_misc`` (40 rules) — §1.5/§1.6 provider-contracting + §3/§4/§5
  cross-cutting no-pay/must-bill gates.
- ``gap_closing_treatment_2`` (44 rules) — §2.2 payment-method + §2.3/§2.5
  treatment-scoped bundling and overseas/emergency gates.

Conditions are predominantly boolean flags evaluated against a flat
``context`` dict (claim-level facts pre-computed by the adapter), with a few
``*_any`` set-membership predicates over claim fields (procedure_category,
diagnosis, facility_tier, provider_type). Rules whose conditions reference
data not present on the claim (``hours_since_onset``, ``stem_cell_type``,
``overseas_treatment_days``) are skipped at evaluation time rather than
guessing — they stay in the rule set for inventory/coverage but do not fire
on claims lacking that data.

``action.billable`` maps to a billable outcome; ``denial_tr``/``payment_tr``
carries the regulatory message.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from ..constants import _PROSE_RULES_DIR

_MISC_RULES_PATH = _PROSE_RULES_DIR / "gap_closing_misc.json"
_TREATMENT_RULES_PATH = _PROSE_RULES_DIR / "gap_closing_treatment_2.json"

# Condition keys that are NOT boolean flags but set/scalar predicates resolved
# against claim fields. Anything not in this set is treated as a boolean flag
# looked up via context.get(key).
_SET_PREDICATE_SUFFIXES = ("_any", "_in", "_not_in", "_not_any")
_SCALAR_FIELDS = {
    "procedure_category",
    "procedure_code",
    "payment_method",
    "provider_type",
    "specialty",
    "visit_type",
    "care_setting",
    "treatment_setting",
    "patient_category",
    "anesthesia_type",
    "stage",
    "indication",
    "drug_category",
    "material_category",
    "facility_tier",
    "expense_type",
    "test_type",
}


@lru_cache(maxsize=1)
def load_gap_closing_misc_rules() -> dict[str, Any]:
    with _MISC_RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_gap_closing_treatment_rules() -> dict[str, Any]:
    with _TREATMENT_RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _condition_matches(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    """Evaluate a gap-closing rule condition against a flat claim context.

    Each condition key is resolved as:
    - boolean flag → ``context.get(key)`` must equal the condition value;
    - ``*_any`` predicate → at least one claim value in the set must be present
      in the context's collection for that base field;
    - scalar field → ``context.get(field)`` must equal the condition value.

    Keys absent from ``context`` cause the rule to be skipped (returns False)
    rather than firing on missing data — this is the honesty guard.
    """
    for key, expected in condition.items():
        if key.endswith(_SET_PREDICATE_SUFFIXES):
            base = key[: -_suffix_len(key)]
            # Prefer the explicit <base>_any / <base>_in collection when the
            # context builder supplied one; fall back to the base field so a
            # single-valued claim still matches. A bare scalar base field is
            # a valid (single-element) collection, but a multi-valued claim
            # MUST surface its full set under the *_any key — otherwise rules
            # like procedure_category_any silently honest-skip on claims that
            # genuinely carry the listed category.
            available = context.get(key)
            if available is None:
                available = context.get(base)
            if available is None:
                return False
            # Normalize to a set for membership testing regardless of shape.
            available_set = (
                set(available) if isinstance(available, (list, tuple, set))
                else {available}
            )
            expected_set = (
                set(expected) if isinstance(expected, (list, tuple, set))
                else {expected}
            )
            if key.endswith("_not_any") or key.endswith("_not_in"):
                # Negated membership: NONE of the expected may be present.
                if available_set & expected_set:
                    return False
            else:
                if not (available_set & expected_set):
                    return False
            continue

        if isinstance(expected, bool) or key in _SCALAR_FIELDS:
            actual = context.get(key)
            if actual is None:
                # Flag/scalar not surfaced on this claim → skip, do not guess.
                return False
            if bool(actual) != bool(expected) if isinstance(expected, bool) else actual != expected:
                return False
            continue

        # Unknown predicate shape → skip rather than mis-evaluate.
        return False

    return True


def _suffix_len(key: str) -> int:
    for suffix in _SET_PREDICATE_SUFFIXES:
        if key.endswith(suffix):
            return len(suffix)
    return 0


def _violation_from_rule(
    rule: dict[str, Any],
    ruleset_id: str,
) -> dict[str, Any]:
    action = rule.get("action") or {}
    billable = bool(action.get("billable", True))
    message = action.get("denial_tr") or action.get("payment_tr") or action.get("message_tr") or rule.get("rule_id", "")
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
        },
    }


def check_gap_closing_misc(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate the §1.5/§1.6/§3-§6 gap-closing rules against a claim context."""
    if not _MISC_RULES_PATH.is_file():
        return []
    return _evaluate(load_gap_closing_misc_rules(), context)


def check_gap_closing_treatment(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate the §2.2/§2.3/§2.5 treatment gap-closing rules against a claim context."""
    if not _TREATMENT_RULES_PATH.is_file():
        return []
    return _evaluate(load_gap_closing_treatment_rules(), context)


def _evaluate(ruleset: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    ruleset_id = ruleset.get("rule_set_id", "")
    violations: list[dict[str, Any]] = []
    for rule in ruleset.get("rules") or []:
        condition = rule.get("condition") or {}
        if not _condition_matches(condition, context):
            continue
        violations.append(_violation_from_rule(rule, ruleset_id))
    return violations


def _derive_payment_method_path(
    header: Any,
    procedures: list[Any],
    *,
    care_setting: str,
) -> str | None:
    """Derive the §2.2.2.B claim-level payment *path* the gap-closing rules gate on.

    The rules use a different vocabulary from the procedure-level
    ``package``/``itemized`` decision: ``diagnosis_based`` = tanıya dayalı
    (EK-2/C DRG package path), ``fee_for_service`` = hizmet başına (EK-2/B
    itemized path). These map cleanly onto the claim-aggregated
    ``PaymentMethodKind`` already computed by ``care_setting_review`` /
    ``claim_strategy``:

    - ``DRG_MANDATORY`` / ``DRG_OVERRIDABLE`` → ``diagnosis_based``
      (both are EK-2/C package paths; overridable still bills as package
      unless the third-tier override is exercised)
    - ``ITEMIZED`` → ``fee_for_service``

    Returns ``None`` when there are no classifiable procedure lines or the
    kind cannot be resolved — the caller MUST leave ``payment_method`` unset
    in that case so ``_condition_matches`` honesty-skips rather than guessing.
    """
    if procedures:
        # Local import to avoid an import cycle: care_setting_review imports
        # from this package's neighbors and would otherwise pull in heavy
        # catalog machinery at module load time.
        from .care_setting_review import _resolve_claim_kind

        kind = _resolve_claim_kind(header, procedures, care_setting=care_setting)
        if kind in {"DRG_MANDATORY", "DRG_OVERRIDABLE"}:
            return "diagnosis_based"
        if kind == "ITEMIZED":
            return "fee_for_service"
        # MISSING_INPUTS / NOT_IN_SUT / None → fall through to the header signal.
    # Header-only fallback: package_candidate=True is a weaker but real signal
    # that a DRG package line is present on the claim (set by the synthetic
    # generators when an EK-2/C package line exists).
    if getattr(header, "package_candidate", None) is True:
        return "diagnosis_based"
    return None


def _build_gap_closing_context(ctx: Any) -> dict[str, Any]:
    """Build the flat claim-context dict from a PatientClaimContext.

    Maps ``ClaimHeader`` fields + derives the most common gap-closing flags
    from existing claim data. Many of the ~118 condition keys will be absent
    (honest skip via ``_condition_matches``). The keys surfaced here cover the
    most frequent conditions: ``procedure_category``, ``is_emergency``,
    ``care_setting``, ``payment_method``, ``facility_*``, ``procedure_code_any``,
    ``drug_category``, ``health_report_present``.
    """
    if not ctx.claims:
        return {}
    header = ctx.claims[0]
    # Scope line aggregations to the first claim only. A PatientClaimContext
    # can carry multiple bills for one patient; aggregating every line while
    # reading header fields from claims[0] would let a second bill's
    # procedures/drugs/materials contaminate this claim's derived flags
    # (procedure_category_any, payment_method, drug_category, ...). This
    # mirrors the claim-scoping the gazette_repricing / material_uplift
    # wrappers apply.
    claim_id = getattr(header, "claim_id", None)

    def _lines_for_claim(attr: str) -> list[Any]:
        return [
            line for line in (getattr(ctx, attr, ()) or ())
            if getattr(line, "claim_id", None) == claim_id
        ]

    context: dict[str, Any] = {
        "facility_tier": header.facility_tier or "",
        "provider_type": header.provider_type or "",
        "claim_type": header.claim_type or "",
    }
    # Care setting: inpatient (yatis) vs outpatient (ayakta/poliklinik) vs
    # day-case (gunubirlik, billed as outpatient per SUT §2.2). The
    # gap-closing JSON expects "inpatient" / "outpatient"; fall back to
    # "outpatient" for unrecognized outpatient-style visit types rather than
    # leaking the raw Turkish token, which _resolve_claim_kind would then
    # mis-classify as inpatient.
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
    # Emergency: department or scenario_tag carries emergency signal.
    dept = (header.department or "").lower()
    tag = (header.scenario_tag or "").lower()
    context["is_emergency"] = (
        "acil" in dept or "emergency" in dept or "acil" in tag or "emergency" in tag
    )
    # Facility contracting: uncontracted if provider_type indicates it.
    # The Turkish contracted/uncontracted marker is "sozlesmesiz" (single s);
    # the synthetic generators use exactly this spelling — see
    # scripts/synthetic/gen/materials_flags.py ("acil_sozlesmesiz_kurum").
    context["facility_uncontracted"] = header.provider_type in ("uncontracted", "sozlesmesiz")
    context["facility_contracted"] = header.provider_type not in ("uncontracted", "sozlesmesiz", "")
    # Health report: drug lines carry board-report presence.
    drug_lines = _lines_for_claim("drug_lines")
    if drug_lines:
        reports = [d for d in drug_lines if d.drug_specialty_board_report_present]
        context["health_report_present"] = bool(reports)
    # Procedure-derived fields.
    procedure_lines = _lines_for_claim("procedure_lines")
    if procedure_lines:
        categories = {p.procedure_category for p in procedure_lines if p.procedure_category}
        codes = {p.procedure_code for p in procedure_lines if p.procedure_code}
        # Surface BOTH shapes so every predicate form can match:
        # - the bare scalar field (procedure_category / procedure_code) is read
        #   by exact-equality rules (11 gap-closing rules use bare
        #   procedure_category); when the claim has multiple distinct values we
        #   cannot pick one truthfully, so we leave it unset and let those rules
        #   honest-skip rather than mis-attribute.
        # - the *_any collection key is read by membership predicates
        #   (procedure_category_any / procedure_code_any); it carries the full
        #   set so any listed value matches.
        if categories:
            context["procedure_category_any"] = sorted(categories)
            if len(categories) == 1:
                context["procedure_category"] = next(iter(categories))
        if codes:
            context["procedure_code_any"] = sorted(codes)
            if len(codes) == 1:
                context["procedure_code"] = next(iter(codes))
    # Payment method (§2.2.2.B path): derived from the claim-aggregated
    # PaymentMethodKind, NOT from package_candidate directly. The kind-based
    # derivation is the canonical SUT §2.2 evaluator's output; package_candidate
    # is only a header-level fallback. See _derive_payment_method_path.
    payment_method = _derive_payment_method_path(
        header, procedure_lines, care_setting=context["care_setting"]
    )
    if payment_method is not None:
        context["payment_method"] = payment_method
    # Drug-derived fields.
    if drug_lines:
        drug_categories = set()
        for d in drug_lines:
            cat = getattr(d, "drug_category", None) or ""
            if cat:
                drug_categories.add(cat)
        if drug_categories:
            context["drug_category"] = sorted(drug_categories)[:1][0]
    # Material-derived fields.
    material_lines = _lines_for_claim("material_lines")
    if material_lines:
        material_categories = {m.specialty_category for m in material_lines if m.specialty_category}
        if material_categories:
            context["material_category"] = sorted(material_categories)[:1][0]
    return context


def check_gap_closing_misc_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Evaluate §1.5/§1.6/§3-§6 gap-closing rules against a PatientClaimContext.

    Wiredness epic W1.3 — bridges the gap_closing evaluator (which takes a flat
    dict) to the typed PatientClaimContext via ``_build_gap_closing_context``.
    """
    context = _build_gap_closing_context(ctx)
    if not context:
        return []
    return check_gap_closing_misc(context)


def check_gap_closing_treatment_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Evaluate §2.2/§2.3/§2.5 treatment gap-closing rules against a PatientClaimContext.

    Wiredness epic W1.3 — bridges the gap_closing evaluator to the typed context.
    """
    context = _build_gap_closing_context(ctx)
    if not context:
        return []
    return check_gap_closing_treatment(context)

"""SUT §2.4 treatment-pricing prose rules — claim-context gates.

This evaluator clones the proven ``gap_closing`` pattern (JSON loader + predicate
engine + context builder + ``check_*_for_context`` entry point) for the
``treatment_pricing_2_4`` rule set (182 rules covering §2.4.1–§2.4.L:
radiosurgery, dialysis, IVF, physiotherapy, ICU, palliative care, etc.).

Scope (Wiredness epic W3): only rules whose condition keys are ENTIRELY within
the wireable set are able to fire — every key must be derivable from a
``PatientClaimContext`` field:

- ``procedure_category`` / ``procedure_category_any`` ← ``ProcedureClaimLine.procedure_category``
- ``procedure_code_any`` ← ``ProcedureClaimLine.procedure_code``
- ``provider_type`` ← ``ClaimHeader.provider_type``
- ``facility_not_in`` / ``facility_type_any`` ← ``ClaimHeader.facility_tier``
- ``diagnosis_any`` / ``diagnosis_in`` ← ``ClaimDiagnosis.icd10_code`` (PREFIX matching)
- ``health_board_report_present`` ← ``DrugClaimLine.drug_specialty_board_report_present``

The remaining ~165 rules (≈142+ in the planner's coarser tally) reference keys
that are NOT present on a ``PatientClaimContext`` — IVF cycle counters, session
frequency windows, BMI, clinical scores, board-report tier, etc. They are kept in
the loaded rule set for inventory/coverage but ``_condition_matches`` returns
``False`` for them (honest skip — never a silent no-op guessing the value).

Two correctness points ported from the plan's W2.5 lessons:

1. ICD-10 PREFIX match: ``diagnosis_in: ["E11"]`` MUST match a billed
   ``"E11.9"``. The drug_indication evaluator does prefix matching;
   ``gap_closing`` does exact set intersection only. We port the prefix logic
   (``_diagnosis_matches``) so diagnosis predicates behave correctly.
2. ``*_any`` keys: when a claim carries multiple distinct procedure categories,
   the predicate MUST read the ``procedure_category_any`` collection (list),
   not the bare scalar (which is left unset on ambiguous claims).
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from ..constants import _PROSE_RULES_DIR

_RULES_PATH = _PROSE_RULES_DIR / "treatment_pricing_2_4.json"
_RULESET_ID = "treatment_pricing_2_4"

# Condition-key suffixes that denote set-membership predicates (positive or
# negated). Mirrors gap_closing._SET_PREDICATE_SUFFIXES (a separate copy kept
# here so the two rule sets can evolve independently).
_SET_PREDICATE_SUFFIXES = ("_any", "_in", "_not_in", "_not_any")

# Scalar (exact-equality) fields surfaced by the context builder. Everything
# not in this set and not ending in a predicate suffix is treated as an unknown
# predicate shape → honest skip.
_SCALAR_FIELDS = {
    "procedure_category",
    "provider_type",
    "health_board_report_present",
}

# Fields where membership is resolved via ICD-10 PREFIX matching (not exact
# intersection). diagnosis_any/diagnosis_in both funnel through
# ``_diagnosis_matches``.
_DIAGNOSIS_KEYS = {"diagnosis_any", "diagnosis_in"}


@lru_cache(maxsize=1)
def load_treatment_pricing_rules() -> dict[str, Any]:
    """Load ``treatment_pricing_2_4.json`` (cached).

    Returns the raw JSON document (``rule_set_id`` + ``rules`` list). The caller
    must NOT mutate the returned dict — it is shared via the lru_cache.
    """
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _diagnosis_matches(codes: list[str], rule_codes: list[str]) -> bool:
    """ICD-10 PREFIX membership — ported from drug_indication._diagnosis_matches_rule.

    A billed ``code`` matches a rule ``listed`` code when they are equal OR the
    billed code starts with ``listed + "."`` (so ``"E11"`` matches ``"E11.9"``).
    Codes are normalized to upper-case + stripped before comparison.

    Returns ``True`` if ANY billed code matches ANY rule code. Empty
    ``rule_codes`` is treated as "no diagnosis restriction" → ``True`` (the
    other condition keys on the rule still gate firing).
    """
    listed = [str(c).strip().upper() for c in (rule_codes or []) if c]
    if not listed:
        return True
    for raw in codes or []:
        code = str(raw or "").strip().upper()
        if not code:
            continue
        if code in listed:
            return True
        for prefix in listed:
            if code == prefix or code.startswith(prefix + "."):
                return True
    return False


def _suffix_len(key: str) -> int:
    """Length of the trailing predicate suffix on ``key`` (0 if none)."""
    for suffix in _SET_PREDICATE_SUFFIXES:
        if key.endswith(suffix):
            return len(suffix)
    return 0


def _condition_matches(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    """Evaluate a treatment-pricing rule condition against a flat claim context.

    Each condition key is resolved as:

    - ``diagnosis_any`` / ``diagnosis_in`` → ICD-10 PREFIX match of the rule's
      listed codes against ``context["diagnosis_codes"]`` (the billed set).
    - ``*_any`` / ``*_in`` (other bases) → set INTERSECTION: at least one rule
      value must be in the context collection surfaced under ``<key>`` (or the
      base scalar when only that is present).
    - ``*_not_in`` / ``*_not_any`` → negated membership: NONE of the rule values
      may be in the context collection.
    - scalar field → ``context.get(field)`` must equal the condition value.
    - boolean flag → ``context.get(key)`` must equal the flag.

    A key absent from ``context`` ⇒ return ``False`` (honest skip — do not
    guess). This is what makes the ~165 out-of-scope rules honest-skip: their
    keys (``sessions_within_6mo``, ``ivf_cycle``, ``bmi``, …) are never surfaced
    by ``_build_treatment_pricing_context``, so every such rule fails its first
    unresolvable key and never fires.
    """
    for key, expected in condition.items():
        # Diagnosis predicates — prefix matching, not exact intersection.
        if key in _DIAGNOSIS_KEYS:
            billed = context.get("diagnosis_codes")
            if billed is None:
                return False
            rule_codes = (
                list(expected) if isinstance(expected, (list, tuple, set)) else [expected]
            )
            if not _diagnosis_matches(billed, rule_codes):
                return False
            continue

        if key.endswith(_SET_PREDICATE_SUFFIXES):
            base = key[: -_suffix_len(key)]
            # Prefer the explicit <key> collection the builder surfaced; fall
            # back to the base scalar so a single-valued claim still matches a
            # *_any predicate (gap_closing parity). A bare scalar base is a
            # valid single-element collection, but a multi-valued claim MUST
            # surface its full set under the *_any key — otherwise the predicate
            # silently honest-skips (the W2.5b lesson).
            available = context.get(key)
            if available is None:
                available = context.get(base)
            if available is None:
                return False
            available_set = (
                set(available) if isinstance(available, (list, tuple, set)) else {available}
            )
            expected_set = (
                set(expected) if isinstance(expected, (list, tuple, set)) else {expected}
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
            if isinstance(expected, bool):
                if bool(actual) != bool(expected):
                    return False
            elif actual != expected:
                return False
            continue

        # Unknown predicate shape (e.g. out-of-scope session/IVF/BMI keys) →
        # skip rather than mis-evaluate.
        return False

    return True


def _violation_from_rule(rule: dict[str, Any], ruleset_id: str) -> dict[str, Any]:
    """Build a violation dict from a firing rule (mirrors gap_closing shape)."""
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
        },
    }


def _evaluate(ruleset: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    ruleset_id = ruleset.get("rule_set_id", _RULESET_ID)
    violations: list[dict[str, Any]] = []
    for rule in ruleset.get("rules") or []:
        condition = rule.get("condition") or {}
        if not _condition_matches(condition, context):
            continue
        violations.append(_violation_from_rule(rule, ruleset_id))
    return violations


def _build_treatment_pricing_context(ctx: Any) -> dict[str, Any]:
    """Map a ``PatientClaimContext`` to the flat dict treatment-pricing rules gate on.

    Surfaces keys: ``procedure_category``, ``procedure_category_any``,
    ``procedure_code_any``, ``provider_type``, ``facility_tier``,
    ``facility_type_any``, ``diagnosis_codes`` (list, for prefix matching),
    ``health_board_report_present``.

    Multi-claim handling: when ``ctx.claims`` carries more than one bill, the
    caller (billing orchestrator) is expected to iterate ``ctx.claims`` and
    ``slice_for_claim`` per bill. This builder evaluates ``ctx.claims[0]`` and
    scopes every line aggregation to that claim's ``claim_id`` so a second
    bill's procedures/diagnoses cannot contaminate this claim's context (parity
    with ``_build_gap_closing_context``'s scoping).
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
        "provider_type": header.provider_type or "",
        # facility_tier is the canonical field; facility_type_any/facility_not_in
        # predicates read the same value via the base-scalar fallback in
        # _condition_matches.
        "facility_tier": header.facility_tier or "",
    }

    # Procedure-derived fields.
    procedure_lines = _lines_for_claim("procedure_lines")
    if procedure_lines:
        categories = {p.procedure_category for p in procedure_lines if p.procedure_category}
        codes = {p.procedure_code for p in procedure_lines if p.procedure_code}
        if categories:
            # Surface the full set under the *_any key so membership predicates
            # match on multi-category claims (W2.5b). The bare scalar is only
            # set when the claim has a single, unambiguous category — otherwise
            # exact-equality rules honest-skip rather than mis-attribute.
            context["procedure_category_any"] = sorted(categories)
            if len(categories) == 1:
                context["procedure_category"] = next(iter(categories))
        if codes:
            context["procedure_code_any"] = sorted(codes)

    # Diagnosis-derived fields (for prefix matching). Pull from both the
    # header primary icd10 and the diagnosis rows, scoped to this claim.
    diagnosis_codes: list[str] = []
    primary = str(getattr(header, "primary_icd10", "") or "").strip().upper()
    if primary:
        diagnosis_codes.append(primary)
    for dg in _lines_for_claim("diagnoses"):
        code = str(getattr(dg, "icd10_code", "") or "").strip().upper()
        if code and code not in diagnosis_codes:
            diagnosis_codes.append(code)
    if diagnosis_codes:
        context["diagnosis_codes"] = diagnosis_codes

    # Health board report (specialty board report) presence — surfaced from
    # drug lines. DrugClaimLine carries drug_specialty_board_report_present.
    # When there are drug lines but none carry the flag as True, we surface
    # False (a positive signal the flag is absent); when there are NO drug
    # lines at all we leave the key unset so rules honest-skip rather than
    # guessing False on a claim that simply has no pharmacy data.
    drug_lines = _lines_for_claim("drug_lines")
    if drug_lines:
        reports = [d for d in drug_lines if getattr(d, "drug_specialty_board_report_present", None)]
        context["health_board_report_present"] = bool(reports)

    return context


def check_treatment_pricing_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Evaluate the §2.4 treatment-pricing rules against a ``PatientClaimContext``.

    Entry point bridging the typed claim context to the rule evaluator. Builds
    the flat context dict, iterates the loaded rules, and emits one violation
    per firing rule. Rules whose condition keys are not derivable from
    ``PatientClaimContext`` (IVF cycles, session windows, BMI, clinical scores,
    …) honest-skip — they never fire here. Each violation carries:
    ``rule_id``, ``rule`` (``"treatment_pricing_2_4"``), ``severity`` (from the
    action), ``sut_section``, and the Turkish ``denial_tr`` message.
    """
    context = _build_treatment_pricing_context(ctx)
    if not context:
        return []
    if not _RULES_PATH.is_file():
        return []
    return _evaluate(load_treatment_pricing_rules(), context)

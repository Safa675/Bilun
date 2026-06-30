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

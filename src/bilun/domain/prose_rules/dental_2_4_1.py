"""SUT §2.4.1 dental prose rules — partial (3 wireable rules).

Of the 10 §2.4.1 dental rules, only 3 evaluate against claim data currently
surfaced on material/procedure lines:

- ``2.4.1.(1).precious_metal_no_pay`` — precious-metal restoration materials
  (altın/platin/...) are not reimbursed.
- ``2.4.1.(2).bone_implant_no_pay_default`` — dental implants without a
  medical-necessity board report are not reimbursed.
- ``2.4.1.B-3.(1).treating_physician_continuity`` — treatment by a physician
  who is a first-degree relative and signed the board report is not paid.

The remaining 7 rules require ``patient_age``, ``years_since_last_prosthesis``,
``facility_type``, ``board_from``/``board_includes`` — data not on the claim
model. They stay in the rule set for inventory/coverage but are skipped at
evaluation time (honesty guard) rather than guessing.

Operates on material-line dicts (like specialty_materials) since dental rules
key on ``material_name`` and ``procedure_category``.
"""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from typing import Any

from ..constants import _PROSE_RULES_DIR

_RULES_PATH = _PROSE_RULES_DIR / "dental_2_4_1.json"

# Conditions that resolve against material-line fields.
_MAPPABLE = {"material_name_any", "procedure_category", "procedure_category_any"}


def _normalize_tr(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


@lru_cache(maxsize=1)
def load_dental_2_4_1_rules() -> dict[str, Any]:
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _material_name_matches(material_name: str, keywords: list[str]) -> bool:
    normalized = _normalize_tr(material_name)
    if not normalized:
        return False
    return any(_normalize_tr(kw) in normalized for kw in keywords)


def _condition_matches(condition: dict[str, Any], mat: dict[str, Any]) -> bool:
    for key, expected in condition.items():
        if key == "material_name_any":
            name = str(mat.get("name") or mat.get("material_name") or "")
            if not _material_name_matches(name, expected or []):
                return False
            continue
        if key in ("procedure_category", "procedure_category_any"):
            cat = mat.get("procedure_category")
            if cat is None:
                return False
            expected_set = {expected} if isinstance(expected, str) else set(expected or [])
            if cat not in expected_set:
                return False
            continue
        # Boolean flag resolved against the material line.
        actual = mat.get(key)
        if actual is None:
            return False
        if bool(actual) != bool(expected):
            return False
    return True


def _violation_from_rule(rule: dict[str, Any]) -> dict[str, Any]:
    action = rule.get("action") or {}
    billable = bool(action.get("billable", True))
    return {
        "rule": "dental_2_4_1",
        "severity": action.get("severity", "warning"),
        "material_name": rule.get("rule_id", ""),
        "message": action.get("denial_tr") or action.get("payment_tr") or rule.get("rule_id", ""),
        "savings_try": 0.0,
        "risk_amount": 0.0,
        "sut_section": rule.get("sut_section", "2.4.1"),
        "rule_id": rule.get("rule_id", ""),
        "billable": billable,
        "material_outcome": "must_bill" if billable else "no_pay",
        "annex_basis": action.get("annex_basis"),
    }


def check_dental_2_4_1_prose(materials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evaluate the wireable §2.4.1 dental rules on material dict lines."""
    if not _RULES_PATH.is_file():
        return []
    ruleset = load_dental_2_4_1_rules()
    violations: list[dict[str, Any]] = []
    for mat in materials:
        for rule in ruleset.get("rules") or []:
            condition = rule.get("condition") or {}
            if not _condition_matches(condition, mat):
                continue
            violations.append(_violation_from_rule(rule))
            break
    return violations

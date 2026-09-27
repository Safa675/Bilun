"""SUT §2.4.1 dental prose rules — partial (3 wireable rules).

Of the 10 §2.4.1 dental rules, only 3 evaluate against claim data currently
surfaced on material/procedure lines:

- ``2.4.1.(1).precious_metal_no_pay`` — precious-metal restoration materials
  (altın/platin/...) are not reimbursed.
- ``2.4.1.(2).bone_implant_no_pay_default`` — dental implants without a
  medical-necessity board report are not reimbursed.
- ``2.4.1.B-3.(1).treating_physician_continuity`` — treatment by a physician
  who is a first-degree relative and signed the board report is not paid.

The remaining dormant rules require ``patient_age``, ``years_since_last_prosthesis``,
``board_from``/``board_includes`` — data not on the claim model. ``facility_type``
is now derived from the claim header and surfaced in each material dict. The
schema-gap fields stay in the rule set for inventory/coverage but are skipped
at evaluation time (honesty guard) rather than guessing.

Operates on material-line dicts (like specialty_materials) since dental rules
key on ``material_name`` and ``procedure_category``.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from typing import Any

from ..constants import _PROSE_RULES_DIR

_RULES_PATH = _PROSE_RULES_DIR / "dental_2_4_1.json"


# Rule-specific boolean conditions surfaced on the material dict. None of these
# are first-class fields on ``MaterialClaimLine`` today (they will land as the
# model is extended); the ``_for_context`` shim copies them through ``hasattr``
# so rules whose flag is absent are honestly skipped by ``_condition_matches``
# rather than guessed — the same guard the module already applies to the 7
# non-wireable §2.4.1 rules.
#
# ``material_contains_precious_metal`` is the exception: the
# ``precious_metal_no_pay`` rule already gates on its own ``material_name_any``
# keyword list (altın/platin/…), so the boolean flag is a redundant mirror of
# that keyword match. Because ``MaterialClaimLine`` does not carry the flag,
# ``hasattr`` always returns False in production and the rule would never fire.
# The ``_for_context`` shim therefore computes it locally from the rule's
# authoritative keyword list (see ``_precious_metal_keywords``) — no model
# change required. The other three flags stay ``hasattr``-gated.
_DENTAL_CLAIM_FLAGS: tuple[str, ...] = (
    "material_contains_precious_metal",
    "medical_necessity_board_report",
    "treating_physician_different_from_board_signatory",
    "patient_in_first_degree_relative_of_physician",
)

# §2.4.1 board-report / signatory / kinship flags that the SUT treats as
# "absent ⇒ False" (their negative default). When a rule gates on one of
# these being false, an absent flag must match rather than honest-skip —
# otherwise the default no-pay rule (e.g. 2.4.1.(2).bone_implant_no_pay_default)
# never fires on typical lines that don't set the flag.
_OPTIONAL_DEFAULT_FALSE_FLAGS: frozenset[str] = frozenset({
    "medical_necessity_board_report",
    "treating_physician_different_from_board_signatory",
    "patient_in_first_degree_relative_of_physician",
    "material_contains_precious_metal",
})


def _normalize_tr(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


@lru_cache(maxsize=1)
def load_dental_2_4_1_rules() -> dict[str, Any]:
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def _precious_metal_keywords() -> tuple[str, ...]:
    """Keyword list driving ``2.4.1.(1).precious_metal_no_pay``.

    Pulled from the rule's own ``material_name_any`` condition so the local
    ``material_contains_precious_metal`` computation stays in lockstep with the
    authoritative rule text (a single source of truth — no second hand-maintained
    keyword list).
    """
    keywords: list[str] = []
    for rule in load_dental_2_4_1_rules().get("rules") or []:
        if rule.get("rule_id") == "2.4.1.(1).precious_metal_no_pay":
            condition = rule.get("condition") or {}
            keywords = list(condition.get("material_name_any") or [])
            break
    return tuple(keywords)


def _material_name_matches(material_name: str, keywords: list[str]) -> bool:
    """Match a named material without treating its explicit absence as presence.

    Negation is local to an occurrence or a joined list of named materials:
    ``altın ve platin içermeyen`` denies both, while ``altın içermeyen platin
    içeren`` still supplies affirmative platinum evidence. Other matching and
    normalization behavior remains the same; this is not a composition parser.
    """
    normalized = _normalize_tr(material_name)
    if not normalized:
        return False
    terms = [re.escape(_normalize_tr(kw)) for kw in keywords if kw]
    if not terms:
        return False
    # An explicit conjunction joins a negated list; punctuation alone must
    # not pull an independently named product into a later negative phrase.
    joined_terms = r"(?:\s*(?:/|\+|\bve\b|\bveya\b)\s*(?:" + "|".join(terms) + r"))*"
    negation = re.compile(
        r"(?:s[ıiu]z\b|" + joined_terms + r"\s+(?:icermeyen|icermez)\b)"
    )
    return any(
        not negation.match(normalized, match.end())
        for term in terms
        for match in re.finditer(term, normalized)
    )


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
        if key in ("facility_type", "facility_type_any"):
            ft = mat.get("facility_type")
            if ft is None:
                return False
            expected_set = {expected} if isinstance(expected, str) else set(expected or [])
            if ft not in expected_set:
                return False
            continue
        # Boolean flag resolved against the material line.
        actual = mat.get(key)
        if actual is None:
            # The §2.4.1 board-report / signatory flags are OPTIONAL on the
            # claim — their regulatory default is "absent ⇒ False" (e.g. an
            # implant with no medical-necessity board report defaults to
            # no-pay per 2.4.1.(2).bone_implant_no_pay_default, which gates on
            # ``medical_necessity_board_report: false``). Treating absent as
            # False (rather than honest-skipping) lets the default no-pay rule
            # fire on typical implant lines that never set the flag. Scoped to
            # the known optional flags so unrelated boolean conditions keep
            # their honesty guard.
            if key in _OPTIONAL_DEFAULT_FALSE_FLAGS:
                actual = False
            else:
                return False
        if bool(actual) != bool(expected):
            return False
    return True


def _violation_from_rule(rule: dict[str, Any], mat: dict[str, Any] | None = None) -> dict[str, Any]:
    action = rule.get("action") or {}
    billable = bool(action.get("billable", True))
    # risk_amount follows the convention used by material_bundling /
    # specialty_materials: for a no_pay outcome the provider risks the billed
    # amount, so surface it as risk. Other outcomes stay 0 (no savings/risk
    # signal is meaningful without a pricing decision).
    risk_amount = 0.0
    if not billable and mat is not None:
        risk_amount = float(
            mat.get("unit_price")
            or mat.get("billed_amount_try")
            or mat.get("billed_amount")
            or 0
        )
    return {
        "rule": "dental_2_4_1",
        "severity": action.get("severity", "warning"),
        "material_name": mat.get("name") or mat.get("material_name") or rule.get("rule_id", "") if mat else rule.get("rule_id", ""),
        "message": action.get("denial_tr") or action.get("payment_tr") or rule.get("rule_id", ""),
        "savings_try": 0.0,
        "risk_amount": risk_amount,
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
            violations.append(_violation_from_rule(rule, mat))
            break
    return violations


def _build_dental_materials(ctx: Any) -> list[dict[str, Any]]:
    """Build the existing dental material rows in exact input-line order.

    Mirrors ``material_bundling.check_material_bundling_for_context`` /
    ``specialty_materials.check_specialty_materials_for_context``: build the
    material dict shape ``check_dental_2_4_1_prose`` expects from each
    ``MaterialClaimLine``, then delegate to the canonical evaluator.

    §2.4.1 conditions key on ``procedure_category`` (a field of
    ``ProcedureClaimLine``, NOT ``MaterialClaimLine`` — see ``claims/models.py``
    line 67). A material's procedure category is resolved via its
    ``procedure_line_id`` against the context's procedure lines; materials with
    no resolvable category fall back to their ``specialty_category`` so a dental
    specialty line still feeds ``procedure_category`` consumers.

    The rule-specific booleans (``material_contains_precious_metal``,
    ``medical_necessity_board_report``, …) are not yet first-class
    ``MaterialClaimLine`` fields. They are copied through ``hasattr`` so the
    module's existing honesty guard (``_condition_matches`` skips rules whose
    condition data is absent rather than guessing) keeps the non-surfaced rules
    silent. ``facility_type`` is derived from the claim header and injected
    into each material dict so ~7 rules gating on facility type now fire.
    The remaining dormant rules require ``patient_age``, ``board_from``/
    ``board_includes`` — schema-gap fields not on the claim model.
    """
    # Index procedure lines by procedure_line_id so each material resolves its
    # own category (a patient with mixed dental + non-dental lines must not
    # cross-contaminate).
    proc_category_by_id = {
        line.procedure_line_id: line.procedure_category
        for line in ctx.procedure_lines
        if getattr(line, "procedure_category", None)
    }

    # Derive facility_type from the claim header — same logic as gap_closing
    # and treatment_pricing context builders. Unblocks ~7 dental rules that
    # gate on facility_type / facility_type_any.
    facility_type: str | None = None
    if ctx.claims:
        header = ctx.claims[0]
        provider_type_lower = (header.provider_type or "").lower()
        facility_tier_lower = (header.facility_tier or "").lower()
        if any(
            token in provider_type_lower
            for token in ("universite", "egitim_arastirma", "training_research")
        ) and "vakif" not in provider_type_lower and "vakif" not in facility_tier_lower:
            facility_type = "training_research_hospital"
        elif "vakif" in provider_type_lower or "vakif" in facility_tier_lower:
            facility_type = "foundation_university"
        elif (
            provider_type_lower in ("private", "ozel")
            or facility_tier_lower in ("ozel", "2_3_basamak_ozel", "private")
            or "ozel" in facility_tier_lower
        ):
            facility_type = "private"

    materials: list[dict[str, Any]] = []
    precious_keywords = _precious_metal_keywords()
    for line in ctx.material_lines:
        row: dict[str, Any] = {
            "name": line.material_name,
            "code": line.material_code,
            "unit_price": float(line.billed_amount_try),
            **({"facility_type": facility_type} if facility_type else {}),
            # procedure_category lives on ProcedureClaimLine; resolve via the
            # material's procedure_line_id, falling back to the material's own
            # specialty_category (e.g. "dental_restoration") when no linked
            # procedure line carries the category.
            "procedure_category": proc_category_by_id.get(
                line.procedure_line_id
            ) or getattr(line, "specialty_category", ""),
        }
        for flag in _DENTAL_CLAIM_FLAGS:
            if hasattr(line, flag):
                row[flag] = getattr(line, flag)
        # ``material_contains_precious_metal`` is not a first-class
        # ``MaterialClaimLine`` field (the ``hasattr`` loop above never sees it),
        # so compute it locally from the ``precious_metal_no_pay`` rule's own
        # ``material_name_any`` keyword list. The keyword match is already done
        # by ``_material_name_matches``; this flag is a redundant mirror of it,
        # surfaced here so ``_condition_matches`` does not skip the rule on a
        # missing boolean condition.
        if precious_keywords and _material_name_matches(
            str(line.material_name or ""), list(precious_keywords)
        ):
            row["material_contains_precious_metal"] = True
        materials.append(row)

    return materials


def check_dental_2_4_1_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Run the original first-winning-rule evaluator on the material bridge."""
    return check_dental_2_4_1_prose(_build_dental_materials(ctx))

"""SUT §4.2 drug-combination / sequential / off-indication prose — claim matcher.

Wave 4 (W4) of the Wiredness epic. This evaluator detects **concurrent drug
pairs/triplets billed on the SAME claim** (plus a couple of single-drug
no-pay gates) using INN name matching, and emits honest violations.

Scope is deliberately narrower than the full 53-rule corpus: only the subset
of rules whose ``condition`` keys are derivable from a ``PatientClaimContext``
(``drug_name_any``, ``diagnosis_any``, ``drug_name_set_any_two``,
``drug_name_set_all``, ``concurrent_drug_name_any``, plus the
``concurrent`` / ``combination`` / ``two_distinct_*`` boolean predicates that
mean "≥2 distinct drugs on the same claim") can fire. Rules that gate on
``drug_class`` maps, PD-L1 / ECOG, EMR history, prior-therapy timing,
facility tier, etc. are **honestly skipped** (deferred) rather than silently
no-op'd — ``_check_combo_condition`` returns a ``reason`` string so the
orchestrator can count deferred rules and their blocking reasons.

Combos are evaluated WITHIN ONE CLAIM (grouped by ``claim_id``), never across
a patient's whole history — a sequential rule across two bills needs the EMR
timeline, which this engine does not ingest.

INN-name and ICD-10-prefix semantics are ported verbatim from
``drug_indication._drug_name_matches`` / ``_diagnosis_matches_rule`` so the
two engines agree on what "match" means.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from ..constants import _PROSE_RULES_DIR
from ..icd10 import Icd10Cover, icd10_any_code_covered, normalize_icd10_list
from ..turkish_fold import TurkishFold, fold_turkish

_RULES_PATH = _PROSE_RULES_DIR / "drug_combination_4_2.json"

# ---------------------------------------------------------------------------
# Condition-key classification — the heart of the honest-skip contract.
# ---------------------------------------------------------------------------

# Keys we CAN evaluate against ``ctx.drug_lines`` + ``ctx.diagnoses``. A rule
# fires only when ALL of its condition keys are wireable AND every predicate
# is satisfied.
_WIREABLE_KEYS: frozenset[str] = frozenset(
    {
        # Set/scalar predicates derived from claim drug lines + diagnoses.
        "drug_name_any",
        "diagnosis_any",
        "drug_name_set_any_two",
        "drug_name_set_all",
        "concurrent_drug_name_any",
        # Boolean predicates that all reduce to "≥2 distinct drugs on the
        # same claim". See _check_combo_condition for the shared evaluation.
        "concurrent",
        "combination",
        "two_distinct_agents_same_class_concurrent",
        "two_distinct_active_ingredients_concurrent",
        # Claim-level scalar predicates (unblocked from _BLOCKED_KEYS).
        "facility_tier_in",
        "indication_not_in",
    }
)

# Keys whose source data (drug-class maps, PD-L1/ECOG, EMR history, prior
# therapy timing, facility tier, NYHA, Child-Pugh, procedure cross-ref, …)
# is NOT present on a PatientClaimContext. A rule carrying ANY of these keys
# is deferred with reason ``skipped_no_data``.
_BLOCKED_KEYS: frozenset[str] = frozenset(
    {
        "drug_class_any",
        "drug_class",
        "concurrent_drug_class_any",
        "pdl1_expression_pct",
        "ecog_score",
        "drug_category",
        "pdl1_cps",
        "stage",
        "treatment_line",
        "different_diagnoses",
        "nsaid_trial_count",
        "indication_met",
        "procedure_code_any",
        "treatment_switch_within_months",
        "medical_reason_documented",
        "prior_ai_therapy_months",
        "disease_progression",
        "poor_prognosis_criteria_met_count",
        "two_oncology_specialist_report",
        "sequential_or_combination",
        "sequential",
        "prior_drug_name_any",
        "after_progression",
        "prior_temozolomide",
        "recurrence_or_progression",
        "prior_daratumumab_resistance",
        "prior_adjuvant_ai_months",
        "recurrence_within_months_after_ai",
        "egfr_alk_ros_mutation",
        "tumor_size_cm",
        "pdl1_tc_pct",
        "prior_chemo_lines",
        "progression",
        "sclc_stage",
        "child_pugh",
        "product_not_in_ek4b",
        "months_since_diagnosis",
        "drug_category_any",
        "expected_neutropenia_days",
        "prescribed_as",
        "drug_class_set",
        "two_distinct_agents_same_eye_same_time",
        "loading_dose_incomplete",
        "switched_to_other_agent",
        "diagnosis",
        "inadequate_glycemic_control_on_metformin_sulfonylurea",
        "switch_within_months",
        "functional_decline_or_life_threatening_ae",
        "nyha_class_any",
        "formulation",
    }
)

# Keys that look derivable but have no reliable source on a claim line
# (``treatment_phase`` is an EMR/clinical-pathway field; ``indication`` is a
# gazette-coded semantic label, not an ICD-10 code). A rule whose ONLY
# non-wireable keys are these is still deferred — but it is conceptually
# tier-B/C rather than permanently blocked, so it is tracked separately.
_DEFER_NO_SOURCE_KEYS: frozenset[str] = frozenset({"treatment_phase", "indication"})


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def load_drug_combination_rules() -> dict[str, Any]:
    """Load ``drug_combination_4_2.json`` (cached).

    Returns the raw payload (``rule_set_id``, ``sut_anchors``, ``rules``).
    The orchestrator and coverage-scope reporters read ``rules`` directly.
    """
    with _RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


# ---------------------------------------------------------------------------
# INN + ICD-10 matching — ported from drug_indication.py (same semantics)
# ---------------------------------------------------------------------------


def _drug_name_matches(codes_or_names: list[str], target: str) -> bool:
    """Match a billed drug name (``target``) against a list of INN tokens.

    Ported from ``drug_indication._drug_name_matches`` (same word-boundary
    semantics): a short token like ``cinacalcet`` must not false-positive
    inside a longer brand name. Drug names follow the SGK format
    ``"BRAND DOSE (INN)"``, so a whole-word/whole-phrase match is correct.

    Note the argument order is inverted from drug_indication's
    ``_drug_name_matches(drug_name, rule_names)`` to read naturally for the
    combination use-case ("do any of these billed names match the target
    INN?"). The matching logic is identical.
    """
    normalized = fold_turkish(target or "", TurkishFold.ACCENTLESS)
    if not normalized:
        return False
    import re

    for inn in codes_or_names:
        token = fold_turkish(inn or "", TurkishFold.ACCENTLESS)
        if not token:
            continue
        pattern = re.compile(r"(?<![\w)])" + re.escape(token) + r"(?![\w(])")
        if pattern.search(normalized):
            return True
    return False


def _diagnosis_matches(codes: list[str], rule_codes: list[str]) -> bool:
    """ICD-10 PREFIX match — ported from ``drug_indication._diagnosis_matches_rule``.

    ``rule_codes = ["K50"]`` matches a billed ``"K50.0"`` (prefix) or ``"K50"``
    (exact); a dotted listed code matches only itself (``Icd10Cover.EXACT``).
    Matching is case-insensitive and ignores stray whitespace. When the rule
    lists no codes the predicate passes (no diagnosis constraint).
    """
    icd_codes = normalize_icd10_list(rule_codes)
    if not icd_codes:
        return True
    return icd10_any_code_covered(codes, icd_codes, cover=Icd10Cover.EXACT)


# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------


def _count_distinct_drug_matches(
    drug_names_on_claim: set[str], listed: list[str]
) -> int:
    """How many DISTINCT billed drug names match at least one listed INN token."""
    matched: set[str] = set()
    for billed in drug_names_on_claim:
        if _drug_name_matches(listed, billed):
            matched.add(billed)
    return len(matched)


def _check_combo_condition(
    condition: dict[str, Any],
    drug_names_on_claim: set[str],
    diagnoses: list[str],
    *,
    facility_tier: str | None = None,
) -> tuple[bool, str]:
    """Evaluate one rule's ``condition`` dict against a single claim's facts.

    Returns ``(matches, reason)`` where:

    - ``reason == "matched"`` → every wireable predicate passed; the rule
      should fire.
    - ``reason == "skipped_no_data"`` → the rule gates on a blocked key or a
      no-source clinical field (``treatment_phase``/``indication``); defer it
      honestly. ``matches`` is ``False``.
    - ``reason == "skipped_unknown_key"`` → a condition key is neither
      wireable, blocked, nor in the no-source set (a genuinely unknown
      predicate). Defer rather than guess. ``matches`` is ``False``.
    - ``reason == "not_matched"`` → all keys wireable but a predicate was not
      satisfied by this claim (the normal non-firing path). ``matches`` is
      ``False``.

    A rule with ANY blocked / no-source / unknown key is deferred — it never
    fires, even if its wireable predicates happen to be satisfied. This is
    the honesty guard: a partial evaluation of a multi-predicate rule would
    silently produce false positives.
    """
    # Two-distinct-agents boolean predicate: shared by ``concurrent``,
    # ``combination``, ``two_distinct_agents_same_class_concurrent``,
    # ``two_distinct_active_ingredients_concurrent``. All four reduce to
    # "≥2 distinct drugs on the same claim". We do NOT have a drug-class map
    # here (that is a blocked key), so "same class" cannot be verified — we
    # treat the predicate as the weaker "≥2 distinct drugs" which is a sound
    # necessary condition (any two same-class drugs are also two distinct
    # drugs). Documenting this interpretation explicitly per the W4 plan.
    has_two_distinct = len(drug_names_on_claim) >= 2

    for key, expected in condition.items():
        # Blocked / no-source / unknown → defer immediately (honest skip).
        if key in _BLOCKED_KEYS or key in _DEFER_NO_SOURCE_KEYS:
            return False, "skipped_no_data"
        if key not in _WIREABLE_KEYS:
            return False, "skipped_unknown_key"

        # Wireable predicates:
        if key == "drug_name_any":
            listed = list(expected or [])
            if not any(_drug_name_matches(listed, name) for name in drug_names_on_claim):
                return False, "not_matched"

        elif key == "concurrent_drug_name_any":
            listed = list(expected or [])
            if not any(_drug_name_matches(listed, name) for name in drug_names_on_claim):
                return False, "not_matched"

        elif key == "diagnosis_any":
            rule_codes = list(expected or [])
            if not _diagnosis_matches(diagnoses, rule_codes):
                return False, "not_matched"

        elif key == "drug_name_set_any_two":
            listed = list(expected or [])
            if _count_distinct_drug_matches(drug_names_on_claim, listed) < 2:
                return False, "not_matched"

        elif key == "drug_name_set_all":
            listed = list(expected or [])
            # ALL listed INNs must be present (each matched by ≥1 billed name).
            for inn in listed:
                if not any(_drug_name_matches([inn], name) for name in drug_names_on_claim):
                    return False, "not_matched"

        elif key in (
            "concurrent",
            "combination",
            "two_distinct_agents_same_class_concurrent",
            "two_distinct_active_ingredients_concurrent",
        ):
            if not has_two_distinct:
                return False, "not_matched"

        elif key == "facility_tier_in":
            if facility_tier is None:
                return False, "skipped_no_data"
            expected_tiers = {expected} if isinstance(expected, str) else set(expected or [])
            if facility_tier not in expected_tiers:
                return False, "not_matched"

        elif key == "indication_not_in":
            # Negated diagnosis membership: NONE of the listed indications
            # may be present in the claim's diagnoses (ICD-10 prefix match).
            rule_codes = list(expected or [])
            if _diagnosis_matches(diagnoses, rule_codes):
                return False, "not_matched"

    return True, "matched"


def _collect_drug_names(ctx: Any, claim_id: str | None = None) -> set[str]:
    """Extract the set of drug INN/name strings from ``ctx.drug_lines``.

    When ``claim_id`` is given, only lines on that claim are counted (combos
    are within ONE claim). Returns the raw billed ``drug_name`` strings — INN
    tokenization happens later inside ``_drug_name_matches``.
    """
    names: set[str] = set()
    for line in (getattr(ctx, "drug_lines", None) or ()):
        if claim_id is not None and getattr(line, "claim_id", None) != claim_id:
            continue
        name = str(getattr(line, "drug_name", "") or "").strip()
        if name:
            names.add(name)
    return names


def _collect_diagnoses(ctx: Any, claim_id: str) -> list[str]:
    """ICD-10 codes for a claim: header primary + every ClaimDiagnosis row."""
    codes: list[str] = []
    for claim in (getattr(ctx, "claims", None) or ()):
        if getattr(claim, "claim_id", None) != claim_id:
            continue
        primary = str(getattr(claim, "primary_icd10", "") or "").strip().upper()
        if primary:
            codes.append(primary)
        break  # claim_id is unique; one header max
    for row in (getattr(ctx, "diagnoses", None) or ()):
        if getattr(row, "claim_id", None) != claim_id:
            continue
        code = str(getattr(row, "icd10_code", "") or "").strip().upper()
        if code and code not in codes:
            codes.append(code)
    return codes


def _violation_from_rule(rule: dict[str, Any], claim_id: str) -> dict[str, Any]:
    """Build the violation dict (mirrors gap_closing's shape, rule=family id)."""
    action = rule.get("action") or {}
    billable = action.get("billable")
    message = (
        action.get("denial_tr")
        or action.get("payment_tr")
        or action.get("message_tr")
        or rule.get("rule_id", "")
    )
    severity = action.get("severity", "error")
    return {
        "rule": "drug_combination_4_2",
        "claim_id": claim_id,
        "severity": severity,
        "message": message,
        "savings_try": 0.0,
        "risk_amount": 0.0,
        "sut_section": rule.get("sut_section", ""),
        "rule_id": rule.get("rule_id", ""),
        "billable": billable,
        "material_outcome": (
            "no_pay"
            if billable is False
            else "must_bill"
            if billable is True
            else "review"
        ),
        "annex_basis": action.get("annex_basis"),
        "details": {
            "prose_rule_set": "drug_combination_4_2",
        },
    }


def check_drug_combination_for_context(ctx: Any) -> list[dict[str, Any]]:
    """Evaluate the §4.2 drug-combination rules against a PatientClaimContext.

    Groups ``ctx.drug_lines`` by ``claim_id`` (combos are within ONE claim),
    evaluates every rule against each claim's drug-name set + diagnoses, and
    emits a violation per (rule, claim) that genuinely matches. Rules with a
    blocked/unknown/no-source key are deferred and never fire on any claim.

    Returns ``[]`` when the context has no drug lines (no crash).
    """
    drug_lines = getattr(ctx, "drug_lines", None) or ()
    if not drug_lines:
        return []

    rules = (load_drug_combination_rules().get("rules") or [])
    if not rules:
        return []

    # Claim ids that actually carry drug lines (the unit of grouping).
    claim_ids: list[str] = []
    seen: set[str] = set()
    for line in drug_lines:
        cid = getattr(line, "claim_id", None)
        if cid and cid not in seen:
            seen.add(cid)
            claim_ids.append(cid)

    violations: list[dict[str, Any]] = []
    for claim_id in claim_ids:
        drug_names = _collect_drug_names(ctx, claim_id=claim_id)
        diagnoses = _collect_diagnoses(ctx, claim_id)
        # Derive facility_tier from the claim header for facility_tier_in predicate.
        facility_tier: str | None = None
        for claim in (getattr(ctx, "claims", None) or ()):
            if getattr(claim, "claim_id", None) == claim_id:
                facility_tier = (getattr(claim, "facility_tier", "") or "").strip().lower()
                break
        for rule in rules:
            condition = rule.get("condition") or {}
            matches, _reason = _check_combo_condition(
                condition, drug_names, diagnoses, facility_tier=facility_tier
            )
            if matches:
                violations.append(_violation_from_rule(rule, claim_id))
    return violations

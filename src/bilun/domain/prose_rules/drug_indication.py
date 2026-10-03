"""SUT §4.2 drug indication / report prose — public API and claim evaluation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ._drug_indication.clinical import apply_clinical_restrictions
from ._drug_indication.gh_runtime import make_gh_observer, attach_gh_runtime

# Keep the established callable names and the original decorated cache objects
# available through this public module.
from ._drug_indication.corpus import (
    _ANTI_VEGF_RULES_PATH as _ANTI_VEGF_RULES_PATH,
    _DRUG_MANIFEST_GLOBS as _DRUG_MANIFEST_GLOBS,
    _MANIFEST_DIR as _MANIFEST_DIR,
    _MANIFEST_PATH as _MANIFEST_PATH,
    _PHASE1_TARGET_RULE_COUNT as _PHASE1_TARGET_RULE_COUNT,
    _PHASE2_TARGET_RULE_COUNT as _PHASE2_TARGET_RULE_COUNT,
    _RULES_PATH as _RULES_PATH,
    _RULE_SET_ID as _RULE_SET_ID,
    _drug_indication_manifest_stats as _drug_indication_manifest_stats,
    _drug_indication_subsection_coverage as _drug_indication_subsection_coverage,
    drug_indication_coverage_scope as drug_indication_coverage_scope,
    drug_indication_registry_promotion_gate as drug_indication_registry_promotion_gate,
    drug_indication_v1_stop_conditions as drug_indication_v1_stop_conditions,
    list_drug_indication_rules as list_drug_indication_rules,
    load_drug_indication_rules as load_drug_indication_rules,
)
from ._drug_indication.matching import (
    _collect_icd10_codes as _collect_icd10_codes,
    _compiled_inn_pattern as _compiled_inn_pattern,
    _diagnosis_matches_rule as _diagnosis_matches_rule,
    _diagnosis_matches_specific_rule as _diagnosis_matches_specific_rule,
    _drug_name_matches as _drug_name_matches,
    _has_biomarker_requirement as _has_biomarker_requirement,
    _has_dose_protocol as _has_dose_protocol,
    _has_prior_therapy_requirement as _has_prior_therapy_requirement,
    _has_tier_b_constraints as _has_tier_b_constraints,
    _is_indication_route_rule as _is_indication_route_rule,
    _normalize_tr as _normalize_tr,
    _rule_has_icd_selector as _rule_has_icd_selector,
    _rule_icd_selectors as _rule_icd_selectors,
    _rule_tier_b_score as _rule_tier_b_score,
    _specialty_matches as _specialty_matches,
)

from ._drug_indication.routing import (
    _drug_rule_candidates as _drug_rule_candidates,
    _route_group_key as _route_group_key,
    _route_preference_key as _route_preference_key,
    _semantic_route_signature as _semantic_route_signature,
    _select_semantically_equivalent_route as _select_semantically_equivalent_route,
    _preferred_route_rule as _preferred_route_rule,
    _route_specificity_key as _route_specificity_key,
    _select_route_rule as _select_route_rule,
    _has_supplemental_constraint as _has_supplemental_constraint,
    _supplemental_matches_route as _supplemental_matches_route,
    _select_supplemental_rule as _select_supplemental_rule,
    _resolve_drug_indication_route as _resolve_drug_indication_route,
    _find_matching_rule as _find_matching_rule,
)
from ._drug_indication.constraints import (
    _evaluate_tier_b_constraints as _evaluate_tier_b_constraints,
    _evaluate_dose_protocol as _evaluate_dose_protocol,
    _evaluate_biomarker_constraints as _evaluate_biomarker_constraints,
    _evaluate_prior_therapy_constraints as _evaluate_prior_therapy_constraints,
    _evaluate_supplemental_constraints as _evaluate_supplemental_constraints,
)
from ._drug_indication.evaluation import (
    _eligible_route_values as _eligible_route_values,
    _route_rule_ids as _route_rule_ids,
    _evaluation_status_for_violation as _evaluation_status_for_violation,
    _decorate_drug_violation as _decorate_drug_violation,
)
from ._drug_indication.evaluation import (
    evaluate_drug_indication_line_with_rules as _evaluate_drug_indication_line_with_rules,
)

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimDiagnosis, ClaimHeader, DrugClaimLine


def evaluate_drug_indication_line_detailed(
    *,
    drug_line: DrugClaimLine,
    claim: ClaimHeader,
    diagnoses: list[ClaimDiagnosis],
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate one line, keeping applicability evidence separate from constraints."""
    encoded_rules = rules if rules is not None else list_drug_indication_rules()
    gh_observer = make_gh_observer(drug_line, encoded_rules)
    base = _evaluate_drug_indication_line_with_rules(
        drug_line=drug_line,
        claim=claim,
        diagnoses=diagnoses,
        rules=encoded_rules,
        gh_observer=gh_observer,
    )
    result = apply_clinical_restrictions(base, drug_line, encoded_rules)
    return attach_gh_runtime(result, gh_observer)


def evaluate_drug_indication_line(
    *,
    drug_line: DrugClaimLine,
    claim: ClaimHeader,
    diagnoses: list[ClaimDiagnosis],
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Legacy projection of the detailed single-line drug evaluation."""
    return evaluate_drug_indication_line_detailed(
        drug_line=drug_line,
        claim=claim,
        diagnoses=diagnoses,
        rules=rules,
    ).get("violation")


def check_drug_indication_for_context(ctx) -> list[dict[str, Any]]:
    """Scan all drug claim lines in a patient context against the pilot corpus."""
    if not ctx.drug_lines:
        return []

    rules = list_drug_indication_rules()
    if not rules:
        return []

    violations: list[dict[str, Any]] = []
    diagnoses = list(ctx.diagnoses or ())
    claims_by_id = {claim.claim_id: claim for claim in ctx.claims}

    for drug_line in ctx.drug_lines:
        claim = claims_by_id.get(drug_line.claim_id)
        if claim is None:
            continue
        hit = evaluate_drug_indication_line(
            drug_line=drug_line,
            claim=claim,
            diagnoses=diagnoses,
            rules=rules,
        )
        if hit is not None:
            violations.append(hit)

    return violations

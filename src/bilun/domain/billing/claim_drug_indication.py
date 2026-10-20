"""§4.2 drug indication / report validation from exact drug claim lines."""

from __future__ import annotations

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules._drug_indication.unencoded_scope import SCOPE_UNKNOWN
from src.bilun.domain.prose_rules.drug_indication import drug_indication_coverage_scope

from .drug_indication_findings import (
    DrugIndicationEvaluationBatch,
    evaluate_drug_indication_findings,
)

from .types import (
    DRUG_INDICATION_CORPUS_UNAVAILABLE_REASON,
    DRUG_INDICATION_INGREDIENT_UNKNOWN_REASON,
    DRUG_INDICATION_NAME_CHECK_REASON,
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    EXACTNESS_STATUS_NOT_APPLICABLE,
    EXACTNESS_STATUS_PARTIAL,
    DRUG_INDICATION_REQUIRED_INPUTS,
    DRUG_INDICATION_UNAVAILABLE_REASON,
    DrugIndicationReview,
)

_PROSE_RULE_SOURCE = (
    "SUT §4.2 drug indication prose — ICD-10 + INN + sağlık kurulu raporu (Tier 3b pilot)"
)


def validate_drug_indication_from_claims(
    ctx: PatientClaimContext,
    *,
    evaluation_batch: DrugIndicationEvaluationBatch | None = None,
) -> DrugIndicationReview:
    """Project one canonical drug-indication batch into the billing review."""
    if not ctx.drug_lines:
        return DrugIndicationReview(
            exactness_status=EXACTNESS_STATUS_NOT_APPLICABLE,
            unavailable_reason=None,
            required_inputs_missing=[],
            rule_source=_PROSE_RULE_SOURCE,
            coverage_scope=drug_indication_coverage_scope(),
        )

    batch = evaluation_batch or evaluate_drug_indication_findings(ctx.patient_id, ctx)
    statuses = [evaluation.evaluation_status for evaluation in batch.evaluations]
    missing_inputs = sorted(
        {
            missing
            for evaluation in batch.evaluations
            for missing in evaluation.missing_inputs
        }
    )
    unavailable = any(status == "unavailable" for status in statuses)
    corpus_noncoverage = any(
        evaluation.applicability_status == "not_in_encoded_corpus"
        for evaluation in batch.evaluations
    )
    # Lines whose ingredient could not be determined are the only reason for the
    # manual review: the others outside the corpus are restricted or named.
    ingredient_unknown_only = corpus_noncoverage and all(
        (evaluation.ingredient_scope or {}).get("result") == SCOPE_UNKNOWN
        for evaluation in batch.evaluations
        if evaluation.applicability_status == "not_in_encoded_corpus"
    )
    name_check_only = any(
        evaluation.applicability_status == "no_sut_restriction_found" for evaluation in batch.evaluations
    )
    missing = any(status == "missing_inputs" for status in statuses)
    evaluated = any(status == "evaluated" for status in statuses)
    if statuses and all(status == "evaluated" for status in statuses):
        exactness_status = EXACTNESS_STATUS_EXACT
    elif evaluated:
        exactness_status = EXACTNESS_STATUS_PARTIAL
    elif missing:
        exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
    else:
        exactness_status = EXACTNESS_STATUS_PARTIAL
    if exactness_status == EXACTNESS_STATUS_EXACT and name_check_only:
        # A line checked only by ingredient name cannot rule out a restriction
        # written for its drug class: it never certifies the block as exact.
        exactness_status = EXACTNESS_STATUS_PARTIAL

    if (missing or unavailable) and not missing_inputs and not corpus_noncoverage:
        missing_inputs = list(DRUG_INDICATION_REQUIRED_INPUTS)
    if exactness_status == EXACTNESS_STATUS_EXACT:
        unavailable_reason = None
    elif corpus_noncoverage:
        unavailable_reason = (
            DRUG_INDICATION_INGREDIENT_UNKNOWN_REASON
            if ingredient_unknown_only
            else DRUG_INDICATION_CORPUS_UNAVAILABLE_REASON
        )
    elif name_check_only and not (missing or unavailable):
        unavailable_reason = DRUG_INDICATION_NAME_CHECK_REASON
    else:
        unavailable_reason = DRUG_INDICATION_UNAVAILABLE_REASON
    return DrugIndicationReview(
        violations=list(batch.legacy_violations),
        findings=list(batch.findings),
        evaluations=list(batch.evaluations),
        exactness_status=exactness_status,
        unavailable_reason=unavailable_reason,
        required_inputs_missing=missing_inputs,
        rule_source=_PROSE_RULE_SOURCE,
        coverage_scope=drug_indication_coverage_scope(),
    )

"""§4.2 drug indication / report validation from exact drug claim lines."""

from __future__ import annotations

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.drug_indication import (
    check_drug_indication_for_context,
    drug_indication_coverage_scope,
)

from .types import (
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_NOT_APPLICABLE,
    DrugIndicationReview,
)

_PROSE_RULE_SOURCE = (
    "SUT §4.2 drug indication prose — ICD-10 + INN + sağlık kurulu raporu (Tier 3b pilot)"
)


def validate_drug_indication_from_claims(
    ctx: PatientClaimContext,
) -> DrugIndicationReview:
    """Match billed drug lines against the §4.2 pilot indication corpus."""
    if not ctx.drug_lines:
        return DrugIndicationReview(
            exactness_status=EXACTNESS_STATUS_NOT_APPLICABLE,
            unavailable_reason=None,
            required_inputs_missing=[],
            rule_source=_PROSE_RULE_SOURCE,
            coverage_scope=drug_indication_coverage_scope(),
        )

    violations = check_drug_indication_for_context(ctx)
    return DrugIndicationReview(
        violations=violations,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
        coverage_scope=drug_indication_coverage_scope(),
    )

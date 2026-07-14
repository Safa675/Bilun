"""ICU (yoğun bakım) billing from exact inpatient claim dates.

This wrapper follows ``claim_yatak_puani.py`` exactly. The result dataclass
``IcuPuaniReview`` is defined LOCALLY here because ``types.py`` is a shared
file the orchestrator wires later; once the orchestrator moves it into
``types.py`` (alongside ``YatakPuaniReview``) and registers the
``BillingBlockSpec``, this local definition should be removed in favour of
the shared one.
"""

from __future__ import annotations


from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.icu_puani import (
    detect_icu_puani_opportunities,
)

# These exactness constants live in the shared types module; importing them
# does NOT edit that file.
from .types import (
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    IcuPuaniReview,
)

ICU_PUANI_REQUIRED_INPUTS = (
    "inpatient_claims_with_dates",
    "procedure_claim_lines_with_icu_codes",
)
ICU_PUANI_UNAVAILABLE_REASON = (
    "ICU (yoğun bakım) puanı requires inpatient claims with admission/discharge "
    "dates and ICU indicator procedure codes (510090 / P55200x), which are not "
    "available in the active SUT runtime inputs."
)

_PROSE_RULE_SOURCE = (
    "SUT §2.4.4.H yoğun bakım — 510090 (first/last) + P55200x (ara günü)"
)


def recommend_icu_puani_from_claims(
    ctx: PatientClaimContext,
) -> IcuPuaniReview:
    """Compute expected ICU (yoğun bakım) charges for inpatient claims."""
    if not ctx.procedure_lines:
        return IcuPuaniReview(
            exactness_status=EXACTNESS_STATUS_MISSING_INPUTS,
            unavailable_reason=ICU_PUANI_UNAVAILABLE_REASON,
            required_inputs_missing=list(ICU_PUANI_REQUIRED_INPUTS),
            rule_source=_PROSE_RULE_SOURCE,
        )

    claim_ids_with_procs = {line.claim_id for line in ctx.procedure_lines}
    opportunities = detect_icu_puani_opportunities(
        list(ctx.claims),
        list(ctx.procedure_lines),
        claim_ids_with_procs=claim_ids_with_procs,
    )

    return IcuPuaniReview(
        opportunities=opportunities,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
    )

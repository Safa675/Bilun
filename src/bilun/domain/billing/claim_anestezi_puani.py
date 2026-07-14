"""Anestezi puanı (anesthesia group charge) billing for inpatient claims.

This wrapper follows ``claim_yatak_puani.py`` / ``claim_icu_puani.py``
exactly. The result dataclass ``AnesteziPuaniReview`` is defined LOCALLY
here because ``types.py`` is a shared file the orchestrator wires later;
once the orchestrator moves it into ``types.py`` (alongside
``YatakPuaniReview`` / ``IcuPuaniReview``) and registers the
``BillingBlockSpec``, this local definition should be removed in favour
of the shared one.
"""

from __future__ import annotations


from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.anestezi_puani import (
    detect_anestezi_puani_opportunities,
)

# These exactness constants live in the shared types module; importing them
# does NOT edit that file.
from .types import (
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    AnesteziPuaniReview,
)

ANESTEZI_PUANI_REQUIRED_INPUTS = (
    "inpatient_claims",
    "procedure_claim_lines",
)
ANESTEZI_PUANI_UNAVAILABLE_REASON = (
    "Anestezi puanı requires inpatient claims and surgical procedure claim "
    "lines, which are not available in the active SUT runtime inputs."
)

_PROSE_RULE_SOURCE = (
    "SUT §2.4.4.A anestezi — surgical procedure puan range → anesthesia "
    "group puan (EK-2B 550130-550190) × katsayı"
)


def recommend_anestezi_puani_from_claims(
    ctx: PatientClaimContext,
) -> AnesteziPuaniReview:
    """Compute expected anesthesia charges for inpatient surgical procedures."""
    if not ctx.procedure_lines:
        return AnesteziPuaniReview(
            exactness_status=EXACTNESS_STATUS_MISSING_INPUTS,
            unavailable_reason=ANESTEZI_PUANI_UNAVAILABLE_REASON,
            required_inputs_missing=list(ANESTEZI_PUANI_REQUIRED_INPUTS),
            rule_source=_PROSE_RULE_SOURCE,
        )

    claim_ids_with_procs = {line.claim_id for line in ctx.procedure_lines}
    opportunities = detect_anestezi_puani_opportunities(
        list(ctx.claims),
        list(ctx.procedure_lines),
        claim_ids_with_procs=claim_ids_with_procs,
    )

    return AnesteziPuaniReview(
        opportunities=opportunities,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
    )

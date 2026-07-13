"""Missing procedure add-on uplift from exact claim lines."""

from __future__ import annotations

from typing import Any

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.procedure_addon_uplift import (
    detect_missing_procedure_addon_opportunities,
)

from .types import (
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    PROCEDURE_ADDON_UPLIFT_REQUIRED_INPUTS,
    PROCEDURE_ADDON_UPLIFT_UNAVAILABLE_REASON,
    ProcedureAddonUplift,
)

_PROSE_RULE_SOURCE = (
    "SUT §2.2.2 same-session procedure add-on pairing — uplift-only"
)


def recommend_procedure_addon_uplift_from_claims(
    ctx: PatientClaimContext,
    *,
    session_opportunities: list[dict[str, Any]] | None = None,
) -> ProcedureAddonUplift:
    """Detect recoverable SGK uplift when expected add-on procedures were not billed.

    ``session_opportunities`` is the output of ``recommend_session_uplift_from_claims``
    — used to suppress add-on opportunities already captured by session-pricing
    uplift (cross-detector de-duplication wired in patient_report.py).
    """
    if not ctx.procedure_lines:
        return ProcedureAddonUplift(
            exactness_status=EXACTNESS_STATUS_MISSING_INPUTS,
            unavailable_reason=PROCEDURE_ADDON_UPLIFT_UNAVAILABLE_REASON,
            required_inputs_missing=list(PROCEDURE_ADDON_UPLIFT_REQUIRED_INPUTS),
            rule_source=_PROSE_RULE_SOURCE,
        )

    opportunities: list[dict] = []
    for claim in ctx.claims:
        claim_procs = [
            line for line in ctx.procedure_lines if line.claim_id == claim.claim_id
        ]
        if not claim_procs:
            continue
        opportunities.extend(
            detect_missing_procedure_addon_opportunities(
                claim,
                claim_procs,
                session_uplift_opportunities=session_opportunities,
            )
        )

    return ProcedureAddonUplift(
        opportunities=opportunities,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
    )

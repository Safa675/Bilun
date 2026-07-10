"""Refakatçi (companion bed, 510121) billing from exact inpatient claim dates.

SUT §2.6.3 + §2.2.2.(5): 510121 Refakat (124.95 puan) is billable for
inpatient stays that are neither günübirlik/day-case nor ICU.

``RefakatciReview`` is defined locally for Phase 1; the orchestrator will
move it to ``types.py`` once the billing wrapper is wired into the patient
report (mirroring the YatakPuaniReview rollout).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.bilun.domain.billing.types import (
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    RefakatciReview,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.refakatci import (
    detect_refakatci_opportunities,
)

_PROSE_RULE_SOURCE = (
    "SUT §2.6.3 companion bed (510121) — companion days × puan × katsayı; "
    "suppressed for day-case (§2.2.2.(5)) and ICU (§2.6.3.(3))"
)

_REFAKATCI_REQUIRED_INPUTS = (
    "inpatient_claims_with_dates",
    "procedure_claim_lines",
)
_REFAKATCI_UNAVAILABLE_REASON = (
    "Refakatçi requires inpatient claims with admission/discharge dates and "
    "procedure claim lines (for ICU detection), which are not available in "
    "the active SUT runtime inputs."
)


def recommend_refakatci_from_claims(ctx: PatientClaimContext) -> RefakatciReview:
    """Compute expected companion-bed charges for inpatient claims.

    Mirrors ``recommend_yatak_puani_from_claims``: returns a
    ``missing_exact_inputs`` review when there are no procedure lines, since
    procedure lines are required for the ICU suppression gate.
    """
    if not ctx.procedure_lines:
        return RefakatciReview(
            exactness_status=EXACTNESS_STATUS_MISSING_INPUTS,
            unavailable_reason=_REFAKATCI_UNAVAILABLE_REASON,
            required_inputs_missing=list(_REFAKATCI_REQUIRED_INPUTS),
            rule_source=_PROSE_RULE_SOURCE,
        )

    opportunities = detect_refakatci_opportunities(
        list(ctx.claims),
        list(ctx.procedure_lines),
    )

    return RefakatciReview(
        opportunities=opportunities,
        exactness_status=EXACTNESS_STATUS_EXACT,
        unavailable_reason=None,
        required_inputs_missing=[],
        rule_source=_PROSE_RULE_SOURCE,
    )

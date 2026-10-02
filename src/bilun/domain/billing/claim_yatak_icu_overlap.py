"""YB→servis geçiş günü yatak koordinasyonu — recoverable-uplift düzeltmesi.

Post-processing wrapper over ``claim_yatak_puani``: after
``recommend_yatak_puani_from_claims`` computes the expected service-bed
(510010) charges, this wrapper drops ICU discharge/transfer days (510090
last days) from the bed-day count. EK-2B defines 510090 as covering
"Yemek, yatak, hasta vizit hizmetlerini kapsar" — the bed is already paid on
the ICU day, so the service bed cannot be billed again and BILUN must not
recommend recovering it.

The audit-exposure counterpart (actually billed 510010 lines dated on an
ICU last day) is wired separately into ``analyze_claim`` via
``prose_rules.yatak_icu_overlap.detect_yatak_icu_overlap``.
"""

from __future__ import annotations

from dataclasses import replace

from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.yatak_icu_overlap import reconcile_yatak_bed_days

from .types import YatakPuaniReview


def reconcile_yatak_icu_overlap(
    ctx: PatientClaimContext,
    yatak_review: YatakPuaniReview,
) -> YatakPuaniReview:
    """Drop ICU discharge/transfer days from yatak bed-day expectations.

    Args:
        ctx: Active patient/bill context; separate known history confirms ICU
            last days without adding historical opportunities or billed money.
        yatak_review: Output of ``recommend_yatak_puani_from_claims``.

    Returns:
        A new ``YatakPuaniReview`` with reconciled opportunities (metadata —
        exactness_status, rule_source — preserved). When there is nothing to
        reconcile (no opportunities / no procedure lines / no overlap) the
        review is returned unchanged.
    """
    if not yatak_review.opportunities or not ctx.procedure_lines:
        return yatak_review

    history = ctx.history
    adjusted = reconcile_yatak_bed_days(
        yatak_review.opportunities,
        list(history.claims),
        list(history.procedure_lines),
    )
    if adjusted is yatak_review.opportunities:
        return yatak_review
    return replace(yatak_review, opportunities=adjusted)

"""Yenidoğan yatağı ↔ standart yatak koordinasyonu — recoverable-uplift correction.

Post-processing over ``claim_yatak_puani`` and ``claim_yenidogan_yatak``: EK-2/B
gives 510010 (standart yatak), 510070 (Kuvöz) and 510081 (Kot) the same text,
"Yemek, yatak, hasta vizit hizmetlerini kapsar" — they are alternatives for one
patient-day, as the project already holds for 510090 against 510010
(``claim_yatak_icu_overlap``). The days the newborn bed motor owns are therefore
no standard-bed days to recover: this step drops exactly those days from the
standard-bed expectation, so the same days are not in ``sgk_uplift_try`` twice
(before it a 3-day newborn stay counted 1,322.94 TL Kuvöz and 667.08 TL standard
bed). Days billed on the standard bed beside a newborn bed (``standard_bed_days``
on the newborn row) stay with the standard-bed motor.

The audit-exposure counterpart (510010 actually billed on a day a Kuvöz / Kot line
covers) is a separate detector and not part of this step:
``prose_rules.yatak_newborn_overlap.detect_yatak_newborn_overlap``, called from
``analyze_claim`` and re-run for the ``audit_exposure`` rows.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from src.bilun.domain.money import money_round_half_up as _money

from .types import YatakPuaniReview, YenidoganYatakReview


def reconcile_yatak_newborn_overlap(
    yatak_review: YatakPuaniReview,
    newborn_review: YenidoganYatakReview,
) -> YatakPuaniReview:
    """Drop the days the newborn bed motor covers from the standard-bed expectation.

    Args:
        yatak_review: Output of ``recommend_yatak_puani_from_claims`` (after the
            ICU reconciliation).
        newborn_review: Output of ``recommend_yenidogan_yatak_from_claims``. Its
            ``days`` are the claim's newborn bed days, whatever is left to recover
            after the billed lines (a stay billed in full still owns its days).

    Returns:
        A new ``YatakPuaniReview`` whose overlapping opportunities carry
        ``bed_days`` / ``expected_yatak_try`` / ``recoverable_uplift_try`` without
        the newborn days and ``newborn_overlap_days`` (the days actually taken
        out); metadata is preserved. When nothing overlaps the review is returned
        unchanged (identity), so callers can tell a no-op.
    """
    if not yatak_review.opportunities or not newborn_review.opportunities:
        return yatak_review

    newborn_days: dict[str, int] = {}
    for opportunity in newborn_review.opportunities:
        claim_id = opportunity.get("claim_id")
        days = int(opportunity.get("days") or 0)
        if claim_id and days > 0:
            newborn_days[claim_id] = max(newborn_days.get(claim_id, 0), days)

    adjusted: list[dict[str, Any]] = []
    changed = False
    for opportunity in yatak_review.opportunities:
        bed_days = int(opportunity.get("bed_days") or 0)
        overlap = min(newborn_days.get(opportunity.get("claim_id"), 0), bed_days)
        if overlap <= 0:
            adjusted.append(opportunity)
            continue

        changed = True
        expected = _money((bed_days - overlap) * float(opportunity.get("daily_rate_try") or 0.0))
        actual_billed_try = float(opportunity.get("actual_billed_try") or 0.0)
        reconciled = dict(opportunity)
        reconciled["bed_days"] = bed_days - overlap
        reconciled["expected_yatak_try"] = expected
        # Never more than the expected charge: a credit line must not recover money on removed days.
        reconciled["recoverable_uplift_try"] = _money(min(expected, max(0.0, expected - actual_billed_try)))
        reconciled["newborn_overlap_days"] = overlap
        reconciled["detail"] = (
            f"{opportunity.get('detail', '')} {overlap} day(s) are newborn bed days "
            "(510070 / 510081 cover yemek + yatak + vizit, EK-2/B) and are not "
            "expected as standard bed."
        ).strip()
        adjusted.append(reconciled)

    if not changed:
        return yatak_review
    return replace(yatak_review, opportunities=adjusted)

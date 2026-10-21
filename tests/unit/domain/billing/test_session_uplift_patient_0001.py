"""Regression: a bill billed in full on the list is not session underbilling (clean control).

Was SENTETIK-HASTA-0001 of the 50-patient set. Patient 0001 is now the S1 story (a package billed itemised),
so the control runs on in-memory clean twins of the showcase bills (`tests/fixtures/t1_showcase_bills.py`)
and carries its own positive control: the same bill with a secondary operation billed below the allowed rate
must show the uplift, so the zeros of the clean bills are not the zeros of a block that cannot fire.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.pricing.temporal import get_ek2b_price_for_date
from tests.fixtures import synthetic_cohort as cohort
from tests.fixtures.t1_showcase_bills import (
    clean_context,
    clean_context_for_story,
    with_extra_operation,
)

pytestmark = pytest.mark.unit

# A second operation of the session is paid at 30 % of its list price, one incision (§2.2.2.A(5)).
_ALLOWED_FACTOR = 0.30
_SECOND_OPERATION = "615995"  # an EK-2/B operation that can follow the S3 operation in one session


def _report(ctx):
    return compute_patient_billing_report(
        ctx.patient_id,
        claim_context=ctx,
        copay_exemption={"exempt": False},
    )


@pytest.mark.parametrize(
    "role_name", [name for name in sorted(cohort.roles()) if name.startswith("showcase_")]
)
def test_clean_twin_has_no_session_or_drg_uplift(role_name: str) -> None:
    """Whatever a story injects, its clean twin has nothing to recover in the uplift blocks."""
    report = _report(clean_context(role_name))

    assert report.session_uplift.confirmed_uplift_try == 0.0
    assert report.drg_uplift.confirmed_uplift_try == 0.0
    assert report.sgk_uplift_try == 0.0


@pytest.mark.parametrize("story", sorted(cohort.scenarios()))
def test_clean_twin_of_a_story_after_the_eighth_has_no_session_or_drg_uplift(story: str) -> None:
    """The same control for the stories that are scenarios and not roles (S9 and later).

    S9's fault is a session fault: its clean twin bills the second operation at the separate-incision rate,
    which the engine reads as correct, so the block that finds the fault stays at zero on the clean bill.
    A clean bill of the cohort (S39, the control visit of patient 4) is its own twin and must show the same zeros."""
    report = _report(clean_context_for_story(story))

    assert report.session_uplift.confirmed_uplift_try == 0.0
    assert report.session_uplift.opportunities == []
    assert report.drg_uplift.confirmed_uplift_try == 0.0
    assert report.sgk_uplift_try == 0.0


def test_full_list_billing_is_not_session_underbilling() -> None:
    """Full EK-2B list billing is not session underbilling (§2.2.2 uses list × factor).

    The S3 clean twin (one operation, anaesthesia) gets a second operation billed at its full list price:
    that is over-billing, which the audit exposure shows, and no session uplift."""
    report = _report(with_extra_operation(clean_context("showcase_S3"), _SECOND_OPERATION))

    # The premise: the engine does see two operations of one session on this bill.
    assert report.audit_exposure_try > 0.0

    session = report.session_uplift
    assert len(session.opportunities) == 0
    assert session.review_opportunity_count == 0
    assert session.confirmed_uplift_try == 0.0
    assert session.total_uplift_try == 0.0


def test_secondary_below_the_allowed_rate_is_session_underbilling() -> None:
    """Positive control: the same bill with the second operation at 10 % of its list price."""
    clean = clean_context("showcase_S3")
    full = _report(with_extra_operation(clean, _SECOND_OPERATION))
    under = _report(with_extra_operation(clean, _SECOND_OPERATION, factor="0.1"))

    day = max(
        (line for line in clean.procedure_lines if line.procedure_category == "islem"),
        key=lambda line: line.billed_amount_try,
    ).procedure_date
    list_price = float(Decimal(str(get_ek2b_price_for_date(_SECOND_OPERATION, day))))
    expected = list_price * (_ALLOWED_FACTOR - 0.10)

    session = under.session_uplift
    assert [row["procedure_code"] for row in session.opportunities] == [_SECOND_OPERATION]
    assert session.opportunities[0]["included_in_sgk_total"] is True
    assert session.confirmed_uplift_try == pytest.approx(expected, abs=0.01)
    # The uplift is in the headline, and it is the only thing that moved it.
    assert under.sgk_uplift_try - full.sgk_uplift_try == pytest.approx(
        session.confirmed_uplift_try, abs=0.01
    )

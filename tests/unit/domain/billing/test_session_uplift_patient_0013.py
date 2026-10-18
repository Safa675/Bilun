"""Regression: must-package operations billed itemised show the package gap, not a session uplift.

Was SENTETIK-HASTA-0013 of the 50-patient set (609270 and 610070, two must-package lines on one claim).
The showcase bill of the same shape is S1 (laparoscopic appendectomy, a mandated package billed itemised);
the second must-package operation is added in memory (`tests/fixtures/t1_showcase_bills.py`).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset
from tests.fixtures import synthetic_cohort as cohort
from tests.fixtures.t1_showcase_bills import with_extra_operation

pytestmark = pytest.mark.unit

ROLE = cohort.role("showcase_S1")
# An EK-2/B operation that is also an EK-2/C package: next to the S1 appendectomy it is a second
# must-package line of the same claim.
SECOND_MUST_PACKAGE_OPERATION = "603840"


def _report(ctx):
    return compute_patient_billing_report(
        ctx.patient_id,
        claim_context=ctx,
        copay_exemption={"exempt": False},
    )


def _must_package_codes(report) -> set[str]:
    return {
        row["procedure_code"]
        for row in report.billing_strategy.recommendations
        if row.get("type") == "compliance_violation"
    }


def _claim_rows(report) -> list[dict]:
    return [
        row
        for row in report.billing_strategy.recommendations
        if row.get("recommendation_kind") and row["claim_id"] == ROLE.claim_id
    ]


def test_must_package_lines_show_the_package_gap_not_a_session_uplift() -> None:
    # Review item 9: the must-package lines of an itemised claim had both a payment-method risk and a
    # session uplift. The mandated-package comparison (#269) owns the claim now.
    dataset = load_sut_claim_dataset()
    ctx = build_patient_claim_context(ROLE.patient_id, dataset)
    assert ctx is not None
    ctx = with_extra_operation(ctx, SECOND_MUST_PACKAGE_OPERATION)

    report = _report(ctx)

    # The premise: both operations are must-package lines of the claim.
    mandated = _must_package_codes(report)
    assert SECOND_MUST_PACKAGE_OPERATION in mandated
    assert len(mandated) == 2

    assert not any(row["procedure_code"] in mandated for row in report.session_uplift.opportunities)
    rows = _claim_rows(report)
    assert len(rows) == 1
    row = rows[0]
    assert (row["payment_method_kind"], row["current_billing"]) == ("DRG_MANDATORY", "itemized")
    assert row["savings_try"] == pytest.approx(
        abs(row["itemized_total_try"] - row["package_total_try"]),
        abs=0.01,
    )
    # Nothing is counted twice: the headline is the package gap.
    assert report.session_uplift.confirmed_uplift_try == 0.0
    assert report.sgk_uplift_try == pytest.approx(row["savings_try"], abs=0.01)


def test_the_committed_s1_bill_has_the_same_shape_with_the_proven_amount() -> None:
    """The bill as committed (one must-package operation): the gap is the amount the registry proved."""
    dataset = load_sut_claim_dataset()
    ctx = build_patient_claim_context(ROLE.patient_id, dataset)
    assert ctx is not None

    report = _report(ctx)

    assert report.session_uplift.opportunities == []
    rows = _claim_rows(report)
    assert len(rows) == 1
    assert (rows[0]["payment_method_kind"], rows[0]["current_billing"]) == (
        "DRG_MANDATORY",
        "itemized",
    )
    assert Decimal(str(rows[0]["savings_try"])).quantize(Decimal("0.01")) == Decimal(
        cohort.fault("S1")["amount_try"]
    )
    assert report.sgk_uplift_try == pytest.approx(rows[0]["savings_try"], abs=0.01)

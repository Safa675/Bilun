"""Regression: SENTETIK-HASTA-0013, a session underbilling demo on must-package lines."""

from __future__ import annotations

import pytest

from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset

pytestmark = pytest.mark.unit

PATIENT_ID = "SENTETIK-HASTA-0013"


def test_sentetik_0013_must_package_lines_show_the_package_gap_not_a_session_uplift() -> None:
    # Review item 9: 609270 and 610070 must be billed as EK-2/C packages on this
    # outpatient claim (§2.2.1.B-1(a)), so 610070 had both a payment-method risk
    # (360.40) and a session uplift (720.79). The mandated-package comparison
    # (#269) owns the claim now.
    dataset = load_sut_claim_dataset()
    ctx = build_patient_claim_context(PATIENT_ID, dataset)
    assert ctx is not None

    report = compute_patient_billing_report(
        PATIENT_ID,
        claim_context=ctx,
        copay_exemption={"exempt": False},
    )

    assert not any(
        row["procedure_code"] == "610070" for row in report.session_uplift.opportunities
    )
    rows = [
        row for row in report.billing_strategy.recommendations
        if row.get("recommendation_kind") and row["claim_id"] == "F-SENTETIK-HASTA-0013-027"
    ]
    assert len(rows) == 1
    row = rows[0]
    assert (row["payment_method_kind"], row["current_billing"]) == ("DRG_MANDATORY", "itemized")
    assert row["savings_try"] == pytest.approx(
        abs(row["itemized_total_try"] - row["package_total_try"]), abs=0.01,
    )

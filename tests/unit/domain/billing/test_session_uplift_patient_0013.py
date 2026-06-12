"""Regression: SENTETIK-HASTA-0013 intentional session underbilling demo."""

from __future__ import annotations

import pytest

from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset

pytestmark = pytest.mark.unit

PATIENT_ID = "SENTETIK-HASTA-0013"


def test_sentetik_0013_session_uplift_demo() -> None:
    dataset = load_sut_claim_dataset()
    ctx = build_patient_claim_context(PATIENT_ID, dataset)
    assert ctx is not None

    report = compute_patient_billing_report(
        PATIENT_ID,
        claim_context=ctx,
        copay_exemption={"exempt": False},
        chapters={"I", "M", "N", "R", "Z"},
    )

    session = report.session_uplift
    assert len(session.opportunities) >= 1
    assert session.confirmed_uplift_try > 0
    assert any(row["procedure_code"] == "610070" for row in session.opportunities)
    assert report.sgk_uplift_try == pytest.approx(session.confirmed_uplift_try, rel=0.01)

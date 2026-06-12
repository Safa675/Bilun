"""Regression: SENTETIK-HASTA-0001 must not show false session uplift on full-list billing."""

from __future__ import annotations

import pytest

from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset

pytestmark = pytest.mark.unit

PATIENT_ID = "SENTETIK-HASTA-0001"


def test_sentetik_0001_no_false_session_uplift() -> None:
    """Full EK-2B list billing is not session underbilling (§2.2.2 uses list × factor)."""
    dataset = load_sut_claim_dataset()
    ctx = build_patient_claim_context(PATIENT_ID, dataset)
    assert ctx is not None

    report = compute_patient_billing_report(
        PATIENT_ID,
        claim_context=ctx,
        copay_exemption={"exempt": False},
        chapters={"I"},
    )

    session = report.session_uplift
    assert len(session.opportunities) == 0
    assert session.review_opportunity_count == 0
    assert session.confirmed_uplift_try == 0.0
    assert session.total_uplift_try == 0.0

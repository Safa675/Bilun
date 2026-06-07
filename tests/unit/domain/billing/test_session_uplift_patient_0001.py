"""Regression: SENTETIK-HASTA-0001 session uplift totals after clinical-review filter."""

from __future__ import annotations

import pytest

from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset

pytestmark = pytest.mark.unit

PATIENT_ID = "SENTETIK-HASTA-0001"


def test_sentetik_0001_session_uplift_totals() -> None:
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
    assert len(session.opportunities) == 15
    assert session.review_opportunity_count == 4
    assert session.total_uplift_try == pytest.approx(16573.83, rel=0.01)
    assert session.confirmed_uplift_try == pytest.approx(3245.9, rel=0.01)
    assert session.review_uplift_try == pytest.approx(13327.93, rel=0.01)

    assert report.sgk_uplift_try == pytest.approx(3245.9, rel=0.01)
    assert report.total_recoverable_try == report.sgk_uplift_try
    assert report.audit_exposure_try > 0

    clinical_codes = {
        row["procedure_code"]
        for row in session.opportunities
        if row.get("review_kind") == "needs_clinical_review"
    }
    assert clinical_codes == {"520080", "L107700", "520090", "L108960"}

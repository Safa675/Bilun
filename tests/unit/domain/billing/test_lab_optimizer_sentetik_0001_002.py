"""Regression test for lab optimizer on SENTETIK-HASTA-0001-002.

Before the fix, the optimizer consumed raw clinical lab result rows and produced
phantom duplicates (4 Kortizol + 4 İdrar + 3 HLA session-fraction flags). After the
fix it uses the 3 billed lab claim lines as the source of truth and does NOT apply
session-fraction rules to lab tests.
"""

from __future__ import annotations

import polars as pl
import pytest

pytestmark = pytest.mark.unit


def test_sentetik_0001_002_lab_optimizer_uses_claim_lines() -> None:
    from src.bilun.cache.loaders import _normalize_lab
    from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
    from src.bilun.domain.claims.loader import load_sut_claim_dataset
    from src.bilun.domain.claims.patient_context import build_bill_claim_context

    dataset = load_sut_claim_dataset("data/synthetic/sut/claims")
    lab_df = _normalize_lab(
        pl.read_parquet("data/synthetic/sut/clean/lab_clean.parquet")
    )

    ctx = build_bill_claim_context(
        "SENTETIK-HASTA-0001",
        "F-SENTETIK-HASTA-0001-002",
        dataset,
    )
    assert ctx is not None

    report = compute_patient_billing_report(
        "SENTETIK-HASTA-0001",
        claim_context=ctx,
        lab_df_pl=lab_df,
    )

    # No session-fraction flags for lab tests; no phantom duplicates from 12 result rows.
    session_flags = [
        f
        for f in report.lab.flagged_tests
        if f["flag_type"] == "session_fraction_overbilling"
    ]
    assert len(session_flags) == 0
    assert report.lab.session_fraction_savings == 0.0

    # No lab capture-gap false positives from the 4 result rows per code.
    lab_gaps = [
        o
        for o in report.procedure_capture_gap.opportunities
        if o.get("type") == "lab_performed_not_submitted"
    ]
    assert len(lab_gaps) == 0

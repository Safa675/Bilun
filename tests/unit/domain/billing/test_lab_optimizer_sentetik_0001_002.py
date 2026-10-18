"""Regression test for the lab optimizer: billed lab lines, not raw lab result rows.

Was SENTETIK-HASTA-0001-002 of the 50-patient set. Before the fix, the optimizer consumed raw clinical lab
result rows and produced phantom duplicates (4 Kortizol + 4 İdrar + 3 HLA session-fraction flags). After the
fix it uses the billed lab claim lines as the source of truth and does NOT apply session-fraction rules to
lab tests. The showcase bill that has many result rows behind few billed lab lines is S1 (the default
landing): the clean lab table holds one row per parameter of each billed lab line.
"""

from __future__ import annotations

from dataclasses import replace

import polars as pl
import pytest

from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit

ROLE = cohort.role("showcase_S1")


def _bill_and_lab_feed():
    """The S1 claim context and the clean lab table, both read from the committed demo data."""
    from src.bilun.cache.loaders import _normalize_lab
    from src.bilun.domain.claims.config import (
        DEFAULT_SYNTHETIC_CLAIMS_DIR,
        DEFAULT_SYNTHETIC_CLEAN_DIR,
    )
    from src.bilun.domain.claims.loader import load_sut_claim_dataset
    from src.bilun.domain.claims.patient_context import build_bill_claim_context

    dataset = load_sut_claim_dataset(DEFAULT_SYNTHETIC_CLAIMS_DIR)
    lab_df = _normalize_lab(pl.read_parquet(DEFAULT_SYNTHETIC_CLEAN_DIR / "lab_clean.parquet"))
    ctx = build_bill_claim_context(ROLE.patient_id, ROLE.claim_id, dataset)
    assert ctx is not None
    return ctx, lab_df


def _lab_findings(ctx, lab_df):
    from src.bilun.domain.billing.orchestrator import compute_patient_billing_report

    report = compute_patient_billing_report(
        ROLE.patient_id,
        claim_context=ctx,
        lab_df_pl=lab_df,
    )
    session_flags = [
        f for f in report.lab.flagged_tests if f["flag_type"] == "session_fraction_overbilling"
    ]
    lab_gaps = [
        o
        for o in report.procedure_capture_gap.opportunities
        if o.get("type") == "lab_performed_not_submitted"
    ]
    return report, session_flags, lab_gaps


def test_lab_optimizer_uses_claim_lines() -> None:
    ctx, lab_df = _bill_and_lab_feed()

    # The premise: more result rows stand behind this bill than it has billed lab lines.
    billed_lab_lines = [
        line for line in ctx.procedure_lines if line.procedure_category == "laboratuvar"
    ]
    result_rows = lab_df.filter(pl.col("visit_id") == ctx.claims[0].episode_id).height
    assert billed_lab_lines
    assert result_rows > len(billed_lab_lines)

    report, session_flags, lab_gaps = _lab_findings(ctx, lab_df)

    # No session-fraction flags for lab tests; no phantom duplicates from the extra result rows.
    assert len(session_flags) == 0
    assert report.lab.session_fraction_savings == 0.0

    # No lab capture-gap false positives from the several result rows per billed code.
    assert len(lab_gaps) == 0


def test_lab_result_without_a_billed_line_is_a_capture_gap() -> None:
    """Positive control: the capture-gap path ran, so the zeros above are not an unread feed's zeros.
    One billed lab line is taken off the bill: its results are now performed and not submitted."""
    ctx, lab_df = _bill_and_lab_feed()
    dropped = next(line for line in ctx.procedure_lines if line.procedure_category == "laboratuvar")
    without = replace(
        ctx,
        procedure_lines=tuple(
            line
            for line in ctx.procedure_lines
            if line.procedure_line_id != dropped.procedure_line_id
        ),
    )

    _report, session_flags, lab_gaps = _lab_findings(without, lab_df)

    assert [gap["procedure_code"] for gap in lab_gaps] == [dropped.procedure_code]
    assert len(session_flags) == 0

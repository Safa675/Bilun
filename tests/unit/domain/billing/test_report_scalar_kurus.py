"""Money report scalars keep their kuruş (showcase S7: 1,138.22 TL, not 1138).

``_apply_report_scalar`` casts a report scalar to the type of its spec's
``scalar_default``; the money scalars used to inherit the int default ``0``.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from src.bilun.domain.billing.block_registry import BILLING_BLOCK_SPECS
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.billing.report_totals import finalize_report_totals
from src.bilun.domain.billing.types import EXACTNESS_STATUS_EXACT, BillingActionReport
from src.bilun.domain.claims.models import PerformedProcedureLine
from tests.unit._helpers.catalog_prices import list_price
from tests.unit.domain.billing.test_showcase_session_and_package_gaps import s7

pytestmark = pytest.mark.unit

_MONEY_SCALARS = [
    spec for spec in BILLING_BLOCK_SPECS
    if spec.report_scalar and spec.report_scalar.endswith("_try")
]


def test_s7_capture_gap_keeps_its_kurus() -> None:
    bill = s7()
    bill.procs = [line for line in bill.procs if line.procedure_code != "R101450"]
    day = bill.start
    performed = tuple(
        PerformedProcedureLine(
            performed_line_id=f"C-SH07-EMR{i:02d}", claim_id="C-SH07", patient_id="SH",
            episode_id="E", service_date=day, procedure_code=code, procedure_name=code,
            source="pacs" if code == "R101450" else "emr",
        )
        for i, code in enumerate(("530100", "530080", "801720", "R101450"), start=1)
    )
    ctx = replace(bill.ctx(), performed_procedure_lines=performed)
    report = compute_patient_billing_report(ctx.patient_id, claim_context=ctx)
    assert report.capture_gap_try == list_price("R101450", day)  # The CT's list price; was cast to int.
    assert isinstance(report.capture_gap_try, float)


def test_report_scalar_defaults_match_their_type() -> None:
    assert [spec.report_scalar for spec in _MONEY_SCALARS] == [
        "capture_gap_try", "package_adequacy_review_try",
    ]
    for spec in BILLING_BLOCK_SPECS:
        if spec.report_scalar:
            expected = float if spec in _MONEY_SCALARS else int
            assert type(spec.scalar_default) is expected, spec.report_scalar


@pytest.mark.parametrize("spec", _MONEY_SCALARS, ids=lambda spec: spec.report_scalar)
def test_every_money_report_scalar_keeps_its_kurus(spec) -> None:
    report = BillingActionReport()
    block = getattr(report, spec.attr)
    block.exactness_status = EXACTNESS_STATUS_EXACT
    block.opportunities = [{
        "recoverable_gap_try": 1138.22,
        "recoverable_uplift_try": 1138.22,
        "included_in_sgk_total": False,
    }]
    finalize_report_totals(report)
    assert getattr(report, spec.report_scalar) == 1138.22

"""A package-mandated bill shows the package gap once.

Showcase S1 (reports/synthetic-data/2026-10-15-showcase-proofs/stories.py) is a
laparoscopic appendectomy that must be billed as EK-2/C package P610131 (group C,
8-day window) but was billed hizmet başı. The package includes bed, anaesthesia and
companion (SUT §2.2.2.B-1(1)(a), (g), (h)) from admission through the window
(§2.2.2.B-1(3)); days after it are billed separately (§2.2.2.B-1(4)). The billing
strategy row already reports the package gap, so these components add nothing
inside the window. The mandate is read from the codes, never from the synthetic-only
``package_candidate`` header flag.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from src.bilun.domain.billing.claim_strategy import recommend_billing_strategy_from_claims
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.yatak_puani import claim_package_window, mandated_package_lines
from tests.unit.domain.billing.test_showcase_session_and_package_gaps import (
    ANEST,
    GENCER,
    ORTO,
    _Bill,
    _d,
    s1,
    s2,
    s3,
    s4,
)

pytestmark = pytest.mark.unit

_BED_DAY = 222.36  # 510010 in force in 2026 (bed rate on S1/S2 days).
_COMPANION_NIGHT = 74.10  # 510121: 124.95 puan × 0.593.


def _report(ctx: PatientClaimContext):
    return compute_patient_billing_report(ctx.patient_id, claim_context=ctx)


def _only(rows: list[dict]) -> dict:
    assert len(rows) == 1, rows
    return rows[0]


def _strategy_savings(ctx: PatientClaimContext) -> float:
    rows = recommend_billing_strategy_from_claims(ctx).recommendations
    return _only([row for row in rows if row.get("recommendation_kind")])["savings_try"]


def _without(bill: _Bill, code: str, *, after=None) -> _Bill:
    """Drop the lines of ``code`` (only those dated after ``after`` when given)."""
    bill.procs = [
        line for line in bill.procs
        if line.procedure_code != code or (after is not None and line.procedure_date <= after)
    ]
    return bill


def _long_s1(*, bed_days: int, bed_qty: int = 1) -> _Bill:
    """Faulty S1 kept 12 days (14–25 July): window through 21 July, 4 days after it."""
    a = _d("2026-07-14")
    bill = _Bill("C-SH01", "yatis", a, _d("2026-07-25"), package_candidate=True)
    bill.proc("610131", a, specialty=GENCER)
    bill.proc("550170", a, specialty=ANEST)
    for i in range(bed_days):
        bill.proc("510010", a + timedelta(days=i), qty=bed_qty, specialty=GENCER)
    bill.labs(a, ("L107020", "L101850"), GENCER)
    return bill


class TestMandatedPackageShownOnce:
    def test_faulty_s1_shows_the_package_gap_once(self) -> None:
        ctx = s1("faulty").ctx()
        report = _report(ctx)
        assert _strategy_savings(ctx) == 4085.87
        assert report.sgk_uplift_try == 4085.87  # Was 4,234.07: + 148.20 companion.
        companion = _only(report.refakatci.opportunities)
        assert (companion["days"], companion["recoverable_uplift_try"]) == (0, 0.0)
        assert companion["included_in_sgk_total"] is False
        assert companion["suppression_notes"][:2] == [
            "package_window_bundled (§2.2.2.B-1(1)(h), (3))",
            "package_mandated_billed_itemized (§2.2.2(1))",
        ]
        bed = _only(report.yatak_puani.opportunities)
        assert (bed["gross_bed_days"], bed["bundled_days"], bed["bed_days"]) == (3, 3, 0)
        assert report.yatak_puani.confirmed_yatak_try == 0.0
        assert report.anestezi_puani.opportunities == []

    def test_missing_anaesthesia_and_bed_inside_the_window_add_nothing(self) -> None:
        # Was +530.33 (550170) and +444.72 (two bed days) on top of the package gap.
        bill = _without(_without(s1("faulty"), "550170"), "510010", after=_d("2026-07-14"))
        ctx = bill.ctx()
        report = _report(ctx)
        assert report.anestezi_puani.opportunities == []
        assert report.yatak_puani.confirmed_yatak_try == 0.0
        assert report.refakatci.confirmed_refakat_try == 0.0
        assert report.sgk_uplift_try == _strategy_savings(ctx)

    def test_days_after_the_window_are_still_expected(self) -> None:
        ctx = _long_s1(bed_days=8).ctx()  # Beds billed 14–21 July only, no companion.
        window = claim_package_window(ctx.claims[0], list(ctx.procedure_lines))
        assert (window.start, window.end, window.mandated) == (
            _d("2026-07-14"), _d("2026-07-21"), True,
        )
        report = _report(ctx)
        bed = _only(report.yatak_puani.opportunities)
        # 22–25 July; the in-window lines belong to the package.
        assert (bed["bed_days"], bed["actual_billed_try"]) == (4, 0.0)
        assert bed["recoverable_uplift_try"] == round(4 * _BED_DAY, 2)
        companion = _only(report.refakatci.opportunities)  # Nights of 22, 23, 24 July.
        assert (companion["days"], companion["included_in_sgk_total"]) == (3, True)
        assert companion["recoverable_uplift_try"] == round(3 * _COMPANION_NIGHT, 2)
        assert report.sgk_uplift_try == round(
            _strategy_savings(ctx) + 4 * _BED_DAY + 3 * _COMPANION_NIGHT, 2,
        )

    def test_a_bed_line_reaching_past_the_window_still_counts(self) -> None:
        # One 510010 line for the whole stay (quantity 12, dated on admission)
        # also pays the days after the window: nothing is expected twice.
        report = _report(_long_s1(bed_days=1, bed_qty=12).ctx())
        bed = _only(report.yatak_puani.opportunities)
        assert (bed["bed_days"], bed["actual_billed_try"]) == (4, round(12 * _BED_DAY, 2))
        assert bed["recoverable_uplift_try"] == 0.0

    def test_the_package_candidate_flag_is_not_read(self) -> None:
        # package_candidate comes only from the synthetic generator; the codes alone
        # say 610131 must be the package, so nothing inside it is expected.
        bill = _without(s1("faulty", package_candidate=False), "550170")
        ctx = bill.ctx()
        assert ctx.claims[0].package_candidate is False
        assert [line.procedure_code for line in mandated_package_lines(
            ctx.claims[0], list(ctx.procedure_lines),
        )] == ["610131"]
        report = _report(ctx)
        assert report.refakatci.confirmed_refakat_try == 0.0  # Was 148.20.
        assert report.anestezi_puani.opportunities == []  # Was 530.33.
        assert report.yatak_puani.confirmed_yatak_try == 0.0


class TestMandateFromTheCodes:
    def test_a_billed_package_is_not_a_mandated_line(self) -> None:
        bill = s1("clean")  # P610131 billed as the package.
        bill.proc("610131", bill.start, specialty=GENCER)
        ctx = bill.ctx()
        assert mandated_package_lines(ctx.claims[0], list(ctx.procedure_lines)) == []
        window = claim_package_window(ctx.claims[0], list(ctx.procedure_lines))
        assert (window.end, window.mandated) == (_d("2026-07-21"), False)

    def test_a_p_code_counts_as_billed_as_package(self) -> None:
        # ``line_billed_as_package``: the paket category or a P code.
        bill = s1("clean")
        bill.procs = [replace(bill.procs[0], procedure_category="islem")]
        ctx = bill.ctx()
        assert mandated_package_lines(ctx.claims[0], list(ctx.procedure_lines)) == []
        assert claim_package_window(ctx.claims[0], list(ctx.procedure_lines)).mandated is False

    @pytest.mark.parametrize(
        "tier, companion",
        [("2_3_basamak_ozel", 0.0), ("egitim_arastirma", round(2 * _COMPANION_NIGHT, 2))],
        ids=["mandated", "third_tier_may_bill_hizmet_basi"],
    )
    def test_the_mandate_follows_the_facility_tier(self, tier: str, companion: float) -> None:
        # 613730 has no star: a third-tier hospital may bill it hizmet başı
        # (§2.2.2(2)), so the companion nights stay expected there.
        a = _d("2026-07-14")
        bill = _Bill("C-ORTO", "yatis", a, a + timedelta(days=2), tier=tier)
        bill.proc("613730", a, specialty=ORTO)
        assert _report(bill.ctx()).refakatci.confirmed_refakat_try == companion


class TestClaimsWithoutAMandatedPackage:
    def test_s2_bed_s3_anaesthesia_and_s4_companion_still_fire(self) -> None:
        s2_faulty = _without(s2(), "510010", after=_d("2026-03-12"))
        s3_faulty = _without(s3(), "550160")
        s4_faulty = _without(s4(), "510121")
        for bill in (s2_faulty, s3_faulty, s4_faulty):
            ctx = bill.ctx()
            assert claim_package_window(ctx.claims[0], list(ctx.procedure_lines)) is None
        assert _report(s2_faulty.ctx()).yatak_puani.confirmed_yatak_try == 667.08
        assert _report(s3_faulty.ctx()).anestezi_puani.confirmed_anestezi_try == 928.09
        assert _report(s4_faulty.ctx()).refakatci.confirmed_refakat_try == 370.50

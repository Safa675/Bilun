"""Unit tests for yatak puanı (bed-day billing) detector."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit


def _make_claim_header(
    *,
    claim_id: str = "C1",
    claim_type: str = "yatis",
    admission: date | None = date(2026, 7, 10),
    discharge: date | None = date(2026, 7, 13),
):
    from src.bilun.domain.claims.models import ClaimHeader

    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        claim_type=claim_type,
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department="genel",
        admission_date=admission,
        discharge_date=discharge,
        claim_start_date=admission or date.today(),
        claim_end_date=discharge or date.today(),
        primary_icd10="Z00.0",
        package_candidate=False,
        expected_total_billed_try=Decimal("1000"),
        expected_total_payable_try=Decimal("900"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def test_inpatient_4day_stay() -> None:
    """Inpatient claim Jul 10→13 → 4 bed-days (inclusive LOS)."""
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 13))
    opps = detect_yatak_puani_opportunities([header], claim_ids_with_procs={"C1"})

    assert len(opps) == 1
    opp = opps[0]
    assert opp["bed_days"] == 4
    assert opp["daily_rate_try"] == pytest.approx(222.36, abs=0.01)
    # 4 × 222.36 = 889.44
    assert opp["expected_yatak_try"] == pytest.approx(889.44, abs=0.01)
    assert opp["rule_id"] == "yatak_puani_510010"
    assert opp["included_in_sgk_total"] is True


def test_same_day_stay_flags_gunduz() -> None:
    """Same-day admission/discharge → 1 day billable, priced at the day bed 510120 (SUT §2.2.2.(3)), not a full 510010 day."""
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 10)
    )
    opps = detect_yatak_puani_opportunities([header], claim_ids_with_procs={"C1"})

    assert len(opps) == 1
    opp = opps[0]
    assert opp["bed_days"] == 1
    assert opp["same_day_stay"] is True
    assert opp["bed_code"] == "510120"
    # 74.96 puan = 44.45 TRY on the 2026-07-07 list (a full 510010 day is 222.36).
    assert opp["daily_rate_try"] == pytest.approx(44.45, abs=0.005)
    assert opp["expected_yatak_try"] == pytest.approx(44.45, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(44.45, abs=0.005)
    assert opp["rule_id"] == "yatak_puani_510010"  # the §2.2.2 bed-day rule; bed_code names the priced code
    assert "510120" in opp["detail"]


def test_outpatient_skipped() -> None:
    """Outpatient claim → no opportunity."""
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    header = _make_claim_header(claim_type="ayakta")
    opps = detect_yatak_puani_opportunities([header], claim_ids_with_procs={"C1"})
    assert opps == []


def test_null_dates_skipped() -> None:
    """Null admission or discharge → no opportunity."""
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    header = _make_claim_header(admission=None, discharge=date(2026, 7, 13))
    assert detect_yatak_puani_opportunities([header], claim_ids_with_procs={"C1"}) == []

    header2 = _make_claim_header(admission=date(2026, 7, 10), discharge=None)
    assert detect_yatak_puani_opportunities([header2], claim_ids_with_procs={"C1"}) == []


def test_claim_without_procs_skipped() -> None:
    """Claim not in claim_ids_with_procs → skipped."""
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    header = _make_claim_header()
    # C1 NOT in the set
    opps = detect_yatak_puani_opportunities([header], claim_ids_with_procs={"OTHER"})
    assert opps == []


def test_historical_2023_claim_uses_2023_bed_tariff() -> None:
    """2023 inpatient claim resolves the 2023 510010 tariff (82.36 TRY), not 2026."""
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    header = _make_claim_header(
        admission=date(2023, 6, 10), discharge=date(2023, 6, 13)
    )
    opps = detect_yatak_puani_opportunities([header], claim_ids_with_procs={"C1"})
    assert len(opps) == 1
    assert opps[0]["daily_rate_try"] == pytest.approx(82.36, abs=0.01)
    assert opps[0]["expected_yatak_try"] == pytest.approx(4 * 82.36, abs=0.01)


def test_confirmed_yatak_and_actions_use_recoverable_gap() -> None:
    """confirmed_yatak_try and collect_billing_actions use recoverable_uplift_try and skip zero-gap rows (#233)."""
    from decimal import Decimal

    from src.bilun.domain.billing.billing_actions import collect_billing_actions
    from src.bilun.domain.billing.types import (
        BillingActionReport,
        IcuPuaniReview,
        YatakPuaniReview,
    )
    from src.bilun.domain.claims.models import ProcedureClaimLine
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    header = _make_claim_header(
        claim_id="F-SENTETIK-HASTA-0001-005",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 13),
    )

    def _bed_line(billed: str) -> ProcedureClaimLine:
        return ProcedureClaimLine(
            procedure_line_id="L-BED",
            claim_id=header.claim_id,
            patient_id="P1",
            episode_id="E1",
            procedure_date=date(2026, 7, 10),
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_category="yatak",
            quantity=1,
            unit_price_try=Decimal(billed),
            billed_amount_try=Decimal(billed),
            expected_payable_try=Decimal(billed),
            is_package_included=False,
            package_code="",
            surcharge_applicable=False,
            copay_rate_applicable=False,
            denial_reason_expected="",
            rule_trace_expected="",
        )

    # Partial billing: 889.44 expected, 693.76 billed -> 195.68 recoverable
    partial_opps = detect_yatak_puani_opportunities([header], [_bed_line("693.76")])
    partial_review = YatakPuaniReview(opportunities=partial_opps, exactness_status="exact")
    assert partial_review.confirmed_yatak_try == pytest.approx(195.68, abs=0.01)
    partial_actions = collect_billing_actions(
        BillingActionReport(patient_id="P1", yatak_puani=partial_review)
    )
    yatak_actions = [a for a in partial_actions if a["surface"] == "yatak_puani"]
    assert len(yatak_actions) == 1
    assert yatak_actions[0]["sgk_uplift_try"] == pytest.approx(195.68, abs=0.01)

    # Full billing: 889.44 billed against 889.44 expected -> 0.0 recoverable, no action
    full_opps = detect_yatak_puani_opportunities([header], [_bed_line("889.44")])
    full_review = YatakPuaniReview(opportunities=full_opps, exactness_status="exact")
    assert full_review.confirmed_yatak_try == 0.0
    full_actions = collect_billing_actions(
        BillingActionReport(patient_id="P1", yatak_puani=full_review)
    )
    assert [a for a in full_actions if a["surface"] == "yatak_puani"] == []

    # Fully billed ICU stay: recoverable_uplift_try == 0.0 does not fall back to total_try
    icu_review = IcuPuaniReview(
        opportunities=[
            {
                "claim_id": "C-ICU",
                "total_try": 5000.0,
                "actual_billed_try": 5000.0,
                "recoverable_uplift_try": 0.0,
                "included_in_sgk_total": True,
            }
        ],
        exactness_status="exact",
    )
    assert icu_review.confirmed_icu_try == 0.0


def test_package_window_bundles_stay_inside_and_bills_excess_days() -> None:
    """SUT §2.2.2.B-1(1), (3)-(4): EK-2/C package window bundles days through window end and bills only post-window days (#259)."""
    from src.bilun.domain.claims.models import ProcedureClaimLine
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    def _pkg_line(claim_id: str, code: str, proc_date: date) -> ProcedureClaimLine:
        return ProcedureClaimLine(
            procedure_line_id=f"PKG-{claim_id}",
            claim_id=claim_id,
            patient_id="P1",
            episode_id="E1",
            procedure_date=proc_date,
            procedure_code=code,
            procedure_name="Paket işlem",
            procedure_category="paket",
            quantity=1,
            unit_price_try=Decimal("5000.00"),
            billed_amount_try=Decimal("5000.00"),
            expected_payable_try=Decimal("5000.00"),
            is_package_included=True,
            package_code=f"P{code}",
            surcharge_applicable=False,
            copay_rate_applicable=False,
            denial_reason_expected="",
            rule_trace_expected="",
        )

    # Stay inside Group C (8-day) window: Jul 10 → Jul 15 (6 gross days), surgery Jul 11 (window through Jul 18) -> 0 billable days
    inside_claim = _make_claim_header(
        claim_id="C-IN",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 15),
    )
    inside_opps = detect_yatak_puani_opportunities(
        [inside_claim],
        [_pkg_line("C-IN", "610130", date(2026, 7, 11))],
    )
    assert len(inside_opps) == 1
    assert inside_opps[0]["gross_bed_days"] == 6
    assert inside_opps[0]["bundled_days"] == 6
    assert inside_opps[0]["bed_days"] == 0
    assert inside_opps[0]["expected_yatak_try"] == 0.0

    # Stay exceeding Group C (8-day) window: Jul 10 → Jul 20 (11 gross days), surgery Jul 11 (window through Jul 18) -> 2 post-window days (Jul 19, Jul 20)
    excess_claim = _make_claim_header(
        claim_id="C-OUT",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 20),
    )
    excess_opps = detect_yatak_puani_opportunities(
        [excess_claim],
        [_pkg_line("C-OUT", "610130", date(2026, 7, 11))],
    )
    assert len(excess_opps) == 1
    assert excess_opps[0]["gross_bed_days"] == 11
    assert excess_opps[0]["bundled_days"] == 9
    assert excess_opps[0]["bed_days"] == 2
    assert excess_opps[0]["expected_yatak_try"] == pytest.approx(2 * 222.36, abs=0.01)




def test_a_credit_line_never_makes_the_recoverable_exceed_the_expected_charge() -> None:
    """A negative 510010 line (a reversal) must not recover more than the stay's expected charge (889.44 on
    4 days): the newborn bed motor's stand-down hands such claims to this motor (review round 2, G4)."""
    from src.bilun.domain.claims.models import ProcedureClaimLine
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 13))
    credit = ProcedureClaimLine(
        procedure_line_id="L1", claim_id="C1", patient_id="P1", episode_id="E1", procedure_date=date(2026, 7, 10),
        procedure_code="510010", procedure_name="Standart yatak", procedure_category="islem", quantity=1,
        unit_price_try=Decimal("0"), billed_amount_try=Decimal("-222.36"), expected_payable_try=Decimal("0"),
        is_package_included=False, package_code="", surcharge_applicable=False, copay_rate_applicable=True,
        denial_reason_expected="", rule_trace_expected="",
    )

    [opp] = detect_yatak_puani_opportunities([header], [credit], claim_ids_with_procs={"C1"})

    assert opp["actual_billed_try"] == pytest.approx(-222.36, abs=0.005)
    assert opp["expected_yatak_try"] == pytest.approx(889.44, abs=0.01)
    assert opp["recoverable_uplift_try"] == pytest.approx(889.44, abs=0.01)  # was 1,111.80


def test_an_over_billed_standard_bed_recovers_nothing() -> None:
    """The floor: 510010 billed above the expected charge leaves 0, never a negative amount."""
    from src.bilun.domain.claims.models import ProcedureClaimLine
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 12))
    line = ProcedureClaimLine(
        procedure_line_id="L1", claim_id="C1", patient_id="P1", episode_id="E1", procedure_date=date(2026, 7, 10),
        procedure_code="510010", procedure_name="Standart yatak", procedure_category="islem", quantity=3,
        unit_price_try=Decimal("0"), billed_amount_try=Decimal("900.00"), expected_payable_try=Decimal("0"),
        is_package_included=False, package_code="", surcharge_applicable=False, copay_rate_applicable=True,
        denial_reason_expected="", rule_trace_expected="",
    )

    [opp] = detect_yatak_puani_opportunities([header], [line], claim_ids_with_procs={"C1"})

    assert opp["recoverable_uplift_try"] == 0.0


# --- SUT §2.2.2.(3): a stay under 24 hours is billed at the day bed 510120 -------------------------------
# 510120 "Gündüz yatak tarifesi" (74.96 puan = 44.45 TRY on the 2026-07-07 list) against 510010 222.36. The claim
# has dates, no times: a stay whose admission date equals its discharge date is certainly under 24 hours.


def _line(
    code: str,
    billed: str,
    *,
    claim_id: str = "C1",
    quantity: int = 1,
    line_id: str | None = None,
    procedure_date: date = date(2026, 7, 10),
    category: str = "islem",
):
    from src.bilun.domain.claims.models import ProcedureClaimLine

    return ProcedureClaimLine(
        procedure_line_id=line_id or f"{claim_id}-{code}-{billed}", claim_id=claim_id, patient_id="P1",
        episode_id="E1", procedure_date=procedure_date, procedure_code=code, procedure_name="bed",
        procedure_category=category, quantity=quantity, unit_price_try=Decimal("0"),
        billed_amount_try=Decimal(billed), expected_payable_try=Decimal("0"), is_package_included=False,
        package_code="", surcharge_applicable=False, copay_rate_applicable=True, denial_reason_expected="",
        rule_trace_expected="",
    )


def _one_date(lines=None, *, header=None):
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    header = header or _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 10))
    return detect_yatak_puani_opportunities([header], lines, claim_ids_with_procs={header.claim_id})


@pytest.mark.parametrize(
    ("lines", "actual", "recoverable"),
    [
        ([], 0.0, 44.45),
        ([("520010", "10")], 0.0, 44.45),  # an unrelated line
        ([("510120", "44.45")], 44.45, 0.0),  # billed correctly: the billed bed, nothing to recover
        ([(" 510120 ", "44.45")], 44.45, 0.0),  # the spelling of the code is read like 510010's
        ([("510120", "20.00")], 20.0, 24.45),  # billed in part
        ([("510120", "100.00")], 100.0, 0.0),  # billed above the day bed: never negative
        ([("510010", "222.36")], 222.36, 0.0),  # billed as a full standard day: nothing to recover (as before)
        ([("510010", "20.00")], 20.0, 24.45),
        ([("510120", "44.45"), ("510010", "222.36")], 266.81, 0.0),  # both codes net the one day
        ([("510120", "-44.45")], -44.45, 44.45),  # a reversal covers no day; capped at the charge, not 88.90
    ],
    ids=[
        "nothing", "unrelated", "day-bed-in-full", "day-bed-spelling", "day-bed-in-part", "day-bed-above",
        "standard-in-full", "standard-in-part", "both", "credit",
    ],
)
def test_billed_bed_lines_of_a_stay_of_one_date_net_the_day_bed(lines, actual, recoverable) -> None:
    [opp] = _one_date([_line(code, billed) for code, billed in lines])

    assert opp["bed_code"] == "510120"
    assert opp["expected_yatak_try"] == pytest.approx(44.45, abs=0.005)
    assert opp["actual_billed_try"] == pytest.approx(actual, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(recoverable, abs=0.005)


def test_the_detail_of_a_stay_of_one_date_says_what_was_priced_and_why() -> None:
    [opp] = _one_date()

    assert opp["detail"].startswith(
        "Gündüz yatak (510120): 1 billable bed-day(s) (gross LOS 1 day(s) at 44.45 TRY/day) = 44.45 TRY"
    )
    assert "Same-day admission/discharge (under 24 hours)" in opp["detail"]
    assert "SUT §2.2.2.(3)" in opp["detail"]
    assert "consider 510120" not in opp["detail"]  # the advice is now the price
    assert "Standart yatak" not in opp["detail"]


def test_a_stay_of_two_dates_is_still_priced_as_standard_bed_days() -> None:
    """Control: 10-11 July is no day-bed stay, whatever lines it carries."""
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 11))
    [opp] = _one_date([_line("510120", "44.45")], header=header)

    assert opp["bed_code"] == "510010"
    assert opp["same_day_stay"] is False
    assert opp["daily_rate_try"] == pytest.approx(222.36, abs=0.005)
    # A day-bed line pays no standard-bed day of a stay of two dates: it is not netted there.
    assert opp["actual_billed_try"] == 0.0
    assert opp["expected_yatak_try"] == pytest.approx(444.72, abs=0.01)
    assert opp["recoverable_uplift_try"] == pytest.approx(444.72, abs=0.01)
    assert "Gündüz" not in opp["detail"]


def test_the_detail_of_a_multi_day_stay_is_unchanged() -> None:
    """The frontend translates this exact sentence (apiMessages.ts): the day-bed rule must not reword a stay of
    two dates or more."""
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 13))
    [opp] = _one_date(header=header)

    assert opp["detail"] == (
        "Standart yatak (510010): 4 billable bed-day(s) (gross LOS 4 day(s) at 222.36 TRY/day) = 889.44 TRY "
        "(inclusive LOS, discharge day billed)."
    )


def test_the_day_bed_price_is_the_one_of_the_admission_date() -> None:
    header = _make_claim_header(admission=date(2023, 6, 10), discharge=date(2023, 6, 10))
    [opp] = _one_date(header=header)

    # 510120 on the 2023 list: 27.77 puan = 16.47 TRY (510010 was 82.36).
    assert opp["daily_rate_try"] == pytest.approx(16.47, abs=0.005)
    assert opp["expected_yatak_try"] == pytest.approx(16.47, abs=0.005)


def test_a_package_window_still_bundles_the_only_day_of_a_stay_of_one_date() -> None:
    """A group-B package on the day: the package includes the bed (§2.2.2.B-1), so no day bed is expected either."""
    [opp] = _one_date([_line("P600040", "5000", category="paket", line_id="PK")])

    assert (opp["gross_bed_days"], opp["bundled_days"], opp["bed_days"]) == (1, 1, 0)
    assert opp["expected_yatak_try"] == 0.0
    assert opp["recoverable_uplift_try"] == 0.0


def test_a_stay_of_one_date_without_a_day_bed_price_emits_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """No 510120 price on file: the full-day price must not stand in for it (pending is a valid state)."""
    from src.bilun.domain.prose_rules import yatak_puani

    real = yatak_puani.lookup_procedure_code
    monkeypatch.setattr(
        yatak_puani, "lookup_procedure_code",
        lambda code, visit_date=None: {} if code == "510120" else real(code, visit_date=visit_date),
    )

    assert _one_date() == []
    # A stay of two dates does not need the day bed.
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 11))
    assert len(_one_date(header=header)) == 1


@pytest.mark.parametrize("code", [" 510.120 ", "510 120", "510-120"])
def test_a_day_bed_line_is_read_like_the_newborn_motors_stand_down_reads_it(code: str) -> None:
    """The newborn motor stands down on a billed 510120 (spacing, dots and hyphens read by
    `normalize_procedure_code`) and hands the day to this motor: it must net the same spellings, or a correctly
    billed day bed shows as unbilled. (A `P` prefix names an EK-2/C package line, which also opens a window.)"""
    [opp] = _one_date([_line(code, "44.45")])

    assert opp["actual_billed_try"] == pytest.approx(44.45, abs=0.005)
    assert opp["recoverable_uplift_try"] == 0.0


@pytest.mark.parametrize("code", [" 510.010 ", "510 010", "510-010"])
def test_a_standard_bed_line_is_read_like_the_newborn_motors_stand_down_reads_it(code: str) -> None:
    """Same agreement for 510010 (before, only the exact code netted: a stay billed ' 510.010 ' showed its whole
    standard bed as unbilled once the newborn motor had stood down on it)."""
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 11))
    [opp] = _one_date([_line(code, "222.36")], header=header)

    assert opp["actual_billed_try"] == pytest.approx(222.36, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(222.36, abs=0.005)  # 444.72 - 222.36


def test_the_rule_source_names_the_day_bed() -> None:
    from src.bilun.domain.billing import claim_yatak_puani
    from src.bilun.domain.billing.types import YatakPuaniReview

    assert "510120" in claim_yatak_puani._PROSE_RULE_SOURCE
    assert YatakPuaniReview().rule_source == claim_yatak_puani._PROSE_RULE_SOURCE

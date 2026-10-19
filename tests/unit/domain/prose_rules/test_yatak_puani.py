"""Unit tests for yatak puanı (bed-day billing) detector."""

from __future__ import annotations

from datetime import date, timedelta
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
    assert (
        "Same-day admission/discharge (under 24 hours): SUT §2.2.2.(3) bills the bed at the day bed "
        "(510120, Gündüz yatak tarifesi), not as a full 510010 day."
    ) in opp["detail"]
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


def test_the_rule_source_names_the_day_bed() -> None:
    from src.bilun.domain.billing import claim_yatak_puani
    from src.bilun.domain.billing.types import YatakPuaniReview

    assert "510120" in claim_yatak_puani._PROSE_RULE_SOURCE
    assert YatakPuaniReview().rule_source == claim_yatak_puani._PROSE_RULE_SOURCE


def test_a_day_bed_line_inside_a_mandated_package_window_belongs_to_the_package() -> None:
    """A one-date stay whose operation must be billed as EK-2/C package P610131 (billed hizmet başı): the package
    includes the bed (§2.2.2.B-1), so no day bed is expected and a 510120 line dated in the window pays the package,
    not the day bed (`counts_against_expected_days`, as for a 510010 line)."""
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities
    from tests.unit.domain.billing.test_showcase_session_and_package_gaps import GENCER, _Bill, _d

    day = _d("2026-07-14")
    bill = _Bill("C-SH01", "yatis", day, day, package_candidate=True)
    bill.proc("610131", day, specialty=GENCER)
    bill.proc("510120", day, specialty=GENCER)
    ctx = bill.ctx()

    [opp] = detect_yatak_puani_opportunities(
        list(ctx.claims), list(ctx.procedure_lines), claim_ids_with_procs={"C-SH01"}
    )

    assert (opp["gross_bed_days"], opp["bundled_days"], opp["bed_days"]) == (1, 1, 0)
    assert opp["expected_yatak_try"] == 0.0
    assert opp["actual_billed_try"] == 0.0  # the line belongs to the package
    assert opp["recoverable_uplift_try"] == 0.0


def test_an_inherited_gap_is_pinned_a_spelled_510010_line_is_not_netted_by_this_motor() -> None:
    """Characterisation of INHERITED behaviour, pinned on purpose (found, not fixed; tasks/todo.md): this motor nets
    the exact code 510010 only, while the newborn motor's stand-down reads spacing, dots and hyphens. The day-bed change
    must not move a stay of two dates, spelled lines included; whoever closes the gap flips this test as a decision."""
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 11))
    [exact] = _one_date([_line("510010", "222.36")], header=header)
    assert exact["recoverable_uplift_try"] == pytest.approx(222.36, abs=0.005)  # 444.72 - 222.36

    for code in (" 510.010 ", "510 010", "510-010"):
        [spelled] = _one_date([_line(code, "222.36")], header=header)
        assert spelled["actual_billed_try"] == 0.0
        assert spelled["recoverable_uplift_try"] == pytest.approx(444.72, abs=0.005)


# --- The bed is already paid, or the day bed may not be billed (tasks/todo.md, 2026-10-19) -------------------------
# Evidence is quoted in test_bed_days_not_expected.py: 530000 / 510100 / 510110 cover the bed of the days they are
# billed on (EK-2/B "Yemek, yatak, hasta vizit hizmetlerini kapsar"); the day bed of a stay of one date is not billed
# beside 530000, inside a hemodialysis price (704210 / 704230, §2.4.4.D-1.(11)) or for the EK-2/C procedures of a day
# case (§2.2.2.(4)). 3 days = 10-12 July 2026: 510010 222.36, day bed 510120 44.45.


def _stay(days: int, lines=(), *, claim_type: str = "yatis"):
    header = _make_claim_header(
        claim_type=claim_type, admission=date(2026, 7, 10), discharge=date(2026, 7, 10) + timedelta(days=days - 1)
    )
    return _one_date(list(lines), header=header)


@pytest.mark.parametrize(
    ("code", "billed"),
    [("530000", "577.45"), ("704230", "4342.48"), ("704210", "4342.48"), (" 704.230 ", "4342.48"), (" 530.000 ", "577.45")],
)
def test_a_stay_of_one_date_whose_day_bed_the_sut_forbids_expects_no_day_bed(code: str, billed: str) -> None:
    [opp] = _one_date([_line(code, billed)])

    assert (opp["bed_code"], opp["same_day_stay"], opp["gross_bed_days"], opp["bed_days"]) == ("510120", True, 1, 0)
    assert opp["bundled_days"] == 0 and opp["surgery_day_bundled"] is False  # the package fields keep their meaning
    assert opp["daily_rate_try"] == pytest.approx(44.45, abs=0.005)  # the price stays visible
    assert opp["expected_yatak_try"] == 0.0
    assert opp["recoverable_uplift_try"] == 0.0
    assert "No day bed (510120) is expected" in opp["detail"]
    assert "Same-day admission/discharge (under 24 hours)" in opp["detail"]  # the sentence that explained the price stays


def test_the_sentence_names_the_er_bed_the_dialysis_and_the_clause() -> None:
    [er] = _one_date([_line("530000", "577.45")])
    [dialysis] = _one_date([_line("704230", "4342.48")])

    assert "530000 (Acil serviste kritik hasta yatak ve takibi) is billed on this claim" in er["detail"]
    assert "does not bill 510120 together with it" in er["detail"]
    assert "hemodialysis (704230) is billed on this claim" in dialysis["detail"]
    assert "includes the day bed fee" in dialysis["detail"] and "§2.4.4.D-1.(11)" in dialysis["detail"]


def test_a_day_bed_billed_beside_530000_or_dialysis_is_not_a_recoverable() -> None:
    """The pair is itself forbidden (an audit matter); the motor only must not expect the bed."""
    for code in ("530000", "704230"):
        [opp] = _one_date([_line(code, "577.45"), _line("510120", "44.45", line_id="DB")])

        assert opp["bed_days"] == 0 and opp["expected_yatak_try"] == 0.0
        assert opp["actual_billed_try"] == pytest.approx(44.45, abs=0.005)  # still the billed bed line
        assert opp["recoverable_uplift_try"] == 0.0


@pytest.mark.parametrize("code", ["530003", "704233", "704290"])
def test_other_codes_leave_the_day_bed_of_a_stay_of_one_date_alone(code: str) -> None:
    """530003 is only the code 530000 is not billed with; 704233 is home hemodialysis (no bed to include) and 704290
    continuous hemodiafiltration, neither "Hemodiyaliz tedavisi" of D-1.(11)."""
    [opp] = _one_date([_line(code, "100.00")])

    assert opp["bed_days"] == 1
    assert opp["recoverable_uplift_try"] == pytest.approx(44.45, abs=0.005)
    assert "No day bed" not in opp["detail"]


@pytest.mark.parametrize("code", ["530000", "704230"])
def test_a_reversed_line_leaves_the_day_bed_alone(code: str) -> None:
    [opp] = _one_date([_line(code, "-100.00")])

    assert opp["bed_days"] == 1
    assert opp["recoverable_uplift_try"] == pytest.approx(44.45, abs=0.005)
    assert "No day bed" not in opp["detail"]


def test_a_dialysis_billed_as_an_ek2c_package_is_still_bundled_not_explained_twice() -> None:
    """P704230 opens a one-day window (EK-2/C lists it with no işlem grubu): the bed was already bundled, and the new
    sentence is not said on top of that."""
    [opp] = _one_date([_line("P704230", "5445.77", category="paket", line_id="PK")])

    assert (opp["gross_bed_days"], opp["bundled_days"], opp["bed_days"]) == (1, 1, 0)
    assert "No day bed" not in opp["detail"]


def test_the_row_has_the_same_keys_with_and_without_the_new_causes() -> None:
    [plain] = _one_date([_line("520010", "10")])
    [er] = _one_date([_line("530000", "577.45")])
    [multi_plain] = _stay(3)
    [multi_er] = _stay(3, [_line("530000", "577.45")])

    assert set(er) == set(plain)
    assert set(multi_er) == set(multi_plain)


@pytest.mark.parametrize(
    ("lines", "bed_days"),
    [
        ([("530000", 0, 1)], 2),
        ([("530000", 1, 1)], 2),
        ([("530000", 2, 1)], 2),
        ([("530000", 0, 2)], 1),
        ([("530000", 1, 2)], 1),
        ([("530000", 0, 5)], 0),  # reaches past the discharge
        ([("530000", 0, 1), ("530000", 1, 1), ("530000", 2, 1)], 0),
        ([("530000", 1, 1), ("530000", 1, 1)], 2),  # twice on one day is one day
        ([("510100", 0, 3)], 0),
        ([("510110", 0, 3)], 0),
        ([("510100", 0, 1)], 2),
        ([("530000", 0, 1), ("510100", 2, 1)], 1),
    ],
    ids=[
        "er-day1", "er-day2", "er-day3", "er-two-days", "er-two-days-middle", "er-quantity-past-the-stay", "er-every-day",
        "er-twice-one-day", "sterile-room-all", "isolation-room-all", "sterile-room-one-day", "er-and-sterile",
    ],
)
def test_the_days_a_bed_including_line_pays_are_not_expected_as_standard_bed_days(lines, bed_days: int) -> None:
    procedure_lines = [
        _line(code, "577.45", quantity=quantity, procedure_date=date(2026, 7, 10) + timedelta(days=day), line_id=f"L{i}")
        for i, (code, day, quantity) in enumerate(lines)
    ]
    [opp] = _stay(3, procedure_lines)

    assert (opp["bed_code"], opp["gross_bed_days"], opp["bed_days"]) == ("510010", 3, bed_days)
    assert opp["expected_yatak_try"] == pytest.approx(bed_days * 222.36, abs=0.01)
    assert opp["recoverable_uplift_try"] == pytest.approx(bed_days * 222.36, abs=0.01)
    assert opp["bundled_days"] == 0 and opp["surgery_day_bundled"] is False
    assert opp["same_day_stay"] is False
    assert opp["daily_rate_try"] == pytest.approx(222.36, abs=0.005)
    if bed_days < 3:
        assert "are paid by" in opp["detail"] and "not expected as bed days" in opp["detail"]


def test_the_detail_names_the_paid_days_and_the_code() -> None:
    [opp] = _stay(3, [_line("530000", "577.45", quantity=2, procedure_date=date(2026, 7, 11))])

    assert (
        "2 day(s) (2026-07-11, 2026-07-12) are paid by 530000 (EK-2/B: it covers yatak, yemek, hasta vizit) and are "
        "not expected as bed days."
    ) in opp["detail"]
    assert opp["detail"].startswith(
        "Standart yatak (510010): 1 billable bed-day(s) (gross LOS 3 day(s) at 222.36 TRY/day) = 222.36 TRY"
    )


@pytest.mark.parametrize(
    ("line", "bed_days"),
    [
        (("530000", "-577.45", date(2026, 7, 10), 1), 3),  # a reversal
        (("530000", "577.45", date(2026, 7, 9), 1), 3),  # the day before the admission
        (("530000", "577.45", date(2026, 7, 13), 1), 3),  # the day after the discharge
        (("530000", "577.45", None, 1), 2),  # undated: the admission date
        (("530000", "0", date(2026, 7, 11), 1), 2),  # listed, money elsewhere
        (("530000", "577.45", date(2026, 7, 9), 2), 2),  # starts the day before: one day inside the stay
    ],
    ids=["reversal", "before", "after", "undated", "zero-priced", "starts-before"],
)
def test_which_lines_of_the_er_bed_cover_a_day_of_the_stay(line, bed_days: int) -> None:
    from dataclasses import replace

    code, billed, day, quantity = line
    procedure_line = replace(_line(code, billed, quantity=quantity, line_id="ER"), procedure_date=day)

    [opp] = _stay(3, [procedure_line])

    assert opp["bed_days"] == bed_days


def test_a_billed_standard_bed_nets_the_days_that_are_left() -> None:
    """530000 on day 1 and 510010 billed for days 2-3 (444.72): nothing is missing."""
    lines = [
        _line("530000", "577.45", line_id="ER"),
        _line("510010", "444.72", quantity=2, procedure_date=date(2026, 7, 11), line_id="STD"),
    ]
    [opp] = _stay(3, lines)

    assert opp["bed_days"] == 2
    assert opp["expected_yatak_try"] == pytest.approx(444.72, abs=0.01)
    assert opp["actual_billed_try"] == pytest.approx(444.72, abs=0.01)
    assert opp["recoverable_uplift_try"] == 0.0
    # Billed for one of the two days left: the other one stays recoverable.
    [part] = _stay(3, [lines[0], _line("510010", "222.36", procedure_date=date(2026, 7, 11), line_id="S1")])
    assert part["recoverable_uplift_try"] == pytest.approx(222.36, abs=0.01)
    # The day the ER bed paid, billed again as 510010 on top: more than expected, never negative.
    [over] = _stay(3, [lines[0], _line("510010", "667.08", quantity=3, line_id="ALL")])
    assert over["recoverable_uplift_try"] == 0.0


def test_hemodialysis_takes_nothing_from_a_stay_of_several_dates() -> None:
    """The clause speaks of the day bed; a stay of two dates bills 510010, which it does not mention."""
    for days in (2, 3):
        [opp] = _stay(days, [_line("704230", "4342.48", procedure_date=date(2026, 7, 11))])

        assert opp["bed_days"] == days
        assert opp["recoverable_uplift_try"] == pytest.approx(days * 222.36, abs=0.01)
        assert "No day bed" not in opp["detail"] and "are paid by" not in opp["detail"]


def test_the_er_bed_on_a_stay_of_several_dates_does_not_take_the_whole_claim() -> None:
    """The claim-level day-bed exclusion is for the stay of one date; here 530000 pays its own day only."""
    [opp] = _stay(2, [_line("530000", "577.45")])

    assert opp["bed_days"] == 1
    assert "No day bed" not in opp["detail"]


def test_the_lines_of_another_claim_do_not_take_a_day() -> None:
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    mine = _make_claim_header(claim_id="MINE", admission=date(2026, 7, 10), discharge=date(2026, 7, 10))
    other = _make_claim_header(claim_id="OTHER", admission=date(2026, 7, 10), discharge=date(2026, 7, 10))
    opps = detect_yatak_puani_opportunities(
        [mine, other],
        [_line("530000", "577.45", claim_id="OTHER"), _line("704230", "4342.48", claim_id="OTHER")],
        claim_ids_with_procs={"MINE", "OTHER"},
    )
    by_claim = {o["claim_id"]: o for o in opps}

    assert by_claim["MINE"]["bed_days"] == 1
    assert by_claim["MINE"]["recoverable_uplift_try"] == pytest.approx(44.45, abs=0.005)
    assert by_claim["OTHER"]["bed_days"] == 0


# --- the package window takes its days first -----------------------------------------------------------------------


def test_the_er_bed_inside_a_package_window_is_not_taken_out_a_second_time() -> None:
    """12 days, group-B package from 11 July: the window runs through 20 July (11 days bundled, one day left, 21
    July). 530000 on 14 July is a bundled day already; on 21 July it is the day that is left."""
    package = _line("P600040", "5000", category="paket", line_id="PK", procedure_date=date(2026, 7, 11))

    [inside] = _stay(12, [package, _line("530000", "577.45", procedure_date=date(2026, 7, 14), line_id="ER")])
    assert (inside["bundled_days"], inside["bed_days"]) == (11, 1)
    assert inside["expected_yatak_try"] == pytest.approx(222.36, abs=0.01)
    assert "are paid by" not in inside["detail"]

    [after] = _stay(12, [package, _line("530000", "577.45", procedure_date=date(2026, 7, 21), line_id="ER")])
    assert (after["bundled_days"], after["bed_days"]) == (11, 0)
    assert after["expected_yatak_try"] == 0.0
    assert "1 day(s) (2026-07-21) are paid by 530000" in after["detail"]


def test_a_package_over_the_only_day_leaves_the_package_to_explain_it() -> None:
    for code, billed in (("530000", "577.45"), ("704230", "4342.48")):
        [opp] = _one_date([_line("P600040", "5000", category="paket", line_id="PK"), _line(code, billed, line_id="X")])

        assert (opp["gross_bed_days"], opp["bundled_days"], opp["bed_days"]) == (1, 1, 0)
        assert opp["expected_yatak_try"] == 0.0
        assert "No day bed" not in opp["detail"]


# --- C000649: a day case with an EK-2/C procedure takes no day bed --------------------------------------------


def test_a_day_case_with_an_ek2c_procedure_expects_no_day_bed() -> None:
    """702580 (hyperbaric oxygen) is on the EK-2/C list with no işlem grubu, so it opens no package window: the case
    the window logic misses. The claim type `day_case` is read as inpatient by `infer_care_setting`."""
    [opp] = _stay(1, [_line("702580", "545.76")], claim_type="day_case")

    assert (opp["bed_code"], opp["same_day_stay"], opp["bed_days"]) == ("510120", True, 0)
    assert opp["expected_yatak_try"] == 0.0 and opp["recoverable_uplift_try"] == 0.0
    assert "a day case (günübirlik) bills EK-2/C procedure(s) (702580)" in opp["detail"]
    assert "§2.2.2.(4)" in opp["detail"]


def test_the_same_bill_on_an_inpatient_claim_keeps_its_day_bed() -> None:
    """A same-date admission and discharge is no day case (C000492 defines it by the absence of both)."""
    [opp] = _stay(1, [_line("702580", "545.76")], claim_type="yatis")

    assert opp["bed_days"] == 1
    assert opp["recoverable_uplift_try"] == pytest.approx(44.45, abs=0.005)
    assert "day case" not in opp["detail"]


def test_a_gunubirlik_claim_is_outpatient_and_has_no_bed_row_at_all() -> None:
    assert _stay(1, [_line("702580", "545.76")], claim_type="gunubirlik") == []


def test_a_day_case_without_an_ek2c_procedure_keeps_its_day_bed() -> None:
    """EK-2/B 510120 is billed "Günübirlik tedaviler ... için": only the EK-2/C procedures take it away."""
    [opp] = _stay(1, [_line("520010", "10")], claim_type="day_case")

    assert opp["bed_days"] == 1
    assert opp["recoverable_uplift_try"] == pytest.approx(44.45, abs=0.005)


@pytest.mark.parametrize("days", [2, 3])
def test_a_day_case_that_crosses_midnight_expects_no_bed_with_an_ek2c_procedure(days: int) -> None:
    """Review of the change: a day case is within 24 hours and has no admission (§2.1.2.B.(1)), so it may span two
    dates and has no ward bed; its day bed is forbidden for EK-2/C procedures (§2.2.2.(4)). 2 x 510010 was a false
    444.72."""
    [opp] = _stay(days, [_line("702580", "545.76")], claim_type="day_case")

    assert (opp["bed_code"], opp["gross_bed_days"], opp["bed_days"]) == ("510010", days, 0)
    assert opp["expected_yatak_try"] == 0.0 and opp["recoverable_uplift_try"] == 0.0
    assert "No bed day is expected: a day case (günübirlik) bills EK-2/C procedure(s) (702580)" in opp["detail"]
    assert "§2.1.2.B.(1)" in opp["detail"]


def test_a_day_case_of_two_dates_without_an_ek2c_procedure_keeps_its_beds() -> None:
    """Untouched (inherited): without an EK-2/C procedure nothing here forbids the day case's bed."""
    [opp] = _stay(2, [_line("520010", "10")], claim_type="day_case")

    assert opp["bed_days"] == 2
    assert opp["recoverable_uplift_try"] == pytest.approx(444.72, abs=0.01)


def test_the_same_bill_of_two_dates_on_an_inpatient_claim_keeps_its_beds() -> None:
    [opp] = _stay(2, [_line("702580", "545.76")], claim_type="yatis")

    assert opp["bed_days"] == 2
    assert opp["recoverable_uplift_try"] == pytest.approx(444.72, abs=0.01)
    assert "day case" not in opp["detail"]

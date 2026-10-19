"""The days of a stay whose bed the SUT says is already paid, or whose day bed it forbids billing.

`bed_days_not_expected` is the one place both bed motors (standard bed, newborn bed) and the ICU reconciliation read
it from. Sources, all read from `data/gazette` on 2026-10-19:

* EK-2/B 530000 "Acil serviste kritik hasta yatak ve takibi": "Yatak, yemek, hasta vizit hizmetlerini kapsar.
  510120, 530003 ile birlikte faturalandırılmaz."; 510100 Steril oda and 510110 İzole radyoaktif tedavi odası:
  "Yemek, yatak, hasta vizit hizmetlerini kapsar." (the sentence the project already reads as "the bed is paid"
  for 510090, 510070 and 510081);
* SUT §2.4.4.D-1.(11) (C000969): hemodialysis, "gündüz yatak ücreti fiyata dâhil olup ayrıca faturalandırılmayacaktır";
* SUT §2.2.2.(4) (C000649): "Günübirlik tedavilerde SUT eki EK-2/C Listesinde yer alan işlemler için gündüz yatak
  bedeli faturalandırılamaz."

A false recoverable on a billed dialysis session or ER bed is worse than silence, so every line that is not clearly a
billed one (a reversal, a line of another claim, a line dated outside the stay) says nothing about the stay's bed.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.prose_rules.yatak_puani import (
    BED_INCLUDING_CODES,
    HEMODIALYSIS_CODES,
    BedNotExpected,
    PackageWindow,
    bed_days_not_expected,
)

pytestmark = pytest.mark.unit

D0 = date(2026, 7, 10)


def _day(offset: int) -> date:
    return D0 + timedelta(days=offset)


def _claim(*, days: int = 3, claim_type: str = "yatis", claim_id: str = "C1") -> ClaimHeader:
    end = _day(days - 1)
    return ClaimHeader(
        claim_id=claim_id, patient_id="P1", episode_id="E1", claim_type=claim_type, facility_tier="devlet",
        provider_type="sozlesmeli", department="genel", admission_date=D0, discharge_date=end,
        claim_start_date=D0, claim_end_date=end, primary_icd10="I10", package_candidate=False,
        expected_total_billed_try=Decimal("1000"), expected_total_payable_try=Decimal("900"),
        expected_denial_reason="", scenario_tag="test",
    )


def _line(
    code: str,
    *,
    day: int | None = 0,
    quantity: int | None = 1,
    billed: str = "100.00",
    claim_id: str = "C1",
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=f"{claim_id}-{code}-{day}-{billed}", claim_id=claim_id, patient_id="P1", episode_id="E1",
        procedure_date=None if day is None else _day(day), procedure_code=code, procedure_name="line",
        procedure_category="islem", quantity=quantity, unit_price_try=Decimal("0"), billed_amount_try=Decimal(billed),
        expected_payable_try=Decimal("0"), is_package_included=False, package_code="", surcharge_applicable=False,
        copay_rate_applicable=True, denial_reason_expected="", rule_trace_expected="",
    )


def _dates(*offsets: int) -> frozenset[date]:
    return frozenset(_day(o) for o in offsets)


def test_the_code_sets_are_the_ones_the_annex_names() -> None:
    assert BED_INCLUDING_CODES == frozenset({"530000", "510100", "510110"})
    assert HEMODIALYSIS_CODES == frozenset({"704210", "704230"})


def test_a_claim_without_such_lines_expects_every_day() -> None:
    result = bed_days_not_expected(_claim(), [_line("520010"), _line("510010", quantity=3)])

    assert result == BedNotExpected(dates=frozenset(), reasons=())


def test_no_lines_at_all_expects_every_day() -> None:
    assert bed_days_not_expected(_claim(), []) == BedNotExpected()


# --- bed-including codes: the days a line covers -------------------------------------------------------------


@pytest.mark.parametrize("code", ["530000", "510100", "510110"])
def test_a_bed_including_line_pays_the_bed_of_its_own_day(code: str) -> None:
    result = bed_days_not_expected(_claim(), [_line(code, day=1)])

    assert result.dates == _dates(1)
    [reason] = result.reasons
    assert code in reason and "2026-07-11" in reason and "1 day(s)" in reason
    assert "yatak" in reason and "EK-2/B" in reason


@pytest.mark.parametrize(
    ("day", "quantity", "covered"),
    [
        (0, 1, (0,)),
        (0, 2, (0, 1)),
        (1, 2, (1, 2)),
        (0, 3, (0, 1, 2)),
        (1, 5, (1, 2)),  # reaches past the discharge: clipped to the stay
        (0, 100000, (0, 1, 2)),  # a huge quantity is clipped, not iterated
        (-1, 2, (0,)),  # starts the day before the admission: only the day inside the stay is covered
        (0, None, (0,)),  # no quantity counts one day
        (0, 0, (0,)),
        (0, -3, (0,)),
    ],
)
def test_a_line_covers_its_quantity_in_days_from_its_date_clipped_to_the_stay(
    day: int, quantity: int | None, covered: tuple[int, ...]
) -> None:
    assert bed_days_not_expected(_claim(), [_line("530000", day=day, quantity=quantity)]).dates == _dates(*covered)


def test_two_lines_on_one_day_cover_it_once() -> None:
    result = bed_days_not_expected(_claim(), [_line("530000", day=1), _line("530000", day=1, billed="50.00")])

    assert result.dates == _dates(1)
    assert "1 day(s)" in result.reasons[0]


def test_different_bed_including_codes_on_different_days_add_up() -> None:
    result = bed_days_not_expected(_claim(), [_line("530000", day=0), _line("510100", day=2)])

    assert result.dates == _dates(0, 2)
    assert "2 day(s)" in result.reasons[0]
    assert "510100" in result.reasons[0] and "530000" in result.reasons[0]


def test_an_undated_line_sits_on_the_admission_date() -> None:
    """As `_package_window_end` places an undated package line."""
    assert bed_days_not_expected(_claim(), [_line("530000", day=None)]).dates == _dates(0)


@pytest.mark.parametrize("day", [-1, 3, 10])
def test_a_line_dated_outside_the_stay_covers_nothing(day: int) -> None:
    assert bed_days_not_expected(_claim(), [_line("530000", day=day)]) == BedNotExpected()


def test_a_reversal_covers_no_day() -> None:
    """A credit line withdraws a charge; it states nothing about the stay's bed (as for a newborn bed line)."""
    assert bed_days_not_expected(_claim(), [_line("530000", day=0, billed="-577.45")]) == BedNotExpected()


def test_a_zero_priced_line_still_covers_its_day() -> None:
    """The service is listed; the money may sit on another bill. Silence is the safe side."""
    assert bed_days_not_expected(_claim(), [_line("530000", day=1, billed="0")]).dates == _dates(1)


@pytest.mark.parametrize("code", [" 530.000 ", "530 000", "530-000", "P510100"])
def test_the_code_is_read_like_the_rest_of_the_engine_reads_it(code: str) -> None:
    assert bed_days_not_expected(_claim(), [_line(code, day=1)]).dates == _dates(1)


def test_the_lines_of_another_claim_say_nothing() -> None:
    assert bed_days_not_expected(_claim(), [_line("530000", day=1, claim_id="OTHER")]) == BedNotExpected()


@pytest.mark.parametrize("code", ["530003", "530001", "510010", "510070", "510081", "510090", "510120", "510121"])
def test_other_bed_or_er_codes_are_not_bed_including_lines(code: str) -> None:
    """530003 is only the code 530000 may not be billed with; the others are the motors' own (or the ICU motor's)."""
    assert bed_days_not_expected(_claim(), [_line(code, day=1)]) == BedNotExpected()


# --- the package window takes its days first -------------------------------------------------------------------


def _window(end_offset: int, *, mandated: bool = False) -> PackageWindow:
    return PackageWindow(start=D0, end=_day(end_offset), mandated=mandated)


def test_a_line_inside_the_package_window_is_not_taken_out_a_second_time() -> None:
    claim = _claim(days=6)
    window = _window(2)  # 10-12 July are in the package

    assert bed_days_not_expected(claim, [_line("530000", day=1)], window) == BedNotExpected()
    assert bed_days_not_expected(claim, [_line("530000", day=2)], window) == BedNotExpected()


def test_a_line_after_the_package_window_is_taken_out() -> None:
    claim = _claim(days=6)
    window = _window(2)

    assert bed_days_not_expected(claim, [_line("530000", day=3)], window).dates == _dates(3)
    # A line that starts inside the window and runs past it covers only the days after it.
    assert bed_days_not_expected(claim, [_line("530000", day=1, quantity=4)], window).dates == _dates(3, 4)


def test_a_window_that_takes_every_day_leaves_nothing_to_explain() -> None:
    claim = _claim(days=1)

    assert bed_days_not_expected(claim, [_line("530000", day=0), _line("704230", day=0)], _window(0)) == BedNotExpected()
    assert bed_days_not_expected(_claim(days=3), [_line("530000", day=2)], _window(5)) == BedNotExpected()


# --- the day bed of a stay under 24 hours (one date) -----------------------------------------------------------


def test_530000_anywhere_on_a_claim_of_one_date_takes_the_day_bed() -> None:
    """EK-2/B: "510120, 530003 ile birlikte faturalandırılmaz": claim level, so the date and the quantity do not matter."""
    claim = _claim(days=1)

    for line in (
        _line("530000", day=0),
        _line("530000", day=None),
        _line("530000", day=-1),  # dated the day before: still on this claim
        _line("530000", day=0, quantity=2),
        _line("530000", day=0, billed="0"),
        _line(" 530.000 ", day=0),
    ):
        result = bed_days_not_expected(claim, [line])
        assert result.dates == _dates(0), line
        [reason] = result.reasons  # one sentence: the claim-level cause, not a second "paid by" sentence
        assert "510120" in reason and "530000" in reason and "together" in reason


def test_a_reversed_530000_takes_no_day_bed() -> None:
    assert bed_days_not_expected(_claim(days=1), [_line("530000", day=0, billed="-577.45")]) == BedNotExpected()


def test_530003_alone_takes_no_day_bed() -> None:
    assert bed_days_not_expected(_claim(days=1), [_line("530003", day=0)]) == BedNotExpected()


@pytest.mark.parametrize("code", ["704210", "704230", "P704210", "P704230", " 704.230 ", "704-210"])
def test_hemodialysis_on_a_claim_of_one_date_takes_the_day_bed(code: str) -> None:
    result = bed_days_not_expected(_claim(days=1), [_line(code, day=0, billed="4342.48")])

    assert result.dates == _dates(0)
    [reason] = result.reasons
    assert "hemodialysis" in reason and "704" in reason and "2.4.4.D-1.(11)" in reason and "510120" in reason


@pytest.mark.parametrize("day", [-1, None, 1])
def test_the_date_of_the_dialysis_line_does_not_matter_on_a_claim_of_one_date(day: int | None) -> None:
    assert bed_days_not_expected(_claim(days=1), [_line("704230", day=day)]).dates == _dates(0)


@pytest.mark.parametrize("code", ["704233", "704231", "704290", "704240", "704260", "607600", "802600"])
def test_other_dialysis_related_codes_take_no_day_bed(code: str) -> None:
    """Home hemodialysis (D-1-1 has no such sentence), catheter placement, hemodiafiltration, hemoperfusion,
    peritoneal follow-up, A-V fistula and fistulogram are not "Hemodiyaliz tedavisi" of D-1.(11)."""
    assert bed_days_not_expected(_claim(days=1), [_line(code, day=0)]) == BedNotExpected()


def test_a_reversed_dialysis_line_takes_no_day_bed() -> None:
    assert bed_days_not_expected(_claim(days=1), [_line("704230", day=0, billed="-4342.48")]) == BedNotExpected()


def test_hemodialysis_takes_nothing_from_a_stay_of_several_dates() -> None:
    """The clause speaks of the day bed, which a stay of two dates does not bill, and says nothing of 510010."""
    for days in (2, 3, 10):
        assert bed_days_not_expected(_claim(days=days), [_line("704230", day=1)]) == BedNotExpected()


def test_530000_on_a_stay_of_several_dates_covers_only_its_days_not_the_whole_claim() -> None:
    result = bed_days_not_expected(_claim(days=3), [_line("530000", day=0)])

    assert result.dates == _dates(0)  # the claim-level day-bed exclusion is for a stay of one date only


def test_a_special_room_on_a_claim_of_one_date_covers_its_own_day_only() -> None:
    claim = _claim(days=1)

    assert bed_days_not_expected(claim, [_line("510100", day=0)]).dates == _dates(0)
    assert bed_days_not_expected(claim, [_line("510100", day=-1)]) == BedNotExpected()  # the exclusion is 530000's
    assert bed_days_not_expected(claim, [_line("510110", day=None)]).dates == _dates(0)


def test_one_date_with_several_causes_names_each() -> None:
    result = bed_days_not_expected(_claim(days=1), [_line("530000"), _line("704230", billed="4342.48")])

    assert result.dates == _dates(0)
    assert len(result.reasons) == 2
    assert "530000" in result.reasons[0] and "hemodialysis" in result.reasons[1]


# --- C000649: a day case with an EK-2/C procedure --------------------------------------------------------------
# 702580 Hiperbarik oksijen tedavisi is on the EK-2/C list with no işlem grubu: it opens no package window, so it is
# the case the window logic misses; 600040 is a group-B package and opens one.


def test_a_day_case_with_an_ek2c_procedure_takes_the_day_bed() -> None:
    result = bed_days_not_expected(_claim(days=1, claim_type="day_case"), [_line("702580", day=0, billed="545.76")])

    assert result.dates == _dates(0)
    [reason] = result.reasons
    assert "day case" in reason and "702580" in reason and "2.2.2.(4)" in reason and "510120" in reason


@pytest.mark.parametrize("claim_type", ["day_case", "Day_Case", "gunubirlik yatis", "gunubirlik"])
def test_every_day_case_spelling_the_engine_knows_counts(claim_type: str) -> None:
    """`claim_is_day_case`: "gunubirlik" or "day_case" in the claim type (the motors skip a plain "gunubirlik" claim
    as outpatient; the helper does not decide that)."""
    assert bed_days_not_expected(_claim(days=1, claim_type=claim_type), [_line("702580")]).dates == _dates(0)


@pytest.mark.parametrize("claim_type", ["yatis", "acil", "poliklinik", "inpatient", "", "Günübirlik"])
def test_a_claim_that_is_not_a_day_case_keeps_its_day_bed(claim_type: str) -> None:
    """A same-date admission and discharge is no day case (C000492); "Günübirlik" with ü is not read by the engine."""
    assert bed_days_not_expected(_claim(days=1, claim_type=claim_type), [_line("702580")]) == BedNotExpected()


def test_a_day_case_without_an_ek2c_procedure_keeps_its_day_bed() -> None:
    claim = _claim(days=1, claim_type="day_case")

    assert bed_days_not_expected(claim, [_line("520010"), _line("510120", billed="44.45")]) == BedNotExpected()


def test_a_reversed_ek2c_line_on_a_day_case_takes_no_day_bed() -> None:
    claim = _claim(days=1, claim_type="day_case")

    assert bed_days_not_expected(claim, [_line("702580", billed="-545.76")]) == BedNotExpected()


@pytest.mark.parametrize("code", ["999999", "520010", "510120", "510010", "530003"])
def test_a_code_on_no_ek2c_list_is_no_ek2c_procedure(code: str) -> None:
    assert bed_days_not_expected(_claim(days=1, claim_type="day_case"), [_line(code)]) == BedNotExpected()


def test_the_ek2c_list_is_read_on_the_date_of_the_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lookup is dated: the line's own date, the admission date for an undated line."""
    from src.bilun.domain.prose_rules import yatak_puani

    seen: list[object] = []
    real = yatak_puani.get_ek2c_entry

    def spy(code, *, as_of_date=None):
        seen.append(as_of_date)
        return real(code, as_of_date=as_of_date)

    monkeypatch.setattr(yatak_puani, "get_ek2c_entry", spy)
    claim = _claim(days=1, claim_type="day_case")

    for day, expected in ((0, D0), (-1, _day(-1)), (None, D0)):
        seen.clear()
        bed_days_not_expected(claim, [_line("702580", day=day)])
        assert seen == [expected], (day, seen)


def test_a_day_case_of_several_dates_keeps_its_beds() -> None:
    assert bed_days_not_expected(_claim(days=2, claim_type="day_case"), [_line("702580")]) == BedNotExpected()


def test_a_package_window_over_the_only_day_of_a_day_case_leaves_nothing_to_explain() -> None:
    claim = _claim(days=1, claim_type="day_case")

    assert bed_days_not_expected(claim, [_line("702580")], _window(0)) == BedNotExpected()


# --- degenerate claims -------------------------------------------------------------------------------------------


def test_a_claim_without_dates_or_with_discharge_before_admission_expects_nothing_to_remove() -> None:
    no_admission = replace(_claim(), admission_date=None)
    no_discharge = replace(_claim(), discharge_date=None)
    backwards = replace(_claim(), discharge_date=D0 - timedelta(days=1))

    for claim in (no_admission, no_discharge, backwards):
        assert bed_days_not_expected(claim, [_line("530000", day=0)]) == BedNotExpected()


def test_the_result_is_immutable() -> None:
    result = bed_days_not_expected(_claim(), [_line("530000", day=1)])

    assert isinstance(result.dates, frozenset) and isinstance(result.reasons, tuple)
    with pytest.raises(AttributeError):
        result.dates = frozenset()  # type: ignore[misc]

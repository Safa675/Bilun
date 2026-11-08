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
    ICU_BED_CODES,
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
        claim_start_date=D0, claim_end_date=end, primary_icd10="I10",
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


@pytest.mark.parametrize("quantity", [float("nan"), float("inf"), float("-inf"), "two", object()])
def test_an_unreadable_quantity_counts_one_day_and_never_loses_the_report(quantity: object) -> None:
    """The parsers hand over an int; a bill built in code may not. The whole report must survive: one day."""
    for code, day in (("530000", 1), ("510100", 1)):
        assert bed_days_not_expected(_claim(), [_line(code, day=day, quantity=quantity)]).dates == _dates(1)  # type: ignore[arg-type]


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


@pytest.mark.parametrize("code", ["530003", "530001", "510010", "510070", "510081", "510120", "510121"])
def test_other_bed_or_er_codes_are_not_bed_including_lines(code: str) -> None:
    """530003 is only the code 530000 may not be billed with; the others are the motors' own. 510090 is an ICU line:
    it has its own cause (the ICU stay of the claim's lines, below), not a place in `BED_INCLUDING_CODES`."""
    assert bed_days_not_expected(_claim(), [_line(code, day=1)]) == BedNotExpected()


def test_510090_pays_a_day_but_is_not_one_of_the_three_bed_including_codes() -> None:
    assert "510090" not in BED_INCLUDING_CODES
    assert bed_days_not_expected(_claim(), [_line("510090", day=1)]).dates == _dates(1)


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


@pytest.mark.parametrize(
    "claim_type", ["day_case", "Day_Case", "gunubirlik yatis", "Günübirlik Yatış", "gunubirlik", "Günübirlik"]
)
def test_every_day_case_spelling_the_engine_knows_counts(claim_type: str) -> None:
    """`claim_is_day_case`: every spelling of the day-case type in the one vocabulary (claims/claim_type.py, #335);
    "Günübirlik" with ü was not read before #335."""
    assert bed_days_not_expected(_claim(days=1, claim_type=claim_type), [_line("702580")]).dates == _dates(0)


@pytest.mark.parametrize("claim_type", ["yatis", "acil", "poliklinik", "inpatient", "", "koruyucu"])
def test_a_claim_that_is_not_a_day_case_keeps_its_day_bed(claim_type: str) -> None:
    """A same-date admission and discharge is no day case (C000492)."""
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


def test_a_day_case_that_crosses_midnight_has_no_bed_at_all_with_an_ek2c_procedure() -> None:
    """A day case is "within 24 hours" and "without admission" (§2.1.2.B.(1)): it may span two dates, has no ward bed,
    and its day bed is forbidden for EK-2/C procedures (§2.2.2.(4)). Every day is not expected, whatever its dates."""
    for days in (2, 3):
        result = bed_days_not_expected(_claim(days=days, claim_type="day_case"), [_line("702580", day=0)])

        assert result.dates == _dates(*range(days))
        [reason] = result.reasons
        assert reason.startswith("No bed day is expected: a day case (günübirlik) bills EK-2/C procedure(s) (702580)")
        assert "2.2.2.(4)" in reason and "2.1.2.B.(1)" in reason and "no other bed" in reason


def test_a_day_case_of_several_dates_without_an_ek2c_procedure_keeps_its_beds() -> None:
    """Untouched: nothing here names the day case's beds (an inherited question: its beds are 510010 days today)."""
    claim = _claim(days=2, claim_type="day_case")

    assert bed_days_not_expected(claim, [_line("520010"), _line("510010", billed="222.36")]) == BedNotExpected()
    assert bed_days_not_expected(claim, [_line("702580", billed="-545.76")]) == BedNotExpected()  # a reversal


def test_the_same_bill_of_several_dates_on_an_inpatient_claim_keeps_its_beds() -> None:
    for claim_type in ("yatis", "acil", "inpatient", "poliklinik"):
        assert bed_days_not_expected(_claim(days=2, claim_type=claim_type), [_line("702580")]) == BedNotExpected()


def test_a_day_case_of_several_dates_leaves_the_package_window_its_days() -> None:
    """Only the days after the window are named: the window explains the others."""
    claim = _claim(days=6, claim_type="day_case")

    assert bed_days_not_expected(claim, [_line("702580", day=0)], _window(2)).dates == _dates(3, 4, 5)
    assert bed_days_not_expected(claim, [_line("702580", day=0)], _window(5)) == BedNotExpected()


def test_a_day_case_of_several_dates_with_530000_still_takes_that_days_only_beside_the_day_case_cause() -> None:
    """530000 on a stay of several dates covers its own day; the day-case cause already names every day."""
    result = bed_days_not_expected(
        _claim(days=2, claim_type="day_case"), [_line("702580", day=0), _line("530000", day=1)]
    )

    assert result.dates == _dates(0, 1)
    assert len(result.reasons) == 2


def test_a_package_window_over_the_only_day_of_a_day_case_leaves_nothing_to_explain() -> None:
    claim = _claim(days=1, claim_type="day_case")

    assert bed_days_not_expected(claim, [_line("702580")], _window(0)) == BedNotExpected()


# --- the ICU stay of the claim's own lines ---------------------------------------------------------------------
# Verbatim: EK-2/B 510090 "Yoğun bakım": "Yemek, yatak, hasta vizit hizmetlerini kapsar." (every list since 2018);
# §2.4.4.H.(2) "Yoğun bakım tedavileri SUT eki EK-2/C Listesinde yer alan puanlar üzerinden faturalandırılır"; §2.4.4.H.(8)
# the first and the exit day are billed hizmet başı. Read from them (inference, no clause says it in one sentence): the EK-2/C
# ICU packages P552001-3 / P552006-8 carry no Açıklama and no işlem grubu and EK-2/C points include "Yatak bedeli"
# (§2.2.2.B-1.(1).a, exceptions in the Açıklama column, (2)), so the bed is in the package; the days between a billed first
# and exit day are package days. A package without işlem grubu opens a window of one day only (its own date).

_ICU_PACKAGES = ("552001", "552002", "552003", "552006", "552007", "552008")
_ICU_CODES = ("510090", *_ICU_PACKAGES)


def _package(code: str, *, day: int | None = 0, quantity: int | None = 1, billed: str = "2000.00") -> ProcedureClaimLine:
    """An ICU package billed the way MEDULA bills it: the P code, category paket."""
    return replace(_line(f"P{code}", day=day, quantity=quantity, billed=billed), procedure_category="paket")


def test_the_icu_code_set_is_the_icu_motors_own_gate() -> None:
    """One definition of "an ICU code": `claim_has_icu_code` decides which claims the ICU motor owns; the set here must
    not drift from it (a code added there needs adding here)."""
    from src.bilun.domain.prose_rules.icu_puani import claim_has_icu_code

    assert ICU_BED_CODES == frozenset(_ICU_CODES)
    for code in _ICU_CODES:
        assert claim_has_icu_code([_line(code)]) is True
    for code in ("510010", "510070", "510081", "510120", "530000", "552004", "552005", "5520020", "55200", "5100900"):
        assert claim_has_icu_code([_line(code)]) is False, code
        assert code not in ICU_BED_CODES


@pytest.mark.parametrize("code", _ICU_CODES)
def test_an_icu_line_pays_the_bed_of_its_own_day(code: str) -> None:
    result = bed_days_not_expected(_claim(), [_line(code, day=1)])

    assert result.dates == _dates(1)
    [reason] = result.reasons
    assert code in reason and "2026-07-11" in reason and "1 day(s)" in reason
    assert "ICU stay" in reason and "2.4.4.H" in reason and "yatak" in reason


@pytest.mark.parametrize("code", ["P552001", "P552002", "P552003", "P552006", "P552007", "P552008"])
def test_an_icu_package_billed_as_a_package_pays_like_the_day_rate(code: str) -> None:
    assert bed_days_not_expected(_claim(), [_package(code[1:], day=1)]).dates == _dates(1)


@pytest.mark.parametrize("code", ["552001", "552002", "552003", "552006", "552007", "552008"])
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
        (0, None, (0,)),
        (0, 0, (0,)),
        (0, -3, (0,)),
    ],
)
def test_an_icu_package_covers_its_quantity_in_days_from_its_date_clipped_to_the_stay(
    code: str, day: int, quantity: int | None, covered: tuple[int, ...]
) -> None:
    assert bed_days_not_expected(_claim(), [_line(code, day=day, quantity=quantity)]).dates == _dates(*covered)


@pytest.mark.parametrize(
    ("day", "quantity", "covered"),
    [
        (0, 1, (0,)),  # a quantity of 1 pays its own day
        (3, 1, (3,)),
        (0, 2, (0, 1, 2, 3, 4, 5)),  # two day-rate units are the first and the exit day: the stay runs to the discharge
        (2, 2, (2, 3, 4, 5)),
        (5, 2, (0, 1, 2, 3, 4, 5)),  # ... dated on the discharge date: the other end is the claim's first day
        (4, 2, (4, 5)),
        (0, 3, (0, 1, 2)),  # three or more units cannot be H.(8)'s two hizmet başı days: a daily billing, quantity = days
        (4, 3, (4, 5)),
        (2, 5, (2, 3, 4, 5)),
        (0, 100000, (0, 1, 2, 3, 4, 5)),  # a huge quantity is clipped, not iterated
        (-1, 2, (0, 1, 2, 3, 4, 5)),  # starts the day before the admission, runs into the stay
        (-2, 2, ()),  # ... but not when its quantity ends before the admission
        (6, 2, ()),  # dated after the discharge
        (0, None, (0,)),  # an unreadable or missing quantity counts one
        (0, 0, (0,)),
        (0, -3, (0,)),
    ],
)
def test_a_510090_line_pays_its_quantity_in_days_or_with_a_quantity_of_exactly_two_the_stay(
    day: int, quantity: int | None, covered: tuple[int, ...]
) -> None:
    """The ICU motor reads two 510090 units as the first and the exit day (§2.4.4.H.(8)), not as two consecutive days:
    the exit day is not on the line, the claim-span model puts it on the claim's last day. A bill built on that reading
    must not show the days between as ward days."""
    assert bed_days_not_expected(_claim(days=6), [_line("510090", day=day, quantity=quantity)]).dates == _dates(*covered)


@pytest.mark.parametrize("code", [" 510.090 ", "510 090", "510-090", "P510090", "p510090"])
def test_a_spelled_day_rate_line_of_quantity_two_is_read_like_the_plain_one(code: str) -> None:
    assert bed_days_not_expected(_claim(days=6), [_line(code, day=1, quantity=2)]).dates == _dates(1, 2, 3, 4, 5)
    assert bed_days_not_expected(_claim(days=6), [_line(code, day=5, quantity=2)]).dates == _dates(0, 1, 2, 3, 4, 5)
    assert bed_days_not_expected(_claim(days=6), [_line(code, day=1, quantity=3)]).dates == _dates(1, 2, 3)


def test_a_day_rate_line_of_quantity_two_with_the_other_lines_of_the_stay() -> None:
    claim = _claim(days=8)
    # first/exit line dated 12 July plus a package at 11 July: the stay starts at the earliest covered day
    assert bed_days_not_expected(claim, [_line("510090", day=2, quantity=2), _package("552002", day=1)]).dates == _dates(
        1, 2, 3, 4, 5, 6, 7
    )
    # two quantity-2 lines: the earlier one starts the stay, both end at the discharge
    assert bed_days_not_expected(claim, [_line("510090", day=1, quantity=2), _line("510090", day=4, quantity=2)]).dates == _dates(
        1, 2, 3, 4, 5, 6, 7
    )


def test_a_package_of_quantity_two_pays_two_days_where_a_day_rate_line_of_quantity_two_pays_the_stay() -> None:
    claim = _claim(days=6)

    assert bed_days_not_expected(claim, [_package("552002", day=0, quantity=2)]).dates == _dates(0, 1)
    assert bed_days_not_expected(claim, [_line("510090", day=0, quantity=2)]).dates == _dates(0, 1, 2, 3, 4, 5)


def test_two_day_rate_lines_of_quantity_one_pay_their_own_days_and_the_days_between() -> None:
    result = bed_days_not_expected(_claim(days=6), [_line("510090", day=1), _line("510090", day=3)])

    assert result.dates == _dates(1, 2, 3)  # ward days before 11 July and after 13 July stay expected


@pytest.mark.parametrize("quantity", [float("nan"), float("inf"), float("-inf"), "two", object()])
def test_an_unreadable_icu_quantity_counts_one_day_and_never_loses_the_report(quantity: object) -> None:
    for code in ("510090", "552002"):
        assert bed_days_not_expected(_claim(), [_line(code, day=1, quantity=quantity)]).dates == _dates(1)  # type: ignore[arg-type]


def test_an_undated_icu_line_sits_on_the_admission_date() -> None:
    assert bed_days_not_expected(_claim(), [_line("510090", day=None)]).dates == _dates(0)
    assert bed_days_not_expected(_claim(), [_line("510090", day=None, quantity=3)]).dates == _dates(0, 1, 2)


@pytest.mark.parametrize("day", [-1, 3, 10])
def test_an_icu_line_dated_outside_the_stay_covers_nothing(day: int) -> None:
    assert bed_days_not_expected(_claim(), [_line("510090", day=day)]) == BedNotExpected()


def test_a_reversed_icu_line_covers_no_day() -> None:
    """A credit line withdraws a charge; it states nothing about the stay's bed."""
    assert bed_days_not_expected(_claim(), [_line("510090", day=0, billed="-742.60")]) == BedNotExpected()
    assert bed_days_not_expected(_claim(), [_package("552002", billed="-2000.00")]) == BedNotExpected()


def test_a_reversal_beside_a_billed_icu_line_changes_nothing() -> None:
    lines = [_line("510090", day=0, billed="742.60"), _line("510090", day=2, billed="-742.60")]

    assert bed_days_not_expected(_claim(), lines).dates == _dates(0)


def test_a_zero_priced_icu_line_still_covers_its_day() -> None:
    """The service is listed; the money may sit on another bill. Silence is the safe side."""
    assert bed_days_not_expected(_claim(), [_line("510090", day=1, billed="0")]).dates == _dates(1)


@pytest.mark.parametrize(
    "code", [" 510.090 ", "510 090", "510-090", "P510090", "p510090", "552.002", "P552002", "p552002", " P 552 002 "]
)
def test_the_icu_code_is_read_like_the_rest_of_the_engine_reads_it(code: str) -> None:
    assert bed_days_not_expected(_claim(), [_line(code, day=1)]).dates == _dates(1)


def test_the_icu_lines_of_another_claim_say_nothing() -> None:
    assert bed_days_not_expected(_claim(), [_line("510090", day=1, claim_id="OTHER")]) == BedNotExpected()


def test_two_icu_lines_on_one_day_cover_it_once() -> None:
    result = bed_days_not_expected(_claim(), [_line("510090", day=1), _package("552002", day=1)])

    assert result.dates == _dates(1)
    [reason] = result.reasons
    assert "1 day(s)" in reason and "510090" in reason and "552002" in reason


def test_the_icu_sentence_names_the_codes_in_sorted_order_whatever_the_order_of_the_lines() -> None:
    result = bed_days_not_expected(_claim(), [_package("552002", day=1), _line("510090", day=0)])

    [reason] = result.reasons
    assert "510090 / 552002" in reason


def test_the_icu_cause_reads_the_lines_not_the_claims_department_or_type() -> None:
    for claim in (_claim(), replace(_claim(), department="Yoğun Bakım"), replace(_claim(), claim_type="inpatient")):
        assert bed_days_not_expected(claim, [_line("510090", day=1)]).dates == _dates(1)


# The days between the first and the last covered day: the ICU stay itself (H.(8) first and exit day on 510090,
# the package days between).


def test_the_days_between_a_first_and_a_last_day_rate_line_are_inside_the_icu_stay() -> None:
    result = bed_days_not_expected(_claim(days=5), [_line("510090", day=0), _line("510090", day=4)])

    assert result.dates == _dates(0, 1, 2, 3, 4)
    [reason] = result.reasons
    assert "5 day(s)" in reason and "2026-07-10, 2026-07-11, 2026-07-12, 2026-07-13, 2026-07-14" in reason


def test_a_package_between_the_day_rate_days_is_the_same_stay() -> None:
    lines = [_line("510090", day=0), _package("552002", day=1, quantity=3), _line("510090", day=4)]

    assert bed_days_not_expected(_claim(days=5), lines).dates == _dates(0, 1, 2, 3, 4)


@pytest.mark.parametrize("order", [(0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)])
def test_the_stay_does_not_depend_on_the_order_of_the_lines(order: tuple[int, ...]) -> None:
    """The first and the last covered day come from every ICU line, whichever code or position they have."""
    lines = [_package("552002", day=2, quantity=2), _line("510090", day=0), _line("510090", day=6)]

    assert bed_days_not_expected(_claim(days=7), [lines[i] for i in order]).dates == _dates(0, 1, 2, 3, 4, 5, 6)


@pytest.mark.parametrize("order", [(0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)])
def test_a_package_at_either_end_of_the_stay_extends_it(order: tuple[int, ...]) -> None:
    lines = [_line("510090", day=3), _package("552001", day=1), _package("552003", day=5)]

    assert bed_days_not_expected(_claim(days=7), [lines[i] for i in order]).dates == _dates(1, 2, 3, 4, 5)


def test_one_icu_line_alone_pays_only_what_its_quantity_reaches() -> None:
    """No second line, no interior: the days after it are unknown, not ICU days (the reconciliation's own rule for the
    claim's last day still applies on top of this). A day-rate line of quantity 2 or more is the exception: it is the
    first and the exit day in one line (see above)."""
    assert bed_days_not_expected(_claim(days=5), [_line("510090", day=1)]).dates == _dates(1)
    assert bed_days_not_expected(_claim(days=5), [_package("552002", day=1, quantity=2)]).dates == _dates(1, 2)
    assert bed_days_not_expected(_claim(days=5), [_line("510090", day=1, quantity=2)]).dates == _dates(1, 2, 3, 4)


def test_ward_days_before_and_after_the_icu_stay_are_still_expected() -> None:
    result = bed_days_not_expected(_claim(days=7), [_line("510090", day=2), _line("510090", day=5)])

    assert result.dates == _dates(2, 3, 4, 5)  # not 10-11 July, not 16 July


def test_ward_days_around_a_stay_billed_on_a_package_quantity_are_still_expected() -> None:
    assert bed_days_not_expected(_claim(days=7), [_package("552002", day=2, quantity=4)]).dates == _dates(2, 3, 4, 5)


def test_ward_days_before_a_day_rate_line_of_quantity_two_are_still_expected() -> None:
    """The line's date is the first day: the days before it are ward days; the days after it are the stay."""
    assert bed_days_not_expected(_claim(days=7), [_line("510090", day=2, quantity=2)]).dates == _dates(2, 3, 4, 5, 6)
    assert bed_days_not_expected(_claim(days=7), [_line("510090", day=2, quantity=4)]).dates == _dates(2, 3, 4, 5)


def test_two_separate_icu_stays_of_one_claim_are_read_as_one_stay() -> None:
    """The documented limit of the reading: a ward interval between two ICU stays of ONE claim is not told apart from
    package days (silence, never a false recoverable)."""
    lines = [_line("510090", day=0), _line("510090", day=1), _line("510090", day=4), _line("510090", day=5)]

    assert bed_days_not_expected(_claim(days=7), lines).dates == _dates(0, 1, 2, 3, 4, 5)


def test_icu_lines_dated_before_the_stay_do_not_stretch_the_stay_backwards() -> None:
    """A line outside the stay covers only what its quantity runs into; it is not the stay's first ICU day."""
    result = bed_days_not_expected(_claim(days=5), [_line("510090", day=-3), _line("510090", day=3)])

    assert result.dates == _dates(3)


def test_icu_lines_dated_after_the_stay_do_not_stretch_the_stay_forwards() -> None:
    result = bed_days_not_expected(_claim(days=5), [_line("510090", day=1), _line("510090", day=9)])

    assert result.dates == _dates(1)


def test_a_stay_of_one_date_with_an_icu_line_has_its_only_day_paid() -> None:
    result = bed_days_not_expected(_claim(days=1), [_line("510090", day=0)])

    assert result.dates == _dates(0)
    [reason] = result.reasons  # the ICU cause alone: 510090 is no day-bed exclusion of its own
    assert "ICU stay" in reason


# The package window takes its days first.


def test_the_icu_days_inside_the_package_window_are_not_named_again() -> None:
    claim = _claim(days=7)
    result = bed_days_not_expected(claim, [_line("510090", day=2), _line("510090", day=5)], _window(3))

    assert result.dates == _dates(4, 5)
    [reason] = result.reasons
    assert "2 day(s)" in reason and "2026-07-14" in reason and "2026-07-15" in reason and "2026-07-12" not in reason


def test_a_window_that_takes_every_icu_day_leaves_nothing_to_explain() -> None:
    claim = _claim(days=7)

    assert bed_days_not_expected(claim, [_line("510090", day=2), _line("510090", day=5)], _window(5)) == BedNotExpected()


def test_an_icu_package_that_opens_the_window_still_explains_the_days_after_it() -> None:
    """P552002 on 11 July opens a window of one day (no işlem grubu); 510090 on 12 July is after it."""
    claim = _claim(days=3)
    lines = [_line("510090", day=0), _package("552002", day=1), _line("510090", day=2)]

    assert bed_days_not_expected(claim, lines, _window(1)).dates == _dates(2)


def test_an_icu_line_that_starts_inside_the_window_and_runs_past_it_covers_the_days_after_it() -> None:
    claim = _claim(days=6)

    assert bed_days_not_expected(claim, [_package("552002", day=1, quantity=4)], _window(2)).dates == _dates(3, 4)


# Together with the other bed-including lines.


def test_an_er_day_and_an_icu_day_are_named_once_each() -> None:
    lines = [_line("530000", day=2), _line("510090", day=0, quantity=2)]
    result = bed_days_not_expected(_claim(), lines)

    assert result.dates == _dates(0, 1, 2)
    assert len(result.reasons) == 2
    assert "530000" in result.reasons[0] and "ICU stay" in result.reasons[1]


def test_each_sentence_counts_and_lists_only_its_own_days() -> None:
    lines = [_line("530000", day=2), _line("510090", day=0, quantity=1), _line("510090", day=1)]
    result = bed_days_not_expected(_claim(days=4), lines)

    assert result.dates == _dates(0, 1, 2)
    er, icu = result.reasons
    assert "1 day(s) (2026-07-12)" in er and "2026-07-10" not in er
    assert "2 day(s) (2026-07-10, 2026-07-11)" in icu and "2026-07-12" not in icu


def test_a_day_case_with_an_ek2c_procedure_keeps_its_day_case_cause_beside_icu_lines() -> None:
    """The day case has no ward bed at all: every day is not expected whatever the ICU lines say, and both are named."""
    claim = _claim(days=4, claim_type="day_case")
    result = bed_days_not_expected(claim, [_line("702580", day=0, billed="545.76"), _line("510090", day=1)])

    assert result.dates == _dates(0, 1, 2, 3)
    assert len(result.reasons) == 2
    assert "ICU stay" in result.reasons[0] and "day case" in result.reasons[1]


def test_a_day_both_causes_cover_is_one_day_with_two_sentences() -> None:
    result = bed_days_not_expected(_claim(), [_line("530000", day=1), _line("510090", day=1)])

    assert result.dates == _dates(1)
    assert len(result.reasons) == 2


def test_a_claim_without_any_icu_line_gets_no_icu_sentence() -> None:
    result = bed_days_not_expected(_claim(), [_line("530000", day=1), _line("510100", day=2), _line("704230", day=0)])

    assert not any("ICU" in reason for reason in result.reasons)


# --- degenerate claims -------------------------------------------------------------------------------------------


def test_a_claim_without_dates_or_with_discharge_before_admission_expects_nothing_to_remove() -> None:
    no_admission = replace(_claim(), admission_date=None)
    no_discharge = replace(_claim(), discharge_date=None)
    backwards = replace(_claim(), discharge_date=D0 - timedelta(days=1))

    for claim in (no_admission, no_discharge, backwards):
        assert bed_days_not_expected(claim, [_line("530000", day=0)]) == BedNotExpected()
        assert bed_days_not_expected(claim, [_line("510090", day=0), _line("510090", day=2)]) == BedNotExpected()


def test_the_result_is_immutable() -> None:
    result = bed_days_not_expected(_claim(), [_line("530000", day=1)])

    assert isinstance(result.dates, frozenset) and isinstance(result.reasons, tuple)
    with pytest.raises(AttributeError):
        result.dates = frozenset()  # type: ignore[misc]

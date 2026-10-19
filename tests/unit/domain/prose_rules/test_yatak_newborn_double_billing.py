"""Audit exposure: a standard bed (510010) billed on a day a newborn bed (510070 Kuvöz / 510081 Kot) covers.

EK-2/B gives 510010, 510070, 510081 and 510090 the same first sentence, "Yemek, yatak, hasta vizit hizmetlerini
kapsar."; no text says "510010 ile birlikte faturalandırılmaz". That one patient-day cannot carry both is an
inference from the identical text, the one `prose_rules/yatak_icu_overlap.py` already applies to 510090 against
510010, so the finding is a *risk* (severity `warning`), not a certain error.

Day model (tasks/todo.md, "Audit-exposure detector for a standard bed ..."): a bed line dated d with quantity n (at
least 1) covers d ... d+n-1, for both sides; the repo's own bed lines are one line per day, quantity 1. A reversed
(negative) or 0-TL line asks no second charge and is ignored. The bills are built in memory.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest

from src.bilun.domain.billing.engine import analyze_claim
from src.bilun.domain.claims.models import ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.yatak_newborn_overlap import detect_yatak_newborn_overlap
from tests.unit.domain.billing.test_blood_uplift_wiring import _claim, _proc

pytestmark = pytest.mark.unit

_D = date(2026, 7, 10)
_NAMES = {"510010": "Standart yatak tarifesi", "510070": "Kuvöz", "510081": "Kot (beşik)"}
_TYPE = "yatak_newborn_overlap_double_billing"


def _bed(
    code: str,
    day: date | None,
    *,
    line_id: str,
    claim_id: str = "C1",
    patient_id: str = "P1",
    quantity: int | None = 1,
    billed: str = "222.36",
) -> ProcedureClaimLine:
    amount = Decimal(billed)
    return _proc(
        procedure_line_id=line_id,
        claim_id=claim_id,
        patient_id=patient_id,
        procedure_code=code,
        procedure_name=_NAMES.get(code.upper().lstrip("P").replace(".", "").replace("-", ""), "Yatak"),
        procedure_date=day,
        quantity=quantity,
        unit_price_try=amount,
        billed_amount_try=amount,
        expected_payable_try=amount,
    )


def _std(day: date | None = _D, **kwargs: Any) -> ProcedureClaimLine:
    kwargs.setdefault("line_id", "STD-1")
    return _bed("510010", day, **kwargs)


def _kuvoz(day: date | None = _D, **kwargs: Any) -> ProcedureClaimLine:
    kwargs.setdefault("line_id", "KUV-1")
    kwargs.setdefault("billed", "440.98")
    return _bed("510070", day, **kwargs)


def _kot(day: date | None = _D, **kwargs: Any) -> ProcedureClaimLine:
    kwargs.setdefault("line_id", "KOT-1")
    kwargs.setdefault("billed", "311.30")
    return _bed("510081", day, **kwargs)


class TestThePair:
    def test_the_exact_pair_on_one_day_is_flagged_with_every_field(self) -> None:
        [v] = detect_yatak_newborn_overlap([_kuvoz(), _std()])

        assert v["type"] == _TYPE
        assert v["rule_id"] == "yatak_newborn_overlap_510010"
        assert v["claim_id"] == "C1"
        assert v["procedure_line_id"] == "STD-1"
        assert v["procedure_code"] == "510010"
        assert v["procedure_name"] == "Standart yatak tarifesi"
        assert v["overlap_date"] == "2026-07-10"
        assert v["overlap_days"] == 1
        assert v["overlap_ranges"] == [["2026-07-10", "2026-07-10"]]
        assert v["newborn_bed_codes"] == ["510070"]
        assert v["newborn_line_ids"] == ["KUV-1"]
        assert v["newborn_claim_id"] == "C1"
        assert v["billed_amount_try"] == pytest.approx(222.36)
        assert v["risk_amount_try"] == pytest.approx(222.36)
        assert v["sut_section_id"] == "2.2.2"
        assert v["savings_category"] == "audit_exposure"
        # An inference from identical EK-2/B text, not an explicit exclusion: a risk, not a certain error, and
        # not "sourced" (review F4).
        assert v["savings_basis"] == "heuristic"
        assert v["severity"] == "warning"
        for word in ("510010", "510070", "Kuvöz", "2026-07-10", "EK-2B", "çift"):
            assert word in v["detail"], word
        # One day, one line per day: no day count, no quantity assumption to name.
        assert "(1 gün)" not in v["detail"] and "tarih + adet" not in v["detail"]
        assert "aynı takvim gününde" in v["detail"] and "aynı gün için" in v["detail"]

    def test_the_input_order_does_not_matter(self) -> None:
        assert detect_yatak_newborn_overlap([_std(), _kuvoz()]) == detect_yatak_newborn_overlap([_kuvoz(), _std()])

    def test_a_kot_beside_the_standard_bed_is_flagged_too(self) -> None:
        [v] = detect_yatak_newborn_overlap([_std(), _kot()])

        assert v["newborn_bed_codes"] == ["510081"]
        assert v["newborn_line_ids"] == ["KOT-1"]
        assert "510081" in v["detail"] and "Kot" in v["detail"]
        assert v["risk_amount_try"] == pytest.approx(222.36)

    @pytest.mark.parametrize("newborn_code", ["P510070", "p510070", "510.070", "510-070", " 510 070 "])
    @pytest.mark.parametrize("standard_code", ["P510010", "510.010", "510-010"])
    def test_code_spellings_are_read_like_the_other_bed_motors(self, newborn_code: str, standard_code: str) -> None:
        lines = [_bed(newborn_code, _D, line_id="NB", billed="440.98"), _bed(standard_code, _D, line_id="STD")]

        [v] = detect_yatak_newborn_overlap(lines)

        assert v["procedure_line_id"] == "STD"
        assert v["newborn_bed_codes"] == ["510070"]

    @pytest.mark.parametrize("offset", [-1, 1, 2, 30])
    def test_a_different_day_is_not_flagged(self, offset: int) -> None:
        assert detect_yatak_newborn_overlap([_kuvoz(), _std(_D + timedelta(days=offset))]) == []
        assert detect_yatak_newborn_overlap([_kot(), _std(_D + timedelta(days=offset))]) == []

    def test_a_stay_billed_one_line_per_day_is_flagged_on_the_shared_days_only(self) -> None:
        kuvoz = [_kuvoz(_D + timedelta(days=i), line_id=f"K{i}") for i in range(3)]  # days 0, 1, 2
        standard = [_std(_D + timedelta(days=i), line_id=f"S{i}") for i in range(2, 5)]  # days 2, 3, 4

        violations = detect_yatak_newborn_overlap([*kuvoz, *standard])

        assert [v["procedure_line_id"] for v in violations] == ["S2"]
        assert violations[0]["overlap_date"] == "2026-07-12"

    def test_a_standard_bed_beside_the_icu_day_rate_is_not_this_detectors_business(self) -> None:
        """510010 beside 510090 is `detect_yatak_icu_overlap`'s finding; this detector reads only 510070 / 510081."""
        for other in ("510090", "P552006", "510121", "510120"):
            assert detect_yatak_newborn_overlap([_bed(other, _D, line_id="O", billed="1252.27"), _std()]) == [], other

    def test_the_newborn_bed_lines_alone_or_the_standard_bed_alone_are_clean(self) -> None:
        assert detect_yatak_newborn_overlap([_kuvoz(), _kot(_D + timedelta(days=1), line_id="K2")]) == []
        assert detect_yatak_newborn_overlap([_std(), _std(_D + timedelta(days=1), line_id="S2")]) == []

    @pytest.mark.parametrize("lines", [None, []])
    def test_no_lines_no_findings(self, lines: Any) -> None:
        assert detect_yatak_newborn_overlap(lines) == []

    def test_both_newborn_beds_on_the_day_make_one_finding_per_standard_bed_line(self) -> None:
        """Kuvöz and Kot together are an explicit SUT exclusion of their own (not this task); the standard bed
        beside them is still one finding naming both."""
        [v] = detect_yatak_newborn_overlap([_kuvoz(), _kot(), _std()])

        assert v["newborn_bed_codes"] == ["510070", "510081"]
        assert v["newborn_line_ids"] == ["KOT-1", "KUV-1"]
        assert v["overlap_days"] == 1

    def test_only_the_newborn_lines_that_share_a_day_are_named(self) -> None:
        lines = [_kuvoz(line_id="K-HIT"), _kot(_D + timedelta(days=5), line_id="K-FAR", claim_id="OTHER"), _std()]

        [v] = detect_yatak_newborn_overlap(lines)

        assert v["newborn_bed_codes"] == ["510070"]
        assert v["newborn_line_ids"] == ["K-HIT"]
        assert v["newborn_claim_id"] == "C1"

    def test_each_standard_bed_line_on_the_day_is_a_finding_of_its_own(self) -> None:
        lines = [_kuvoz(), _std(line_id="S-A"), _std(line_id="S-B", billed="100.00"), _std(_D + timedelta(days=5), line_id="S-C")]

        violations = detect_yatak_newborn_overlap(lines)

        assert [v["procedure_line_id"] for v in violations] == ["S-A", "S-B"]
        assert [v["risk_amount_try"] for v in violations] == [222.36, 100.0]


class TestReversedAndZeroLines:
    @pytest.mark.parametrize("standard_billed", ["-222.36", "-0.01", "0", "0.00"])
    def test_a_reversed_or_free_standard_bed_asks_no_money(self, standard_billed: str) -> None:
        assert detect_yatak_newborn_overlap([_kuvoz(), _std(billed=standard_billed)]) == []

    @pytest.mark.parametrize("newborn_billed", ["-440.98", "-0.01", "0", "0.00"])
    def test_a_reversed_or_free_newborn_bed_covers_no_day(self, newborn_billed: str) -> None:
        assert detect_yatak_newborn_overlap([_kuvoz(billed=newborn_billed), _std()]) == []
        assert detect_yatak_newborn_overlap([_kot(billed=newborn_billed), _std()]) == []

    def test_a_reversal_does_not_hide_the_charged_line_beside_it(self) -> None:
        lines = [
            _kuvoz(line_id="KUV-REV", billed="-440.98"),
            _kuvoz(line_id="KUV-OK"),
            _std(line_id="STD-REV", billed="-222.36"),
            _std(line_id="STD-OK"),
        ]

        [v] = detect_yatak_newborn_overlap(lines)

        assert v["procedure_line_id"] == "STD-OK"
        assert v["newborn_line_ids"] == ["KUV-OK"]


class TestQuantityDays:
    def test_a_newborn_line_with_quantity_n_covers_n_days_from_its_date(self) -> None:
        kuvoz = _kuvoz(quantity=3, billed="1322.94")  # days 0, 1, 2

        assert [v["procedure_line_id"] for v in detect_yatak_newborn_overlap([kuvoz, _std(_D + timedelta(days=2))])] == ["STD-1"]
        assert detect_yatak_newborn_overlap([kuvoz, _std(_D + timedelta(days=3))]) == []
        assert detect_yatak_newborn_overlap([kuvoz, _std(_D - timedelta(days=1))]) == []

    @pytest.mark.parametrize("quantity", [0, None, -2])
    def test_a_quantity_below_one_counts_as_one_day(self, quantity: int | None) -> None:
        assert len(detect_yatak_newborn_overlap([_kuvoz(quantity=quantity), _std(quantity=quantity)])) == 1
        assert detect_yatak_newborn_overlap([_kuvoz(quantity=quantity), _std(_D + timedelta(days=1), quantity=quantity)]) == []

    def test_a_standard_bed_line_with_several_days_is_flagged_for_the_shared_days_pro_rata(self) -> None:
        standard = _std(quantity=3, billed="667.08")  # days 0, 1, 2: 222.36 a day
        kuvoz = _kuvoz(_D + timedelta(days=1))  # day 1

        [v] = detect_yatak_newborn_overlap([standard, kuvoz])

        assert v["overlap_days"] == 1
        assert v["overlap_ranges"] == [["2026-07-11", "2026-07-11"]]
        assert v["overlap_date"] == "2026-07-11"
        assert v["billed_amount_try"] == pytest.approx(667.08)
        assert v["risk_amount_try"] == pytest.approx(222.36)

    def test_the_pro_rata_amount_is_rounded_half_up_to_the_cent(self) -> None:
        standard = _std(quantity=3, billed="100.00")
        assert detect_yatak_newborn_overlap([standard, _kuvoz()])[0]["risk_amount_try"] == 33.33
        two_days = _kuvoz(quantity=2, line_id="KUV-2")
        assert detect_yatak_newborn_overlap([standard, two_days])[0]["risk_amount_try"] == 66.67
        half = _std(quantity=8, billed="0.04")  # 0.04 / 8 = 0.005 a day: half rounds up
        assert detect_yatak_newborn_overlap([half, _kuvoz()])[0]["risk_amount_try"] == 0.01
        # 0.03 / 2 = 0.015 is below half as a float: round(0.015, 2) would give 0.01
        float_trap = _std(quantity=2, billed="0.03")
        assert detect_yatak_newborn_overlap([float_trap, _kuvoz()])[0]["risk_amount_try"] == 0.02

    def test_adjacent_newborn_lines_make_one_overlap_range_and_both_codes_are_named(self) -> None:
        standard = _std(quantity=2, billed="444.72")  # days 0, 1
        lines = [standard, _kuvoz(line_id="KUV-A"), _kot(_D + timedelta(days=1), line_id="KOT-B")]

        [v] = detect_yatak_newborn_overlap(lines)

        assert v["overlap_days"] == 2
        assert v["overlap_ranges"] == [["2026-07-10", "2026-07-11"]]
        assert v["newborn_bed_codes"] == ["510070", "510081"]
        assert v["newborn_line_ids"] == ["KOT-B", "KUV-A"]
        assert v["risk_amount_try"] == pytest.approx(444.72)
        assert "510070 Kuvöz, 510081 Kot" in v["detail"]
        assert "2026-07-10 – 2026-07-11 (2 gün)" in v["detail"] and "günlerinde" in v["detail"]

    @pytest.mark.parametrize("second_day", [2, 3, 5])
    def test_separate_overlaps_are_separate_ranges_and_both_count(self, second_day: int) -> None:
        """One free day between two shared days (second_day 2) is the closest pair that must stay two ranges."""
        standard = _std(quantity=6, billed="1334.16")  # days 0 ... 5, 222.36 a day
        late = _D + timedelta(days=second_day)
        lines = [standard, _kuvoz(line_id="K0"), _kuvoz(late, line_id="K-LATE")]

        [v] = detect_yatak_newborn_overlap(lines)

        assert v["overlap_days"] == 2
        assert v["overlap_ranges"] == [["2026-07-10", "2026-07-10"], [late.isoformat(), late.isoformat()]]
        assert v["overlap_date"] == "2026-07-10"  # the first shared day
        assert v["risk_amount_try"] == pytest.approx(444.72)

    def test_overlapping_newborn_lines_count_each_shared_day_once(self) -> None:
        standard = _std(quantity=4, billed="889.44")
        lines = [standard, _kuvoz(quantity=3, line_id="K-A"), _kuvoz(_D + timedelta(days=1), quantity=3, line_id="K-B")]

        [v] = detect_yatak_newborn_overlap(lines)

        assert v["overlap_days"] == 4  # days 0-2 and 1-3 cover all four days, once each
        assert v["risk_amount_try"] == pytest.approx(889.44)

    def test_two_aggregated_lines_dated_on_the_same_day_overlap_by_date_and_the_detail_says_so(self) -> None:
        """Kuvöz x2 and 510010 x3, both dated on the admission day (review F1). The bed motors read this as a clean
        2 + 3 split: they sum quantities and ignore dates. The detector places the days from the dates, so the first
        two days are shared. Whether MEDULA dates an aggregated bed line on its first day is not known (the synthetic
        data has quantity 1 per day), so a finding that rests on a quantity above 1 names the assumption."""
        newborn = _kuvoz(quantity=2, billed="881.96")
        standard = _std(quantity=3, billed="667.08")

        [v] = detect_yatak_newborn_overlap([newborn, standard])

        assert v["overlap_days"] == 2
        assert v["overlap_ranges"] == [["2026-07-10", "2026-07-11"]]
        assert v["risk_amount_try"] == pytest.approx(444.72)
        assert "tarih + adet varsayımı" in v["detail"] and "bu günler için" in v["detail"]

    @pytest.mark.parametrize(
        ("newborn_quantity", "standard_quantity", "names_the_assumption"),
        [(1, 1, False), (2, 1, True), (1, 2, True), (3, 3, True)],
    )
    def test_the_detail_names_the_date_plus_quantity_assumption_only_when_a_line_has_several_days(
        self, newborn_quantity: int, standard_quantity: int, names_the_assumption: bool
    ) -> None:
        lines = [_kuvoz(quantity=newborn_quantity), _std(quantity=standard_quantity)]

        [v] = detect_yatak_newborn_overlap(lines)

        assert ("tarih + adet varsayımı" in v["detail"]) is names_the_assumption

    def test_the_pro_rata_cent_is_exact_half_up_not_float(self) -> None:
        # 0.03 x 5 / 6 = 0.025 exactly; float arithmetic gives 0.02
        [v] = detect_yatak_newborn_overlap([_kuvoz(quantity=5, billed="2.00"), _std(quantity=6, billed="0.03")])
        assert v["risk_amount_try"] == 0.03

    def test_the_3660_day_cap_is_exact(self) -> None:
        standard = _std(quantity=3661, billed="3660000.00")  # capped at 3660 days: 1000.00 a day
        [v] = detect_yatak_newborn_overlap([_kuvoz(), standard])
        assert v["risk_amount_try"] == 1000.0  # 3659 days would give 1000.27, 3661 days 999.73
        last_day = _D + timedelta(days=3659)
        assert len(detect_yatak_newborn_overlap([_kuvoz(last_day, line_id="K-LAST"), standard])) == 1
        assert detect_yatak_newborn_overlap([_kuvoz(last_day + timedelta(days=1), line_id="K-PAST"), standard]) == []

    def test_newborn_lines_in_any_input_order_give_the_same_ranges(self) -> None:
        lines = [_kuvoz(_D + timedelta(days=2), line_id="K2"), _kuvoz(_D, line_id="K0"), _std(quantity=3, billed="300.00")]

        [v] = detect_yatak_newborn_overlap(lines)

        assert v["overlap_days"] == 2
        assert v["overlap_ranges"] == [["2026-07-10", "2026-07-10"], ["2026-07-12", "2026-07-12"]]
        assert v["risk_amount_try"] == 200.0

    def test_a_newborn_line_inside_another_newborn_line_changes_nothing(self) -> None:
        standard = _std(quantity=5, billed="1111.80")
        lines = [standard, _kuvoz(quantity=5, line_id="K-LONG"), _kot(_D + timedelta(days=2), line_id="K-IN")]

        [v] = detect_yatak_newborn_overlap(lines)

        assert v["overlap_days"] == 5
        assert v["overlap_ranges"] == [["2026-07-10", "2026-07-14"]]
        assert v["risk_amount_try"] == pytest.approx(1111.80)

    def test_the_newborn_stay_inside_a_longer_standard_bed_line_is_only_the_shared_part(self) -> None:
        standard = _std(quantity=10, billed="2223.60")
        kuvoz = _kuvoz(_D + timedelta(days=4), quantity=2)

        [v] = detect_yatak_newborn_overlap([standard, kuvoz])

        assert v["overlap_days"] == 2
        assert v["risk_amount_try"] == pytest.approx(444.72)


class TestPatientAndClaimScope:
    def test_the_newborn_bed_of_another_claim_of_the_patient_counts(self) -> None:
        lines = [_kuvoz(claim_id="NICU"), _std(claim_id="WARD")]

        [v] = detect_yatak_newborn_overlap(lines)

        assert v["claim_id"] == "WARD"
        assert v["newborn_claim_id"] == "NICU"

    def test_findings_are_emitted_only_for_the_claims_in_scope(self) -> None:
        lines = [_kuvoz(claim_id="NICU"), _std(claim_id="WARD")]

        assert detect_yatak_newborn_overlap(lines, claim_ids_with_procs={"NICU"}) == []
        assert [v["claim_id"] for v in detect_yatak_newborn_overlap(lines, claim_ids_with_procs={"WARD"})] == ["WARD"]
        assert [v["claim_id"] for v in detect_yatak_newborn_overlap(lines, claim_ids_with_procs={"WARD", "NICU"})] == ["WARD"]
        assert detect_yatak_newborn_overlap(lines, claim_ids_with_procs=set()) == []

    def test_the_newborn_claims_of_the_finding_are_named_together(self) -> None:
        lines = [_kot(claim_id="NICU-B", line_id="KB"), _kuvoz(claim_id="NICU-A", line_id="KA"), _std(claim_id="WARD")]

        [v] = detect_yatak_newborn_overlap(lines)

        assert v["newborn_claim_id"] == "NICU-A,NICU-B"
        assert v["newborn_line_ids"] == ["KA", "KB"]
        assert v["newborn_bed_codes"] == ["510070", "510081"]

    def test_another_patients_newborn_bed_is_nothing_to_this_patient(self) -> None:
        assert detect_yatak_newborn_overlap([_kuvoz(patient_id="P2"), _std(patient_id="P1")]) == []

    def test_each_patient_is_matched_on_their_own_lines(self) -> None:
        lines = [
            _kuvoz(patient_id="P1", line_id="K1", claim_id="C1"),
            _std(patient_id="P2", line_id="S2", claim_id="C2"),
            _std(patient_id="P1", line_id="S1", claim_id="C1"),
            _kot(patient_id="P2", line_id="K2", claim_id="C2"),
        ]

        violations = detect_yatak_newborn_overlap(lines)

        assert [(v["claim_id"], v["procedure_line_id"], v["newborn_line_ids"]) for v in violations] == [
            ("C2", "S2", ["K2"]),
            ("C1", "S1", ["K1"]),
        ]


class TestBadData:
    def test_a_line_without_a_date_is_skipped(self) -> None:
        assert detect_yatak_newborn_overlap([_kuvoz(None), _std(None)]) == []
        assert len(detect_yatak_newborn_overlap([_kuvoz(None), _kuvoz(line_id="K2"), _std()])) == 1

    def test_a_dateless_standard_bed_beside_a_dated_newborn_bed_is_skipped(self) -> None:
        assert detect_yatak_newborn_overlap([_kuvoz(), _std(None)]) == []

    def test_a_line_running_past_the_end_of_the_calendar_covers_the_days_left(self) -> None:
        last = date.max
        lines = [_kuvoz(last - timedelta(days=3), quantity=10, billed="440.98"), _std(last - timedelta(days=1))]
        assert len(detect_yatak_newborn_overlap(lines)) == 1

    def test_a_huge_quantity_neither_crashes_nor_changes_the_answer(self) -> None:
        huge = 10**9
        [v] = detect_yatak_newborn_overlap([_kuvoz(quantity=huge, billed="1.00"), _std(_D + timedelta(days=3000))])
        assert v["overlap_days"] == 1  # inside the 3,660-day cap
        assert detect_yatak_newborn_overlap([_kuvoz(quantity=huge), _std(_D + timedelta(days=4000))]) == []

    def test_dates_near_the_end_of_the_calendar_do_not_overflow(self) -> None:
        last = date.max
        [v] = detect_yatak_newborn_overlap([_kuvoz(last, quantity=500), _std(last, quantity=500)])
        assert v["overlap_date"] == "9999-12-31"
        assert v["overlap_days"] == 1

    def test_the_input_is_not_changed(self) -> None:
        lines = [_kuvoz(), _std()]
        snapshot = list(lines)

        detect_yatak_newborn_overlap(lines)

        assert lines == snapshot


class TestKnownLimits:
    """Pinned so that closing one is a visible decision (tasks/todo.md, "found, not fixed")."""

    def test_a_reversal_is_ignored_not_netted_against_its_positive_twin(self) -> None:
        """+222.36 and its −222.36 reversal beside a Kuvöz still make a finding for the positive line, and a
        reversed Kuvöz does not cancel the positive Kuvöz. That is the convention of the other audit-exposure
        buckets (a +500 and −500 `bundled_line_flag` line still counts 500); netting a reversal pair is a
        decision, not built (review F2)."""
        reversed_standard = [_kuvoz(), _std(line_id="STD-POS"), _std(line_id="STD-REV", billed="-222.36")]
        [v] = detect_yatak_newborn_overlap(reversed_standard)
        assert (v["procedure_line_id"], v["risk_amount_try"]) == ("STD-POS", 222.36)

        reversed_newborn = [_kuvoz(line_id="K-POS"), _kuvoz(line_id="K-REV", billed="-440.98"), _std()]
        [v] = detect_yatak_newborn_overlap(reversed_newborn)
        assert v["newborn_line_ids"] == ["K-POS"]


# ── analyze_claim wiring ────────────────────────────────────────────────────


def _context(
    *claim_ids: str, lines: list[ProcedureClaimLine], patient_id: str = "P1", stay_days: int = 3
) -> PatientClaimContext:
    claims = tuple(
        _claim(
            claim_id=claim_id,
            patient_id=patient_id,
            department="yenidoğan",
            primary_icd10="Z38.0",
            admission_date=_D,
            discharge_date=_D + timedelta(days=stay_days - 1),
            claim_start_date=_D,
            claim_end_date=_D + timedelta(days=stay_days - 1),
            package_candidate=False,
            scenario_tag="newborn_bed_pair",
        )
        for claim_id in claim_ids
    )
    return PatientClaimContext(
        patient_id=patient_id,
        claims=claims,
        procedure_lines=tuple(lines),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


def _hits(violations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [v for v in violations if v.get("type") == _TYPE]


class TestAnalyzeClaimWiring:
    def test_the_pair_reaches_analyze_claim(self) -> None:
        ctx = _context("C1", lines=[_kuvoz(), _std()])

        [hit] = _hits(analyze_claim(ctx))

        assert hit["rule_id"] == "yatak_newborn_overlap_510010"
        assert hit["claim_id"] == "C1"
        assert hit["procedure_line_id"] == "STD-1"
        assert hit["savings_category"] == "audit_exposure"
        assert hit["severity"] == "warning"
        assert hit["risk_amount_try"] == pytest.approx(222.36)

    def test_a_clean_bill_has_no_finding(self) -> None:
        assert _hits(analyze_claim(_context("C1", lines=[_kuvoz(), _std(_D + timedelta(days=1))]))) == []
        assert _hits(analyze_claim(_context("C1", lines=[_std()]))) == []

    def test_it_is_gated_like_the_icu_detector_on_a_patient_and_procedure_lines(self) -> None:
        pair = [_kuvoz(), _std()]
        assert _hits(analyze_claim(_context("C1", lines=pair, patient_id=""))) == []
        assert _hits(analyze_claim(_context("C1", lines=[]))) == []

    def test_a_bill_sees_the_newborn_bed_of_the_patients_other_claim_and_is_flagged_alone(self) -> None:
        ctx = _context("NICU", "WARD", lines=[_kuvoz(claim_id="NICU"), _std(claim_id="WARD")])
        ward, nicu = ctx.slice_for_claim("WARD"), ctx.slice_for_claim("NICU")
        assert ward is not None and nicu is not None

        assert [v["claim_id"] for v in _hits(analyze_claim(ctx))] == ["WARD"]
        assert [v["claim_id"] for v in _hits(analyze_claim(ward))] == ["WARD"]
        assert _hits(analyze_claim(nicu)) == []

    def test_the_icu_pair_and_the_newborn_pair_are_told_apart(self) -> None:
        """A 510010 on a day with a Kuvöz line and on an ICU last day is two different findings."""
        icu_day = _D + timedelta(days=2)
        icu = _claim(
            claim_id="ICU",
            patient_id="P1",
            department="yoğun bakım",
            primary_icd10="P22.0",
            admission_date=_D,
            discharge_date=icu_day,
            claim_start_date=_D,
            claim_end_date=icu_day,
        )
        base = _context("WARD", lines=[], patient_id="P1")
        lines = [
            _bed("510090", _D, line_id="ICU-1", claim_id="ICU", billed="1252.27"),
            _kuvoz(icu_day, claim_id="WARD"),
            _std(icu_day, claim_id="WARD"),
        ]
        ctx = PatientClaimContext(
            patient_id="P1",
            claims=(icu, *base.claims),
            procedure_lines=tuple(lines),
            material_lines=(),
            drug_lines=(),
            diagnoses=(),
        )

        types = sorted(
            v["type"]
            for v in analyze_claim(ctx)
            if v.get("type") in {_TYPE, "yatak_icu_overlap_double_billing"}
        )

        assert types == ["yatak_icu_overlap_double_billing", _TYPE]


class TestOneDateStay:
    """A stay inside one calendar date (admission = discharge, under 24 hours) is billed at the day bed 510120, not as a
    full 510010 or Kuvöz day (SUT §2.2.2.(3); the short-stay branch prices both bed motors that way). This detector reads
    line dates and quantities, never the stay, so it does not depend on that rule: a full standard bed and a Kuvöz on the
    one date are still one day asked for twice, and the day bed beside a newborn bed is not its business."""

    def test_a_full_standard_bed_beside_a_kuvoz_on_the_one_date_is_still_flagged_once(self) -> None:
        ctx = _context("C1", lines=[_kuvoz(), _std()], stay_days=1)

        [hit] = _hits(analyze_claim(ctx))

        assert (hit["overlap_days"], hit["risk_amount_try"], hit["overlap_date"]) == (1, 222.36, "2026-07-10")

    @pytest.mark.parametrize("day_bed_amount", ["44.45", "20.00"])
    def test_the_day_bed_beside_a_newborn_bed_is_not_flagged(self, day_bed_amount: str) -> None:
        day_bed = _bed("510120", _D, line_id="DAY", billed=day_bed_amount)

        assert _hits(analyze_claim(_context("C1", lines=[_kuvoz(), day_bed], stay_days=1))) == []
        assert detect_yatak_newborn_overlap([_kot(), day_bed]) == []

    def test_the_day_bed_beside_a_standard_bed_is_not_flagged_either(self) -> None:
        assert detect_yatak_newborn_overlap([_std(), _bed("510120", _D, line_id="DAY", billed="44.45")]) == []


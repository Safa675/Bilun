"""Unit tests for yenidoğan (newborn) bed billing detector."""

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
    primary_icd10: str = "Z38.0",
    department: str = "genel",
):
    from src.bilun.domain.claims.models import ClaimHeader

    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        claim_type=claim_type,
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department=department,
        admission_date=admission,
        discharge_date=discharge,
        claim_start_date=admission or date.today(),
        claim_end_date=discharge or date.today(),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("1000"),
        expected_total_payable_try=Decimal("900"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _make_diagnosis(*, claim_id: str = "C1", icd10_code: str = "Z38.0"):
    from src.bilun.domain.claims.models import ClaimDiagnosis

    return ClaimDiagnosis(
        diagnosis_id="DX1",
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        icd10_code=icd10_code,
        is_primary=True,
        diagnosis_role="primary",
        diagnosis_date=date(2026, 7, 10),
        exemption_eligible=False,
    )


def test_newborn_3day_stay_emits_kuvoz() -> None:
    """Newborn claim (Z38) with 3-day stay → Kuvöz (510070) opportunity."""
    from src.bilun.domain.prose_rules.yenidogan_yatak import (
        detect_yenidogan_yatak_opportunities,
    )

    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 12)
    )
    opps = detect_yenidogan_yatak_opportunities(
        [header],
        [_make_diagnosis(claim_id="C1", icd10_code="Z38.0")],
        claim_ids_with_procs={"C1"},
    )

    assert len(opps) == 1
    opp = opps[0]
    # 3-day inclusive stay (Jul 10, 11, 12).
    assert opp["days"] == 3
    assert opp["bed_code"] == "510070"
    assert opp["puan"] == pytest.approx(743.65, abs=0.01)
    # 3 × 440.98 = 1322.94
    assert opp["expected_try"] == pytest.approx(1322.94, abs=0.01)
    assert opp["rule_id"] == "yenidogan_yatak_510070"
    assert opp["rooming_in"] is False
    assert opp["included_in_sgk_total"] is True
    assert opp["sut_section_id"] == "2.2.2"


def test_rooming_in_suppresses_kot() -> None:
    """Rooming-in baby → Kot (510081) suppressed, no opportunity emitted."""
    from src.bilun.domain.prose_rules.yenidogan_yatak import (
        detect_yenidogan_yatak_opportunities,
    )

    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 13)
    )
    # Mark this claim as rooming-in ('anne yanında').
    opps = detect_yenidogan_yatak_opportunities(
        [header],
        [_make_diagnosis(claim_id="C1", icd10_code="Z38.1")],
        claim_ids_with_procs={"C1"},
        rooming_in_claim_ids={"C1"},
    )

    # Rooming-in → Kot not billable, Kuvöz not opted in → no opportunity.
    assert opps == []

    # Opting in Kuvöz for rooming-in emits 510070 (not Kot).
    opps_kuvoz = detect_yenidogan_yatak_opportunities(
        [header],
        [_make_diagnosis(claim_id="C1", icd10_code="Z38.1")],
        claim_ids_with_procs={"C1"},
        rooming_in_claim_ids={"C1"},
        emit_kuvoz_for_rooming_in=True,
    )
    assert len(opps_kuvoz) == 1
    assert opps_kuvoz[0]["bed_code"] == "510070"
    assert opps_kuvoz[0]["rooming_in"] is True
    # 510081 Kot must NEVER be emitted for a rooming-in claim.
    assert all(o["bed_code"] != "510081" for o in opps_kuvoz)


def test_non_newborn_claim_skipped() -> None:
    """Adult inpatient claim (no newborn signal) → no opportunity."""
    from src.bilun.domain.prose_rules.yenidogan_yatak import (
        detect_yenidogan_yatak_opportunities,
    )

    header = _make_claim_header(
        primary_icd10="I10",  # adult hypertension, no newborn signal
        department="kardiyoloji",
    )
    opps = detect_yenidogan_yatak_opportunities(
        [header],
        [_make_diagnosis(claim_id="C1", icd10_code="I10")],
        claim_ids_with_procs={"C1"},
    )
    assert opps == []


def test_missing_diagnosis_skipped() -> None:
    """No newborn detection signal (dx nor department) → honest skip."""
    from src.bilun.domain.prose_rules.yenidogan_yatak import (
        detect_yenidogan_yatak_opportunities,
    )

    header = _make_claim_header(primary_icd10="J00", department="genel")
    # No diagnoses list at all, and neither dx nor dept signals newborn.
    opps = detect_yenidogan_yatak_opportunities(
        [header], (), claim_ids_with_procs={"C1"}
    )
    assert opps == []


def test_perinatal_p_code_detected() -> None:
    """P-range perinatal code (P07) also marks a newborn episode."""
    from src.bilun.domain.prose_rules.yenidogan_yatak import (
        detect_yenidogan_yatak_opportunities,
    )

    header = _make_claim_header(
        primary_icd10="P07.3", department="yenidoğan"
    )
    opps = detect_yenidogan_yatak_opportunities(
        [header],
        [_make_diagnosis(claim_id="C1", icd10_code="P07.3")],
        claim_ids_with_procs={"C1"},
    )
    assert len(opps) == 1
    assert opps[0]["bed_code"] == "510070"


def test_department_only_detection() -> None:
    """Department 'yenidoğan' triggers detection even without Z38/P dx."""
    from src.bilun.domain.prose_rules.yenidogan_yatak import (
        detect_yenidogan_yatak_opportunities,
    )

    header = _make_claim_header(primary_icd10="R50", department="Yenidoğan Servisi")
    opps = detect_yenidogan_yatak_opportunities(
        [header], (), claim_ids_with_procs={"C1"}
    )
    assert len(opps) == 1
    assert opps[0]["bed_code"] == "510070"


def test_historical_2023_newborn_claim_uses_2023_tariff() -> None:
    """2023 newborn claim resolves the 2023 510070 tariff (275.43 puan), not 2026."""
    from src.bilun.domain.prose_rules.yenidogan_yatak import (
        detect_yenidogan_yatak_opportunities,
    )

    header = _make_claim_header(
        admission=date(2023, 6, 10), discharge=date(2023, 6, 12)
    )
    opps = detect_yenidogan_yatak_opportunities(
        [header], (), claim_ids_with_procs={"C1"}
    )
    assert len(opps) == 1
    assert opps[0]["puan"] == pytest.approx(275.43, abs=0.01)
    assert opps[0]["expected_try"] == pytest.approx(3 * 163.33, abs=0.02)



# --- Billed bed lines are netted (the ICU and standard-bed motors do it since #13) -------------------------


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
        procedure_line_id=line_id or f"{claim_id}-{code}-{billed}",
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        procedure_date=procedure_date,
        procedure_code=code,
        procedure_name="bed",
        procedure_category=category,
        quantity=quantity,
        unit_price_try=Decimal("0"),
        billed_amount_try=Decimal(billed),
        expected_payable_try=Decimal("0"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _detect(lines, *, header=None, **kwargs):
    from src.bilun.domain.prose_rules.yenidogan_yatak import (
        detect_yenidogan_yatak_opportunities,
    )

    header = header or _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 12))
    return detect_yenidogan_yatak_opportunities(
        [header],
        [_make_diagnosis(claim_id=header.claim_id, icd10_code="Z38.0")],
        procedure_lines=lines,
        claim_ids_with_procs={header.claim_id},
        **kwargs,
    )


# 3 inclusive days: Kuvöz 3 x 440.98 = 1322.94, Kot 3 x 311.30 = 933.90 (price_try of the 2026-07-07 list).


def test_a_bed_billed_in_full_leaves_nothing_recoverable() -> None:
    [opp] = _detect([_line("510070", "1322.94", quantity=3)])

    assert opp["expected_try"] == pytest.approx(1322.94, abs=0.005)
    assert opp["actual_billed_try"] == pytest.approx(1322.94, abs=0.005)
    assert opp["recoverable_uplift_try"] == 0.0
    # The opportunity is still emitted: the standard-bed reconciliation reads the days from it.
    assert opp["days"] == 3
    assert opp["included_in_sgk_total"] is True


def test_a_bed_billed_in_part_leaves_the_remainder() -> None:
    [opp] = _detect([_line("510070", "440.98")])

    assert opp["expected_try"] == pytest.approx(1322.94, abs=0.005)
    assert opp["actual_billed_try"] == pytest.approx(440.98, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(881.96, abs=0.005)


def test_nothing_billed_leaves_the_full_charge() -> None:
    [opp] = _detect([_line("520010", "10")])  # an unrelated line on the claim

    assert opp["actual_billed_try"] == 0.0
    assert opp["recoverable_uplift_try"] == pytest.approx(opp["expected_try"], abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(1322.94, abs=0.005)


def test_without_procedure_lines_the_charge_is_unchanged() -> None:
    """The detector keeps working for callers that pass no lines: no netting, no ICU-code gate."""
    [opp] = _detect(None)

    assert opp["actual_billed_try"] == 0.0
    assert opp["recoverable_uplift_try"] == pytest.approx(1322.94, abs=0.005)
    assert "No newborn bed line" not in opp["detail"]  # it cannot tell, so it does not say


def test_a_bed_billed_above_the_charge_never_goes_negative() -> None:
    [opp] = _detect([_line("510070", "2000.00", quantity=3)])

    assert opp["actual_billed_try"] == pytest.approx(2000.0, abs=0.005)
    assert opp["recoverable_uplift_try"] == 0.0


def test_two_billed_lines_are_added_and_spellings_of_the_code_are_read() -> None:
    lines = [_line("510070", "400.00", line_id="L1"), _line(" 510.070 ", "300.00", line_id="L2")]
    [opp] = _detect(lines)

    assert opp["actual_billed_try"] == pytest.approx(700.0, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(622.94, abs=0.005)


def test_lines_of_another_claim_do_not_net() -> None:
    [opp] = _detect([_line("510070", "1322.94", claim_id="C-OTHER", quantity=3)])

    assert opp["actual_billed_try"] == 0.0
    assert opp["recoverable_uplift_try"] == pytest.approx(1322.94, abs=0.005)


def test_a_standard_bed_billed_and_no_newborn_bed_stands_down() -> None:
    """The claim has stated its bed: the standard bed (510010). The standard-bed motor owns the stay and nets
    its own lines; expecting a Kuvöz beside it would offer money the SGK pays under the other code."""
    assert _detect([_line("510010", "667.08", quantity=3)]) == []
    assert _detect([_line("520010", "10"), _line("510010", "222.36", line_id="STD1")]) == []


def test_a_standard_bed_billed_beside_a_newborn_bed_line_covers_its_days_only() -> None:
    """A Kuvöz line is the newborn-bed statement. A 510010 line beside it covers its own day (the standard-bed
    motor's), and its money neither nets this motor's charge nor stands it down."""
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 12))
    [opp] = _detect(
        [_line("510070", "440.98", line_id="K"), _line("510010", "222.36", line_id="S", procedure_date=date(2026, 7, 11))],
        header=header,
    )

    assert (opp["days"], opp["standard_bed_days"]) == (2, 1)
    assert opp["expected_try"] == pytest.approx(2 * 440.98, abs=0.005)
    assert opp["actual_billed_try"] == pytest.approx(440.98, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(440.98, abs=0.005)


def test_a_credit_line_covers_no_day() -> None:
    """A negative line is a reversal, not a billed day: it adds no standard-bed or Kot day."""
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 12))
    [opp] = _detect(
        [
            _line("510070", "440.98", line_id="K"),
            _line("510010", "-222.36", quantity=2, line_id="S"),
            _line("510081", "-311.30", quantity=2, line_id="T"),
        ],
        header=header,
    )

    assert opp["days"] == 3 and "standard_bed_days" not in opp
    assert opp["bed_code"] == "510070"
    assert opp["expected_try"] == pytest.approx(3 * 440.98, abs=0.005)  # no Kot day


# --- The bed type: a billed Kot is the hospital's own choice, never "upgraded" to Kuvöz --------------------


def test_a_billed_kot_is_priced_at_the_kot_rate_and_billed_in_full_leaves_nothing() -> None:
    [opp] = _detect([_line("510081", "933.90", quantity=3)])

    assert opp["bed_code"] == "510081"
    assert opp["rule_id"] == "yenidogan_yatak_510081"
    assert opp["puan"] == pytest.approx(524.95, abs=0.01)
    assert opp["expected_try"] == pytest.approx(933.90, abs=0.005)
    assert opp["recoverable_uplift_try"] == 0.0


def test_a_cot_billed_for_part_of_the_stay_prices_every_owned_day_as_a_cot() -> None:
    """Only Kot is billed (one day of three): the hospital stated a cot, nothing says Kuvöz, so the two unbilled
    days are Kot days too (311.30 each), not the 129.68 TL dearer Kuvöz default."""
    [opp] = _detect([_line("510081", "311.30")])

    assert opp["bed_code"] == "510081"
    assert opp["expected_try"] == pytest.approx(3 * 311.30, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(2 * 311.30, abs=0.005)
    assert "A Kot (510081) line is billed" in opp["detail"]


@pytest.mark.parametrize("day_offset", [0, 2])
def test_where_the_billed_cot_days_lie_does_not_matter(day_offset: int) -> None:
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 13))
    [opp] = _detect(
        [_line("510081", "622.60", quantity=2, procedure_date=date(2026, 7, 10 + day_offset))], header=header
    )

    assert opp["expected_try"] == pytest.approx(4 * 311.30, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(2 * 311.30, abs=0.005)


def test_a_single_cot_line_carrying_several_days_is_priced_as_a_cot_stay() -> None:
    """Quantity 1 with a four-day amount (out of the per-day convention): no quantity is read for a cot-only
    stay, the amount nets the cot charge, so an exactly billed stay leaves nothing (review round 2, G1)."""
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 13))
    [opp] = _detect([_line("510081", "1245.20", quantity=1)], header=header)

    assert opp["expected_try"] == pytest.approx(1245.20, abs=0.005)
    assert opp["recoverable_uplift_try"] == 0.0


def test_the_per_day_split_applies_when_kuvoz_is_billed_too() -> None:
    [opp] = _detect([_line("510070", "440.98", line_id="K"), _line("510081", "311.30", line_id="T")])

    assert opp["bed_code"] == "510070"
    assert "3 bed-day(s) = 2 at 440.98 + 1 billed Kot day(s) at 311.30 TRY/day" in opp["detail"]
    assert "A Kot (510081) line is billed on this claim" not in opp["detail"]  # only for an all-Kot stay


def test_a_claim_billing_both_codes_prices_each_billed_day_as_billed_and_the_rest_at_kuvoz() -> None:
    [opp] = _detect([_line("510070", "440.98", line_id="K"), _line("510081", "311.30", line_id="T")])

    assert opp["bed_code"] == "510070"
    assert opp["expected_try"] == pytest.approx(311.30 + 2 * 440.98, abs=0.005)
    assert opp["actual_billed_try"] == pytest.approx(752.28, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(440.98, abs=0.005)  # the one unbilled day


@pytest.mark.parametrize(
    "days,kuvoz_days,kot_days", [(4, 2, 2), (10, 4, 6), (3, 0, 3), (2, 1, 1)]
)
def test_a_stay_billed_kuvoz_then_kot_exactly_leaves_nothing(days: int, kuvoz_days: int, kot_days: int) -> None:
    """A baby billed an incubator first and a cot after (a plausible path; the repo has no data on its
    frequency). Every day billed, nothing to recover (review F2: the Kuvöz-Kot difference of 129.68 TL a day
    used to stay behind)."""
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 10 + days - 1))
    lines = []
    if kuvoz_days:
        lines.append(_line("510070", f"{kuvoz_days * 440.98:.2f}", quantity=kuvoz_days, line_id="K"))
    if kot_days:
        lines.append(
            _line("510081", f"{kot_days * 311.30:.2f}", quantity=kot_days, line_id="T", procedure_date=date(2026, 7, 10 + kuvoz_days))
        )

    [opp] = _detect(lines, header=header)

    assert opp["recoverable_uplift_try"] == 0.0
    assert opp["actual_billed_try"] == pytest.approx(opp["expected_try"], abs=0.01)


def test_billed_kot_days_never_exceed_the_stay() -> None:
    [opp] = _detect([_line("510081", "1556.50", quantity=5)])  # 5 units on a 3-day stay

    assert opp["bed_code"] == "510081"
    assert opp["expected_try"] == pytest.approx(933.90, abs=0.005)  # 3 Kot days, not 5
    assert opp["recoverable_uplift_try"] == 0.0


def test_a_kot_line_without_a_quantity_counts_one_day() -> None:
    [opp] = _detect([_line("510070", "440.98", line_id="K"), _line("510081", "311.30", quantity=0, line_id="T")])

    assert opp["expected_try"] == pytest.approx(311.30 + 2 * 440.98, abs=0.005)  # one Kot day, two Kuvöz days


def test_a_zero_priced_kot_line_is_still_the_hospitals_bed_statement() -> None:
    """A Kot line billed at 0 TL: the bed type is the cot, the charge is the Kot rate, all of it recoverable."""
    [opp] = _detect([_line("510081", "0", quantity=3)])

    assert opp["bed_code"] == "510081"
    assert opp["recoverable_uplift_try"] == pytest.approx(933.90, abs=0.005)


def test_without_a_bed_line_kuvoz_is_assumed_and_the_detail_says_so() -> None:
    [opp] = _detect([_line("520010", "10")])

    assert opp["bed_code"] == "510070"
    assert "No newborn bed line (510070 / 510081) is billed" in opp["detail"]
    assert "Kuvöz (510070) is assumed" in opp["detail"]

    [billed] = _detect([_line("510070", "100.00")])
    assert "is assumed" not in billed["detail"]


# --- The ICU gate: a newborn ICU stay is the ICU motor's (module docstring), not a Kuvöz ward stay ---------


@pytest.mark.parametrize(
    "code", ["510090", "P552001", "P552002", "P552003", "P552006", "P552007", "P552008", "552006", " p552006 "]
)
def test_a_claim_carrying_an_icu_code_is_left_to_the_icu_motor(code: str) -> None:
    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 13), primary_icd10="P22.0", department="yenidoğan"
    )

    assert _detect([_line(code, "0")], header=header) == []
    assert _detect([_line("520010", "10"), _line(code, "0")], header=header) == []


@pytest.mark.parametrize(
    "department", ["Yenidoğan Yoğun Bakım", "YENİDOĞAN YOĞUN BAKIM", "Yenidogan Yogun Bakim", "yenidoğan yoğun bakım ünitesi"]
)
def test_a_claim_naming_an_icu_department_is_left_alone_without_any_icu_code(department: str) -> None:
    """No ICU code on the bill, so the ICU motor is silent too; a Kuvöz is the wrong bed for a unit that is not a ward."""
    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 13), primary_icd10="P22.0", department=department
    )

    assert _detect([_line("520010", "10")], header=header) == []
    assert _detect(None, header=header) == []


def test_the_icu_gate_is_per_claim() -> None:
    icu = _make_claim_header(claim_id="C-ICU", primary_icd10="P22.0", department="yenidoğan")
    ward = _make_claim_header(claim_id="C-WARD", primary_icd10="Z38.0", department="yenidoğan")
    from src.bilun.domain.prose_rules.yenidogan_yatak import detect_yenidogan_yatak_opportunities

    opps = detect_yenidogan_yatak_opportunities(
        [icu, ward],
        [_make_diagnosis(claim_id="C-ICU", icd10_code="P22.0"), _make_diagnosis(claim_id="C-WARD")],
        procedure_lines=[_line("P552006", "0", claim_id="C-ICU"), _line("520010", "10", claim_id="C-WARD")],
        claim_ids_with_procs={"C-ICU", "C-WARD"},
    )

    assert [o["claim_id"] for o in opps] == ["C-WARD"]


def test_the_gate_is_the_icu_motors_own_predicate() -> None:
    """The code gate is the ICU motor's own test: a claim with an ICU code is the ICU motor's and never also the
    newborn motor's. (A department-only ICU claim is the newborn motor's silence and no ICU motor's: by design.)"""
    from src.bilun.domain.prose_rules.icu_puani import claim_has_icu_code

    assert claim_has_icu_code([_line("P552006", "0")]) is True
    assert claim_has_icu_code([_line("510090", "0")]) is True
    assert claim_has_icu_code([_line("510070", "0"), _line("520010", "0")]) is False
    assert claim_has_icu_code([]) is False


# --- EK-2/C package window (SUT 2.2.2.B-1(1),(3)-(4)): the package includes the bed -----------------------
# Group B = 10 calendar days, group E = 3, counted from the package's procedure date (PACKAGE_WINDOW_DAYS).


def _package(code: str, procedure_date: date):
    return _line(code, "5000", procedure_date=procedure_date, category="paket", line_id=f"PK-{code}")


def _ten_day_header():
    return _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 19))


def test_a_group_b_package_bundles_the_whole_stay_and_the_newborn_bed_expects_nothing() -> None:
    """The probe bill: 10 days, group-B package P600040 from day 2. The standard-bed motor already bundled
    all 10 days; this motor counted 10 x 440.98 = 4,409.80 TL."""
    [opp] = _detect([_package("P600040", date(2026, 7, 11))], header=_ten_day_header())

    assert opp["days"] == 0
    assert opp["bundled_days"] == 10
    assert opp["expected_try"] == 0.0
    assert opp["recoverable_uplift_try"] == 0.0
    assert "10 of 10 day(s) are bundled into the EK-2/C package window" in opp["detail"]


def test_a_short_package_window_leaves_the_days_after_it() -> None:
    """Group E: 3 days from 10 July, window through 12 July; 13-19 July (7 days) are newborn bed days."""
    [opp] = _detect([_package("P600330", date(2026, 7, 10))], header=_ten_day_header())

    assert opp["days"] == 7
    assert opp["bundled_days"] == 3
    assert opp["expected_try"] == pytest.approx(7 * 440.98, abs=0.01)
    assert opp["recoverable_uplift_try"] == pytest.approx(7 * 440.98, abs=0.01)


def test_the_window_and_the_netting_work_together() -> None:
    lines = [_package("P600330", date(2026, 7, 10)), _line("510070", "440.98", procedure_date=date(2026, 7, 13))]
    [opp] = _detect(lines, header=_ten_day_header())

    assert (opp["days"], opp["bundled_days"]) == (7, 3)
    assert opp["actual_billed_try"] == pytest.approx(440.98, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(6 * 440.98, abs=0.01)


def test_a_package_dated_outside_the_stay_opens_no_window() -> None:
    [opp] = _detect([_package("P600040", date(2026, 8, 1))], header=_ten_day_header())

    assert (opp["days"], opp["bundled_days"]) == (10, 0)
    assert opp["expected_try"] == pytest.approx(4409.8, abs=0.01)


def test_without_a_package_nothing_is_bundled() -> None:
    [opp] = _detect([_line("520010", "10")])

    assert opp["bundled_days"] == 0
    assert opp["days"] == 3
    assert "bundled into" not in opp["detail"]


# --- The recoverable amount never exceeds the charge (review F3) ----------------------------------------


def test_a_negative_billed_line_never_makes_the_recoverable_exceed_the_charge() -> None:
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 11))
    [opp] = _detect([_line("510070", "-100.00")], header=header)

    assert opp["expected_try"] == pytest.approx(881.96, abs=0.005)
    assert opp["actual_billed_try"] == pytest.approx(-100.0, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(881.96, abs=0.005)  # was 981.96

    # The same cap on the day bed of a stay of one date (expected 44.45).
    [day] = _detect([_line("510070", "-100.00")], header=_make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 10)))
    assert day["expected_try"] == pytest.approx(44.45, abs=0.005)
    assert day["recoverable_uplift_try"] == pytest.approx(44.45, abs=0.005)  # was 144.45


def test_a_negative_billed_line_inside_a_fully_bundled_stay_recovers_nothing() -> None:
    lines = [_package("P600040", date(2026, 7, 11)), _line("510070", "-617.37", quantity=7)]
    [opp] = _detect(lines, header=_ten_day_header())

    assert opp["expected_try"] == 0.0
    assert opp["recoverable_uplift_try"] == 0.0  # was 617.37


# --- Surviving mutants of the review: the boundaries of the new code -------------------------------------


def test_a_discharge_before_the_admission_emits_nothing() -> None:
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 9))

    assert _detect([_line("520010", "10")], header=header) == []


def test_one_day_left_after_a_package_window_is_not_a_same_day_stay() -> None:
    """4 days, group-E package from day 1 (window through 12 July): only 13 July remains, but the stay is not same-day."""
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 13))
    [opp] = _detect([_package("P600330", date(2026, 7, 10))], header=header)

    assert opp["days"] == 1
    assert opp["same_day_stay"] is False
    assert "Same-day" not in opp["detail"]
    # Not a stay of one date: the day bed does not apply, the day is a Kuvöz day.
    assert opp["bed_code"] == "510070"
    assert opp["expected_try"] == pytest.approx(440.98, abs=0.005)


def test_a_genuine_same_day_stay_is_priced_at_the_day_bed() -> None:
    """SUT §2.2.2.(3): under 24 hours the bed is the day bed 510120 (44.45 TRY), not a full Kuvöz day (440.98)."""
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 10))
    [opp] = _detect([_line("520010", "10")], header=header)

    assert opp["same_day_stay"] is True
    assert opp["days"] == 1
    assert opp["bed_code"] == "510120"
    assert opp["rule_id"] == "yenidogan_yatak_510120"
    assert opp["puan"] == pytest.approx(74.96, abs=0.005)
    assert opp["expected_try"] == pytest.approx(44.45, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(44.45, abs=0.005)
    assert "Same-day admission/discharge (under 24 hours)" in opp["detail"]
    assert "SUT §2.2.2.(3)" in opp["detail"]
    for gone in ("is assumed", "mutually exclusive", "confirm newborn ward admission", "Kot rate"):
        assert gone not in opp["detail"]


def test_the_assumed_kuvoz_sentence_is_not_said_for_a_rooming_in_opt_in() -> None:
    [opp] = _detect(
        [_line("520010", "10")], rooming_in_claim_ids={"C1"}, emit_kuvoz_for_rooming_in=True
    )

    assert opp["rooming_in"] is True
    assert "is assumed" not in opp["detail"]
    assert "Rooming-in" in opp["detail"]


@pytest.mark.parametrize(
    "department",
    [
        "NICU", "YYBÜ", "Yenidoğan 1. Basamak YB", "Yoğunbakım", "yoğun  bakım", "Yenidoğan YB Ünitesi",
        "Neonatal ICU", "YENİDOĞAN YOĞUN BAKIM", "Yenidoğan YBÜ", "Çocuk YBÜ", "ÇYBÜ", "PICU",
    ],
)
def test_the_icu_department_spellings_of_the_review_are_left_alone(department: str) -> None:
    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 13), primary_icd10="P22.0", department=department
    )

    assert _detect([_line("520010", "10")], header=header) == []


@pytest.mark.parametrize(
    "department", ["Yenidoğan Servisi", "Yenidoğan Yoğun Tedavi Servisi", "Yenidoğan Hybrid Odası"]
)
def test_a_ward_whose_name_only_resembles_an_icu_still_emits(department: str) -> None:
    """'yoğun' alone, 'yb' inside a longer word and similar are not intensive care."""
    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 13), primary_icd10="Z38.0", department=department
    )
    assert len(_detect([_line("520010", "10")], header=header)) == 1


# --- The ICU transfer day: 510090 on another claim pays that day's bed (review F4) --------------------------


def test_an_icu_last_day_paid_on_another_claim_is_not_a_newborn_bed_day() -> None:
    """The standard-bed motor drops the ICU last day of any claim of the patient (EK-2/B: 510090 covers yemek +
    yatak + vizit); the newborn motor does the same. Stay 10-12 July, ICU claim discharged 10 July."""
    [opp] = _detect([_line("520010", "10")], icu_last_days={date(2026, 7, 10)})

    assert opp["days"] == 2
    assert opp["expected_try"] == pytest.approx(2 * 440.98, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(2 * 440.98, abs=0.005)
    assert opp["icu_overlap_days"] == 1
    assert opp["icu_overlap_dates"] == ["2026-07-10"]
    assert "2026-07-10" in opp["detail"] and "510090" in opp["detail"]


def test_without_icu_last_days_the_row_has_no_overlap_keys() -> None:
    for icu_last_days in (None, set(), {date(2026, 7, 9), date(2026, 7, 13)}):  # the last two lie outside the stay
        [opp] = _detect([_line("520010", "10")], icu_last_days=icu_last_days)
        assert opp["days"] == 3
        assert "icu_overlap_days" not in opp and "icu_overlap_dates" not in opp


def test_an_icu_last_day_inside_a_package_window_is_not_taken_out_twice() -> None:
    """Group E from 10 July bundles 10-12 July; an ICU last day on 11 July is already bundled, 15 July is not."""
    [opp] = _detect(
        [_package("P600330", date(2026, 7, 10))],
        header=_ten_day_header(),
        icu_last_days={date(2026, 7, 11), date(2026, 7, 15)},
    )

    assert (opp["days"], opp["bundled_days"]) == (6, 3)  # 13-19 July is 7 days, minus 15 July
    assert opp["icu_overlap_dates"] == ["2026-07-15"]


def test_the_icu_days_taken_out_floor_the_stay_at_zero() -> None:
    [opp] = _detect(
        [_line("520010", "10")],
        icu_last_days={date(2026, 7, 10), date(2026, 7, 11), date(2026, 7, 12)},
    )

    assert opp["days"] == 0
    assert opp["expected_try"] == 0.0
    assert opp["recoverable_uplift_try"] == 0.0
    assert opp["icu_overlap_days"] == 3


def test_the_billed_lines_net_the_days_that_are_left_after_the_icu_day() -> None:
    [opp] = _detect([_line("510070", "440.98")], icu_last_days={date(2026, 7, 10)})

    assert opp["expected_try"] == pytest.approx(881.96, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(440.98, abs=0.005)


# --- Standard-bed days beside a newborn bed (incubator, then a standard bed) ------------------------------
# A newborn bed line is the evidence of a newborn bed; billed 510010 days beside it are standard-bed days
# owned by the standard-bed motor, so this motor expects only the other days (review round 2, "both-billed cliff").


def test_a_stay_billed_incubator_then_standard_bed_exactly_leaves_nothing() -> None:
    """10 days: 2 Kuvöz (881.96) then 8 standard bed (1,778.88), both exact. This motor owned all 10 days and
    left 8 x 440.98 = 3,527.84 as a row on an exactly billed stay."""
    lines = [
        _line("510070", "881.96", quantity=2, line_id="K"),
        _line("510010", "1778.88", quantity=8, line_id="S", procedure_date=date(2026, 7, 12)),
    ]
    [opp] = _detect(lines, header=_ten_day_header())

    assert opp["days"] == 2
    assert opp["standard_bed_days"] == 8
    assert opp["expected_try"] == pytest.approx(881.96, abs=0.005)
    assert opp["actual_billed_try"] == pytest.approx(881.96, abs=0.005)  # the 510010 money is the other motor's
    assert opp["recoverable_uplift_try"] == 0.0
    assert "8 day(s) are billed on the standard bed" in opp["detail"]


def test_a_cot_then_standard_bed_stay_billed_exactly_leaves_nothing() -> None:
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 13))
    lines = [
        _line("510081", "311.30", quantity=1, line_id="T"),
        _line("510010", "667.08", quantity=3, line_id="S", procedure_date=date(2026, 7, 11)),
    ]
    [opp] = _detect(lines, header=header)

    assert (opp["days"], opp["standard_bed_days"]) == (1, 3)
    assert opp["bed_code"] == "510081"
    assert opp["recoverable_uplift_try"] == 0.0


def test_the_days_neither_bed_family_covers_stay_unbilled_kuvoz_days() -> None:
    """1 Kuvöz day and 3 standard-bed days billed of 10: the 6 unbilled days are the motor's Kuvöz default."""
    lines = [
        _line("510070", "440.98", quantity=1, line_id="K"),
        _line("510010", "667.08", quantity=3, line_id="S", procedure_date=date(2026, 7, 11)),
    ]
    [opp] = _detect(lines, header=_ten_day_header())

    assert (opp["days"], opp["standard_bed_days"]) == (7, 3)
    assert opp["expected_try"] == pytest.approx(7 * 440.98, abs=0.01)
    assert opp["recoverable_uplift_try"] == pytest.approx(6 * 440.98, abs=0.01)


def test_standard_bed_units_beyond_the_stay_take_only_the_days_no_newborn_line_covers() -> None:
    """A newborn bed line covers its day first; 510010 lines beside it (here 12 units on a 10-day stay) can only
    cover the other days. The excess is double billing (an audit matter), not a standard-bed shortfall."""
    lines = [
        _line("510070", "440.98", quantity=1, line_id="K"),
        _line("510010", "2668.32", quantity=12, line_id="S", procedure_date=date(2026, 7, 11)),
    ]
    [opp] = _detect(lines, header=_ten_day_header())

    assert (opp["days"], opp["standard_bed_days"]) == (1, 9)
    assert opp["expected_try"] == pytest.approx(440.98, abs=0.005)
    assert opp["recoverable_uplift_try"] == 0.0


def test_double_covered_line_days_are_not_a_standard_bed_shortfall() -> None:
    """7 days: Kuvöz x7 billed in full and two 510010 lines billed 0 TL. The Kuvöz lines cover all 7 days, so the
    510010 lines own no day (review round 3, H2: the standard-bed motor used to claim 444.72 for them)."""
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 16))
    lines = [
        _line("510070", "3086.86", quantity=7, line_id="K"),
        _line("510010", "0", quantity=2, line_id="S", procedure_date=date(2026, 7, 11)),
    ]
    [opp] = _detect(lines, header=header)

    assert opp["days"] == 7 and "standard_bed_days" not in opp
    assert opp["recoverable_uplift_try"] == 0.0


def test_standard_bed_lines_inside_a_mandated_window_do_not_count_as_standard_days() -> None:
    """Lines of a mandated package window belong to the package (counts_against_expected_days)."""
    from datetime import timedelta  # noqa: PLC0415

    from tests.unit.domain.billing.test_showcase_session_and_package_gaps import GENCER, _Bill, _d  # noqa: PLC0415

    start = _d("2026-07-14")
    bill = _Bill("C-SH01", "yatis", start, _d("2026-07-25"), package_candidate=True)
    bill.proc("610131", start, specialty=GENCER)  # mandated package, window through 21 July
    bill.proc("510070", _d("2026-07-22"), qty=1, specialty=GENCER)
    for i in range(8):  # 14-21 July: inside the window, they pay the package
        bill.proc("510010", start + timedelta(days=i), qty=1, specialty=GENCER)
    ctx = bill.ctx()
    from dataclasses import replace  # noqa: PLC0415

    from src.bilun.domain.prose_rules.yenidogan_yatak import detect_yenidogan_yatak_opportunities  # noqa: PLC0415

    claim = replace(ctx.claims[0], department="yenidoğan")
    [opp] = detect_yenidogan_yatak_opportunities(
        [claim], [], procedure_lines=list(ctx.procedure_lines), claim_ids_with_procs={claim.claim_id}
    )

    assert (opp["days"], opp["bundled_days"]) == (4, 8)
    assert "standard_bed_days" not in opp  # the 8 in-window lines pay the package, not standard days
    assert opp["recoverable_uplift_try"] == pytest.approx(3 * 440.98, abs=0.01)  # 23-25 July unbilled; 22 July billed


def test_a_claim_billing_no_standard_bed_has_no_standard_bed_key() -> None:
    [opp] = _detect([_line("510070", "440.98")])

    assert "standard_bed_days" not in opp
    assert "billed on the standard bed" not in opp["detail"]


# --- Detail text and labels of the three stay shapes (review round 2 survivors K12, K14, K19, K20) ----------


def test_a_single_rate_stay_names_one_rate_and_no_mix() -> None:
    [kuvoz] = _detect([_line("520010", "10")])
    assert "3 bed-day(s) at 440.98 TRY/day" in kuvoz["detail"]
    assert "billed Kot day" not in kuvoz["detail"]
    assert "A Kot (510081) line is billed" not in kuvoz["detail"]

    [cot] = _detect([_line("510081", "933.90", quantity=3)])
    assert "3 bed-day(s) at 311.30 TRY/day" in cot["detail"]
    assert "billed Kot day" not in cot["detail"]
    assert "A Kot (510081) line is billed" in cot["detail"]


def test_a_mixed_stay_names_both_rates_and_not_the_cot_only_sentence() -> None:
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 13))
    [mixed] = _detect(
        [_line("510070", "881.96", quantity=2, line_id="K"), _line("510081", "622.60", quantity=2, line_id="T")],
        header=header,
    )

    assert "4 bed-day(s) = 2 at 440.98 + 2 billed Kot day(s) at 311.30 TRY/day" in mixed["detail"]
    assert "A Kot (510081) line is billed" not in mixed["detail"]
    assert mixed["bed_code"] == "510070" and mixed["rule_id"] == "yenidogan_yatak_510070"


def test_a_fully_bundled_stay_is_labelled_kuvoz_even_when_only_a_cot_is_billed() -> None:
    lines = [_package("P600040", date(2026, 7, 11)), _line("510081", "311.30", procedure_date=date(2026, 7, 10))]
    [opp] = _detect(lines, header=_ten_day_header())

    assert opp["days"] == 0
    assert opp["bed_code"] == "510070" and opp["rule_id"] == "yenidogan_yatak_510070"


def test_billed_cot_lines_inside_a_mandated_window_are_the_bed_statement_but_net_nothing() -> None:
    """12 days, mandated 610131 (window 8 days from 14 July), Kot x8 dated 14 July (inside the window): they pay
    the package, so they net nothing, but they still state a cot for the days after it."""
    import dataclasses

    from tests.unit.domain.billing.test_showcase_session_and_package_gaps import GENCER, _Bill, _d

    def newborn_ctx(bed_lines):
        start = _d("2026-07-14")
        bill = _Bill("C-SH01", "yatis", start, _d("2026-07-25"), package_candidate=True)
        bill.proc("610131", start, specialty=GENCER)
        for code, day, quantity in bed_lines:
            bill.proc(code, day, qty=quantity, specialty=GENCER)
        ctx = bill.ctx()
        return dataclasses.replace(ctx, claims=(dataclasses.replace(ctx.claims[0], department="yenidoğan"),))

    from src.bilun.domain.prose_rules.yenidogan_yatak import detect_yenidogan_yatak_opportunities

    def detect(ctx):
        return detect_yenidogan_yatak_opportunities(
            list(ctx.claims), [], procedure_lines=list(ctx.procedure_lines),
            claim_ids_with_procs={ctx.claims[0].claim_id},
        )

    [cot_only] = detect(newborn_ctx([("510081", _d("2026-07-14"), 8)]))
    assert (cot_only["days"], cot_only["bundled_days"]) == (4, 8)
    assert cot_only["bed_code"] == "510081"  # the cot statement carries to the days after the window
    assert cot_only["actual_billed_try"] == 0.0
    assert cot_only["recoverable_uplift_try"] == pytest.approx(4 * 311.30, abs=0.01)

    # With a Kuvöz line after the window the Kot lines inside it count as no Kot day: all four days are Kuvöz.
    [mixed] = detect(newborn_ctx([("510070", _d("2026-07-22"), 1), ("510081", _d("2026-07-14"), 8)]))
    assert mixed["bed_code"] == "510070"
    assert mixed["expected_try"] == pytest.approx(4 * 440.98, abs=0.01)


# --- Zero rates in the catalog (guards) --------------------------------------------------------------------


def test_a_missing_cot_rate_falls_back_to_the_kuvoz_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.bilun.domain.prose_rules import yenidogan_yatak

    real = yenidogan_yatak._daily_rate
    monkeypatch.setattr(yenidogan_yatak, "_daily_rate", lambda code, visit_date=None: 0.0 if code == "510081" else real(code, visit_date))

    [opp] = _detect([_line("510081", "933.90", quantity=3)])

    assert opp["bed_code"] == "510070"
    assert opp["expected_try"] == pytest.approx(3 * 440.98, abs=0.005)


def test_a_missing_kuvoz_rate_still_prices_an_all_cot_stay_and_skips_a_kuvoz_stay(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.bilun.domain.prose_rules import yenidogan_yatak

    real = yenidogan_yatak._daily_rate
    monkeypatch.setattr(yenidogan_yatak, "_daily_rate", lambda code, visit_date=None: 0.0 if code == "510070" else real(code, visit_date))

    [cot] = _detect([_line("510081", "933.90", quantity=3)])
    assert cot["bed_code"] == "510081" and cot["expected_try"] == pytest.approx(933.90, abs=0.005)
    assert _detect([_line("520010", "10")]) == []  # nothing billed: the Kuvöz default cannot be priced


# --- Standard-bed spelling, ICU dates order, window end, spellings (review round 2 survivors) ---------------


@pytest.mark.parametrize("code", ["510010", " 510.010 ", "P510010", "510 010"])
def test_the_standard_bed_stand_down_reads_the_code_like_the_rest_of_the_engine(code: str) -> None:
    assert _detect([_line(code, "667.08", quantity=3)]) == []


def test_icu_last_days_are_listed_in_date_order() -> None:
    stay = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 19))
    days = {date(2026, 7, 17), date(2026, 7, 11), date(2026, 7, 14), date(2026, 7, 12), date(2026, 7, 19)}
    [opp] = _detect([_line("520010", "10")], header=stay, icu_last_days=days)

    assert opp["icu_overlap_dates"] == sorted(day.isoformat() for day in days)
    assert opp["icu_overlap_days"] == 5 and opp["days"] == 5


def test_an_icu_last_day_on_the_window_end_is_already_bundled_not_dropped_again() -> None:
    """Group E from 10 July bundles 10-12 July; an ICU last day on 12 July (the window end) is not dropped again."""
    [opp] = _detect(
        [_package("P600330", date(2026, 7, 10))], header=_ten_day_header(), icu_last_days={date(2026, 7, 12)}
    )

    assert (opp["days"], opp["bundled_days"]) == (7, 3)
    assert "icu_overlap_dates" not in opp


@pytest.mark.parametrize("department", ["Yoğun-Bakım", "YB.", "Yenidoğan YB1", "NICU2", "Yenidoğan  Yoğun   Bakım"])
def test_hyphens_dots_digits_and_spacing_do_not_hide_an_icu_department(department: str) -> None:
    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 13), primary_icd10="P22.0", department=department
    )

    assert _detect([_line("520010", "10")], header=header) == []


# --- A credit line states the bed type but covers no day (review round 3, H3 and survivors) ----------------


def test_a_reversed_standard_bed_line_alone_still_states_the_standard_bed() -> None:
    """The only bed line is a reversal of 510010: the bed that was billed is the standard bed, so the standard-bed
    motor keeps the stay. Reading it as 'no bed' would offer a 4,409.80 Kuvöz row on a 10-day stay (round 3, H3)."""
    assert _detect([_line("510010", "-667.08", quantity=3)]) == []


def test_a_credit_cot_line_states_the_cot_but_covers_no_day() -> None:
    [opp] = _detect([_line("510081", "-933.90", quantity=3)])

    assert opp["bed_code"] == "510081"  # a cot was billed (and reversed)
    assert opp["expected_try"] == pytest.approx(933.90, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(933.90, abs=0.005)  # capped: the reversal recovers no more
    assert "is assumed" not in opp["detail"]  # the bed type is stated


def test_a_credit_kuvoz_line_states_the_bed_so_nothing_is_assumed() -> None:
    [opp] = _detect([_line("510070", "-440.98")])

    assert opp["bed_code"] == "510070"
    assert "is assumed" not in opp["detail"]


def test_a_credit_cot_line_beside_a_kuvoz_line_is_no_cot_day() -> None:
    [opp] = _detect([_line("510070", "440.98", line_id="K"), _line("510081", "-311.30", quantity=2, line_id="T")])

    assert opp["bed_code"] == "510070"
    assert opp["expected_try"] == pytest.approx(3 * 440.98, abs=0.005)


def test_a_negative_quantity_covers_one_day_at_most() -> None:
    [opp] = _detect([_line("510070", "440.98", line_id="K"), _line("510081", "311.30", quantity=-3, line_id="T")])

    assert opp["expected_try"] == pytest.approx(311.30 + 2 * 440.98, abs=0.005)  # one Kot day, not minus three


def test_an_inflated_cot_quantity_beside_kuvoz_prices_the_stay_as_a_cot_stay() -> None:
    """Kot quantity 10 on a 4-day stay is capped at the 4 days (and then every day is a billed Kot day)."""
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 13))
    [opp] = _detect(
        [_line("510070", "881.96", quantity=2, line_id="K"), _line("510081", "3113.00", quantity=10, line_id="T")],
        header=header,
    )

    assert opp["days"] == 4
    assert opp["bed_code"] == "510081"
    assert opp["expected_try"] == pytest.approx(4 * 311.30, abs=0.005)


# --- An ICU-named unit that bills a newborn bed is netted, not silenced (review round 3, H4) -----------------


@pytest.mark.parametrize("department", ["Çocuk YBÜ", "Yenidoğan Yoğun Bakım", "NICU"])
def test_an_icu_named_department_that_bills_a_newborn_bed_is_netted(department: str) -> None:
    """No ICU code on the bill and the hospital billed Kuvöz in full: the stay is paid, nothing to recover — and,
    because this motor still owns the days, the standard-bed motor cannot call them missing."""
    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 15), primary_icd10="P22.0", department=department
    )
    [opp] = _detect([_line("510070", "2645.88", quantity=6)], header=header)

    assert opp["days"] == 6 and opp["recoverable_uplift_try"] == 0.0


def test_an_icu_named_department_that_bills_the_standard_bed_stays_with_the_standard_bed_motor() -> None:
    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 12), primary_icd10="P22.0", department="NICU"
    )

    assert _detect([_line("510010", "667.08", quantity=3)], header=header) == []


# --- Pins for the survivors of the confirmation round (BU1, N13, N17, N19) --------------------------------


def test_a_zero_priced_standard_bed_line_still_covers_its_day() -> None:
    """A 0 TL line is a non-credit line: it covers its day (its money is the standard-bed motor's to net)."""
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 13))
    [opp] = _detect(
        [_line("510070", "440.98", line_id="K"), _line("510010", "0", quantity=2, line_id="S", procedure_date=date(2026, 7, 11))],
        header=header,
    )

    assert (opp["days"], opp["standard_bed_days"]) == (2, 2)


def test_the_icu_code_gate_stays_absolute_even_when_a_newborn_bed_is_billed() -> None:
    """Only the department gate and the standard-bed stand-down give way to a billed newborn bed; an ICU code never."""
    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 12), primary_icd10="P22.0", department="yenidoğan"
    )

    assert _detect([_line("510090", "0", line_id="I"), _line("510070", "1322.94", quantity=3, line_id="K")], header=header) == []


def test_billed_cot_days_cover_days_first_beside_standard_bed_lines() -> None:
    """Kot x4 billed in full beside two 0 TL standard-bed lines on a 4-day stay: the cot lines cover all 4 days, the
    510010 lines own none (the newborn priority counts Kot units as well as Kuvöz units)."""
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 13))
    [opp] = _detect(
        [_line("510081", "1245.20", quantity=4, line_id="T"), _line("510010", "0", quantity=2, line_id="S")], header=header
    )

    assert opp["days"] == 4 and "standard_bed_days" not in opp
    assert opp["bed_code"] == "510081" and opp["recoverable_uplift_try"] == 0.0


def test_newborn_lines_inside_a_mandated_window_do_not_take_days_from_the_standard_bed_lines() -> None:
    """12 days, mandated 610131 (window through 21 July): Kuvöz x8 dated 14 July pay the package, so they cover none
    of the 4 days after it, and three 510010 lines dated after the window keep their 3 days."""
    import dataclasses

    from src.bilun.domain.prose_rules.yenidogan_yatak import detect_yenidogan_yatak_opportunities
    from tests.unit.domain.billing.test_showcase_session_and_package_gaps import GENCER, _Bill, _d

    start = _d("2026-07-14")
    bill = _Bill("C-SH01", "yatis", start, _d("2026-07-25"), package_candidate=True)
    bill.proc("610131", start, specialty=GENCER)
    bill.proc("510070", start, qty=8, specialty=GENCER)
    for offset in range(3):
        bill.proc("510010", _d("2026-07-22") + (_d("2026-07-23") - _d("2026-07-22")) * offset, qty=1, specialty=GENCER)
    ctx = bill.ctx()
    claim = dataclasses.replace(ctx.claims[0], department="yenidoğan")

    [opp] = detect_yenidogan_yatak_opportunities(
        [claim], [], procedure_lines=list(ctx.procedure_lines), claim_ids_with_procs={claim.claim_id}
    )

    assert (opp["days"], opp["bundled_days"], opp["standard_bed_days"]) == (1, 8, 3)


# --- SUT §2.2.2.(3): a stay under 24 hours is billed at the day bed 510120 -------------------------------
# A stay whose admission date equals its discharge date is certainly under 24 hours (the claim has dates, no
# times). The day bed (74.96 puan = 44.45 TRY on the 2026-07-07 list) is the bed of such a stay whoever the patient
# is, so the newborn motor prices its one day at 510120, not as a Kuvöz (440.98) or Kot (311.30) day.


def _one_date_header(**kwargs):
    return _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 10), **kwargs)


@pytest.mark.parametrize(
    ("lines", "actual", "recoverable"),
    [
        ([], 0.0, 44.45),
        ([("520010", "10")], 0.0, 44.45),
        ([("510070", "440.98")], 440.98, 0.0),  # an incubator billed for a stay under 24 hours: above the day bed
        ([("510081", "311.30")], 311.30, 0.0),
        ([("510070", "20.00")], 20.0, 24.45),
        ([("510081", "20.00")], 20.0, 24.45),
        ([("510070", "-100.00")], -100.0, 44.45),  # a credit line: capped at the charge
        ([("510070", "440.98"), ("510120", "44.45")], 440.98, 0.0),  # a day-bed line beside a newborn line: not counted here
    ],
    ids=["nothing", "unrelated", "kuvoz-in-full", "kot-in-full", "kuvoz-in-part", "kot-in-part", "credit", "kuvoz-and-day-bed"],
)
def test_a_stay_of_one_date_is_priced_at_the_day_bed_and_nets_the_newborn_bed_lines(lines, actual, recoverable) -> None:
    [opp] = _detect([_line(code, billed) for code, billed in lines], header=_one_date_header())

    assert (opp["days"], opp["bed_code"], opp["same_day_stay"]) == (1, "510120", True)
    assert opp["expected_try"] == pytest.approx(44.45, abs=0.005)
    assert opp["actual_billed_try"] == pytest.approx(actual, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(recoverable, abs=0.005)
    assert "standard_bed_days" not in opp
    for gone in ("Kot rate", "mutually exclusive", "is assumed"):
        assert gone not in opp["detail"]


def test_a_stay_of_one_date_billed_as_the_day_bed_stands_down() -> None:
    """The claim has stated its bed, the day bed: the standard-bed motor owns the day and nets the line (review F5:
    a correctly billed 510120 still showed a full Kuvöz row)."""
    header = _one_date_header()

    assert _detect([_line("520010", "10"), _line("510120", "20.00", line_id="D")], header=header) == []
    for code in ("510120", " 510.120 ", "P510120", "510 120"):  # read like the 510010 stand-down reads its code
        assert _detect([_line(code, "44.45")], header=header) == []


def test_a_day_bed_line_on_a_stay_of_two_dates_is_no_stated_bed() -> None:
    """Control: on 10-11 July a 510120 line pays no bed day; the stay stays a newborn bed stay (the Kuvöz default)."""
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 11))
    [opp] = _detect([_line("510120", "44.45")], header=header)

    assert (opp["days"], opp["bed_code"], opp["same_day_stay"]) == (2, "510070", False)
    assert opp["actual_billed_try"] == 0.0
    assert opp["expected_try"] == pytest.approx(881.96, abs=0.005)
    assert "Gündüz" not in opp["detail"]
    assert "is assumed" in opp["detail"] and "mutually exclusive" in opp["detail"]


def test_the_only_day_of_a_stay_of_one_date_can_be_bundled_in_a_package() -> None:
    [opp] = _detect([_package("P600330", date(2026, 7, 10))], header=_one_date_header())

    assert (opp["days"], opp["bundled_days"], opp["expected_try"], opp["recoverable_uplift_try"]) == (0, 1, 0.0, 0.0)
    assert opp["bed_code"] == "510120"
    assert opp["same_day_stay"] is False  # no day is left, so no day-bed stay to note
    assert "Same-day" not in opp["detail"]


def test_the_icu_last_day_of_another_claim_takes_the_only_day_of_a_stay_of_one_date() -> None:
    [opp] = _detect([_line("520010", "10")], header=_one_date_header(), icu_last_days={date(2026, 7, 10)})

    assert (opp["days"], opp["expected_try"], opp["icu_overlap_days"], opp["bed_code"]) == (0, 0.0, 1, "510120")
    assert opp["same_day_stay"] is False


def test_an_icu_stay_of_one_date_is_left_to_the_icu_motor() -> None:
    header = _one_date_header(primary_icd10="P22.0")

    assert _detect([_line("510090", "0")], header=header) == []
    assert _detect([_line("P552006", "0")], header=header) == []
    # And a unit named as an intensive care unit, with nothing billed.
    icu_named = _one_date_header(primary_icd10="P22.0", department="Yenidoğan Yoğun Bakım")
    assert _detect([_line("520010", "10")], header=icu_named) == []


def test_rooming_in_of_one_date_is_priced_at_the_day_bed_only_when_opted_in() -> None:
    header = _one_date_header()

    assert _detect([_line("520010", "10")], header=header, rooming_in_claim_ids={"C1"}) == []  # as before
    [opp] = _detect(
        [_line("520010", "10")], header=header, rooming_in_claim_ids={"C1"}, emit_kuvoz_for_rooming_in=True
    )
    assert (opp["rooming_in"], opp["bed_code"]) == (True, "510120")
    assert opp["expected_try"] == pytest.approx(44.45, abs=0.005)
    assert "Rooming-in" in opp["detail"] and "Kot (510081) is not billable" in opp["detail"]
    assert "Kuvöz (510070) billed per opt-in" not in opp["detail"]  # the bed is the day bed


def test_without_procedure_lines_a_stay_of_one_date_is_priced_at_the_day_bed() -> None:
    [opp] = _detect(None, header=_one_date_header())

    assert (opp["bed_code"], opp["actual_billed_try"]) == ("510120", 0.0)
    assert opp["recoverable_uplift_try"] == pytest.approx(44.45, abs=0.005)


def test_the_day_bed_price_is_the_one_of_the_admission_date_for_a_newborn_too() -> None:
    header = _make_claim_header(admission=date(2023, 6, 10), discharge=date(2023, 6, 10))
    [opp] = _detect([_line("520010", "10")], header=header)

    assert opp["puan"] == pytest.approx(27.77, abs=0.005)  # 510120 on the 2023 list
    assert opp["expected_try"] == pytest.approx(16.47, abs=0.005)


def test_a_stay_of_two_dates_keeps_the_kuvoz_default_and_its_sentences() -> None:
    """Control: the day bed is for a stay of one date only."""
    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 11))
    [opp] = _detect([_line("520010", "10")], header=header)

    assert (opp["days"], opp["bed_code"], opp["same_day_stay"]) == (2, "510070", False)
    assert opp["expected_try"] == pytest.approx(881.96, abs=0.005)
    assert "Gündüz" not in opp["detail"] and "Same-day" not in opp["detail"]
    assert "is assumed" in opp["detail"]


def test_a_missing_day_bed_price_skips_a_stay_of_one_date_whatever_the_kuvoz_price(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.bilun.domain.prose_rules import yenidogan_yatak

    real = yenidogan_yatak._daily_rate
    monkeypatch.setattr(
        yenidogan_yatak, "_daily_rate", lambda code, visit_date=None: 0.0 if code == "510120" else real(code, visit_date)
    )

    assert _detect([_line("520010", "10")], header=_one_date_header()) == []  # the Kuvöz price must not stand in
    assert len(_detect([_line("520010", "10")])) == 1  # a stay of three dates does not need the day bed


def test_the_kuvoz_and_cot_prices_are_not_needed_for_a_stay_of_one_date(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.bilun.domain.prose_rules import yenidogan_yatak

    real = yenidogan_yatak._daily_rate
    monkeypatch.setattr(
        yenidogan_yatak, "_daily_rate",
        lambda code, visit_date=None: 0.0 if code in ("510070", "510081") else real(code, visit_date),
    )

    [opp] = _detect([_line("520010", "10")], header=_one_date_header())
    assert (opp["bed_code"], opp["expected_try"]) == ("510120", pytest.approx(44.45, abs=0.005))

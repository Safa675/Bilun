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
        procedure_category="islem",
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


def test_a_standard_bed_line_is_not_a_newborn_bed_line() -> None:
    """510010 is the other motor's code: it neither nets nor prices the newborn charge."""
    [opp] = _detect([_line("510010", "667.08", quantity=3)])

    assert opp["actual_billed_try"] == 0.0
    assert opp["recoverable_uplift_try"] == pytest.approx(1322.94, abs=0.005)


# --- The bed type: a billed Kot is the hospital's own choice, never "upgraded" to Kuvöz --------------------


def test_a_billed_kot_is_priced_at_the_kot_rate_and_billed_in_full_leaves_nothing() -> None:
    [opp] = _detect([_line("510081", "933.90", quantity=3)])

    assert opp["bed_code"] == "510081"
    assert opp["rule_id"] == "yenidogan_yatak_510081"
    assert opp["puan"] == pytest.approx(524.95, abs=0.01)
    assert opp["expected_try"] == pytest.approx(933.90, abs=0.005)
    assert opp["recoverable_uplift_try"] == 0.0


def test_a_kot_billed_in_part_leaves_the_kot_remainder_not_the_kuvoz_difference() -> None:
    [opp] = _detect([_line("510081", "311.30")])

    assert opp["bed_code"] == "510081"
    assert opp["expected_try"] == pytest.approx(933.90, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(622.60, abs=0.005)


def test_a_claim_billing_both_codes_is_priced_at_kuvoz_and_nets_both() -> None:
    [opp] = _detect([_line("510070", "440.98", line_id="K"), _line("510081", "311.30", line_id="T")])

    assert opp["bed_code"] == "510070"
    assert opp["expected_try"] == pytest.approx(1322.94, abs=0.005)
    assert opp["actual_billed_try"] == pytest.approx(752.28, abs=0.005)
    assert opp["recoverable_uplift_try"] == pytest.approx(570.66, abs=0.005)


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
    """The two motors split the claims on the same test, so no claim is counted by both or by neither."""
    from src.bilun.domain.prose_rules.icu_puani import claim_has_icu_code

    assert claim_has_icu_code([_line("P552006", "0")]) is True
    assert claim_has_icu_code([_line("510090", "0")]) is True
    assert claim_has_icu_code([_line("510070", "0"), _line("520010", "0")]) is False
    assert claim_has_icu_code([]) is False

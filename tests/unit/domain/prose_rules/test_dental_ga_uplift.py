"""Unit tests for the dental general-anesthesia +%30 billing rule detector.

Covers SUT §2-04.1 Madde 4: when EK-2/Ç dental procedures are performed under
general anesthesia, the anesthesia fee is +%30 of the dental procedure total,
billed as an uplift — NOT as a separate 550xxx anesthesia procedure line.

Two violation classes are detected:

- **Double-billed anesthesia** (severity ``error``): a 550xxx line is billed
  alongside dental work under GA. The anesthesia line is mutually exclusive
  with the +30% uplift.
- **Missing uplift** (severity ``info``): GA was performed but neither the
  +30% uplift nor a separate anesthesia line is present (capture gap).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.prose_rules.dental_ga_uplift import (
    detect_dental_ga_uplift_violations,
)

pytestmark = pytest.mark.unit

# EK-2Ç dental codes confirmed present in the catalog (annex=EK-2Ç):
#   402010  Amalgam dolgu, bir yüzlü          puan = 632.98
#   402020  Amalgam dolgu, iki yüzlü          puan = 776.77
#   405010  Diş çekimi, infiltrasyon anestezi  puan = 489.024  (a DENTAL code,
#                                                        despite the name)
# 550130 is the surgical anesthesia A1 group code (annex=None, puan=8942.14).
_GA_RATE = 0.30


def _make_claim_header(
    *,
    claim_id: str = "C1",
    claim_type: str = "ayakta",
    admission: date | None = date(2026, 7, 10),
    discharge: date | None = date(2026, 7, 10),
) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        claim_type=claim_type,
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department="dis",
        admission_date=admission,
        discharge_date=discharge,
        claim_start_date=admission or date.today(),
        claim_end_date=discharge or date.today(),
        primary_icd10="K02.1",
        package_candidate=False,
        expected_total_billed_try=Decimal("1000"),
        expected_total_payable_try=Decimal("900"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _make_proc_line(
    *,
    procedure_line_id: str = "PL1",
    claim_id: str = "C1",
    procedure_code: str = "402010",
    procedure_category: str = "dental_treatment",
    billed_amount_try: Decimal = Decimal("1000"),
    procedure_date: date = date(2026, 7, 10),
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=procedure_line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        procedure_date=procedure_date,
        procedure_code=procedure_code,
        procedure_name="test procedure",
        procedure_category=procedure_category,
        quantity=1,
        unit_price_try=billed_amount_try,
        billed_amount_try=billed_amount_try,
        expected_payable_try=billed_amount_try,
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


# ── Violation type 1: double-billed anesthesia ───────────────────────────────


def test_double_billed_anesthesia_line_flagged() -> None:
    """Dental procedure + separate 550130 anesthesia line → double-bill error.

    The anesthesia line is mutually exclusive with the +%30 uplift. The
    expected GA fee is dental_total × 0.30 = 1000 × 0.30 = 300 TRY.
    """
    claim = _make_claim_header()
    dental = _make_proc_line(
        procedure_line_id="PL1",
        procedure_code="402010",
        billed_amount_try=Decimal("1000"),
    )
    anesthesia = _make_proc_line(
        procedure_line_id="PL2",
        procedure_code="550130",
        procedure_category="islem",
        billed_amount_try=Decimal("5300"),
    )

    violations = detect_dental_ga_uplift_violations([claim], [dental, anesthesia])

    assert len(violations) == 1
    v = violations[0]
    assert v["violation_kind"] == "double_billed_anesthesia"
    assert v["severity"] == "error"
    assert v["rule_id"] == "2-04.1.4_dental_ga_double_billed_anesthesia"
    assert v["sut_section_id"] == "2-04.1"
    assert v["ga_uplift_rate"] == _GA_RATE
    # 1000 × 0.30 = 300.00
    assert v["dental_total_try"] == pytest.approx(1000.0)
    assert v["expected_ga_fee_try"] == pytest.approx(300.0)
    assert v["anesthesia_procedure_codes"] == ["550130"]
    assert v["dental_procedure_codes"] == ["402010"]
    # The auditor-facing detail must reference the rule and the correct method.
    assert "%30" in v["detail"]
    assert "550130" in v["detail"]


def test_double_billed_sums_multiple_dental_lines() -> None:
    """Two dental lines + one anesthesia line → uplift = sum(dental) × 0.30."""
    claim = _make_claim_header()
    d1 = _make_proc_line(
        procedure_line_id="PL1", procedure_code="402010",
        billed_amount_try=Decimal("1000"),
    )
    d2 = _make_proc_line(
        procedure_line_id="PL2", procedure_code="402020",
        billed_amount_try=Decimal("1500"),
    )
    anes = _make_proc_line(
        procedure_line_id="PL3", procedure_code="550140",
        procedure_category="islem", billed_amount_try=Decimal("4000"),
    )

    violations = detect_dental_ga_uplift_violations([claim], [d1, d2, anes])

    assert len(violations) == 1
    v = violations[0]
    assert v["violation_kind"] == "double_billed_anesthesia"
    # (1000 + 1500) × 0.30 = 750
    assert v["dental_total_try"] == pytest.approx(2500.0)
    assert v["expected_ga_fee_try"] == pytest.approx(750.0)
    assert set(v["dental_procedure_codes"]) == {"402010", "402020"}


# ── Violation type 2: missing uplift ─────────────────────────────────────────


def test_missing_uplift_when_ga_marked_but_no_anesthesia_line() -> None:
    """Dental under GA (category marker), no anesthesia line, no uplift → info.

    The dental line carries a GA procedure_category marker (mirrors the
    ``procedure_under_ga_or_sedoanalgesia`` flag in the SUT encoding). No
    550xxx line and no uplift are billed → recoverable capture gap.
    """
    claim = _make_claim_header()
    dental = _make_proc_line(
        procedure_line_id="PL1",
        procedure_code="402010",
        procedure_category="dental_ga",  # GA signal via category marker
        billed_amount_try=Decimal("2000"),
    )

    violations = detect_dental_ga_uplift_violations([claim], [dental])

    assert len(violations) == 1
    v = violations[0]
    assert v["violation_kind"] == "missing_uplift"
    assert v["severity"] == "info"
    assert v["rule_id"] == "2-04.1.4_dental_ga_missing_uplift"
    assert v["sut_section_id"] == "2-04.1"
    # 2000 × 0.30 = 600
    assert v["dental_total_try"] == pytest.approx(2000.0)
    assert v["expected_ga_fee_try"] == pytest.approx(600.0)
    assert v["recoverable_uplift_try"] == pytest.approx(600.0)
    assert v["anesthesia_procedure_codes"] == []


def test_missing_uplift_recognises_sedoanalgesia_marker() -> None:
    """The GA marker set also covers sedo-analgesia (same billing method)."""
    claim = _make_claim_header()
    dental = _make_proc_line(
        procedure_line_id="PL1",
        procedure_code="402010",
        procedure_category="ga_sedoanalgesia",
        billed_amount_try=Decimal("500"),
    )

    violations = detect_dental_ga_uplift_violations([claim], [dental])

    assert len(violations) == 1
    assert violations[0]["violation_kind"] == "missing_uplift"
    assert violations[0]["expected_ga_fee_try"] == pytest.approx(150.0)


# ── No-violation cases ───────────────────────────────────────────────────────


def test_dental_without_ga_no_violation() -> None:
    """Dental procedure WITHOUT a GA signal → no violation (uplift N/A)."""
    claim = _make_claim_header()
    dental = _make_proc_line(
        procedure_line_id="PL1",
        procedure_code="402010",
        procedure_category="dental_treatment",  # no GA marker
        billed_amount_try=Decimal("1000"),
    )

    violations = detect_dental_ga_uplift_violations([claim], [dental])
    assert violations == []


def test_non_dental_plus_anesthesia_no_violation() -> None:
    """Surgical procedure + anesthesia line → not our rule.

    A non-dental surgical procedure under anesthesia is §2.4.4.A
    (``anestezi_puani``) territory, not the dental +%30 rule. 610130 is
    Appendektomi (EK-2B), so it is not dental and must be ignored here.
    """
    claim = _make_claim_header(claim_type="yatis")
    surgical = _make_proc_line(
        procedure_line_id="PL1",
        procedure_code="610130",  # Appendektomi — NOT dental
        procedure_category="islem",
        billed_amount_try=Decimal("3000"),
    )
    anesthesia = _make_proc_line(
        procedure_line_id="PL2",
        procedure_code="550130",
        procedure_category="islem",
        billed_amount_try=Decimal("5300"),
    )

    violations = detect_dental_ga_uplift_violations(
        [claim], [surgical, anesthesia]
    )
    assert violations == []


def test_outpatient_dental_still_checked() -> None:
    """Dental GA applies to outpatient (ayakta) dental work too.

    Dental treatment is overwhelmingly outpatient; the surgical-anesthesia
    motor gates on inpatient-only, but the dental +30% rule does NOT. A
    double-billed outpatient dental claim must still be flagged.
    """
    claim = _make_claim_header(claim_type="ayakta")  # outpatient
    assert claim.claim_type == "ayakta"
    dental = _make_proc_line(
        procedure_line_id="PL1",
        procedure_code="402010",
        billed_amount_try=Decimal("1000"),
    )
    anesthesia = _make_proc_line(
        procedure_line_id="PL2",
        procedure_code="550130",
        procedure_category="islem",
        billed_amount_try=Decimal("5300"),
    )

    violations = detect_dental_ga_uplift_violations([claim], [dental, anesthesia])

    assert len(violations) == 1
    assert violations[0]["violation_kind"] == "double_billed_anesthesia"
    assert violations[0]["expected_ga_fee_try"] == pytest.approx(300.0)


# ── Edge cases ───────────────────────────────────────────────────────────────


def test_dental_extraction_code_treated_as_dental_not_anesthesia() -> None:
    """405010 ('Diş çekimi, infiltrasyon anestezi ile') is dental, not anesthesia.

    Despite the word 'anestezi' in its name, 405010 is an EK-2Ç dental code.
    It must be classified as dental (the +30% base), never as a billed 550xxx
    anesthesia line. With a GA marker on another dental line and 405010 also
    present, the missing-uplift computation must include 405010's billed amount.
    """
    claim = _make_claim_header()
    extraction = _make_proc_line(
        procedure_line_id="PL1",
        procedure_code="405010",
        procedure_category="dental_ga",  # GA marker → triggers missing-uplift
        billed_amount_try=Decimal("500"),
    )
    filling = _make_proc_line(
        procedure_line_id="PL2",
        procedure_code="402010",
        procedure_category="dental_treatment",
        billed_amount_try=Decimal("500"),
    )

    violations = detect_dental_ga_uplift_violations([claim], [extraction, filling])

    assert len(violations) == 1
    v = violations[0]
    assert v["violation_kind"] == "missing_uplift"
    # (500 + 500) × 0.30 = 300
    assert v["dental_total_try"] == pytest.approx(1000.0)
    assert v["expected_ga_fee_try"] == pytest.approx(300.0)
    assert set(v["dental_procedure_codes"]) == {"405010", "402010"}


def test_claim_ids_with_procs_filter_respected() -> None:
    """The optional filter gates which claims are evaluated."""
    claim = _make_claim_header()
    dental = _make_proc_line(
        procedure_line_id="PL1",
        procedure_code="402010",
        billed_amount_try=Decimal("1000"),
    )
    anesthesia = _make_proc_line(
        procedure_line_id="PL2",
        procedure_code="550130",
        procedure_category="islem",
        billed_amount_try=Decimal("5300"),
    )

    # C1 not in the filter set → no violations emitted.
    violations = detect_dental_ga_uplift_violations(
        [claim], [dental, anesthesia], claim_ids_with_procs=set()
    )
    assert violations == []

    # C1 in the filter set → violation emitted.
    violations = detect_dental_ga_uplift_violations(
        [claim], [dental, anesthesia], claim_ids_with_procs={"C1"}
    )
    assert len(violations) == 1


def test_no_dental_lines_no_violation() -> None:
    """Claim with only anesthesia lines (no dental) → nothing to flag."""
    claim = _make_claim_header()
    anesthesia = _make_proc_line(
        procedure_line_id="PL1",
        procedure_code="550130",
        procedure_category="islem",
        billed_amount_try=Decimal("5300"),
    )

    violations = detect_dental_ga_uplift_violations([claim], [anesthesia])
    assert violations == []


def test_empty_inputs() -> None:
    """Empty claim / line lists → no violations, no crash."""
    assert detect_dental_ga_uplift_violations([], []) == []

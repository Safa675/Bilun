"""Unit tests for EMR vs claim procedure capture gap detector."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, PerformedProcedureLine, ProcedureClaimLine
from src.bilun.domain.prose_rules.procedure_capture_gap import detect_procedure_capture_gaps
from tests.unit._helpers.catalog_prices import list_price, list_text


def _claim(**overrides) -> ClaimHeader:
    base = {
        "claim_id": "F-DEMO-001",
        "patient_id": "P1",
        "episode_id": "E1",
        "claim_type": "gunubirlik",
        "facility_tier": "egitim_arastirma",
        "provider_type": "Universite",
        "department": "Gastro",
        "admission_date": date(2024, 6, 1),
        "discharge_date": date(2024, 6, 1),
        "claim_start_date": date(2024, 6, 1),
        "claim_end_date": date(2024, 6, 1),
        "primary_icd10": "K50.9",
        "package_candidate": False,
        "expected_total_billed_try": Decimal("1000.00"),
        "expected_total_payable_try": Decimal("900.00"),
        "expected_denial_reason": "",
        "scenario_tag": "sgk_procedure_capture_kolonoskopi",
    }
    base.update(overrides)
    return ClaimHeader(**base)


def _proc_line(**overrides) -> ProcedureClaimLine:
    base = {
        "procedure_line_id": "ISL-1",
        "claim_id": "F-DEMO-001",
        "patient_id": "P1",
        "episode_id": "E1",
        "procedure_date": date(2024, 6, 1),
        "procedure_code": "701450",
        "procedure_name": "Kolonoskopi",
        "procedure_category": "islem",
        "quantity": 1,
        "unit_price_try": Decimal("1200.00"),
        "billed_amount_try": Decimal("1200.00"),
        "expected_payable_try": Decimal("1080.00"),
        "is_package_included": False,
        "package_code": "",
        "surcharge_applicable": False,
        "copay_rate_applicable": True,
        "denial_reason_expected": "",
        "rule_trace_expected": "",
    }
    base.update(overrides)
    return ProcedureClaimLine(**base)


def _performed(**overrides) -> PerformedProcedureLine:
    base = {
        "performed_line_id": "EMR-1",
        "claim_id": "F-DEMO-001",
        "patient_id": "P1",
        "episode_id": "E1",
        "service_date": date(2024, 6, 1),
        "procedure_code": "701460",
        "procedure_name": "Polipektomi",
        "source": "emr",
    }
    base.update(overrides)
    return PerformedProcedureLine(**base)


class TestProcedureCaptureGap:
    def test_flags_performed_not_submitted(self) -> None:
        claim = _claim()
        procs = [_proc_line()]
        performed = [_performed()]

        rows = detect_procedure_capture_gaps(claim, performed, procs)
        assert len(rows) == 1
        assert rows[0]["procedure_code"] == "701460"
        assert rows[0]["included_in_sgk_total"] is False
        assert rows[0]["recoverable_gap_try"] > 0
        assert rows[0]["price_methodology"] in ("ek2b_list_price", "ek2c_package_price")

    def test_suppresses_when_claim_submitted(self) -> None:
        claim = _claim()
        procs = [
            _proc_line(),
            _proc_line(
                procedure_line_id="ISL-2",
                procedure_code="701460",
                procedure_name="Polipektomi",
                billed_amount_try=Decimal("400.00"),
            ),
        ]
        performed = [_performed()]

        rows = detect_procedure_capture_gaps(claim, performed, procs)
        assert rows == []

    def test_suppresses_zero_billed_line_still_counts_as_missing_for_capture(self) -> None:
        claim = _claim()
        procs = [
            _proc_line(),
            _proc_line(
                procedure_line_id="ISL-2",
                procedure_code="701460",
                billed_amount_try=Decimal("0.00"),
            ),
        ]
        performed = [_performed()]

        rows = detect_procedure_capture_gaps(claim, performed, procs)
        assert len(rows) == 1


# Clean showcase package bills (reports/synthetic-data/2026-10-15-showcase-proofs/
# stories.py): admission, operation day, discharge, and the paket lines billed at
# the EK-2C price in force on the operation day (S8's second operation at 25%), read from the curated catalog
# histories.
_PACKAGE_BILLS: dict[str, tuple[date, date, date, tuple[tuple[str, str], ...]]] = {
    "S1": (date(2026, 7, 14), date(2026, 7, 14), date(2026, 7, 16), (("P610131", list_text("P610131", "2026-07-14")),)),
    "S5": (date(2026, 9, 3), date(2026, 9, 4), date(2026, 9, 8), (("P612320", list_text("P612320", "2026-09-04")),)),
    "S8": (
        date(2026, 9, 15),
        date(2026, 9, 15),
        date(2026, 9, 16),
        (
            ("P609235", list_text("P609235", "2026-09-15")),
            ("P603840", str((Decimal(list_text("P603840", "2026-09-15")) * Decimal("0.25")).quantize(Decimal("0.01")))),
        ),
    ),
}


def _package_bill(
    story: str, *, line_date: date | None = None, unbilled: str = ""
) -> tuple[ClaimHeader, list[ProcedureClaimLine]]:
    """Showcase package bill; ``unbilled`` puts that package line at 0 TL."""
    admission, op_day, discharge, packages = _PACKAGE_BILLS[story]
    claim_id = f"C-{story}"
    claim = _claim(
        claim_id=claim_id,
        claim_type="yatis",
        admission_date=admission,
        discharge_date=discharge,
        claim_start_date=admission,
        claim_end_date=discharge,
        package_candidate=True,
        scenario_tag=f"showcase_{story}",
    )
    procs = []
    for i, (code, amount) in enumerate(packages, start=1):
        billed = Decimal("0.00") if code == unbilled else Decimal(amount)
        procs.append(
            _proc_line(
                procedure_line_id=f"{claim_id}-P{i:02d}",
                claim_id=claim_id,
                procedure_date=line_date or op_day,
                procedure_code=code,
                procedure_name=code,
                procedure_category="paket",
                unit_price_try=Decimal(amount),
                billed_amount_try=billed,
                expected_payable_try=billed,
            )
        )
    return claim, procs


def _or_log(claim: ClaimHeader, codes: list[str], on: date) -> list[PerformedProcedureLine]:
    return [
        _performed(
            performed_line_id=f"{claim.claim_id}-OR{i:02d}",
            claim_id=claim.claim_id,
            service_date=on,
            procedure_code=code,
            procedure_name=code,
            source="or",
        )
        for i, code in enumerate(codes, start=1)
    ]


class TestPackageLinesCountAsSubmitted:
    """#266: the operation a package bills is never a performed-not-submitted gap."""

    @pytest.mark.parametrize("strip_p", [False, True], ids=["package_code", "ek2b_code"])
    @pytest.mark.parametrize("story", sorted(_PACKAGE_BILLS))
    def test_or_log_of_package_codes_has_no_gap(self, story: str, strip_p: bool) -> None:
        claim, procs = _package_bill(story)
        codes = [
            line.procedure_code.removeprefix("P") if strip_p else line.procedure_code
            for line in procs
        ]
        performed = _or_log(claim, codes, procs[0].procedure_date)

        assert detect_procedure_capture_gaps(claim, performed, procs) == []

    def test_package_covers_its_operation_logged_on_another_day(self) -> None:
        # Package line dated on admission; the OR log dates the operation a day later.
        claim, procs = _package_bill("S5", line_date=date(2026, 9, 3))
        performed = _or_log(claim, ["P612320"], date(2026, 9, 4))

        assert detect_procedure_capture_gaps(claim, performed, procs) == []

    def test_unbilled_package_gap_is_priced_from_ek2c_not_ek2b(self) -> None:
        # P609235 sits on the claim at 0 TL: the gap is the package, not an EK-2B line.
        claim, procs = _package_bill("S8", unbilled="P609235")
        performed = _or_log(claim, ["609235", "603840"], date(2026, 9, 15))

        rows = detect_procedure_capture_gaps(claim, performed, procs)
        assert [(r["procedure_code"], r["price_methodology"]) for r in rows] == [
            ("609235", "ek2c_package_price")
        ]
        # EK-2C P609235 on 2026-09-15, not the EK-2B 609235 price.
        assert rows[0]["recoverable_gap_try"] == pytest.approx(list_price("P609235", "2026-09-15"), abs=0.005)
        assert list_price("609235", "2026-09-15") != list_price("P609235", "2026-09-15")


# Showcase S7 (stories.py s7): the ER lines its EMR/PACS log lists, at the EK-2B
# price in force on 2026-02-19. The faulty bill leaves out CT angiography R101450.
_S7_DAY = date(2026, 2, 19)
_S7_LINES = tuple((code, list_text(code, _S7_DAY)) for code in ("530100", "530080", "801720", "R101450"))


def _s7_bill(
    *, ct_billed: bool
) -> tuple[ClaimHeader, list[PerformedProcedureLine], list[ProcedureClaimLine]]:
    claim = _claim(
        claim_id="C-SH07",
        claim_type="acil",
        department="Acil Tip",
        admission_date=None,
        discharge_date=None,
        claim_start_date=_S7_DAY,
        claim_end_date=_S7_DAY,
        primary_icd10="R07.1",
        scenario_tag="showcase_S7",
    )
    procs = [
        _proc_line(
            procedure_line_id=f"C-SH07-{code}",
            claim_id="C-SH07",
            procedure_date=_S7_DAY,
            procedure_code=code,
            procedure_name=code,
            unit_price_try=Decimal(amount),
            billed_amount_try=Decimal(amount),
            expected_payable_try=Decimal(amount),
        )
        for code, amount in _S7_LINES
        if ct_billed or code != "R101450"
    ]
    performed = [
        _performed(
            performed_line_id=f"C-SH07-EMR-{code}",
            claim_id="C-SH07",
            service_date=_S7_DAY,
            procedure_code=code,
            procedure_name=code,
            source="pacs" if code == "R101450" else "emr",
        )
        for code, _ in _S7_LINES
    ]
    return claim, performed, procs


class TestShowcaseS7CaptureGap:
    def test_ct_in_pacs_log_but_not_on_bill_is_a_gap(self) -> None:
        claim, performed, procs = _s7_bill(ct_billed=False)

        rows = detect_procedure_capture_gaps(claim, performed, procs)
        assert [
            (r["type"], r["procedure_code"], r["source"], r["price_methodology"]) for r in rows
        ] == [("performed_not_submitted", "R101450", "pacs", "ek2b_list_price")]
        assert rows[0]["recoverable_gap_try"] == pytest.approx(list_price("R101450", _S7_DAY), abs=0.005)

    def test_clean_bill_has_no_gap(self) -> None:
        claim, performed, procs = _s7_bill(ct_billed=True)

        assert detect_procedure_capture_gaps(claim, performed, procs) == []

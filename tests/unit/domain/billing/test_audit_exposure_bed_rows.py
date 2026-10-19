"""The `audit_exposure` rows of a standard bed (510010) billed on a day a newborn bed (510070 / 510081) covers.

The detector (`prose_rules/yatak_newborn_overlap.py`, tests in `test_yatak_newborn_double_billing.py`) is re-run by
`recommend_audit_exposure_from_claims`, so the rows and `audit_exposure_try` come from the same function and cannot
drift from each other. The ICU sibling `detect_yatak_icu_overlap` reaches the patient report only as a hidden
Wave A financial review; this one is a visible Compliance-view row. Bills are built in memory.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from src.bilun.api.routes.billing import _serialize_billing_report
from src.bilun.cache.build_streaming import json_ready
from src.bilun.domain.billing import claim_audit_exposure
from src.bilun.domain.billing.billing_actions import collect_billing_actions
from src.bilun.domain.billing.claim_audit_exposure import (
    audit_exposure_rows,
    audit_exposure_total,
    compute_audit_exposure_from_claims,
    recommend_audit_exposure_from_claims,
    unbundling_findings_from_claims,
)
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.billing.report_totals import finalize_report_totals
from src.bilun.domain.billing.types import BillingActionReport
from src.bilun.domain.prose_rules.drg_unbundling import ClaimUnbundlingFinding
from src.bilun.domain.prose_rules.yatak_newborn_overlap import detect_yatak_newborn_overlap
from tests.unit.domain.prose_rules.test_yatak_newborn_double_billing import (
    _D,
    _TYPE,
    _bed,
    _context,
    _kot,
    _kuvoz,
    _std,
)

pytestmark = pytest.mark.unit

_NOT_EXEMPT = {"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []}
_CONTRACTS = Path(__file__).resolve().parents[4] / "src" / "bilun" / "api" / "public_contracts.json"


def _bed_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row["kind"] == _TYPE]


def _contract_row_keys() -> set[str]:
    def find(node: Any) -> Any:
        if isinstance(node, dict):
            if "audit_exposure_rows" in node:
                return node["audit_exposure_rows"]
            for value in node.values():
                if (found := find(value)) is not None:
                    return found
        return None

    section = find(json.loads(_CONTRACTS.read_text(encoding="utf-8")))
    assert section is not None
    return set(section["$list"])


class TestRowsAndTotal:
    def test_the_pair_is_one_row_and_its_money_is_the_total(self) -> None:
        ctx = _context("C1", lines=[_kuvoz(), _std()])

        review = recommend_audit_exposure_from_claims(ctx)

        [violation] = detect_yatak_newborn_overlap(list(ctx.procedure_lines))
        assert review.total_try == pytest.approx(222.36)
        assert review.rows == [
            {
                "kind": _TYPE,
                "claim_id": "C1",
                "procedure_line_id": "STD-1",
                "procedure_code": "510010",
                "procedure_name": "Standart yatak tarifesi",
                "risk_amount_try": 222.36,
                "sut_section": "2.2.2",
                "rule_id": "yatak_newborn_overlap_510010",
                "detail": violation["detail"],
            }
        ]

    def test_the_row_keeps_the_spelling_the_line_was_billed_with(self) -> None:
        review = recommend_audit_exposure_from_claims(_context("C1", lines=[_kuvoz(), _bed("510.010", _D, line_id="STD-P")]))

        [row] = review.rows
        assert row["procedure_code"] == "510.010"

    def test_a_kot_makes_the_same_row(self) -> None:
        review = recommend_audit_exposure_from_claims(_context("C1", lines=[_kot(), _std()]))

        [row] = review.rows
        assert row["kind"] == _TYPE and "510081" in row["detail"]
        assert review.total_try == pytest.approx(222.36)

    def test_a_bill_without_the_pair_is_exactly_the_unbundling_review(self) -> None:
        for lines in ([_kuvoz(), _std(_D + timedelta(days=1))], [_std()], [_kuvoz()], [_bed("510090", _D, line_id="I")]):
            ctx = _context("C1", lines=lines)
            findings = unbundling_findings_from_claims(ctx)

            review = recommend_audit_exposure_from_claims(ctx)

            assert review.rows == audit_exposure_rows(findings)
            assert review.total_try == audit_exposure_total(findings)

    def test_the_reversed_or_free_line_makes_no_row_and_no_money(self) -> None:
        for lines in ([_kuvoz(), _std(billed="-222.36")], [_kuvoz(), _std(billed="0")], [_kuvoz(billed="-1"), _std()]):
            ctx = _context("C1", lines=lines)

            review = recommend_audit_exposure_from_claims(ctx)

            assert _bed_rows(review.rows) == [], lines
            assert review.total_try == audit_exposure_total(unbundling_findings_from_claims(ctx)), lines

    def test_compute_audit_exposure_follows_the_review(self) -> None:
        ctx = _context("C1", lines=[_kuvoz(), _std()])
        assert compute_audit_exposure_from_claims(ctx) == recommend_audit_exposure_from_claims(ctx).total_try == 222.36

    def test_a_context_without_procedure_lines_is_silent(self) -> None:
        review = recommend_audit_exposure_from_claims(_context("C1", lines=[]))
        assert review.rows == [] and review.total_try == 0.0

    def test_several_lines_make_several_rows_with_distinct_ids_and_their_money_adds_up(self) -> None:
        lines = [
            _kuvoz(quantity=2, billed="881.96"),
            _std(line_id="S-A", billed="222.36"),
            _std(_D + timedelta(days=1), line_id="S-B", billed="200.00"),
            _std(_D + timedelta(days=4), line_id="S-C", billed="150.00"),
        ]

        review = recommend_audit_exposure_from_claims(_context("C1", lines=lines))

        assert [row["procedure_line_id"] for row in review.rows] == ["S-A", "S-B"]
        assert [row["risk_amount_try"] for row in review.rows] == [222.36, 200.0]
        assert review.total_try == pytest.approx(422.36)


class TestAddedToTheUnbundlingRows:
    """The unbundling findings come first, the bed rows after them; both add into one total."""

    @staticmethod
    def _finding(line_id: str, risk: float, bucket: str = "bundled_violations") -> ClaimUnbundlingFinding:
        entry = {
            "procedure_line_id": line_id,
            "procedure_code": "P600001",
            "procedure_name": "Package-included line",
            "risk_amount_try": risk,
            "detail": "HEURISTIC — package-included flag on claim line; not verified against SUT §2.2 prose.",
        }
        return ClaimUnbundlingFinding(claim_id="C1", chapter="Z", **{bucket: [entry]})

    def test_the_bed_rows_follow_the_unbundling_rows_and_both_are_in_the_total(self, monkeypatch) -> None:
        monkeypatch.setattr(
            claim_audit_exposure, "unbundling_findings_from_claims", lambda ctx: [self._finding("OTHER", 40.0)]
        )

        review = recommend_audit_exposure_from_claims(_context("C1", lines=[_kuvoz(), _std()]))

        assert [row["kind"] for row in review.rows] == ["bundled_line_flag", _TYPE]
        assert review.total_try == pytest.approx(40.0 + 222.36)

    @pytest.mark.parametrize(
        ("already", "bucket", "bed_row_risk"),
        [
            (0.0, "bundled_violations", 222.36),
            (60.0, "bundled_violations", 162.36),
            (222.36, "bundled_violations", None),
            (300.0, "bundled_violations", None),
            (100.0, "payment_method_violations", 122.36),  # money in the total with no row of its own
            (50.0, "session_violations", 172.36),
            (20.0, "blood_component_violations", 202.36),
        ],
    )
    def test_the_exposure_of_one_line_never_exceeds_what_it_billed(
        self, monkeypatch, already: float, bucket: str, bed_row_risk: float | None
    ) -> None:
        monkeypatch.setattr(
            claim_audit_exposure,
            "unbundling_findings_from_claims",
            lambda ctx: [self._finding("STD-1", already, bucket)] if already else [],
        )

        review = recommend_audit_exposure_from_claims(_context("C1", lines=[_kuvoz(), _std()]))

        bed = _bed_rows(review.rows)
        if bed_row_risk is None:
            assert bed == []
        else:
            [row] = bed
            assert row["risk_amount_try"] == pytest.approx(bed_row_risk)
        assert review.total_try == pytest.approx(min(max(already, 0.0) + 222.36, max(already, 222.36)))

    def test_several_unbundling_entries_on_the_line_add_up_before_the_cap(self, monkeypatch) -> None:
        finding = ClaimUnbundlingFinding(
            claim_id="C1",
            chapter="Z",
            bundled_violations=[{"procedure_line_id": "STD-1", "risk_amount_try": 30.0}],
            session_violations=[{"procedure_line_id": "STD-1", "risk_amount_try": 40.0}],
        )
        monkeypatch.setattr(claim_audit_exposure, "unbundling_findings_from_claims", lambda ctx: [finding])

        review = recommend_audit_exposure_from_claims(_context("C1", lines=[_kuvoz(), _std()]))

        assert _bed_rows(review.rows)[0]["risk_amount_try"] == pytest.approx(222.36 - 70.0)
        assert review.total_try == pytest.approx(222.36)

    def test_a_line_id_reused_by_another_claim_is_not_the_same_line(self, monkeypatch) -> None:
        """A line is identified by its (claim_id, line id) pair: the package-included L1 of C1 must not cap the
        L1 of C2, which is the one on the Kuvöz day (review F3). Both the patient and the bill report agree."""
        finding = ClaimUnbundlingFinding(
            claim_id="C1", chapter="Z", bundled_violations=[{"procedure_line_id": "L1", "risk_amount_try": 222.36}]
        )
        monkeypatch.setattr(claim_audit_exposure, "unbundling_findings_from_claims", lambda ctx: [finding])
        ctx = _context("C1", "C2", lines=[_kuvoz(claim_id="C2"), _std(claim_id="C2", line_id="L1")])

        review = recommend_audit_exposure_from_claims(ctx)

        [row] = _bed_rows(review.rows)
        assert (row["claim_id"], row["procedure_line_id"], row["risk_amount_try"]) == ("C2", "L1", 222.36)
        assert review.total_try == pytest.approx(222.36 + 222.36)
        bill = ctx.slice_for_claim("C2")
        assert bill is not None
        assert _bed_rows(recommend_audit_exposure_from_claims(bill).rows) == [row]

    def test_the_total_and_the_capped_row_are_whole_cents(self, monkeypatch) -> None:
        # 0.1 + 0.2 is 0.30000000000000004 as a float; 222.36 − 100.0 is 122.36000000000001
        monkeypatch.setattr(
            claim_audit_exposure, "unbundling_findings_from_claims", lambda ctx: [self._finding("OTHER", 0.1)]
        )
        review = recommend_audit_exposure_from_claims(_context("C1", lines=[_kuvoz(), _std(billed="0.20")]))
        assert review.total_try == 0.3

        monkeypatch.setattr(
            claim_audit_exposure, "unbundling_findings_from_claims", lambda ctx: [self._finding("STD-1", 100.0)]
        )
        review = recommend_audit_exposure_from_claims(_context("C1", lines=[_kuvoz(), _std()]))
        assert _bed_rows(review.rows)[0]["risk_amount_try"] == 122.36

    def test_another_lines_exposure_does_not_cap_this_line(self, monkeypatch) -> None:
        monkeypatch.setattr(
            claim_audit_exposure, "unbundling_findings_from_claims", lambda ctx: [self._finding("SOMEONE-ELSE", 999.0)]
        )

        review = recommend_audit_exposure_from_claims(_context("C1", lines=[_kuvoz(), _std()]))

        assert _bed_rows(review.rows)[0]["risk_amount_try"] == pytest.approx(222.36)
        assert review.total_try == pytest.approx(999.0 + 222.36)


class TestPatientAndBillScope:
    def _ctx(self):
        return _context("NICU", "WARD", lines=[_kuvoz(claim_id="NICU"), _std(claim_id="WARD")])

    def test_the_row_belongs_to_the_claim_of_the_standard_bed_line_in_every_scope(self) -> None:
        ctx = self._ctx()
        ward, nicu = ctx.slice_for_claim("WARD"), ctx.slice_for_claim("NICU")
        assert ward is not None and nicu is not None

        patient_rows = recommend_audit_exposure_from_claims(ctx).rows
        ward_rows = recommend_audit_exposure_from_claims(ward).rows
        nicu_review = recommend_audit_exposure_from_claims(nicu)

        assert [row["claim_id"] for row in patient_rows] == ["WARD"]
        assert ward_rows == patient_rows
        assert nicu_review.rows == [] and nicu_review.total_try == 0.0

    def test_the_patient_and_bill_reports_carry_the_same_row_and_money(self) -> None:
        ctx = self._ctx()
        ward = ctx.slice_for_claim("WARD")
        assert ward is not None

        patient = compute_patient_billing_report("P1", claim_context=ctx, copay_exemption=_NOT_EXEMPT)
        bill = compute_patient_billing_report("P1", claim_context=ward, copay_exemption=_NOT_EXEMPT)

        assert patient.audit_exposure_rows == bill.audit_exposure_rows
        assert _bed_rows(bill.audit_exposure_rows)[0]["claim_id"] == "WARD"
        assert patient.audit_exposure_try == bill.audit_exposure_try == pytest.approx(222.36)


class TestInTheReport:
    def _report(self, *lines) -> BillingActionReport:
        return compute_patient_billing_report(
            "P1", claim_context=_context("C1", lines=list(lines)), copay_exemption=_NOT_EXEMPT
        )

    def test_the_report_carries_the_row_the_total_and_one_compliance_action(self) -> None:
        report = self._report(_kuvoz(), _std())

        assert report.audit_exposure_try == pytest.approx(222.36)
        [row] = _bed_rows(report.audit_exposure_rows)
        [action] = [a for a in report.recommended_actions if a["surface"] == "audit_exposure"]
        assert action["kind"] == _TYPE
        assert action["finding_type"] == "compliance"
        assert action["action_id"] == f"audit_exposure:C1:{_TYPE}:STD-1"
        assert action["claim_id"] == "C1"
        assert action["procedure_code"] == "510010"
        assert action["procedure_name"] == "Standart yatak tarifesi"
        assert action["audit_risk_try"] == action["billed_try"] == pytest.approx(222.36)
        # Over-billing risk is never SGK revenue.
        assert action["sgk_uplift_try"] is None
        assert action["compliance_savings_try"] is None
        assert action["sut_section_id"] == "2.2.2"
        assert action["detail"] == row["detail"]

    def test_the_action_rows_come_from_collect_billing_actions_alone(self) -> None:
        report = self._report(_kuvoz(), _std())
        assert collect_billing_actions(report) == report.recommended_actions

    def test_a_bill_without_the_pair_has_no_such_row_or_action(self) -> None:
        report = self._report(_kuvoz(), _std(_D + timedelta(days=1)))

        assert _bed_rows(report.audit_exposure_rows) == []
        assert [a for a in report.recommended_actions if a["kind"] == _TYPE] == []

    def test_the_total_is_added_when_the_totals_are_finalized_without_a_review(self) -> None:
        ctx = _context("C1", lines=[_kuvoz(), _std()])
        report = BillingActionReport(patient_id="P1")

        finalize_report_totals(report, claim_context=ctx)

        assert report.audit_exposure_try == pytest.approx(222.36)

    def test_the_wire_shapes_carry_the_row_with_exactly_the_contract_keys(self) -> None:
        report = self._report(_kuvoz(), _std())
        contract_keys = _contract_row_keys()

        shapes = {
            "live": report.audit_exposure_rows,
            "cache": json.loads(json.dumps(json_ready(report), default=str))["audit_exposure_rows"],
            "api": json.loads(json.dumps(_serialize_billing_report(report), default=str))["audit_exposure_rows"],
        }
        for name, rows in shapes.items():
            [row] = _bed_rows(rows)
            assert set(row) == contract_keys, name
            assert row["risk_amount_try"] == pytest.approx(222.36), name

    def test_moving_the_standard_bed_off_the_pair_day_removes_exactly_its_money(self) -> None:
        with_pair = self._report(_kuvoz(), _std())
        without = self._report(_kuvoz(), _std(_D + timedelta(days=1)))

        assert without.audit_exposure_try == 0.0 and without.audit_exposure_rows == []
        assert with_pair.audit_exposure_try - without.audit_exposure_try == pytest.approx(222.36)

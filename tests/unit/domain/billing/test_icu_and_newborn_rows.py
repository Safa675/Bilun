"""Action rows for the ICU motor and the newborn bed motor.

`icu_puani` feeds `sgk_uplift_try` through `confirmed_icu_try` (the expected 510090 + P55200x charge minus
the ICU lines already billed). `yenidogan_yatak` feeds it through `confirmed_yenidogan_yatak_try` (the expected
Kuvöz / Kot charge minus the newborn bed lines already billed; it stands down on an ICU stay and shares no day
with the standard-bed motor, tasks/todo.md, "Newborn bed motor"). Rows of both must add up to their component:
a row exists only for money the headline counts. No showcase story exercises either motor, so the bills are
built in memory (amounts are read from the engine's own opportunity, never typed here).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from itertools import product
from typing import Any

import pytest

from src.bilun.api.routes.billing import _serialize_billing_report
from src.bilun.cache.build_streaming import json_ready
from src.bilun.domain.billing.billing_actions import collect_billing_actions
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.billing.recovery_summary import (
    patient_recovery_summary_entry,
    patient_recovery_summary_from_payload,
)
from src.bilun.domain.billing.types import (
    AnesteziPuaniReview,
    BillingActionReport,
    IcuPuaniReview,
    RefakatciReview,
    YenidoganYatakReview,
)
from src.bilun.domain.claims.models import ClaimDiagnosis
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.icu_puani import detect_icu_tier_overbilling
from tests.unit._helpers.catalog_prices import list_price, list_text
from tests.unit.domain.billing.test_blood_uplift_wiring import _claim, _proc

pytestmark = pytest.mark.unit

_NOT_EXEMPT = {"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []}
_CENT = Decimal("0.01")


def _try(value: object) -> Decimal:
    assert value is not None
    return Decimal(str(value)).quantize(_CENT)


def _sum_try(values: list[object]) -> Decimal:
    return sum((_try(value) for value in values), Decimal("0.00"))


def _rows(report: BillingActionReport, surface: str) -> list[dict[str, Any]]:
    return [row for row in report.recommended_actions if row["surface"] == surface]


def _icu_claim(claim_id: str = "CLM-ICU") -> Any:
    return _claim(
        claim_id=claim_id,
        department="yoğun bakım",
        primary_icd10="J96.0",
        admission_date=date(2026, 7, 10),
        discharge_date=date(2026, 7, 14),
        claim_start_date=date(2026, 7, 10),
        claim_end_date=date(2026, 7, 14),
    )


def _icu_lines(
    claim_id: str = "CLM-ICU", *, day_rate_billed: str = "100", package_billed: str = "500"
) -> list[Any]:
    """First and last ICU day (510090) around three days of the 3rd-level package (P552003)."""
    return [
        _proc(procedure_line_id=f"{claim_id}-D1", claim_id=claim_id, procedure_code="510090",
              procedure_name="Yoğun bakım", billed_amount_try=Decimal(day_rate_billed),
              procedure_date=date(2026, 7, 10)),
        _proc(procedure_line_id=f"{claim_id}-P3", claim_id=claim_id, procedure_code="P552003",
              procedure_name="Yoğun bakım 3. basamak", quantity=3, billed_amount_try=Decimal(package_billed),
              procedure_date=date(2026, 7, 11)),
        _proc(procedure_line_id=f"{claim_id}-D2", claim_id=claim_id, procedure_code="510090",
              procedure_name="Yoğun bakım", billed_amount_try=Decimal(day_rate_billed),
              procedure_date=date(2026, 7, 14)),
    ]


def _icu_report(*, day_rate_billed: str = "100", package_billed: str = "500") -> BillingActionReport:
    ctx = PatientClaimContext(
        patient_id="P1", claims=(_icu_claim(),), material_lines=(), drug_lines=(), diagnoses=(),
        procedure_lines=tuple(_icu_lines(day_rate_billed=day_rate_billed, package_billed=package_billed)),
    )
    return compute_patient_billing_report("P1", claim_context=ctx, copay_exemption=_NOT_EXEMPT)


class TestIcuRows:
    def test_a_partly_billed_stay_gets_one_revenue_row_with_the_unbilled_remainder(self) -> None:
        report = _icu_report()

        [opportunity] = report.icu_puani.opportunities
        [row] = _rows(report, "icu_puani")
        billed = _sum_try([100, 500, 100])
        assert _try(opportunity["actual_billed_try"]) == billed
        remainder = _try(opportunity["total_try"]) - billed
        assert remainder > 0

        assert row["finding_type"] == "opportunity"
        assert row["kind"] == opportunity["type"] == "icu_puani_yogun_bakim"
        assert row["claim_id"] == opportunity["claim_id"]
        assert row["sut_section_id"] == opportunity["sut_section_id"] == "2.4.4.H"
        assert _try(row["sgk_uplift_try"]) == _try(opportunity["recoverable_uplift_try"]) == remainder
        # Revenue money only: nothing is filed as a risk, a saving or a billed-at-risk amount, and the row
        # spans 510090 and P55200x lines, so it points at no single procedure.
        assert row["audit_risk_try"] is None
        assert row["compliance_savings_try"] is None
        assert row["billed_try"] is None
        assert row["procedure_code"] is None

        # The detail states the full expected charge; the row says what the billed lines leave of it.
        assert row["detail"].startswith(opportunity["detail"])
        assert f"{billed} TRY" in row["detail"]
        assert "unbilled remainder" in row["detail"]

        # The headline counts exactly the rows' money, and the ICU component is this row.
        assert _try(report.icu_puani.confirmed_icu_try) == remainder
        counted = [
            action["sgk_uplift_try"]
            for action in report.recommended_actions
            if action["sgk_uplift_try"] is not None
        ]
        assert _sum_try(counted) == _try(report.sgk_uplift_try)

    def test_a_stay_with_nothing_billed_keeps_the_engine_detail(self) -> None:
        report = _icu_report(day_rate_billed="0", package_billed="0")
        [opportunity] = report.icu_puani.opportunities
        [row] = _rows(report, "icu_puani")
        assert opportunity["actual_billed_try"] == 0
        assert _try(row["sgk_uplift_try"]) == _try(opportunity["total_try"])
        assert row["detail"] == opportunity["detail"]

    def test_an_opportunity_without_a_detail_gets_none_invented(self) -> None:
        opportunity = {
            "type": "icu_puani_yogun_bakim",
            "claim_id": "CLM-X",
            "recoverable_uplift_try": 50.0,
            "actual_billed_try": 10.0,
        }
        report = BillingActionReport(patient_id="P1", icu_puani=IcuPuaniReview(opportunities=[opportunity]))
        [row] = collect_billing_actions(report)
        assert row["detail"] is None
        assert _try(row["sgk_uplift_try"]) == _try(report.icu_puani.confirmed_icu_try)

    def test_a_stay_billed_in_full_makes_no_row(self) -> None:
        """The motor nets the billed ICU lines (#13); a stay that is billed in full has nothing to recover."""
        expected = _icu_report().icu_puani.opportunities[0]["total_try"]
        report = _icu_report(package_billed=str(Decimal(str(expected)) + 1))

        [opportunity] = report.icu_puani.opportunities
        assert opportunity["recoverable_uplift_try"] == 0.0
        assert report.icu_puani.confirmed_icu_try == 0.0
        assert _rows(report, "icu_puani") == []

    def test_two_icu_claims_get_two_rows_that_add_up_to_the_component(self) -> None:
        claims = (_icu_claim("CLM-ICU-A"), _icu_claim("CLM-ICU-B"))
        lines = _icu_lines("CLM-ICU-A") + _icu_lines("CLM-ICU-B", package_billed="900")
        ctx = PatientClaimContext(
            patient_id="P1", claims=claims, procedure_lines=tuple(lines), material_lines=(),
            drug_lines=(), diagnoses=(),
        )
        report = compute_patient_billing_report("P1", claim_context=ctx, copay_exemption=_NOT_EXEMPT)

        rows = _rows(report, "icu_puani")
        assert [row["claim_id"] for row in rows] == ["CLM-ICU-A", "CLM-ICU-B"]
        assert len({row["action_id"] for row in rows}) == 2
        assert _sum_try([row["sgk_uplift_try"] for row in rows]) == _try(report.icu_puani.confirmed_icu_try)
        assert _try(rows[0]["sgk_uplift_try"]) > _try(rows[1]["sgk_uplift_try"])  # B billed 400 TL more

    def test_the_tier_overbilling_review_is_not_an_uplift_row(self) -> None:
        """`detect_icu_tier_overbilling` (P552003 without a support line) is an audit review row with
        `included_in_sgk_total` False and no money; it must never become an uplift row."""
        claim, lines = _icu_claim(), _icu_lines()
        [tier] = detect_icu_tier_overbilling([claim], lines)
        assert tier["type"] == "icu_tier_overbilling"
        assert tier["included_in_sgk_total"] is False
        assert tier["at_risk_try"] == 0.0

        # In the pipeline the review goes to the claim-audit violations, not into the ICU block.
        report = _icu_report()
        assert {row["type"] for row in report.icu_puani.opportunities} == {"icu_puani_yogun_bakim"}

        # And if a review row ever lands in the block, it makes no row and does not move the sum.
        [opportunity] = report.icu_puani.opportunities
        mixed = BillingActionReport(
            patient_id="P1", icu_puani=IcuPuaniReview(opportunities=[tier, opportunity, tier])
        )
        [row] = [r for r in collect_billing_actions(mixed) if r["surface"] == "icu_puani"]
        assert row["action_id"] == "icu_puani:CLM-ICU:1"  # the position in the block, not renumbered
        assert _try(row["sgk_uplift_try"]) == _try(mixed.icu_puani.confirmed_icu_try)
        review_only = BillingActionReport(patient_id="P1", icu_puani=IcuPuaniReview(opportunities=[tier]))
        assert collect_billing_actions(review_only) == []


_MISSING = object()
# surface -> (block, the field its component reads without `recoverable_uplift_try`, the other puan field, the component)
_COUNTED_BLOCKS = {
    "icu_puani": (IcuPuaniReview, "total_try", "expected_try", "confirmed_icu_try"),
    "anestezi_puani": (AnesteziPuaniReview, "expected_try", "total_try", "confirmed_anestezi_try"),
    "refakatci": (RefakatciReview, "expected_try", "total_try", "confirmed_refakat_try"),
    "yenidogan_yatak": (YenidoganYatakReview, "expected_try", "total_try", "confirmed_yenidogan_yatak_try"),
}


def _opportunity(recoverable: object, fallback: object, included: object, fallback_field: str, other_field: str):
    row: dict[str, Any] = {"type": "x", "claim_id": "CLM-X", other_field: 77.7}  # the field it must NOT read
    for key, value in (("recoverable_uplift_try", recoverable), (fallback_field, fallback),
                       ("included_in_sgk_total", included)):
        if value is not _MISSING:
            row[key] = value
    return row


@pytest.mark.parametrize("surface", sorted(_COUNTED_BLOCKS))
def test_rows_add_up_to_the_blocks_component_for_every_field_combination(surface: str) -> None:
    block_type, fallback_field, other_field, component = _COUNTED_BLOCKS[surface]
    # `included_in_sgk_total` is read by truthiness in the components (`row.get(..., True)`): None and 0 leave
    # the headline, 1 stays in; the rows must follow.
    combinations = list(
        product(
            [_MISSING, None, 0.0, 125.5],
            [_MISSING, 0.0, 300.0],
            [_MISSING, True, False, None, 0, 1],
        )
    )
    every_row = []
    for recoverable, fallback, included in combinations:
        row = _opportunity(recoverable, fallback, included, fallback_field, other_field)
        every_row.append(row)
        report = BillingActionReport(patient_id="P1", **{surface: block_type(opportunities=[row])})
        rows = [r for r in collect_billing_actions(report) if r["surface"] == surface]
        assert _sum_try([r["sgk_uplift_try"] for r in rows]) == _try(getattr(getattr(report, surface), component)), (
            recoverable, fallback, included,
        )
        assert len(rows) <= 1
    # All of them in one block: no cross-talk between opportunities.
    report = BillingActionReport(patient_id="P1", **{surface: block_type(opportunities=every_row)})
    rows = [r for r in collect_billing_actions(report) if r["surface"] == surface]
    assert rows, "the combinations include counted money"
    assert _sum_try([r["sgk_uplift_try"] for r in rows]) == _try(getattr(getattr(report, surface), component))


def _newborn_context(
    *,
    bed_billed: str | None = None,
    bed_code: str = "510070",
    quantity: int = 3,
    days: int = 3,
    department: str = "yenidoğan",
    icd10: str = "Z38.0",
    icu_codes: tuple[str, ...] = (),
    icu_billed: str = "0",
) -> PatientClaimContext:
    start = date(2026, 7, 10)
    end = start + timedelta(days=days - 1)
    claim = _claim(
        claim_id="CLM-NB", department=department, primary_icd10=icd10,
        admission_date=start, discharge_date=end, claim_start_date=start, claim_end_date=end,
    )
    lines = [_proc(procedure_line_id="NB-EXAM", claim_id="CLM-NB", procedure_code="520010",
                   procedure_name="Muayene", billed_amount_try=Decimal("10"), procedure_date=start)]
    if bed_billed is not None:
        lines.append(_proc(procedure_line_id="NB-BED", claim_id="CLM-NB", procedure_code=bed_code,
                           procedure_name="bed", quantity=quantity, billed_amount_try=Decimal(bed_billed),
                           procedure_date=start))
    for index, code in enumerate(icu_codes):
        lines.append(_proc(procedure_line_id=f"NB-ICU{index}", claim_id="CLM-NB", procedure_code=code,
                           procedure_name="Yoğun bakım", billed_amount_try=Decimal(icu_billed),
                           procedure_date=start + timedelta(days=min(index, days - 1))))
    diagnosis = ClaimDiagnosis(
        diagnosis_id="DX1", claim_id="CLM-NB", patient_id="P1", episode_id="E1", icd10_code=icd10,
        is_primary=True, diagnosis_role="primary", diagnosis_date=start, exemption_eligible=False,
    )
    return PatientClaimContext(
        patient_id="P1", claims=(claim,), procedure_lines=tuple(lines), material_lines=(),
        drug_lines=(), diagnoses=(diagnosis,),
    )


def _newborn_report(**kwargs: Any) -> BillingActionReport:
    return compute_patient_billing_report(
        "P1", claim_context=_newborn_context(**kwargs), copay_exemption=_NOT_EXEMPT
    )


def _newborn_icu_report(*, icu_billed: str = "0") -> BillingActionReport:
    """The reviewer's bill: yenidoğan yoğun bakım, P22.0, 510090 + P552006, 4 inclusive days."""
    return _newborn_report(
        days=4, department="Yenidoğan Yoğun Bakım", icd10="P22.0", icu_codes=("510090", "P552006"),
        icu_billed=icu_billed,
    )


def _counted(report: BillingActionReport) -> Decimal:
    return _sum_try([a["sgk_uplift_try"] for a in report.recommended_actions if a["sgk_uplift_try"] is not None])


class TestNewbornBedRows:
    def test_an_unbilled_newborn_stay_gets_one_revenue_row_with_the_full_charge(self) -> None:
        report = _newborn_report()

        [opportunity] = report.yenidogan_yatak.opportunities
        [row] = _rows(report, "yenidogan_yatak")
        assert opportunity["days"] == 3
        assert opportunity["actual_billed_try"] == 0
        assert _try(report.yenidogan_yatak.confirmed_yenidogan_yatak_try) == _try(opportunity["expected_try"]) > 0

        assert row["finding_type"] == "opportunity"
        assert row["kind"] == opportunity["type"] == "yenidogan_yatak"
        assert row["claim_id"] == opportunity["claim_id"] == "CLM-NB"
        assert row["sut_section_id"] == opportunity["sut_section_id"] == "2.2.2"
        assert _try(row["sgk_uplift_try"]) == _try(opportunity["recoverable_uplift_try"]) == _try(opportunity["expected_try"])
        # Revenue money only; the row names no single procedure line (the bed line is what is missing).
        assert row["audit_risk_try"] is None
        assert row["compliance_savings_try"] is None
        assert row["billed_try"] is None
        assert row["procedure_code"] is None
        # Nothing is billed, so the row says what it assumes instead of the billed sentence.
        assert row["detail"] == opportunity["detail"]
        assert "Kuvöz (510070) is assumed" in row["detail"]

    def test_a_partly_billed_stay_gets_a_row_with_the_unbilled_remainder(self) -> None:
        report = _newborn_report(bed_billed="440.98", quantity=1)

        [opportunity] = report.yenidogan_yatak.opportunities
        [row] = _rows(report, "yenidogan_yatak")
        remainder = _try(opportunity["expected_try"]) - Decimal("440.98")
        assert _try(opportunity["actual_billed_try"]) == Decimal("440.98")
        assert remainder > 0
        assert _try(row["sgk_uplift_try"]) == _try(opportunity["recoverable_uplift_try"]) == remainder
        assert _try(report.yenidogan_yatak.confirmed_yenidogan_yatak_try) == remainder
        # The detail states the full expected charge; the row says what the billed lines leave of it.
        assert row["detail"].startswith(opportunity["detail"])
        assert "Already billed on newborn bed lines (510070 / 510081): 440.98 TRY" in row["detail"]
        assert "unbilled remainder" in row["detail"]
        assert "is assumed" not in row["detail"]

    def test_a_newborn_bed_billed_in_full_leaves_nothing_recoverable(self) -> None:
        """Was the strict xfail of the puan-motor work: the motor now nets the billed 510070 / 510081 lines."""
        expected = _newborn_report().yenidogan_yatak.opportunities[0]["expected_try"]
        report = _newborn_report(bed_billed=str(Decimal(str(expected))))

        [opportunity] = report.yenidogan_yatak.opportunities
        assert opportunity["recoverable_uplift_try"] == 0.0
        assert report.yenidogan_yatak.confirmed_yenidogan_yatak_try == 0.0
        assert _rows(report, "yenidogan_yatak") == []

    def test_a_credit_line_makes_a_row_of_the_charge_at_most(self) -> None:
        """Review F3: -100 TL billed on a 440.98 TL day used to make a row of 540.98."""
        report = _newborn_report(days=1, quantity=1, bed_billed="-100.00")

        [opportunity] = report.yenidogan_yatak.opportunities
        [row] = _rows(report, "yenidogan_yatak")
        assert _try(opportunity["recoverable_uplift_try"]) == _try(opportunity["expected_try"])
        assert _try(row["sgk_uplift_try"]) == _try(opportunity["expected_try"])
        assert _counted(report) == _try(report.sgk_uplift_try)

    def test_a_billed_kot_is_not_a_row_for_the_kuvoz_difference(self) -> None:
        report = _newborn_report(bed_billed=list_text("510081", "2026-07-10", 3), bed_code="510081")

        [opportunity] = report.yenidogan_yatak.opportunities
        assert opportunity["bed_code"] == "510081"
        assert report.yenidogan_yatak.confirmed_yenidogan_yatak_try == 0.0
        assert _rows(report, "yenidogan_yatak") == []

    @pytest.mark.parametrize("billed", [None, "440.98", "1322.94"])
    def test_the_rows_explain_the_whole_headline_of_a_newborn_bill(self, billed: str | None) -> None:
        """Before the fix the headline held the newborn block with no row (aggregate-only) and, on the same
        days, the standard-bed money too (2,138.22 against rows of 815.28)."""
        report = _newborn_report(bed_billed=billed, quantity=1 if billed == "440.98" else 3)

        assert _counted(report) == _try(report.sgk_uplift_try)

    def test_a_newborn_icu_stay_is_the_icu_motors_not_a_kuvoz_ward_stay(self) -> None:
        report = _newborn_icu_report(icu_billed="250")

        assert report.yenidogan_yatak.opportunities == []
        assert report.yenidogan_yatak.confirmed_yenidogan_yatak_try == 0.0
        assert _rows(report, "yenidogan_yatak") == []
        assert report.icu_puani.confirmed_icu_try > 0
        # The review's bill: 1,763.92 TL of Kuvöz on top of the ICU charge and a standard-bed day left the
        # rows 1,763.92 short of the headline. Now the rows are the headline.
        assert _counted(report) == _try(report.sgk_uplift_try)

    def test_the_top_action_of_a_newborn_bill_has_a_row_behind_it_on_every_path(self) -> None:
        report = _newborn_report()
        payloads = {
            "live": patient_recovery_summary_entry(report),
            "cache": patient_recovery_summary_from_payload(json.loads(json.dumps(json_ready(report), default=str))),
            "api": patient_recovery_summary_from_payload(
                json.loads(json.dumps(_serialize_billing_report(report), default=str))
            ),
        }

        assert {path: entry["top_action_type"] for path, entry in payloads.items()} == {
            "live": "yenidogan_yatak", "cache": "yenidogan_yatak", "api": "yenidogan_yatak",
        }
        [row] = _rows(report, "yenidogan_yatak")
        assert _try(row["sgk_uplift_try"]) == _try(report.yenidogan_yatak.confirmed_yenidogan_yatak_try)

    def test_the_public_projection_keeps_the_new_row_keys(self) -> None:
        """`actual_billed_try`, `bundled_days` and `newborn_overlap_days` exist only on newborn rows, which no
        showcase bill has: without this test a missing entry in public_contracts.json would fail nothing."""
        from src.bilun.api.public_responses import project_public_response

        kuvoz = list_price("510070", "2026-07-10")  # one of the three days billed at list
        report = _newborn_report(bed_billed=list_text("510070", "2026-07-10"), quantity=1)
        payload = json.loads(json.dumps(_serialize_billing_report(report), default=str))

        public = project_public_response(payload, "/api/billing-report/{patient_id}")

        [newborn] = public["yenidogan_yatak"]["opportunities"]
        assert newborn["actual_billed_try"] == pytest.approx(kuvoz, abs=0.005)
        assert newborn["bundled_days"] == 0
        assert newborn["days"] == 3
        [standard] = public["yatak_puani"]["opportunities"]
        assert standard["newborn_overlap_days"] == 3
        [row] = [a for a in public["recommended_actions"] if a["surface"] == "yenidogan_yatak"]
        assert row["sgk_uplift_try"] == pytest.approx(2 * kuvoz, abs=0.005)

        # Incubator, then a standard bed: `standard_bed_days` of the newborn row.
        from tests.unit.domain.billing.test_yatak_newborn_overlap import _report as _stay_report

        stay = _stay_report(
            newborn=True, days=10, bed_code="510070", bed_billed="881.96", bed_units=2,
            standard_bed_billed="1778.88", standard_bed_units=8, standard_bed_start_day=2,
        )
        payload = json.loads(json.dumps(_serialize_billing_report(stay), default=str))
        public = project_public_response(payload, "/api/billing-report/{patient_id}")
        [mixed] = public["yenidogan_yatak"]["opportunities"]
        assert mixed["standard_bed_days"] == 8 and mixed["days"] == 2

        # The ICU transfer day: the two overlap keys of the newborn row.
        from tests.unit.domain.billing.test_yatak_newborn_overlap import _transfer_context

        transfer = compute_patient_billing_report("P1", claim_context=_transfer_context(), copay_exemption=_NOT_EXEMPT)
        payload = json.loads(json.dumps(_serialize_billing_report(transfer), default=str))
        public = project_public_response(payload, "/api/billing-report/{patient_id}")
        [ward] = [o for o in public["yenidogan_yatak"]["opportunities"] if o["claim_id"] == "CLM-WARD"]
        assert ward["icu_overlap_days"] == 1
        assert ward["icu_overlap_dates"] == ["2026-07-10"]

    @pytest.mark.parametrize("days", [1, 2, 4])
    @pytest.mark.parametrize("bed_code", ["510070", "510081"])
    @pytest.mark.parametrize("share", [None, "0", "half", "full", "over", "credit"])
    def test_every_bill_of_the_grid_keeps_rows_equal_to_the_headline_and_the_top_action_backed(
        self, days: int, bed_code: str, share: str | None
    ) -> None:
        rate = Decimal(list_text(bed_code, "2026-07-10"))
        full = rate * days
        billed = {
            None: None, "0": "0", "half": str((full / 2).quantize(_CENT)), "full": str(full), "over": str(full + 50),
            "credit": "-25.00",
        }[share]
        report = _newborn_report(bed_billed=billed, bed_code=bed_code, quantity=days, days=days)

        assert _counted(report) == _try(report.sgk_uplift_try)
        top = patient_recovery_summary_entry(report)["top_action_type"]
        if top == "yenidogan_yatak":
            assert _rows(report, "yenidogan_yatak"), "the top action names a motor with no row behind it"
        rows = _rows(report, "yenidogan_yatak")
        component = _try(report.yenidogan_yatak.confirmed_yenidogan_yatak_try)
        assert _sum_try([r["sgk_uplift_try"] for r in rows]) == component
        if share in ("full", "over"):
            assert component == Decimal("0.00") and not rows
        for opportunity in report.yenidogan_yatak.opportunities:
            assert opportunity["recoverable_uplift_try"] <= opportunity["expected_try"]

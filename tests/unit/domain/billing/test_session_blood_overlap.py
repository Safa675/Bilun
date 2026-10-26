"""Blood lines and same-session operations each yield one recoverable gap.

#261: a blood component is never a §2.2.2.A(5)/B(3) session secondary. On the
operation date only its §2.2.2.B-1(e) package ceiling applies, through the blood
detector; operation secondaries keep their session gap independently.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from itertools import permutations

import pytest

from src.bilun.domain.billing.claim_blood_uplift import recommend_blood_uplift_from_claims
from src.bilun.domain.billing.claim_session_uplift import recommend_session_uplift_from_claims
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.blood_uplift import (
    detect_blood_component_underbilling_opportunities,
)
from src.bilun.domain.prose_rules.session_uplift import detect_session_underbilling_opportunities
from tests.unit._helpers.catalog_prices import list_text
from tests.unit.domain.billing.test_blood_uplift_wiring import _claim, _proc

pytestmark = pytest.mark.unit

_DAY = "2026-01-10"  # the date of `_proc`'s lines


def _cents(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding="ROUND_HALF_UP"))


# The list prices on _DAY (curated catalog histories) and what the SUT pays of them: a blood component's package
# share (C000694: 36 % for 705430, 20 % for 705441) and a share of the operation secondary 615995 (§2.2.2.B).
_PRIMARY = list_text("P610070", _DAY)
_PLASMA = Decimal(list_text("705430", _DAY))
_PLASMA_SHARE = _cents(_PLASMA * Decimal("0.36"))
_FFP_SHARE = _cents(Decimal(list_text("705441", _DAY)) * Decimal("0.20"))
_SECOND = Decimal(list_text("615995", _DAY))


def _of_second(factor: str) -> float:
    return _cents(_SECOND * Decimal(factor))


@pytest.fixture(autouse=True)
def stable_catalog(monkeypatch):
    from src.bilun.domain.prose_rules import session_pricing

    monkeypatch.setattr(
        session_pricing, "procedure_annex_membership",
        lambda code, **kwargs: (True, code == "610070"),
    )
    monkeypatch.setattr(
        session_pricing, "_procedure_point_score",
        lambda code, **kwargs: 100 if code == "610070" else 10,
    )


def _primary(**overrides):
    values = dict(
        procedure_line_id="operation", procedure_code="P610070", procedure_category="paket",
        procedure_specialty_code="surgery", unit_price_try=Decimal(_PRIMARY),
        expected_payable_try=Decimal(_PRIMARY), billed_amount_try=Decimal(_PRIMARY),
    )
    values.update(overrides)
    return _proc(**values)


def _blood(**overrides):
    values = dict(
        procedure_line_id="plasma", procedure_code="705430",
        procedure_specialty_code="surgery", unit_price_try=_PLASMA,
        expected_payable_try=_PLASMA, billed_amount_try=Decimal("200"),
    )
    values.update(overrides)
    return _proc(**values)


def _operation(**overrides):
    """An EK-2/B §6 secondary operation in the primary's session, at its list price.

    615995 is EK-2/B only. 610080 was used before, but its EK-2/C package makes
    it a must-package line at this tier, which has no hizmet başı session
    uplift (review item 9). Its EK-2/B list on 2026-01-10 is the session base,
    never the line's unit price (#300; was a unit price of 1,000).
    """
    values = dict(
        procedure_line_id="second-operation", procedure_code="615995",
        procedure_specialty_code="surgery", unit_price_try=_SECOND,
        expected_payable_try=_SECOND, billed_amount_try=Decimal("100"),
    )
    values.update(overrides)
    return _proc(**values)


def _context(lines, claims=None):
    return PatientClaimContext(
        patient_id="P1", claims=tuple(claims or [_claim(department="general_surgery")]),
        procedure_lines=tuple(lines), material_lines=(), drug_lines=(), diagnoses=(),
    )


def _blocks(lines, claims=None):
    ctx = _context(lines, claims)
    return recommend_session_uplift_from_claims(ctx), recommend_blood_uplift_from_claims(ctx)


@pytest.mark.parametrize("reverse", [False, True])
def test_original_plasma_gap_counts_once_in_direct_detectors_and_blocks(reverse):
    lines = [_primary(), _blood()]
    if reverse:
        lines.reverse()
    session = detect_session_underbilling_opportunities(lines, claim=_claim())
    blood = detect_blood_component_underbilling_opportunities(lines)
    # #261: the plasma line is not a session secondary (was 30 % = 340.41);
    # its 36 % package ceiling is the one gap, counted by the blood detector.
    assert session == []
    assert len(blood) == 1
    assert blood[0]["max_billable_try"] == _PLASMA_SHARE
    assert blood[0]["recoverable_uplift_try"] == round(_PLASMA_SHARE - 200, 2)
    session_block, blood_block = _blocks(lines)
    assert session_block.confirmed_uplift_try == 0
    assert blood_block.confirmed_uplift_try == round(_PLASMA_SHARE - 200, 2)


@pytest.mark.parametrize(
    "code,unit,payable,billed,expected",
    [
        # #336: the base is the EK-2/B list price on the date, never the line's unit price or payable (was 36 % of
        # payable 1000).
        ("705430", "1000", "1000", "310", f"{_PLASMA_SHARE - 310:.2f}"),  # 36 % of the list.
        ("705441", "1000", "1000", "600", None),  # Above the 20 % ceiling.
        ("705441", "1000", "1000", "100", f"{_FFP_SHARE - 100:.2f}"),
        ("705430", "2000", "1000", "100", f"{_PLASMA_SHARE - 100:.2f}"),  # The list, not the unit price, is the base.
        ("705430", "1000", "2000", "100", f"{_PLASMA_SHARE - 100:.2f}"),  # Nor the payable.
        ("705430", "1000", "1000", "295", f"{_PLASMA_SHARE - 295:.2f}"),
        ("705441", "1000", "1000", "503", None),  # Within the 2 % tolerance of the 20 % ceiling.
    ],
)
def test_blood_ceiling_alone_applies_on_the_operation_date(
    code, unit, payable, billed, expected,
):
    # #261: no session ceiling composes with the blood ceiling any more.
    line = _blood(
        procedure_code=code, unit_price_try=Decimal(unit),
        expected_payable_try=Decimal(payable), billed_amount_try=Decimal(billed),
    )
    session, blood = _blocks([_primary(billed_amount_try=Decimal("1000")), line])
    assert session.opportunities == []
    if expected is None:
        assert blood.opportunities == []
    else:
        assert blood.opportunities[0]["recoverable_uplift_try"] == float(expected)


def test_blood_gap_is_not_held_back_by_the_session_review_heuristic():
    # #261: the session chart-review heuristic (tiny secondary, large primary)
    # no longer applies to blood; the 20 % ceiling gap is confirmed money.
    session, blood = _blocks([
        _primary(), _blood(
            procedure_code="705441", unit_price_try=Decimal("1000"),
            expected_payable_try=Decimal("1000"), billed_amount_try=Decimal("50"),
        ),
    ])
    assert session.opportunities == []
    assert blood.opportunities[0]["max_billable_try"] == _FFP_SHARE  # 20 % of the list price (#336)
    assert blood.confirmed_uplift_try == round(_FFP_SHARE - 50, 2)


def test_partial_overlap_preserves_same_code_on_other_lines_dates_and_claims():
    overlap = _blood()
    next_day = _blood(procedure_line_id="next-day", procedure_date=date(2026, 1, 11))
    other_claim = _blood(claim_id="OTHER")  # Same code and line ID, different claim.
    claims = [_claim(), _claim(claim_id="OTHER")]
    for lines in permutations([_primary(), overlap, next_day, other_claim]):
        session, blood = _blocks([*lines, _primary(
            claim_id="OTHER", procedure_date=date(2026, 1, 12),
        )], claims)
        # #261: the same-date plasma is the blood detector's too (was session 140.41).
        assert session.confirmed_uplift_try == 0
        assert blood.confirmed_uplift_try == round(3 * (_PLASMA_SHARE - 200), 2)
        assert {(r["claim_id"], r["procedure_line_id"]) for r in blood.opportunities} == {
            ("CLM-BLOOD", "plasma"), ("CLM-BLOOD", "next-day"), ("OTHER", "plasma"),
        }


def test_two_same_code_blood_lines_keep_distinct_amounts():
    lines = [_primary(), _blood(), _blood(procedure_line_id="plasma-2", billed_amount_try=Decimal("250"))]
    for order in permutations(lines):
        session, blood = _blocks(order)
        # #261: both are blood-detector gaps against the 36 % share (were session 140.41 / 90.41).
        assert {r["procedure_line_id"]: r["recoverable_uplift_try"] for r in blood.opportunities} == {
            "plasma": round(_PLASMA_SHARE - 200, 2), "plasma-2": round(_PLASMA_SHARE - 250, 2),
        }
        assert session.opportunities == []


@pytest.mark.parametrize("reverse", [False, True])
def test_same_normalized_blood_codes_never_form_a_session(reverse):
    lines = [_blood(procedure_line_id="first", procedure_code="P705430"), _blood(procedure_line_id="second")]
    if reverse:
        lines.reverse()
    session, blood = _blocks([*lines, _primary(procedure_date=date(2026, 1, 12))])
    # #261: two blood lines on one date were a primary and a 30 % secondary.
    assert session.opportunities == []
    assert [r["procedure_line_id"] for r in blood.opportunities] == [
        line.procedure_line_id for line in lines
    ]
    assert blood.confirmed_uplift_try == round(2 * (_PLASMA_SHARE - 200), 2)


def test_zero_billed_and_package_included_lines_keep_existing_eligibility():
    session, blood = _blocks([
        _primary(), _blood(billed_amount_try=Decimal("0")),
        _blood(procedure_line_id="included", is_package_included=True),
    ])
    assert session.opportunities == []
    assert len(blood.opportunities) == 1
    assert blood.confirmed_uplift_try == _PLASMA_SHARE


def test_standalone_blood_line_in_actual_package_treatment():
    session, blood = _blocks([_blood(), _primary(procedure_date=date(2026, 1, 12))])
    assert session.opportunities == []
    assert blood.confirmed_uplift_try == round(_PLASMA_SHARE - 200, 2)


def test_quantity_and_fractional_cent_rounding_use_whole_line_bases():
    session, blood = _blocks([
        _primary(billed_amount_try=Decimal("1000")),
        _blood(quantity=2, unit_price_try=Decimal("500.025"),
               expected_payable_try=Decimal("1000.05"), billed_amount_try=Decimal("100")),
    ])
    # #261: not a 30 % session secondary. #336: 36 % of the list price times the
    # whole quantity, rounded once, whatever the line's payable says.
    assert session.opportunities == []
    assert blood.opportunities[0]["max_billable_try"] == _cents(2 * _PLASMA * Decimal("0.36"))
    assert blood.confirmed_uplift_try == round(_cents(2 * _PLASMA * Decimal("0.36")) - 100, 2)


def test_direct_detector_never_borrows_another_claims_session():
    lines = [_primary(claim_id="OTHER"), _blood()]
    assert detect_session_underbilling_opportunities(lines) == []
    blood = detect_blood_component_underbilling_opportunities(lines)
    assert blood == []  # The other claim is not package evidence for this blood line.


def test_blank_line_ids_do_not_collapse_distinct_occurrences():
    lines = [_blood(procedure_line_id=""), _blood(procedure_line_id="")]
    session, blood = _blocks([*lines, _primary(procedure_date=date(2026, 1, 12))])
    # #261: both occurrences are blood gaps (were one session row and one blood row).
    assert session.opportunities == []
    assert len(blood.opportunities) == 2
    assert blood.confirmed_uplift_try == round(2 * (_PLASMA_SHARE - 200), 2)


def test_operation_secondary_gap_remains_independent_of_blood():
    # #261: the secondary must be an EK-2/B §6 operation to form a session
    # (was placeholder 111111); P610070 (EK-2/C) + 615995 (EK-2/B) is §2.2.2.B.c, 30 %.
    lines = [_primary(billed_amount_try=Decimal("1000")), _blood(), _operation()]
    session, blood = _blocks(lines)
    assert [r["procedure_line_id"] for r in session.opportunities] == ["second-operation"]
    assert session.opportunities[0]["expected_billed_try"] == _of_second("0.30")  # 30 % of its list.
    assert session.confirmed_uplift_try == round(_of_second("0.30") - 100, 2)
    assert blood.confirmed_uplift_try == round(_PLASMA_SHARE - 200, 2)


def test_a_missing_payable_leaves_the_list_price_ceiling_unchanged():
    # #336: the ceiling never read the payable's billed fallback (200 x 36 % = 72).
    session, blood = _blocks([_primary(), _blood(expected_payable_try=Decimal("0"))])
    assert session.opportunities == []
    assert [r["recoverable_uplift_try"] for r in blood.opportunities] == [round(_PLASMA_SHARE - 200, 2)]


@pytest.mark.parametrize(
    "cross_specialty,same_incision,expected",
    [(True, True, _of_second("0.55")), (False, False, _of_second("0.50"))],  # §2.2.2.B.c/ç: 30 %+25 or 50 %.
)
def test_direct_detectors_share_nondefault_session_options(
    cross_specialty, same_incision, expected,
):
    # #261: the options act on an operation secondary; blood keeps its own ceiling.
    lines = [_primary(billed_amount_try=Decimal("1000")), _operation(), _blood()]
    options = {"cross_specialty": cross_specialty, "same_incision": same_incision}
    session = detect_session_underbilling_opportunities(lines, **options)
    blood = detect_blood_component_underbilling_opportunities(lines, **options)
    assert [r["procedure_line_id"] for r in session] == ["second-operation"]
    assert session[0]["expected_billed_try"] == expected
    assert session[0]["recoverable_uplift_try"] == round(expected - 100, 2)
    assert [r["recoverable_uplift_try"] for r in blood] == [round(_PLASMA_SHARE - 200, 2)]


def test_claim_context_reaches_both_detectors(monkeypatch):
    from src.bilun.domain.prose_rules import session_specialty

    seen = []

    def cross_specialty(lines, claim):
        seen.append(claim.claim_id if claim else None)
        return claim is not None and claim.department == "cross-specialty"

    # Both readings of a session read the branches here (cross_specialty_readings).
    monkeypatch.setattr(session_specialty, "detect_cross_specialty_session", cross_specialty)
    # #261: a session needs two operations; the blood line keeps its own gap.
    session, blood = _blocks(
        [_primary(billed_amount_try=Decimal("1000")), _operation(), _blood()],
        [_claim(department="cross-specialty")],
    )
    assert session.confirmed_uplift_try == round(_of_second("0.55") - 100, 2)  # 55 % of the list − 100.
    assert blood.confirmed_uplift_try == round(_PLASMA_SHARE - 200, 2)
    assert seen == ["CLM-BLOOD", "CLM-BLOOD"]


@pytest.mark.parametrize("review_only", [False, True])
def test_report_actions_serialization_and_cohort_receive_reconciled_rows(monkeypatch, review_only):
    from dataclasses import replace

    from src.bilun.api.routes.billing import _serialize_billing_report
    from src.bilun.api.public_responses import project_public_response
    from src.bilun.domain.billing import patient_report
    from src.bilun.domain.billing.cohort_summary import build_cohort_recovery_summary
    from src.bilun.domain.billing.recovery_summary import (
        patient_recovery_summary_entry, patient_recovery_summary_from_payload,
    )
    from src.bilun.domain.billing.report_totals import sum_sgk_uplift_try
    from src.bilun.domain.billing.types import BloodComponentUplift, SessionPricingUplift

    # #261: the session row comes from an operation secondary (was the plasma
    # line, composed with its blood ceiling); 30 % of its list
    # (#300: was 30 % of a unit price of 1,134.71, 340.41, billed 200). Billed at
    # 700 it is no chart-review case (5.6 % of the primary).
    lines = [_primary(), _operation(billed_amount_try=Decimal("700"))]
    expected_total = round(_of_second("0.30") - 700, 2)
    if review_only:
        lines[1] = _operation(billed_amount_try=Decimal("50"))
        expected_total = round(_of_second("0.30") - 50, 2)
    expected_confirmed = 0 if review_only else expected_total
    seen = []

    # Exercise the real report assembler and downstream detectors. Observe the
    # argument boundary to prove capped/review-only session rows arrive first.
    for name in ("recommend_drg_uplift_from_claims", "recommend_procedure_addon_uplift_from_claims"):
        original = getattr(patient_report, name)

        def checked(ctx, *, _name=name, _original=original, **kwargs):
            rows = kwargs["session_opportunities"]
            assert len(rows) == 1
            assert rows[0]["recoverable_uplift_try"] == expected_confirmed
            assert rows[0]["expected_billed_try"] == _of_second("0.30")
            seen.append(_name)
            return _original(ctx, **kwargs)

        monkeypatch.setattr(patient_report, name, checked)

    report = patient_report.compute_patient_billing_report(
        "P1", claim_context=_context(lines, [_claim(
            claim_type="ayakta", admission_date=None, discharge_date=None,
        )]), copay_exemption={"exempt": False},
    )
    assert len(seen) == 2
    assert report.session_uplift.confirmed_uplift_try == expected_confirmed
    assert report.session_uplift.total_uplift_try == expected_total
    assert report.blood_uplift.opportunities == []
    # Other independent report blocks remain real; attribute only these blocks.
    without_pair = replace(report, session_uplift=SessionPricingUplift(), blood_uplift=BloodComponentUplift())
    assert report.sgk_uplift_try - sum_sgk_uplift_try(without_pair) == pytest.approx(expected_confirmed)
    pair_actions = [a for a in report.recommended_actions if a["surface"] in {"session_uplift", "blood_uplift"}]
    assert len(pair_actions) == 1
    assert float(pair_actions[0]["sgk_uplift_try"] or 0) == expected_confirmed

    payload = _serialize_billing_report(report)
    assert payload["session_uplift"]["confirmed_uplift_try"] == expected_confirmed
    assert payload["session_uplift"]["total_uplift_try"] == expected_total
    assert payload["blood_uplift"]["opportunities"] == []
    raw_row = payload["session_uplift"]["opportunities"][0]
    raw_row["private_injected"] = {"domain_modules": ["private.py"]}
    for surface in ("get_billing_report", "get_bill_billing_report"):
        public = project_public_response(payload, surface)
        public_row = public["session_uplift"]["opportunities"][0]
        assert public_row["expected_billed_try"] == raw_row["expected_billed_try"]
        assert public_row["recoverable_uplift_try"] == expected_confirmed
        assert public_row["review_uplift_try"] == (expected_total if review_only else 0)
        assert "private_injected" not in public_row
    assert patient_recovery_summary_from_payload(payload) == patient_recovery_summary_entry(report)
    cohort = build_cohort_recovery_summary({"P1": report}, claim_dataset=None)
    assert cohort.total_session_uplift == expected_confirmed
    assert cohort.total_blood_uplift == 0
    assert cohort.total_sgk_uplift == report.sgk_uplift_try

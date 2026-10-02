"""A procedure's session and blood ceilings constrain one recoverable gap."""

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
from tests.unit.domain.billing.test_blood_uplift_wiring import _claim, _proc

pytestmark = pytest.mark.unit


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
        procedure_specialty_code="surgery", unit_price_try=Decimal("12562.36"),
        expected_payable_try=Decimal("12562.36"), billed_amount_try=Decimal("12562.36"),
    )
    values.update(overrides)
    return _proc(**values)


def _blood(**overrides):
    values = dict(
        procedure_line_id="plasma", procedure_code="705430",
        procedure_specialty_code="surgery", unit_price_try=Decimal("1134.71"),
        expected_payable_try=Decimal("1134.71"), billed_amount_try=Decimal("200"),
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
    assert len(session) == 1
    assert session[0]["expected_billed_try"] == 340.41
    assert session[0]["recoverable_uplift_try"] == 140.41
    assert blood == []
    session_block, blood_block = _blocks(lines)
    assert session_block.confirmed_uplift_try == 140.41
    assert blood_block.confirmed_uplift_try == 0


@pytest.mark.parametrize(
    "code,unit,payable,billed,expected",
    [
        ("705430", "1000", "1000", "310", None),  # No session gap, positive blood gap.
        ("705441", "1000", "1000", "250", None),  # No blood gap, positive session gap.
        ("705441", "1000", "1000", "100", "200"),  # 20% blood cap < 30% session.
        ("705430", "2000", "1000", "100", "360"),  # Different reference bases.
        ("705430", "1000", "2000", "100", "300"),
        ("705430", "1000", "1000", "295", None),  # Existing session tolerance.
        ("705441", "1000", "1000", "197", None),  # Tolerance at the composed cap.
    ],
)
def test_both_actual_monetary_ceilings_apply_even_without_two_positive_rows(
    code, unit, payable, billed, expected,
):
    line = _blood(
        procedure_code=code, unit_price_try=Decimal(unit),
        expected_payable_try=Decimal(payable), billed_amount_try=Decimal(billed),
    )
    session, blood = _blocks([_primary(billed_amount_try=Decimal("1000")), line])
    assert blood.opportunities == []
    if expected is None:
        assert session.opportunities == []
    else:
        row = session.opportunities[0]
        assert row["expected_billed_try"] == float(expected)
        assert row["recoverable_uplift_try"] == float(Decimal(expected) - Decimal(billed))


def test_blood_cap_does_not_promote_clinical_review_to_confirmed_money():
    # Original session gap250 is review-only; composed blood gap150 must stay so.
    session, blood = _blocks([
        _primary(), _blood(
            procedure_code="705441", unit_price_try=Decimal("1000"),
            expected_payable_try=Decimal("1000"), billed_amount_try=Decimal("50"),
        ),
    ])
    row = session.opportunities[0]
    assert row["expected_billed_try"] == 200
    assert row["review_uplift_try"] == 150
    assert row["recoverable_uplift_try"] == 0
    assert row["included_in_sgk_total"] is False
    assert row["review_kind"] == "needs_clinical_review"
    assert session.confirmed_uplift_try == blood.confirmed_uplift_try == 0
    assert blood.opportunities == []


def test_partial_overlap_preserves_same_code_on_other_lines_dates_and_claims():
    overlap = _blood()
    next_day = _blood(procedure_line_id="next-day", procedure_date=date(2026, 1, 11))
    other_claim = _blood(claim_id="OTHER")  # Same code and line ID, different claim.
    claims = [_claim(), _claim(claim_id="OTHER")]
    for lines in permutations([_primary(), overlap, next_day, other_claim]):
        session, blood = _blocks([*lines, _primary(
            claim_id="OTHER", procedure_date=date(2026, 1, 12),
        )], claims)
        assert session.confirmed_uplift_try == 140.41
        assert blood.confirmed_uplift_try == 417
        assert {(r["claim_id"], r["procedure_line_id"]) for r in blood.opportunities} == {
            ("CLM-BLOOD", "next-day"), ("OTHER", "plasma"),
        }


def test_two_same_code_secondaries_keep_distinct_amounts():
    lines = [_primary(), _blood(), _blood(procedure_line_id="plasma-2", billed_amount_try=Decimal("250"))]
    for order in permutations(lines):
        session, blood = _blocks(order)
        assert {r["procedure_line_id"]: r["recoverable_uplift_try"] for r in session.opportunities} == {
            "plasma": 140.41, "plasma-2": 90.41,
        }
        assert blood.opportunities == []


@pytest.mark.parametrize("reverse", [False, True])
def test_same_normalized_blood_code_preserves_primary_occurrence(reverse):
    lines = [_blood(procedure_line_id="first", procedure_code="P705430"), _blood(procedure_line_id="second")]
    if reverse:
        lines.reverse()
    session, blood = _blocks([*lines, _primary(procedure_date=date(2026, 1, 12))])
    assert [r["procedure_line_id"] for r in session.opportunities] == [lines[1].procedure_line_id]
    assert [r["procedure_line_id"] for r in blood.opportunities] == [lines[0].procedure_line_id]
    assert session.confirmed_uplift_try == 140.41
    assert blood.confirmed_uplift_try == 208.5


def test_zero_billed_and_package_included_lines_keep_existing_eligibility():
    session, blood = _blocks([
        _primary(), _blood(billed_amount_try=Decimal("0")),
        _blood(procedure_line_id="included", is_package_included=True),
    ])
    assert session.opportunities == []
    assert len(blood.opportunities) == 1
    assert blood.confirmed_uplift_try == 408.5


def test_standalone_blood_line_in_actual_package_treatment():
    session, blood = _blocks([_blood(), _primary(procedure_date=date(2026, 1, 12))])
    assert session.opportunities == []
    assert blood.confirmed_uplift_try == 208.5


def test_quantity_and_fractional_cent_rounding_use_whole_line_bases():
    session, blood = _blocks([
        _primary(billed_amount_try=Decimal("1000")),
        _blood(quantity=2, unit_price_try=Decimal("500.025"),
               expected_payable_try=Decimal("1000.05"), billed_amount_try=Decimal("100")),
    ])
    assert session.opportunities[0]["expected_billed_try"] == 300.02
    assert session.confirmed_uplift_try == 200.02
    assert blood.opportunities == []


def test_direct_detector_never_borrows_another_claims_session():
    lines = [_primary(claim_id="OTHER"), _blood()]
    assert detect_session_underbilling_opportunities(lines) == []
    blood = detect_blood_component_underbilling_opportunities(lines)
    assert blood == []  # The other claim is not package evidence for this blood line.


def test_blank_line_ids_do_not_collapse_distinct_occurrences():
    lines = [_blood(procedure_line_id=""), _blood(procedure_line_id="")]
    session, blood = _blocks([*lines, _primary(procedure_date=date(2026, 1, 12))])
    assert len(session.opportunities) == len(blood.opportunities) == 1
    assert session.confirmed_uplift_try == 140.41
    assert blood.confirmed_uplift_try == 208.5


def test_nonblood_secondary_gap_remains_independent():
    lines = [
        _primary(billed_amount_try=Decimal("1000")), _blood(),
        _blood(procedure_line_id="other-procedure", procedure_code="111111",
               unit_price_try=Decimal("1000"), billed_amount_try=Decimal("100")),
    ]
    session, blood = _blocks(lines)
    assert session.confirmed_uplift_try == 340.41
    assert len(session.opportunities) == 2
    assert blood.opportunities == []


def test_missing_positive_payable_preserves_blood_billed_fallback():
    session, blood = _blocks([_primary(), _blood(expected_payable_try=Decimal("0"))])
    assert session.opportunities == blood.opportunities == []


@pytest.mark.parametrize("cross_specialty,same_incision", [(True, True), (False, False)])
def test_direct_detectors_share_nondefault_session_options(cross_specialty, same_incision):
    lines = [_primary(billed_amount_try=Decimal("1000")), _blood()]
    options = {"cross_specialty": cross_specialty, "same_incision": same_incision}
    session = detect_session_underbilling_opportunities(lines, **options)
    blood = detect_blood_component_underbilling_opportunities(lines, **options)
    assert session[0]["expected_billed_try"] == 408.5
    assert session[0]["recoverable_uplift_try"] == 208.5
    assert blood == []


def test_claim_context_reaches_both_detectors(monkeypatch):
    from src.bilun.domain.prose_rules import session_uplift

    seen = []

    def cross_specialty(lines, claim):
        seen.append(claim.claim_id if claim else None)
        return claim is not None and claim.department == "cross-specialty"

    monkeypatch.setattr(session_uplift, "detect_cross_specialty_session", cross_specialty)
    session, blood = _blocks(
        [_primary(billed_amount_try=Decimal("1000")), _blood()],
        [_claim(department="cross-specialty")],
    )
    assert session.confirmed_uplift_try == 208.5
    assert blood.opportunities == []
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

    lines = [_primary(), _blood()]
    expected_total = 140.41
    if review_only:
        lines[1] = _blood(
            procedure_code="705441", unit_price_try=Decimal("1000"),
            expected_payable_try=Decimal("1000"), billed_amount_try=Decimal("50"),
        )
        expected_total = 150.0
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
            assert rows[0]["expected_billed_try"] == (200 if review_only else 340.41)
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
        assert public_row["session_expected_billed_try"] == raw_row["session_expected_billed_try"]
        assert public_row["blood_max_billable_try"] == raw_row["blood_max_billable_try"]
        assert public_row["expected_billed_try"] == raw_row["expected_billed_try"]
        assert public_row["recoverable_uplift_try"] == expected_confirmed
        assert public_row["review_uplift_try"] == (expected_total if review_only else 0)
        assert "private_injected" not in public_row
    assert patient_recovery_summary_from_payload(payload) == patient_recovery_summary_entry(report)
    cohort = build_cohort_recovery_summary({"P1": report}, claim_dataset=None)
    assert cohort.total_session_uplift == expected_confirmed
    assert cohort.total_blood_uplift == 0
    assert cohort.total_sgk_uplift == report.sgk_uplift_try

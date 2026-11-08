"""Source-backed radiation review candidates must not assert unverified excess."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.prose_rules.radiation_oncology import (
    detect_radiation_oncology_violations,
)

pytestmark = pytest.mark.unit


def _claim(**overrides) -> ClaimHeader:
    base = dict(
        claim_id="CLM1",
        patient_id="P1",
        episode_id="E1",
        claim_type="yatarak",
        facility_tier="3",
        provider_type="hospital",
        department="radyasyon onkolojisi",
        admission_date=date(2026, 7, 10),
        discharge_date=date(2026, 7, 12),
        claim_start_date=date(2026, 7, 10),
        claim_end_date=date(2026, 7, 12),
        primary_icd10="C50.9",
        expected_total_billed_try=Decimal("5000"),
        expected_total_payable_try=Decimal("4000"),
        expected_denial_reason="",
        scenario_tag="test",
    )
    base.update(overrides)
    return ClaimHeader(**base)


def _proc(**overrides) -> ProcedureClaimLine:
    base = dict(
        procedure_line_id="PL1",
        claim_id="CLM1",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 7, 10),
        procedure_code="800070",
        procedure_name="Basit eksternal radyoterapi tasarımı",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
        expected_payable_try=Decimal("800"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    base.update(overrides)
    return ProcedureClaimLine(**base)


# ---------------------------------------------------------------------------
# Required test cases
# ---------------------------------------------------------------------------


class TestRadiationOncology:
    def test_two_codes_same_family_same_claim_emits_violation(self) -> None:
        """Two external-RT design codes preserve the source-backed review evidence.

        800070 and 800110 are both in the external_rt_design family, which
        is course-scoped with cap=1. Billing both on one claim violates the
        once-per-course condition only if a shared course is established.
        """
        claim = _claim()
        lines = [
            _proc(
                procedure_line_id="PL1",
                procedure_code="800070",
                procedure_name="Basit eksternal radyoterapi tasarımı",
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="800110",
                procedure_name="IMRT eksternal radyoterapi tasarımı",
            ),
        ]

        violations = detect_radiation_oncology_violations([claim], lines)

        assert len(violations) == 2  # preserve both participants without pricing excess
        assert all(v["claim_id"] == "CLM1" for v in violations)
        assert all(v["family_key"] == "external_rt_design" for v in violations)
        assert all(v["rule_kind"] == "course_cap" for v in violations)
        assert {v["procedure_code"] for v in violations} == {"800070", "800110"}
        for v in violations:
            assert v["rule_id"] == "radiation_oncology.course_cap.external_rt_design"
            assert v["sut_section"] == "EK-2/B 8.1.2.A"
            assert v["type"] == "radiation_oncology"
            assert v["risk_amount_try"] is None

    def test_codes_from_different_families_no_violation(self) -> None:
        """One code each from two different families → no violation.

        800070 (external design) and 800120 (planning) are in different
        families, so this combination alone does not establish a conflict.
        """
        claim = _claim()
        lines = [
            _proc(
                procedure_line_id="PL1",
                procedure_code="800070",
                procedure_name="Basit eksternal radyoterapi tasarımı",
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="800120",
                procedure_name="Basit radyoterapi planlama",
            ),
        ]

        violations = detect_radiation_oncology_violations([claim], lines)
        assert violations == []

    def test_non_radiation_codes_no_violation(self) -> None:
        """Non-800xxx procedure codes → no violation."""
        claim = _claim()
        lines = [
            _proc(
                procedure_line_id="PL1",
                procedure_code="610070",  # not a radiation code
                procedure_name="Some other procedure",
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="530180",  # not a radiation code
                procedure_name="Another procedure",
            ),
        ]

        violations = detect_radiation_oncology_violations([claim], lines)
        assert violations == []

    def test_single_radiation_code_no_violation(self) -> None:
        """A single radiation code → no violation."""
        claim = _claim()
        lines = [
            _proc(
                procedure_line_id="PL1",
                procedure_code="800110",
                procedure_name="IMRT eksternal radyoterapi tasarımı",
            ),
        ]

        violations = detect_radiation_oncology_violations([claim], lines)
        assert violations == []


# ---------------------------------------------------------------------------
# Additional coverage for the same-day collapse + brachy families
# ---------------------------------------------------------------------------


class TestRadiationSameDayCollapse:
    def test_two_application_codes_same_day_emits_violation(self) -> None:
        """Two conventional RT application codes on one date require review.

        800330 and 800350 are both in the rt_application (same-day) family.
        The actual treatment-day records and payable code remain unverified.
        """
        claim = _claim()
        same_day = date(2026, 7, 11)
        lines = [
            _proc(
                procedure_line_id="PL1",
                procedure_code="800330",
                procedure_name="Basit eksternal radyoterapi uygulaması",
                procedure_date=same_day,
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="800350",
                procedure_name="Kompleks eksternal radyoterapi uygulaması",
                procedure_date=same_day,
            ),
        ]

        violations = detect_radiation_oncology_violations([claim], lines)

        assert len(violations) == 2
        assert all(v["rule_kind"] == "same_day_collapse" for v in violations)
        assert all(v["family_key"] == "rt_application" for v in violations)
        assert all(v["service_date"] == "2026-07-11" for v in violations)

    def test_application_codes_on_different_days_no_violation(self) -> None:
        """Different dated applications alone do not establish a daily conflict."""
        claim = _claim()
        lines = [
            _proc(
                procedure_line_id="PL1",
                procedure_code="800330",
                procedure_date=date(2026, 7, 10),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="800350",
                procedure_date=date(2026, 7, 11),
            ),
        ]

        violations = detect_radiation_oncology_violations([claim], lines)
        assert violations == []

    def test_brachytherapy_application_family_enforced(self) -> None:
        """Two brachytherapy application codes need session evidence.

        A common service date is not proof of a common treatment session.
        """
        claim = _claim()
        same_day = date(2026, 7, 11)
        lines = [
            _proc(
                procedure_line_id="PL1",
                procedure_code="800500",
                procedure_name="Basit intrakaviter brakiterapi uygulaması",
                procedure_date=same_day,
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="800550",
                procedure_name="Kompleks intertisiyel brakiterapi uygulaması",
                procedure_date=same_day,
            ),
        ]

        violations = detect_radiation_oncology_violations([claim], lines)
        assert len(violations) == 2
        assert all(v["family_key"] == "brachy_application" for v in violations)


class TestRadiationMultiClaim:
    def test_violations_isolated_per_claim(self) -> None:
        """Claim-local review evidence is not combined into an invented course."""
        claim_a = _claim(claim_id="CA")
        claim_b = _claim(claim_id="CB")
        lines = [
            _proc(
                procedure_line_id="A1",
                claim_id="CA",
                procedure_code="800070",
            ),
            _proc(
                procedure_line_id="A2",
                claim_id="CA",
                procedure_code="800090",
            ),
            _proc(
                procedure_line_id="B1",
                claim_id="CB",
                procedure_code="800120",
            ),
            # CB is clean (single planning code) — no violation.
        ]

        violations = detect_radiation_oncology_violations([claim_a, claim_b], lines)
        # Only claim CA has a candidate pair of alternative design codes.
        claim_ids = {v["claim_id"] for v in violations}
        assert claim_ids == {"CA"}

    def test_empty_inputs_return_empty(self) -> None:
        assert detect_radiation_oncology_violations([], []) == []
        assert detect_radiation_oncology_violations([_claim()], []) == []


@pytest.mark.parametrize(
    "codes",
    [("800170", "800180"), ("800235", "800260"), ("800270", "800280")],
)
def test_independent_source_items_do_not_inherit_a_family_exclusion(codes) -> None:
    # EK-2/B C3661/C3669 excludes only the complexity alternatives; C3675–78
    # gives individual device limits, not a single mutually exclusive group.
    lines = [_proc(procedure_line_id=f"L{i}", procedure_code=c) for i, c in enumerate(codes)]
    assert detect_radiation_oncology_violations([_claim()], lines) == []


@pytest.mark.parametrize("codes", [("800070", "800110"), ("800330", "800350")])
def test_participant_billing_is_not_confirmed_excess(codes) -> None:
    lines = [_proc(procedure_line_id=f"L{i}", procedure_code=c) for i, c in enumerate(codes)]
    rows = detect_radiation_oncology_violations([_claim()], lines)
    assert len(rows) == 2
    for row in rows:
        assert row["billed_amount_try"] == 1000
        assert row["risk_amount_try"] is None
        assert row["candidate_classification"] == "review_only"
        assert row["evaluation_status"] == "unavailable"
        assert row["severity"] == "info"
        assert row["missing_inputs"]
        assert row["source_ref"]["annex"] == "EK-2/B"
        assert row["source_ref"]["section"].startswith("8.1.")
        assert row["included_in_sgk_total"] is False


def test_quantity_two_cannot_be_assumed_to_mean_two_same_day_applications() -> None:
    rows = detect_radiation_oncology_violations(
        [_claim()],
        [_proc(procedure_code="800330", quantity=2, billed_amount_try=Decimal("2000"))],
    )
    assert len(rows) == 1
    assert rows[0]["risk_amount_try"] is None
    assert "application_dates" in rows[0]["missing_inputs"]
    assert rows[0]["review_basis"] == "application_date_allocation"


@pytest.mark.parametrize("code", ["800150", "800160"])
@pytest.mark.parametrize("quantity", [2, 3, 4])
def test_repeated_advanced_planning_requires_justification_not_a_cap_of_one(code, quantity) -> None:
    rows = detect_radiation_oncology_violations(
        [_claim()],
        [_proc(procedure_code=code, quantity=quantity)],
    )
    assert len(rows) == 1
    assert "planning_justification" in rows[0]["missing_inputs"]
    assert rows[0]["review_basis"] == "planning_justification"
    assert rows[0]["risk_amount_try"] is None
    assert "capped at 1" not in rows[0]["detail"]
    assert "up to three" in rows[0]["detail"]
    assert "treatment_course_id" in rows[0]["missing_inputs"]


@pytest.mark.parametrize("code", ["800210", "800220"])
def test_repeated_advanced_dose_calculation_requires_plan_count(code) -> None:
    rows = detect_radiation_oncology_violations(
        [_claim()],
        [_proc(procedure_code=code, quantity=2)],
    )
    assert len(rows) == 1
    assert "planning_count" in rows[0]["missing_inputs"]
    assert rows[0]["risk_amount_try"] is None


def test_different_advanced_planning_alternatives_remain_unconfirmed_course_review() -> None:
    # C3655 excludes a/b/c/d/e together; its justified-repeat exception does
    # not establish that two different advanced alternatives are payable.
    rows = detect_radiation_oncology_violations(
        [_claim()],
        [
            _proc(procedure_line_id=f"L{i}", procedure_code=c)
            for i, c in enumerate(("800150", "800160"))
        ],
    )
    assert len(rows) == 2
    assert all(r["source_ref"]["locator"] == "EK-2B!C3655" for r in rows)
    assert all(r["review_basis"] == "course_alternatives" for r in rows)
    assert all("treatment_course_id" in r["missing_inputs"] for r in rows)
    assert all(r["risk_amount_try"] is None for r in rows)


def test_basic_brachy_dose_is_independent_but_repetition_needs_course_evidence() -> None:
    # C3669 permits basic(a) plus one of b/c/d, but individually limits a–d.
    rows = detect_radiation_oncology_violations(
        [_claim()],
        [_proc(procedure_code="800235", quantity=2)],
    )
    assert len(rows) == 1
    assert rows[0]["source_ref"]["locator"] == "EK-2B!C3669"
    assert "treatment_course_id" in rows[0]["missing_inputs"]
    assert rows[0]["risk_amount_try"] is None


def test_same_day_external_applications_share_a_limit_across_catalog_families() -> None:
    rows = detect_radiation_oncology_violations(
        [_claim()],
        [
            _proc(procedure_line_id=f"L{i}", procedure_code=c)
            for i, c in enumerate(("800330", "800380"))
        ],
    )
    assert len(rows) == 2
    assert {r["family_key"] for r in rows} == {"rt_application", "linac_application"}
    assert all(r["risk_amount_try"] is None for r in rows)


@pytest.mark.parametrize(
    ("code", "family", "locator"),
    [("800370", "rt_application", "EK-2B!C3688"), ("800430", "linac_application", "EK-2B!C3695")],
)
def test_repeated_special_application_has_a_distinct_course_identity(code, family, locator) -> None:
    rows = detect_radiation_oncology_violations(
        [_claim()],
        [
            _proc(
                procedure_line_id=f"L{i}",
                procedure_code=code,
                procedure_date=date(2026, 7, 10 + i),
            )
            for i in range(2)
        ],
    )
    assert len(rows) == 2
    assert {r["rule_id"] for r in rows} == {f"radiation_oncology.course_cap.{family}"}
    assert all("treatment_course_id" in r["missing_inputs"] for r in rows)
    assert all(r["source_ref"]["locator"] == locator for r in rows)
    assert all(r["risk_amount_try"] is None for r in rows)


@pytest.mark.parametrize("codes", [("800500", "800550"), ("800560", "800590")])
def test_brachytherapy_same_date_does_not_establish_same_session(codes) -> None:
    rows = detect_radiation_oncology_violations(
        [_claim()],
        [_proc(procedure_line_id=f"L{i}", procedure_code=c) for i, c in enumerate(codes)],
    )
    assert len(rows) == 2
    assert all("treatment_session_id" in r["missing_inputs"] for r in rows)
    assert all(r["review_basis"] == "session_identity" for r in rows)
    assert all(r["risk_amount_try"] is None for r in rows)


def test_hyperthermia_does_not_inherit_an_unverified_daily_family_exclusion() -> None:
    assert (
        detect_radiation_oncology_violations(
            [_claim()],
            [
                _proc(procedure_line_id=f"L{i}", procedure_code=c)
                for i, c in enumerate(("800450", "800460"))
            ],
        )
        == []
    )


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-100")])
@pytest.mark.parametrize("codes", [("800070", "800110"), ("800330", "800350")])
def test_zero_or_credit_lines_do_not_create_a_positive_charge_conflict(amount, codes) -> None:
    assert (
        detect_radiation_oncology_violations(
            [_claim()],
            [
                _proc(procedure_line_id="L1", procedure_code=codes[0]),
                _proc(procedure_line_id="L2", procedure_code=codes[1], billed_amount_try=amount),
            ],
        )
        == []
    )


def test_review_output_does_not_choose_a_retained_line_by_input_order() -> None:
    lines = [
        _proc(procedure_line_id="Z", procedure_code="800070"),
        _proc(procedure_line_id="A", procedure_code="800110", billed_amount_try=Decimal("2500")),
    ]
    forward = detect_radiation_oncology_violations([_claim()], lines)
    assert forward == detect_radiation_oncology_violations([_claim()], list(reversed(lines)))
    assert {r["billed_amount_try"] for r in forward} == {1000, 2500}
    assert all(r["risk_amount_try"] is None for r in forward)


@pytest.mark.parametrize("codes", [("800170", "800180", "800190"), ("800235", "800240", "800250")])
def test_dose_alternative_review_does_not_indict_the_independent_basic_calculation(codes) -> None:
    rows = detect_radiation_oncology_violations(
        [_claim()],
        [_proc(procedure_line_id=f"L{i}", procedure_code=c) for i, c in enumerate(codes)],
    )
    assert {r["procedure_code"] for r in rows} == set(codes[1:])
    assert all(r["related_procedure_line_ids"] == ["L1", "L2"] for r in rows)
    assert all(r["risk_amount_try"] is None for r in rows)


@pytest.mark.parametrize("code", ["800280", "800290", "800300"])
def test_device_repetition_retains_individual_source_evidence(code) -> None:
    rows = detect_radiation_oncology_violations(
        [_claim()],
        [_proc(procedure_code=code, quantity=2)],
    )
    assert len(rows) == 1
    assert rows[0]["billed_quantity"] == 2
    assert rows[0]["risk_amount_try"] is None
    assert "treatment_course_id" in rows[0]["missing_inputs"]
    if code in {"800290", "800300"}:
        assert "device_material_identity" in rows[0]["missing_inputs"]


@pytest.mark.parametrize("day", [None, date.min])
def test_unknown_application_date_is_unavailable_not_a_known_same_day_conflict(day) -> None:
    rows = detect_radiation_oncology_violations(
        [_claim()],
        [_proc(procedure_code="800330", procedure_date=day)],
    )
    assert len(rows) == 1
    assert rows[0]["service_date"] is None
    assert rows[0]["procedure_date"] is None
    assert rows[0]["evaluation_status"] == "unavailable"
    assert "application_dates" in rows[0]["missing_inputs"]
    assert rows[0]["risk_amount_try"] is None


def test_different_claims_are_not_assumed_to_be_one_treatment_course() -> None:
    assert (
        detect_radiation_oncology_violations(
            [_claim(claim_id="A"), _claim(claim_id="B")],
            [
                _proc(claim_id="A", procedure_line_id="L1", procedure_code="800070"),
                _proc(claim_id="B", procedure_line_id="L2", procedure_code="800110"),
            ],
        )
        == []
    )

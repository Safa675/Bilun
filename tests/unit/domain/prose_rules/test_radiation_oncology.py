"""Unit tests for radiation oncology (800xxx) mutual-exclusion / cap detector."""

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
        package_candidate=False,
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
        """Two external-RT design codes on the same claim → course-cap violation.

        800070 and 800110 are both in the external_rt_design family, which
        is course-scoped with cap=1. Billing both on one claim violates the
        once-per-course rule.
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

        assert len(violations) == 2  # one per line in the over-cap family
        assert all(v["claim_id"] == "CLM1" for v in violations)
        assert all(v["family_key"] == "external_rt_design" for v in violations)
        assert all(v["rule_kind"] == "course_cap" for v in violations)
        assert {v["procedure_code"] for v in violations} == {"800070", "800110"}
        for v in violations:
            assert v["rule_id"] == "radiation_oncology.course_cap.external_rt_design"
            assert v["sut_section"] == "2.4.4.C"
            assert v["type"] == "radiation_oncology"
            assert v["risk_amount_try"] > 0

    def test_codes_from_different_families_no_violation(self) -> None:
        """One code each from two different families → no violation.

        800070 (external design) and 800120 (planning) are in different
        families, so billing both is compliant.
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
        """Two conventional RT application codes on the same day → violation.

        800330 and 800350 are both in the rt_application (same-day) family.
        Two fractions on the same day must collapse to one bill.
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
        """Two RT application codes on different days → compliant (one fraction/day)."""
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
        """Two brachytherapy application codes same day → violation.

        800500 and 800550 are both in the brachy_application family.
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
        """Two claims each with their own violation are reported separately."""
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
        # Only claim CA over-caps (two design codes).
        claim_ids = {v["claim_id"] for v in violations}
        assert claim_ids == {"CA"}

    def test_empty_inputs_return_empty(self) -> None:
        assert detect_radiation_oncology_violations([], []) == []
        assert detect_radiation_oncology_violations([_claim()], []) == []

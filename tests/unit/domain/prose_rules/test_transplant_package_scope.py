"""Unit tests for the transplant package-scope (P609080) detector."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.prose_rules.transplant_package_scope import (
    detect_transplant_package_scope_violations,
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
        department="transplant",
        admission_date=date(2026, 1, 10),
        discharge_date=date(2026, 1, 20),
        claim_start_date=date(2026, 1, 10),
        claim_end_date=date(2026, 1, 20),
        primary_icd10="K76.9",
        package_candidate=True,
        expected_total_billed_try=Decimal("900000"),
        expected_total_payable_try=Decimal("900000"),
        expected_denial_reason="",
        scenario_tag="test_transplant",
    )
    base.update(overrides)
    return ClaimHeader(**base)


def _proc(**overrides) -> ProcedureClaimLine:
    base = dict(
        procedure_line_id="PL1",
        claim_id="CLM1",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 10),
        procedure_code="609080",
        procedure_name="Karaciğer Transplantasyonu",
        procedure_category="paket",
        quantity=1,
        unit_price_try=Decimal("908561.2"),
        billed_amount_try=Decimal("908561.2"),
        expected_payable_try=Decimal("908561.2"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    base.update(overrides)
    return ProcedureClaimLine(**base)


class TestTransplantPackageScope:
    def test_flags_separate_surgical_procedure_on_transplant_claim(self) -> None:
        claim = _claim()
        lines = [
            _proc(
                procedure_line_id="PL-PKG",
                procedure_code="609080",
                procedure_category="paket",
            ),
            _proc(
                procedure_line_id="PL-SURG",
                procedure_code="510030",
                procedure_name="Karaciğer rezeksiyonu",
                procedure_category="islem",
                billed_amount_try=Decimal("15000"),
                expected_payable_try=Decimal("12000"),
            ),
        ]
        violations = detect_transplant_package_scope_violations(claim, lines)
        assert len(violations) == 1
        v = violations[0]
        assert v["procedure_code"] == "510030"
        assert v["procedure_line_id"] == "PL-SURG"
        assert v["claim_id"] == "CLM1"
        assert v["type"] == "transplant_bundled_violation"
        assert v["rule_id"] == "transplant_bundled_surgical_procedure"
        assert v["package_code"] == "P609080"
        assert "P609080" in v["detail"]
        assert v["savings_category"] == "audit_exposure"
        assert v["savings_basis"] == "heuristic"
        assert v["risk_amount_try"] == pytest.approx(15000.0)
        assert v["care_setting"] == "inpatient"

    def test_transplant_package_alone_produces_no_violation(self) -> None:
        claim = _claim()
        lines = [
            _proc(
                procedure_line_id="PL-PKG",
                procedure_code="609080",
                procedure_category="paket",
            )
        ]
        violations = detect_transplant_package_scope_violations(claim, lines)
        assert violations == []

    def test_non_transplant_claim_produces_no_violation(self) -> None:
        claim = _claim()
        lines = [
            _proc(
                procedure_line_id="PL-SURG",
                procedure_code="510030",
                procedure_name="Karaciğer rezeksiyonu",
                procedure_category="islem",
                billed_amount_try=Decimal("15000"),
            )
        ]
        violations = detect_transplant_package_scope_violations(claim, lines)
        assert violations == []

    def test_outpatient_transplant_claim_is_not_flagged(self) -> None:
        # Transplants are inpatient; the care-setting gate suppresses
        # outpatient claims even if a P609080 line is present.
        claim = _claim(claim_type="poliklinik")
        lines = [
            _proc(
                procedure_line_id="PL-PKG",
                procedure_code="609080",
                procedure_category="paket",
            ),
            _proc(
                procedure_line_id="PL-SURG",
                procedure_code="510030",
                procedure_name="Karaciğer rezeksiyonu",
                procedure_category="islem",
                billed_amount_try=Decimal("15000"),
            ),
        ]
        violations = detect_transplant_package_scope_violations(claim, lines)
        assert violations == []

    def test_allow_listed_blood_component_is_not_flagged(self) -> None:
        # Blood components (SUT §4.6.4) remain separately billable; place a
        # code on the allow-list and confirm it is suppressed.
        from src.bilun.domain.prose_rules import transplant_package_scope as mod

        blood_code = "900100"
        original = mod.ALLOWED_SEPARATELY_BILLABLE_CODES
        mod.ALLOWED_SEPARATELY_BILLABLE_CODES = frozenset({blood_code})
        try:
            claim = _claim()
            lines = [
                _proc(
                    procedure_line_id="PL-PKG",
                    procedure_code="609080",
                    procedure_category="paket",
                ),
                _proc(
                    procedure_line_id="PL-BLOOD",
                    procedure_code=blood_code,
                    procedure_name="Eritrosit süspansiyonu",
                    procedure_category="islem",
                    billed_amount_try=Decimal("2500"),
                ),
                # A non-allow-listed surgical procedure is still flagged.
                _proc(
                    procedure_line_id="PL-SURG",
                    procedure_code="510030",
                    procedure_name="Karaciğer rezeksiyonu",
                    procedure_category="islem",
                    billed_amount_try=Decimal("15000"),
                ),
            ]
            violations = detect_transplant_package_scope_violations(claim, lines)
            assert len(violations) == 1
            assert violations[0]["procedure_code"] == "510030"
        finally:
            mod.ALLOWED_SEPARATELY_BILLABLE_CODES = original

    def test_zero_billed_surgical_procedure_is_not_flagged(self) -> None:
        claim = _claim()
        lines = [
            _proc(
                procedure_line_id="PL-PKG",
                procedure_code="609080",
                procedure_category="paket",
            ),
            _proc(
                procedure_line_id="PL-SURG",
                procedure_code="510030",
                procedure_category="islem",
                billed_amount_try=Decimal("0"),
            ),
        ]
        violations = detect_transplant_package_scope_violations(claim, lines)
        assert violations == []

    def test_non_surgical_category_is_not_flagged(self) -> None:
        # Only surgical (``islem``) procedures fall under the package scope.
        # A ``muayene`` (examination) line is not in scope.
        claim = _claim()
        lines = [
            _proc(
                procedure_line_id="PL-PKG",
                procedure_code="609080",
                procedure_category="paket",
            ),
            _proc(
                procedure_line_id="PL-EXAM",
                procedure_code="700010",
                procedure_name="Uzman muayenesi",
                procedure_category="muayene",
                billed_amount_try=Decimal("500"),
            ),
        ]
        violations = detect_transplant_package_scope_violations(claim, lines)
        assert violations == []

    def test_p609080_with_p_prefix_is_normalized(self) -> None:
        # The catalog stores the code as "P609080"; normalization must still
        # recognize it as the liver transplant package line.
        claim = _claim()
        lines = [
            _proc(
                procedure_line_id="PL-PKG",
                procedure_code="P609080",
                procedure_category="paket",
            ),
            _proc(
                procedure_line_id="PL-SURG",
                procedure_code="510030",
                procedure_name="Karaciğer rezeksiyonu",
                procedure_category="islem",
                billed_amount_try=Decimal("15000"),
            ),
        ]
        violations = detect_transplant_package_scope_violations(claim, lines)
        assert len(violations) == 1
        assert violations[0]["procedure_code"] == "510030"

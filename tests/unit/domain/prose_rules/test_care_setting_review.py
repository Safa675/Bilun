"""Unit tests for care-setting ambiguity and advisory review detector."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.prose_rules.claim_utils import (
    detect_care_setting_ambiguity,
    infer_care_setting,
)
from src.bilun.domain.prose_rules.care_setting_review import (
    detect_care_setting_review_opportunities,
)

pytestmark = pytest.mark.unit

TIER_3 = "egitim_arastirma"


def _claim(**overrides) -> ClaimHeader:
    base = dict(
        claim_id="CLM-CS",
        patient_id="P1",
        episode_id="E1",
        claim_type="gunubirlik",
        facility_tier=TIER_3,
        provider_type="Universite",
        department="cardiology",
        admission_date=date(2026, 1, 10),
        discharge_date=date(2026, 1, 10),
        claim_start_date=date(2026, 1, 10),
        claim_end_date=date(2026, 1, 10),
        primary_icd10="I21.9",
        expected_total_billed_try=Decimal("12000"),
        expected_total_payable_try=Decimal("12000"),
        expected_denial_reason="",
        scenario_tag="sgk_care_setting_review_gunubirlik",
    )
    base.update(overrides)
    return ClaimHeader(**base)


def _proc(**overrides) -> ProcedureClaimLine:
    base = dict(
        procedure_line_id="PL1",
        claim_id="CLM-CS",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 10),
        procedure_code="600150",
        procedure_name="Itemized A",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("4500"),
        billed_amount_try=Decimal("0"),
        expected_payable_try=Decimal("4500"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    base.update(overrides)
    return ProcedureClaimLine(**base)


class TestInferCareSetting:
    def test_poliklinik_maps_outpatient(self) -> None:
        claim = _claim(claim_type="poliklinik")
        assert infer_care_setting(claim) == "outpatient"

    def test_yatis_maps_inpatient(self) -> None:
        claim = _claim(claim_type="yatis")
        assert infer_care_setting(claim) == "inpatient"

    def test_gunubirlik_maps_outpatient(self) -> None:
        claim = _claim(claim_type="gunubirlik")
        assert infer_care_setting(claim) == "outpatient"


class TestCareSettingAmbiguity:
    def test_gunubirlik_is_ambiguous(self) -> None:
        ambiguity = detect_care_setting_ambiguity(_claim())
        assert ambiguity is not None
        assert ambiguity.reason == "gunubirlik"
        assert ambiguity.primary_setting == "outpatient"
        assert ambiguity.alternate_setting == "inpatient"

    def test_plain_yatis_not_ambiguous_without_same_day(self) -> None:
        claim = _claim(
            claim_type="yatis",
            admission_date=date(2026, 1, 10),
            discharge_date=date(2026, 1, 12),
        )
        assert detect_care_setting_ambiguity(claim) is None


class TestCareSettingReviewDetector:
    def test_gunubirlik_tier3_emits_review_row(self) -> None:
        claim = _claim()
        procs = [
            _proc(),
            _proc(
                procedure_line_id="PL2",
                procedure_code="600160",
                procedure_name="Itemized B",
                expected_payable_try=Decimal("3500"),
            ),
            _proc(
                procedure_line_id="PL3",
                procedure_code="609270",
                procedure_name="Package",
                procedure_category="paket",
                billed_amount_try=Decimal("3500"),
                expected_payable_try=Decimal("3500"),
            ),
        ]
        rows = detect_care_setting_review_opportunities(claim, procs)
        assert len(rows) == 1
        row = rows[0]
        assert row["recommendation_kind"] == "coding_review"
        assert row["included_in_sgk_total"] is False
        assert row["recoverable_uplift_try"] > 0
        assert row["alternate_payment_method_kind"] == "DRG_OVERRIDABLE"
        assert row["actual_payment_method_kind"] == "DRG_MANDATORY"

    def test_non_tier3_skips(self) -> None:
        claim = _claim(facility_tier="2_basamak_kamu")
        procs = [
            _proc(),
            _proc(
                procedure_line_id="PL3",
                procedure_code="609270",
                procedure_category="paket",
                billed_amount_try=Decimal("3500"),
                expected_payable_try=Decimal("3500"),
            ),
        ]
        assert detect_care_setting_review_opportunities(claim, procs) == []

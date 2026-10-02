"""Blood component fraction under-billing detector (Phase 1.4)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ProcedureClaimLine
from src.bilun.domain.prose_rules.blood_uplift import (
    detect_blood_component_underbilling_opportunities,
)
from src.bilun.domain.prose_rules.drg_unbundling import detect_blood_component_violations

pytestmark = pytest.mark.unit


def _proc(**overrides) -> ProcedureClaimLine:
    base = dict(
        procedure_line_id="PL1",
        claim_id="CLM1",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 10),
        procedure_code="705371",
        procedure_name="Eritrosit süspansiyonu",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("50"),
        expected_payable_try=Decimal("1000"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    base.update(overrides)
    return ProcedureClaimLine(**base)


def _package():
    # Actual package treatment on another day; a candidate flag is insufficient.
    return _proc(procedure_line_id="package", procedure_code="P610070",
                 procedure_category="paket", procedure_date=date(2026, 1, 9),
                 billed_amount_try=Decimal("10000"), expected_payable_try=Decimal("10000"))


class TestBloodComponentUplift:
    def test_detects_underbilling_below_fraction(self) -> None:
        hits = detect_blood_component_underbilling_opportunities(
            [_package(), _proc()],
            claim_id="CLM1",
        )
        assert len(hits) == 1
        assert hits[0]["type"] == "blood_component_underbilling"
        assert hits[0]["allowed_fraction"] == pytest.approx(0.36)
        assert hits[0]["max_billable_try"] == pytest.approx(360.0)
        assert hits[0]["recoverable_uplift_try"] == pytest.approx(310.0)
        assert hits[0]["savings_category"] == "sgk_uplift"

    def test_skips_when_billed_within_tolerance(self) -> None:
        hits = detect_blood_component_underbilling_opportunities(
            [_package(), _proc(billed_amount_try=Decimal("360"))],
            claim_id="CLM1",
        )
        assert hits == []

    def test_overbilling_goes_to_audit_not_uplift(self) -> None:
        line = _proc(billed_amount_try=Decimal("500"))
        assert detect_blood_component_underbilling_opportunities([_package(), line]) == []
        violations = detect_blood_component_violations([_package(), line])
        assert len(violations) == 1
        assert violations[0]["risk_amount_try"] > 0

    def test_ignores_non_blood_codes(self) -> None:
        hits = detect_blood_component_underbilling_opportunities(
            [_proc(procedure_code="520080", billed_amount_try=Decimal("10"))],
            claim_id="CLM1",
        )
        assert hits == []

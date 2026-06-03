"""Material KDV pricing (§3.1.1(12))."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_gazette_price_with_kdv_default_rate() -> None:
    from src.bilun.domain.pricing.material_kdv import (
        DEFAULT_MATERIAL_KDV_RATE,
        gazette_price_with_kdv,
    )

    assert gazette_price_with_kdv(100.0, apply_kdv=True) == round(
        100.0 * (1.0 + DEFAULT_MATERIAL_KDV_RATE), 2
    )
    assert gazette_price_with_kdv(100.0, apply_kdv=False) == 100.0


def test_foreign_facility_skips_kdv() -> None:
    from src.bilun.domain.pricing.material_kdv import (
        ek3_payable_ceiling_try,
        should_apply_kdv_to_material,
    )

    assert should_apply_kdv_to_material(foreign_facility=True) is False
    assert ek3_payable_ceiling_try(250.0, foreign_facility=True) == 250.0


def test_kdv_price_review_when_billed_above_ceiling() -> None:
    from datetime import date
    from decimal import Decimal

    from src.bilun.domain.billing.claim_materials import precheck_materials_from_claims
    from src.bilun.domain.claims.models import MaterialClaimLine
    from src.bilun.domain.claims.patient_context import PatientClaimContext
    from src.bilun.domain.materials.catalog_lookup import lookup_ek3_list_price_try

    code = "OP1592"
    list_price = lookup_ek3_list_price_try(code)
    assert list_price is not None and list_price > 0

    line = MaterialClaimLine(
        material_line_id="M1",
        claim_id="C1",
        procedure_line_id="P1",
        patient_id="PT1",
        material_date=date(2024, 6, 1),
        material_code=code,
        material_name="ICD",
        material_type="cihaz",
        specialty_category="cardiology",
        quantity=1,
        unit_price_try=Decimal("999999"),
        billed_amount_try=Decimal("999999"),
        expected_payable_try=Decimal("800000"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    ctx = PatientClaimContext(
        patient_id="PT1",
        claims=(),
        procedure_lines=(),
        material_lines=(line,),
        drug_lines=(),
        diagnoses=(),
    )
    result = precheck_materials_from_claims(ctx)
    assert result.kdv_price_reviews
    assert result.kdv_price_reviews[0]["sut_code"] == code
    assert result.kdv_price_reviews[0]["kdv_applied"] is True

"""L3.5 exact material pre-check (claim_materials.py)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit


def _material_line(
    *,
    code: str = "OP1000",
    claim_id: str = "C1",
    line_id: str = "M1",
    material_date: date = date(2024, 6, 1),
    is_bundled: bool = False,
    requires_pre_auth: bool = False,
    billed: str = "100",
) -> "MaterialClaimLine":
    from src.bilun.domain.claims.models import MaterialClaimLine

    return MaterialClaimLine(
        material_line_id=line_id,
        claim_id=claim_id,
        procedure_line_id="P1",
        patient_id="PT1",
        material_date=material_date,
        material_code=code,
        material_name="Test material",
        material_type="ortez",
        specialty_category="ortho",
        quantity=1,
        unit_price_try=Decimal(billed),
        billed_amount_try=Decimal(billed),
        expected_payable_try=Decimal("80"),
        is_bundled=is_bundled,
        requires_pre_auth=requires_pre_auth,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _ctx(*lines: "MaterialClaimLine") -> "PatientClaimContext":
    from src.bilun.domain.claims.patient_context import PatientClaimContext

    return PatientClaimContext(
        patient_id="PT1",
        claims=(),
        procedure_lines=(),
        material_lines=lines,
        drug_lines=(),
        diagnoses=(),
    )


def test_bundled_separate_billing_not_miat_only_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bundled lines must not be filed solely under miat_restricted (L3.5 taxonomy)."""
    from src.bilun.domain.billing import claim_materials as cm

    monkeypatch.setattr(cm, "_get_ek3c1_preauth", lambda: [])
    monkeypatch.setattr(cm, "_get_ek3c2_miat", lambda: [])
    monkeypatch.setattr(cm, "check_material_bundling_for_context", lambda _ctx: [])

    line = _material_line(code="EK3B99", is_bundled=True)
    result = cm.precheck_materials_from_claims(_ctx(line))

    assert len(result.bundled_separate_billing) == 1
    assert result.bundled_separate_billing[0]["sut_code"] == "EK3B99"
    assert result.miat_restricted == []
    assert result.miat_interval_violations == []


def test_preauth_note_uses_tibbi_uygunluk(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.bilun.domain.billing import claim_materials as cm

    monkeypatch.setattr(
        cm,
        "_get_ek3c1_preauth",
        lambda: [
            {
                "sut_code": "PA001",
                "material_name": "Board item",
                "price_try": 1.0,
            }
        ],
    )
    monkeypatch.setattr(cm, "_get_ek3c2_miat", lambda: [])
    monkeypatch.setattr(cm, "check_material_bundling_for_context", lambda _ctx: [])

    line = _material_line(code="PA001")
    result = cm.precheck_materials_from_claims(_ctx(line))

    assert len(result.pre_auth_required) == 1
    assert "tıbbi uygunluk" in result.pre_auth_required[0]["note"]
    assert "sağlık kurulu" not in result.pre_auth_required[0]["note"].lower()


def test_miat_interval_violation_separate_from_catalog_advisory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.bilun.domain.billing import claim_materials as cm

    monkeypatch.setattr(cm, "_get_ek3c1_preauth", lambda: [])
    monkeypatch.setattr(
        cm,
        "_get_ek3c2_miat",
        lambda: [
            {
                "sut_code": "OP1000",
                "material_name": "Brace",
                "miat_period": "6 ay",
                "price_try": 100.0,
            }
        ],
    )
    monkeypatch.setattr(cm, "check_material_bundling_for_context", lambda _ctx: [])

    prior = _material_line(
        line_id="M1",
        claim_id="C1",
        material_date=date(2024, 1, 1),
    )
    current = _material_line(
        line_id="M2",
        claim_id="C2",
        material_date=date(2024, 2, 1),
    )
    result = cm.precheck_materials_from_claims(_ctx(prior, current))

    assert len(result.miat_interval_violations) == 1
    assert result.miat_interval_violations[0]["last_use_date"] == "2024-01-01"
    assert result.miat_restricted == []


def test_miat_catalog_advisory_when_no_prior_use(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.bilun.domain.billing import claim_materials as cm

    monkeypatch.setattr(cm, "_get_ek3c1_preauth", lambda: [])
    monkeypatch.setattr(
        cm,
        "_get_ek3c2_miat",
        lambda: [
            {
                "sut_code": "OP1000",
                "material_name": "Brace",
                "miat_period": "6 ay",
                "price_try": 100.0,
            }
        ],
    )
    monkeypatch.setattr(cm, "check_material_bundling_for_context", lambda _ctx: [])

    line = _material_line(material_date=date(2024, 6, 1))
    result = cm.precheck_materials_from_claims(_ctx(line))

    assert len(result.miat_restricted) == 1
    assert "Catalog MIAT period" in result.miat_restricted[0]["note"]
    assert result.miat_interval_violations == []

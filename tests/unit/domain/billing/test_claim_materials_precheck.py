"""L3.5 exact material pre-check (claim_materials.py)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from src.bilun.domain.claims.models import MaterialClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext

pytestmark = pytest.mark.unit


def _material_line(
    *,
    code: str = "OP1000",
    claim_id: str = "C1",
    line_id: str = "M1",
    material_date: date = date(2024, 6, 1),
    is_bundled: bool = False,
    is_ek3b1_bundled: bool = False,
    requires_pre_auth: bool = False,
    billed: str = "100",
    material_name: str = "Test material",
) -> MaterialClaimLine:
    return MaterialClaimLine(
        material_line_id=line_id,
        claim_id=claim_id,
        procedure_line_id="P1",
        patient_id="PT1",
        material_date=material_date,
        material_code=code,
        material_name=material_name,
        material_type="ortez",
        specialty_category="ortho",
        quantity=1,
        unit_price_try=Decimal(billed),
        billed_amount_try=Decimal(billed),
        expected_payable_try=Decimal("80"),
        is_bundled=is_bundled,
        is_ek3b1_bundled=is_ek3b1_bundled,
        requires_pre_auth=requires_pre_auth,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _ctx(*lines: MaterialClaimLine) -> PatientClaimContext:
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


def test_bundled_note_distinguishes_ek3b1_vs_package_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Option A: labels must not claim EK-3B-1 for broad is_bundled-only rows."""
    from src.bilun.domain.billing import claim_materials as cm

    monkeypatch.setattr(cm, "_get_ek3c1_preauth", lambda: [])
    monkeypatch.setattr(cm, "_get_ek3c2_miat", lambda: [])
    monkeypatch.setattr(cm, "check_material_bundling_for_context", lambda _ctx: [])

    flag_only = _material_line(code="FLAG1", is_bundled=True, is_ek3b1_bundled=False)
    ek3b1 = _material_line(
        code="EK3B1",
        line_id="M2",
        material_name="Bistüri ucu",
        is_bundled=True,
        is_ek3b1_bundled=True,
    )
    result = cm.precheck_materials_from_claims(_ctx(flag_only, ek3b1))
    by_code = {row["sut_code"]: row for row in result.bundled_separate_billing}

    assert by_code["FLAG1"]["sut_section_id"] == "package_flag"
    assert "invoice/package flag" in by_code["FLAG1"]["note"]
    assert "not EK-3B-1 regulatory annex" in by_code["FLAG1"]["note"]
    # Must not claim the row *is* an EK-3B-1 annex hit (negation phrase is ok).
    assert "review package inclusion (EK-3B-1)" not in by_code["FLAG1"]["note"]

    assert "EK-3B-1" in by_code["EK3B1"]["note"]
    assert by_code["EK3B1"]["sut_section_id"] == "EK-3B-1"
    assert "review package inclusion (EK-3B-1)" in by_code["EK3B1"]["note"]


def test_specialty_prose_violation_on_wound_keyword(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.bilun.domain.billing import claim_materials as cm

    monkeypatch.setattr(cm, "_get_ek3c1_preauth", lambda: [])
    monkeypatch.setattr(cm, "_get_ek3c2_miat", lambda: [])
    monkeypatch.setattr(cm, "check_material_bundling_for_context", lambda _ctx: [])

    line = _material_line(
        code="DEMO-W1",
        billed="85",
        material_name="Transparan film yara örtüsü",
    )
    result = cm.precheck_materials_from_claims(_ctx(line))

    assert len(result.specialty_prose_violations) == 1
    assert result.specialty_prose_violations[0]["rule_id"] == (
        "3.3.1.(10).wound_dressing_cover_no_pay"
    )
    assert result.specialty_coverage_scope["prose_engine_status"] == "implemented"


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


def test_precheck_rows_include_sut_section_claim_and_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.bilun.domain.billing import claim_materials as cm

    monkeypatch.setattr(
        cm,
        "_get_ek3c1_preauth",
        lambda: [
            {
                "sut_code": "OP1198",
                "material_name": "Board item",
                "price_try": 1.0,
            }
        ],
    )
    monkeypatch.setattr(cm, "_get_ek3c2_miat", lambda: [])
    monkeypatch.setattr(cm, "check_material_bundling_for_context", lambda _ctx: [])

    line = _material_line(code="OP1198", claim_id="F-TEST-001", billed="250.50")
    result = cm.precheck_materials_from_claims(_ctx(line))

    row = result.pre_auth_required[0]
    assert row["sut_section_id"] == "3.1.2"
    assert row["claim_id"] == "F-TEST-001"
    assert row["price_try"] == pytest.approx(250.50)
    assert row["material_name"] == "Test material"


def test_preauth_note_distinguishes_real_catalog_member_and_input_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.bilun.domain.billing import claim_materials as cm
    from src.bilun.domain.billing.billing_actions import collect_billing_actions
    from src.bilun.domain.billing.types import BillingActionReport

    catalog_codes = {row["sut_code"] for row in cm._get_ek3c1_preauth()}
    assert "100000" in catalog_codes and "NF1040" not in catalog_codes
    monkeypatch.setattr(cm, "_get_ek3c2_miat", lambda: [])
    monkeypatch.setattr(cm, "check_material_bundling_for_context", lambda _ctx: [])
    monkeypatch.setattr(cm, "check_specialty_materials_for_context", lambda _ctx: [])
    member = _material_line(code="100000", line_id="MEMBER", claim_id="C-MEMBER")
    flag_only = _material_line(
        code="NF1040", line_id="FLAG", claim_id="C-FLAG", requires_pre_auth=True,
    )
    result = cm.precheck_materials_from_claims(_ctx(member, flag_only))
    by_code = {row["sut_code"]: row for row in result.pre_auth_required}
    assert set(by_code) == {"100000", "NF1040"}
    assert by_code["100000"]["note"] == cm._PREAUTH_NOTE
    assert "material-line input flag" in by_code["NF1040"]["note"]
    assert "catalog membership not verified" in by_code["NF1040"]["note"]
    assert by_code["NF1040"]["claim_id"] == "C-FLAG"
    assert by_code["NF1040"]["price_try"] == 100.0
    assert result.exactness_status == "exact"
    actions = collect_billing_actions(BillingActionReport(patient_id="PT1", materials=result))
    flagged = next(row for row in actions if row["material_code"] == "NF1040")
    assert flagged["kind"] == "material_pre_auth"
    assert flagged["detail"] == by_code["NF1040"]["note"]
    assert flagged["sut_section_id"] == "3.1.2"
    assert flagged["clause_ref"] is None
    assert flagged["sgk_uplift_try"] is None
    assert cm.precheck_materials_from_claims(
        _ctx(_material_line(code="NF1040", requires_pre_auth=False)),
    ).pre_auth_required == []


def test_none_material_date_does_not_crash_latest_line_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B-H6 regression: a MaterialClaimLine with material_date=None must
    not raise TypeError in the latest-line-by-code selection loop.  The
    dated line should win over the None-dated line for the same code.
    """
    from src.bilun.domain.billing import claim_materials as cm

    monkeypatch.setattr(cm, "_get_ek3c1_preauth", lambda: [])
    monkeypatch.setattr(cm, "_get_ek3c2_miat", lambda: [])
    monkeypatch.setattr(cm, "check_material_bundling_for_context", lambda _ctx: [])

    none_dated = _material_line(
        code="OP9990",
        line_id="M_NONE",
        billed="50",
        material_date=None,
    )
    dated = _material_line(
        code="OP9990",
        line_id="M_DATED",
        billed="80",
        material_date=date(2026, 1, 15),
    )

    result = cm.precheck_materials_from_claims(_ctx(none_dated, dated))
    assert len(result.pre_auth_required) == 0
    assert len(result.miat_restricted) == 0


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

"""Unit tests for the EK-3C-2 MIAT prose evaluator (Phase 3.5)."""

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
    billed: str = "100",
    material_name: str = "Test material",
) -> "MaterialClaimLine":
    from src.bilun.domain.claims.models import MaterialClaimLine

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
        is_bundled=False,
        requires_pre_auth=False,
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


def _miat_catalog() -> list[dict]:
    return [
        {
            "sut_code": "OP1000",
            "material_name": "MIAT Brace",
            "miat_period": "6 ay",  # 180 days
            "price_try": 100.0,
        }
    ]


def test_miat_violation_when_renewed_too_soon(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two same-code material lines inside the MIAT window → one violation."""
    from src.bilun.domain.prose_rules import material_miat_ek3c2 as mod

    monkeypatch.setattr(mod, "_get_ek3c2_miat", _miat_catalog)

    prior = _material_line(
        line_id="M1",
        claim_id="C1",
        material_date=date(2024, 1, 1),
        billed="120",
    )
    current = _material_line(
        line_id="M2",
        claim_id="C2",  # different bill, same patient
        material_date=date(2024, 2, 1),  # 31 days later, MIAT is 180
        billed="150",
    )

    violations = mod.check_material_miat_for_context(_ctx(prior, current))

    assert len(violations) == 1
    v = violations[0]
    assert v["rule"] == "material_miat_ek3c2"
    assert v["severity"] == "warning"
    assert v["material_code"] == "OP1000"
    assert v["risk_amount"] == pytest.approx(150.0)
    assert v["sut_section"] == "3.1.4"
    assert v["details"]["last_use_date"] == "2024-01-01"
    assert v["details"]["days_since_last_use"] == 31
    assert v["details"]["minimum_interval_days"] == 180
    assert v["details"]["claim_id"] == "C2"


def test_no_violation_when_renewed_outside_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Renewal past the MIAT window → no violation."""
    from src.bilun.domain.prose_rules import material_miat_ek3c2 as mod

    monkeypatch.setattr(mod, "_get_ek3c2_miat", _miat_catalog)

    prior = _material_line(
        line_id="M1",
        material_date=date(2024, 1, 1),
    )
    # 200 days later — strictly greater than the 180-day MIAT window.
    current = _material_line(
        line_id="M2",
        material_date=date(2024, 7, 19),
    )

    violations = mod.check_material_miat_for_context(_ctx(prior, current))

    assert violations == []


def test_no_violation_for_non_miat_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """A code absent from the MIAT catalog → never flagged, even when repeated."""
    from src.bilun.domain.prose_rules import material_miat_ek3c2 as mod

    monkeypatch.setattr(mod, "_get_ek3c2_miat", _miat_catalog)

    prior = _material_line(
        line_id="M1",
        code="XYZ-NOT-IN-CATALOG",
        material_date=date(2024, 1, 1),
    )
    current = _material_line(
        line_id="M2",
        code="XYZ-NOT-IN-CATALOG",
        material_date=date(2024, 1, 3),  # 2 days apart
    )

    violations = mod.check_material_miat_for_context(_ctx(prior, current))

    assert violations == []


def test_no_violation_when_no_prior_use(monkeypatch: pytest.MonkeyPatch) -> None:
    """A single MIAT-catalog line with no prior → no violation (interval check
    only fires on a renewal inside the window; this is the catalog-advisory
    case, which this evaluator intentionally does NOT emit)."""
    from src.bilun.domain.prose_rules import material_miat_ek3c2 as mod

    monkeypatch.setattr(mod, "_get_ek3c2_miat", _miat_catalog)

    solo = _material_line(line_id="M1", material_date=date(2024, 6, 1))

    violations = mod.check_material_miat_for_context(_ctx(solo))

    assert violations == []


def test_empty_catalog_emits_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defensive: missing/empty EK-3C-2 catalog → no crash, no violations."""
    from src.bilun.domain.prose_rules import material_miat_ek3c2 as mod

    monkeypatch.setattr(mod, "_get_ek3c2_miat", lambda: [])

    line = _material_line(line_id="M1", material_date=date(2024, 6, 1))
    assert mod.check_material_miat_for_context(_ctx(line)) == []

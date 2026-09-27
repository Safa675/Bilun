"""One focused detector pass retains the existing engine order and payloads."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.bilun.domain.billing import focused_legacy_materializer as materializer
from src.bilun.domain.billing.engine import analyze_claim
from src.bilun.domain.billing.focused_rule_projection import FOCUSED_RULE_SPECS
from src.bilun.domain.claims.models import (
    ClaimHeader,
    DrugClaimLine,
    MaterialClaimLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext

pytestmark = pytest.mark.unit
_DAY = date(2026, 7, 10)
_RULE_IDS = {spec.rule_id for spec in FOCUSED_RULE_SPECS}


def _header(claim_id: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id=f"E-{claim_id}",
        claim_type="ayakta",
        facility_tier="ozel",
        provider_type="private",
        department="genel",
        admission_date=None,
        discharge_date=None,
        claim_start_date=_DAY,
        claim_end_date=_DAY,
        primary_icd10="Z00.0",
        package_candidate=False,
        expected_total_billed_try=Decimal("100"),
        expected_total_payable_try=Decimal("90"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _procedure(
    claim_id: str,
    line_id: str,
    code: str,
    category: str,
    day: date,
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id=f"E-{claim_id}",
        procedure_date=day,
        procedure_code=code,
        procedure_name="Test procedure",
        procedure_category=category,
        procedure_specialty_code="CARD",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("90"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _material() -> MaterialClaimLine:
    return MaterialClaimLine(
        material_line_id="M1",
        claim_id="C1",
        procedure_line_id="E1",
        patient_id="P1",
        material_date=_DAY,
        material_code="500000",
        material_name="Material",
        material_type="",
        specialty_category="general",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("90"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _drug() -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D1",
        prescription_id="RX1",
        claim_id="C1",
        patient_id="P1",
        episode_id="E-C1",
        drug_claim_date=_DAY,
        drug_name="Drug",
        drug_code="D1",
        barkod="8690000000001",
        equivalence_group="",
        quantity=0,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("90"),
        discount_tier_expected=Decimal("0.1"),
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _context() -> PatientClaimContext:
    return PatientClaimContext(
        patient_id="P1",
        claims=(_header("C1"), _header("C2")),
        procedure_lines=(
            _procedure("C1", "E1", "520010", "muayene", _DAY),
            _procedure("C2", "E2", "520010", "muayene", _DAY + timedelta(days=1)),
            _procedure("C1", "R1", "800070", "islem", _DAY),
            _procedure("C1", "R2", "800110", "islem", _DAY),
        ),
        material_lines=(_material(),),
        drug_lines=(_drug(),),
        diagnoses=(),
    )


def test_all_group_rows_equal_the_current_engine_focused_subsequence() -> None:
    ctx = _context()
    original = [row for row in analyze_claim(ctx) if row.get("rule_id") in _RULE_IDS]
    collector = materializer.FocusedLegacyMaterializer(ctx)

    assert len(materializer.FOCUSED_GROUP_ORDER) == 18
    assert set(materializer.FOCUSED_GROUP_ORDER) == {spec.group for spec in FOCUSED_RULE_SPECS}
    assert [
        (
            row["rule_id"],
            row["claim_id"],
            row.get("procedure_line_id")
            or row.get("material_line_id")
            or row.get("drug_claim_line_id"),
        )
        for row in original
    ] == [
        ("radiation_oncology.course_cap.external_rt_design", "C1", "R1"),
        ("radiation_oncology.course_cap.external_rt_design", "C1", "R2"),
        ("tablo15_2_duplicate_exam_10day", "C2", "E2"),
        ("tablo15_16_material_type_missing", "C1", "M1"),
        ("tablo15_11_drug_quantity_error", "C1", "D1"),
    ]
    assert collector.all_rows() == tuple(original)


def test_each_group_executes_once_even_after_repeated_empty_or_full_reads() -> None:
    ctx = _context()
    call_order: list[str] = []
    with ExitStack() as stack:
        spies = {}
        for group in materializer.FOCUSED_GROUP_ORDER:
            original = getattr(materializer, group)

            def counted(*args, _group=group, _original=original, **kwargs):
                call_order.append(_group)
                return _original(*args, **kwargs)

            spies[group] = stack.enter_context(
                patch.object(materializer, group, side_effect=counted)
            )
        collector = materializer.FocusedLegacyMaterializer(ctx)
        first = collector.all_rows()
        assert collector.all_rows() == first
        assert collector.rows("detect_radiation_oncology_violations")
        assert collector.rows("detect_admission_billing_window") == ()
        for group, spy in spies.items():
            expected = (
                len(ctx.claims) if group == "detect_transplant_package_scope_violations" else 1
            )
            assert spy.call_count == expected, group
        assert call_order == [
            group
            for group in materializer.FOCUSED_GROUP_ORDER
            for _ in range(
                len(ctx.claims) if group == "detect_transplant_package_scope_violations" else 1
            )
        ]

    # Requesting a late group first must not change the legacy flat order.
    out_of_order = materializer.FocusedLegacyMaterializer(ctx)
    assert out_of_order.rows("detect_radiation_oncology_violations")
    assert out_of_order.all_rows() == first


def test_legacy_patient_gate_and_line_presence_gates_are_preserved() -> None:
    ctx = _context()
    no_patient = replace(ctx, patient_id="")
    with patch.object(materializer, "detect_admission_billing_window") as admission:
        assert materializer.FocusedLegacyMaterializer(no_patient).all_rows() == ()
        admission.assert_not_called()

    without_procedures = replace(ctx, procedure_lines=())
    with patch.object(materializer, "detect_duplicate_exam_10day") as exam:
        rows = materializer.FocusedLegacyMaterializer(without_procedures).all_rows()
        exam.assert_not_called()
    original = [row for row in analyze_claim(without_procedures) if row.get("rule_id") in _RULE_IDS]
    assert rows == tuple(original)


def test_unknown_group_fails_without_running_a_detector() -> None:
    collector = materializer.FocusedLegacyMaterializer(_context())
    with pytest.raises(KeyError, match="Unknown focused detector group"):
        collector.rows("not_a_focused_group")

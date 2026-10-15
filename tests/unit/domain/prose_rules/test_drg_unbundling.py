"""Unit tests for prose-rule DRG unbundling analysis."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.optimization.unbundling import detect_drg_unbundling
from src.bilun.domain.prose_rules.drg_unbundling import analyze_claim_unbundling
from src.bilun.domain.claims.patient_context import PatientClaimContext

pytestmark = pytest.mark.unit


def _claim(**overrides) -> ClaimHeader:
    base = dict(
        claim_id="CLM1",
        patient_id="P1",
        episode_id="E1",
        claim_type="yatarak",
        facility_tier="3",
        provider_type="hospital",
        department="cardiology",
        admission_date=date(2026, 1, 10),
        discharge_date=date(2026, 1, 12),
        claim_start_date=date(2026, 1, 10),
        claim_end_date=date(2026, 1, 12),
        primary_icd10="I21.9",
        package_candidate=True,
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
        procedure_date=date(2026, 1, 10),
        procedure_code="610070",
        procedure_name="Test procedure",
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


class TestProseDrgUnbundling:
    def test_detects_package_included_bundling(self) -> None:
        claim = _claim()
        lines = [
            _proc(
                procedure_line_id="PL1",
                is_package_included=True,
                billed_amount_try=Decimal("500"),
                expected_payable_try=Decimal("0"),
            )
        ]
        finding = analyze_claim_unbundling(claim, lines)
        assert finding is not None
        assert len(finding.bundled_violations) == 1
        assert finding.potential_savings_try == 0.0
        assert finding.heuristic_savings_try > 0
        assert finding.sourced_savings_try == 0.0
        assert finding.bundled_violations[0]["savings_basis"] == "audit_flag"

    def test_itemized_package_uplift_is_heuristic(self, monkeypatch) -> None:
        claim = _claim()
        lines = [
            _proc(
                procedure_line_id="PL1",
                procedure_category="islem",
                expected_payable_try=Decimal("3000"),
                billed_amount_try=Decimal("3000"),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_category="paket",
                expected_payable_try=Decimal("1000"),
                billed_amount_try=Decimal("1000"),
            ),
        ]

        from src.bilun.domain.prose_rules.types import PaymentMethodResult, ProseRuleTrace

        def _always_itemized(code, **_kwargs):
            return PaymentMethodResult(
                procedure_code=code,
                payment_method="itemized",
                kind="ITEMIZED",
                in_ek2b=True,
                in_ek2c=False,
                has_star=False,
                bill_materials_separately=False,
                bill_drugs_separately=False,
                visit_fee_annex=None,
                trace=ProseRuleTrace(
                    rule_id="test",
                    sut_section="2.2.2",
                    rule_set_id="test",
                    detail="test",
                ),
            )

        monkeypatch.setattr(
            "src.bilun.domain.prose_rules.drg_unbundling.resolve_payment_method",
            _always_itemized,
        )
        finding = analyze_claim_unbundling(claim, lines)
        assert finding is not None
        assert finding.itemized_package_uplift_try == pytest.approx(2000.0)
        assert finding.heuristic_savings_try == pytest.approx(2000.0)
        assert finding.sourced_savings_try == 0.0

    def test_detect_drg_payload_keeps_heuristic_audit_separate(self) -> None:
        claim = _claim()
        lines = [
            _proc(
                is_package_included=True,
                billed_amount_try=Decimal("200"),
                expected_payable_try=Decimal("0"),
            )
        ]
        ctx = PatientClaimContext(
            patient_id="P1",
            claims=(claim,),
            procedure_lines=tuple(lines),
            material_lines=(),
            drug_lines=(),
            diagnoses=(),
        )
        result = detect_drg_unbundling({"I"}, ctx)
        assert result["has_unbundling_risk"] is True
        assert result["total_potential_savings"] == 0.0
        assert result["chapter_analysis"][0]["heuristic_savings_try"] > 0
        assert "total_heuristic_savings" not in result
        assert "has_heuristic_savings" not in result

    def test_session_violations_skipped_when_same_incision_unknown(self) -> None:
        claim = _claim()
        session_day = date(2026, 1, 10)
        lines = [
            _proc(
                procedure_line_id="PL1",
                procedure_code="610070",
                procedure_date=session_day,
                billed_amount_try=Decimal("1000"),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="609270",
                procedure_date=session_day,
                billed_amount_try=Decimal("1000"),
            ),
        ]
        finding = analyze_claim_unbundling(claim, lines)
        assert finding is not None
        assert finding.session_violations == []

    @pytest.mark.parametrize(
        "category, rule_id, risk",
        [
            # Hizmet başı: §2.2.2.A(5) 30 %; both codes are also EK-2/C packages.
            ("islem", "2.2.2.A.(5)", 700.0),
            # Billed as packages: §2.2.2.B(3)(a) 25 %.
            ("paket", "2.2.2.B.a", 750.0),
        ],
    )
    def test_detects_session_point_overbilling(self, category, rule_id, risk) -> None:
        claim = _claim()
        session_day = date(2026, 1, 10)
        lines = [
            _proc(
                procedure_line_id="PL1",
                procedure_code="610070",
                procedure_category=category,
                procedure_date=session_day,
                billed_amount_try=Decimal("1000"),
                procedure_specialty_code="cerrahi",
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="609270",
                procedure_category=category,
                procedure_date=session_day,
                billed_amount_try=Decimal("1000"),
                procedure_specialty_code="cerrahi",
            ),
        ]
        finding = analyze_claim_unbundling(claim, lines, same_incision=True)
        assert finding is not None
        assert len(finding.session_violations) == 1
        assert finding.session_violations[0]["rule_id"] == rule_id
        assert finding.session_violations[0]["procedure_code"] == "610070"
        assert finding.session_violations[0]["risk_amount_try"] == pytest.approx(risk, rel=0.01)

    def test_detects_payment_method_mismatch(self) -> None:
        claim = _claim(facility_tier="2_basamak_kamu")
        lines = [
            _proc(
                procedure_code="610070",
                procedure_category="islem",
                billed_amount_try=Decimal("1000"),
            )
        ]
        finding = analyze_claim_unbundling(claim, lines)
        assert finding is not None
        assert len(finding.payment_method_violations) == 1
        assert finding.payment_method_violations[0]["mandated_method"] == "package"

    def test_tier_3_non_star_itemized_is_permitted(self) -> None:
        claim = _claim(facility_tier="egitim_arastirma")
        lines = [
            _proc(
                procedure_code="600150",
                procedure_category="islem",
                billed_amount_try=Decimal("1000"),
            )
        ]
        finding = analyze_claim_unbundling(claim, lines)
        assert finding is not None
        assert finding.payment_method_violations == []

    def test_detect_drg_unbundling_exposes_patient_icd10_chapters(self) -> None:
        claim = _claim(primary_icd10="I21.9")
        ctx = PatientClaimContext(
            patient_id="P1",
            claims=(claim,),
            procedure_lines=(),
            material_lines=(),
            drug_lines=(),
            diagnoses=(),
        )
        result = detect_drg_unbundling({"I", "E"}, ctx)
        assert result["patient_icd10_chapters"] == ["E", "I"]
        assert result["n_chapters_analyzed"] == 2

    def test_detect_drg_unbundling_integration(self) -> None:
        claim = _claim()
        lines = [
            _proc(
                procedure_line_id="PL1",
                procedure_code="610070",
                procedure_date=date(2026, 1, 10),
                billed_amount_try=Decimal("1000"),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="609270",
                procedure_date=date(2026, 1, 10),
                billed_amount_try=Decimal("1000"),
            ),
        ]
        ctx = PatientClaimContext(
            patient_id="P1",
            claims=(claim,),
            procedure_lines=tuple(lines),
            material_lines=(),
            drug_lines=(),
            diagnoses=(),
        )
        result = detect_drg_unbundling({"I"}, ctx)
        assert result["exactness_status"] == "exact"
        assert result["has_unbundling_risk"] is True
        assert result["session_violations"] >= 1
        assert "prose_rules/drg_unbundling" in result["rule_source"]

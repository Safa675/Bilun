"""Unit tests for prose-rule DRG unbundling analysis."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.optimization.unbundling import detect_drg_unbundling
from src.bilun.domain.prose_rules.drg_unbundling import analyze_claim_unbundling
from src.bilun.domain.claims.patient_context import PatientClaimContext
from tests.unit._helpers.catalog_prices import list_text

pytestmark = pytest.mark.unit

# 610070 and 609270 at their EK-2/B (hizmet başı) and EK-2/C (package) list prices on the session day, read from the
# curated catalog histories.
_SESSION_DAY = "2026-01-10"
_EK2B_610070, _EK2B_609270 = list_text("610070", _SESSION_DAY), list_text("609270", _SESSION_DAY)
_EK2C_610070, _EK2C_609270 = list_text("P610070", _SESSION_DAY), list_text("P609270", _SESSION_DAY)


def _above(listed: str, factor: str) -> float:
    """What a line billed in full at ``listed`` holds above ``factor`` of it."""
    price = Decimal(listed)
    return float(price - (price * Decimal(factor)).quantize(Decimal("0.01"), rounding="ROUND_HALF_UP"))


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
                # Another day: no §2.2.2 session with PL1 (sessions are always read).
                procedure_date=date(2026, 1, 11),
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
        # A package claim by its codes (P610070 billed as the package): the
        # synthetic package_candidate flag is no longer read (review item 3).
        lines = [
            _proc(procedure_line_id="PKG", procedure_code="P610070", procedure_category="paket"),
            _proc(
                is_package_included=True,
                billed_amount_try=Decimal("200"),
                expected_payable_try=Decimal("0"),
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
        assert result["has_unbundling_risk"] is True
        assert result["total_potential_savings"] == 0.0
        assert result["chapter_analysis"][0]["heuristic_savings_try"] > 0
        assert "total_heuristic_savings" not in result
        assert "has_heuristic_savings" not in result

    def test_unknown_incision_and_branch_take_the_most_lenient_reading(self) -> None:
        # Safa 2026-10-16: unknown incision → lenient reading. No line shows the
        # incision or a branch: money only above A(5)(b) 50 % + 25 points (75 %);
        # the 30 % of one incision in one branch is a 0-TL review (was: skipped).
        # Both billed in full at their EK-2/B list on the day (#300: the list, not
        # the unit price, is the base): 610070 against 75 % of it.
        claim = _claim()
        session_day = date(2026, 1, 10)
        lines = [
            _proc(
                procedure_line_id="PL1",
                procedure_code="610070",
                procedure_date=session_day,
                unit_price_try=Decimal(_EK2B_610070),
                billed_amount_try=Decimal(_EK2B_610070),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="609270",
                procedure_date=session_day,
                unit_price_try=Decimal(_EK2B_609270),
                billed_amount_try=Decimal(_EK2B_609270),
            ),
        ]
        finding = analyze_claim_unbundling(claim, lines)
        assert finding is not None
        assert [
            (r["procedure_code"], r["expected_point_factor"], r["risk_amount_try"],
             r["review_risk_try"], r["missing_facts"])
            for r in finding.session_violations
        ] == [("610070", 0.75, _above(_EK2B_610070, "0.75"), _above(_EK2B_610070, "0.55"), ["kesi", "branş"])]
        assert finding.session_reviews == []
        assert finding.sourced_savings_try == _above(_EK2B_610070, "0.75")

    @pytest.mark.parametrize(
        "category, rule_id, lists, risk",
        [
            # Hizmet başı: §2.2.2.A(5) 30 %; both codes are also EK-2/C packages.
            # 70 % of 610070's EK-2/B list (was 70 % of a unit price of 1,000).
            ("islem", "2.2.2.A.(5)", (_EK2B_610070, _EK2B_609270), _above(_EK2B_610070, "0.30")),
            # Billed as packages: §2.2.2.B(3)(a) 25 %, 75 % of the EK-2/C list.
            ("paket", "2.2.2.B.a", (_EK2C_610070, _EK2C_609270), _above(_EK2C_610070, "0.25")),
        ],
    )
    def test_detects_session_point_overbilling(self, category, rule_id, lists, risk) -> None:
        claim = _claim()
        session_day = date(2026, 1, 10)
        lines = [
            _proc(
                procedure_line_id="PL1",
                procedure_code="610070",
                procedure_category=category,
                procedure_date=session_day,
                unit_price_try=Decimal(lists[0]),
                billed_amount_try=Decimal(lists[0]),
                procedure_specialty_code="cerrahi",
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="609270",
                procedure_category=category,
                procedure_date=session_day,
                unit_price_try=Decimal(lists[1]),
                billed_amount_try=Decimal(lists[1]),
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
        # A package claim by its codes: P609270 billed as the package, 610070
        # hizmet başı next to it (§2.2.2.B(3)(c), 30 %). Two hizmet başı lines a
        # third-tier hospital may bill that way are no package claim (review
        # item 3: the package_candidate flag is no longer read). Each is billed in
        # full at its list on the day (#300: the list, not the unit price).
        lines = [
            _proc(
                procedure_line_id="PL1",
                procedure_code="610070",
                procedure_date=date(2026, 1, 10),
                unit_price_try=Decimal(_EK2B_610070),
                billed_amount_try=Decimal(_EK2B_610070),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="P609270",
                procedure_category="paket",
                procedure_date=date(2026, 1, 10),
                unit_price_try=Decimal(_EK2C_609270),
                billed_amount_try=Decimal(_EK2C_609270),
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

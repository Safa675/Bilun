"""Phase 1.2 — DRG itemized-vs-package uplift wiring and de-dupe."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.claim_drg_uplift import recommend_drg_uplift_from_claims
from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext

pytestmark = pytest.mark.unit


def _claim(**overrides) -> ClaimHeader:
    base = dict(
        claim_id="CLM1",
        patient_id="P1",
        episode_id="E1",
        claim_type="yatis",
        facility_tier="egitim_arastirma",
        provider_type="Kamu",
        department="cardiology",
        admission_date=date(2026, 1, 10),
        discharge_date=date(2026, 1, 12),
        claim_start_date=date(2026, 1, 10),
        claim_end_date=date(2026, 1, 12),
        primary_icd10="I21.9",
        package_candidate=False,
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
        procedure_code="600150",
        procedure_name="Test procedure",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
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


def _ctx(claim: ClaimHeader, *lines: ProcedureClaimLine) -> PatientClaimContext:
    return PatientClaimContext(
        patient_id=claim.patient_id,
        claims=(claim,),
        procedure_lines=tuple(lines),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


def _patch_overridable_payment_methods(monkeypatch) -> None:
    from src.bilun.domain.prose_rules.types import PaymentMethodResult, ProseRuleTrace

    def _resolve(code, **_kwargs):
        method = "package" if str(code).startswith("P") else "itemized"
        return PaymentMethodResult(
            procedure_code=code,
            payment_method=method,
            kind="DRG_OVERRIDABLE",
            in_ek2b=True,
            in_ek2c=str(code).startswith("P"),
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
        "src.bilun.domain.billing.claim_strategy.resolve_payment_method",
        _resolve,
    )
    monkeypatch.setattr(
        "src.bilun.domain.prose_rules.drg_unbundling.resolve_payment_method",
        _resolve,
    )


class TestDrgUpliftWiring:
    @pytest.mark.parametrize("package_amount, expected_uplift", [("1100", 0.0), ("1000", 30.0)])
    def test_secondary_own_payable_controls_itemized_uplift(
        self, monkeypatch, package_amount, expected_uplift,
    ) -> None:
        from src.bilun.domain.billing import claim_strategy
        from src.bilun.domain.prose_rules import payment_method, session_pricing

        _patch_overridable_payment_methods(monkeypatch)
        monkeypatch.setattr(
            payment_method, "resolve_payment_method", claim_strategy.resolve_payment_method,
        )
        monkeypatch.setattr(
            session_pricing, "procedure_annex_membership", lambda code, **kwargs: (True, False),
        )
        monkeypatch.setattr(
            session_pricing, "_procedure_point_score",
            lambda code, **kwargs: {"111111": 20, "222222": 10}[code],
        )
        claim = _claim(package_candidate=False)
        lines = [
            _proc(
                procedure_code="111111",
                procedure_specialty_code="same-specialty",
                expected_payable_try=Decimal("1000"),
                billed_amount_try=Decimal("1000"),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="222222",
                procedure_specialty_code="same-specialty",
                unit_price_try=Decimal("100"),
                expected_payable_try=Decimal("100"),
                billed_amount_try=Decimal("100"),
            ),
            _proc(
                procedure_line_id="PL3",
                procedure_code="P333333",
                procedure_category="paket",
                unit_price_try=Decimal(package_amount),
                expected_payable_try=Decimal(package_amount),
                billed_amount_try=Decimal(package_amount),
            ),
        ]

        drg = recommend_drg_uplift_from_claims(_ctx(claim, *lines))

        assert drg.confirmed_uplift_try == expected_uplift
        if expected_uplift == 0.0:
            assert drg.opportunities == []
        else:
            assert len(drg.opportunities) == 1
            opportunity = drg.opportunities[0]
            assert opportunity["current_billing"] == "package"
            assert opportunity["itemized_raw_try"] == 1100.0
            assert opportunity["itemized_total_try"] == 1030.0
            assert opportunity["package_total_try"] == float(package_amount)
            assert opportunity["gross_uplift_try"] == 30.0
            assert opportunity["recoverable_uplift_try"] == 30.0
            assert opportunity["itemized_price_methodology"] == "session_adjusted"

    def test_non_package_candidate_uplift_counts_in_sgk_headline(
        self, monkeypatch
    ) -> None:
        _patch_overridable_payment_methods(monkeypatch)
        claim = _claim(package_candidate=False)
        lines = [
            _proc(
                procedure_code="600150",
                procedure_category="islem",
                expected_payable_try=Decimal("3000"),
                billed_amount_try=Decimal("3000"),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="P617610",
                procedure_category="paket",
                expected_payable_try=Decimal("1000"),
                billed_amount_try=Decimal("1000"),
            ),
        ]
        ctx = _ctx(claim, *lines)
        drg = recommend_drg_uplift_from_claims(ctx)
        assert len(drg.opportunities) == 1
        assert drg.confirmed_uplift_try > 0
        assert drg.opportunities[0]["savings_category"] == "sgk_uplift"

        report = compute_patient_billing_report(
            "P1",
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )
        assert report.drg_uplift.confirmed_uplift_try == drg.confirmed_uplift_try
        assert report.sgk_uplift_try >= drg.confirmed_uplift_try
        assert report.audit_exposure_try >= 0

    def test_drg_mandatory_package_billed_excluded_from_uplift(self) -> None:
        claim = _claim(
            facility_tier="2_basamak_kamu",
            package_candidate=True,
        )
        lines = [
            _proc(
                procedure_code="610070",
                procedure_category="islem",
                expected_payable_try=Decimal("5000"),
                billed_amount_try=Decimal("5000"),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="P617610",
                procedure_category="paket",
                expected_payable_try=Decimal("1000"),
                billed_amount_try=Decimal("1000"),
            ),
        ]
        drg = recommend_drg_uplift_from_claims(_ctx(claim, *lines))
        assert drg.opportunities == []
        assert drg.confirmed_uplift_try == 0.0

    def test_skips_when_strategy_already_counts_claim(self) -> None:
        claim = _claim(package_candidate=True)
        lines = [
            _proc(
                procedure_code="600150",
                expected_payable_try=Decimal("3000"),
                billed_amount_try=Decimal("3000"),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="P617610",
                procedure_category="paket",
                expected_payable_try=Decimal("1000"),
                billed_amount_try=Decimal("1000"),
            ),
        ]
        strategy_recs = [
            {
                "claim_id": "CLM1",
                "recommendation_kind": "optional_override",
                "savings_try": 500.0,
            }
        ]
        drg = recommend_drg_uplift_from_claims(
            _ctx(claim, *lines),
            strategy_recommendations=strategy_recs,
        )
        assert drg.opportunities == []

    def test_session_confirmed_deduped_from_drg_uplift(self, monkeypatch) -> None:
        _patch_overridable_payment_methods(monkeypatch)
        claim = _claim(package_candidate=False)
        lines = [
            _proc(
                procedure_code="600150",
                expected_payable_try=Decimal("3000"),
                billed_amount_try=Decimal("3000"),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="P617610",
                procedure_category="paket",
                expected_payable_try=Decimal("1000"),
                billed_amount_try=Decimal("1000"),
            ),
        ]
        session_rows = [
            {
                "claim_id": "CLM1",
                "recoverable_uplift_try": 500.0,
                "included_in_sgk_total": True,
            }
        ]
        drg = recommend_drg_uplift_from_claims(
            _ctx(claim, *lines),
            session_opportunities=session_rows,
        )
        assert len(drg.opportunities) == 1
        gross = drg.opportunities[0]["gross_uplift_try"]
        assert drg.opportunities[0]["deduped_session_try"] == pytest.approx(
            min(500.0, gross)
        )
        assert drg.confirmed_uplift_try == pytest.approx(max(0.0, gross - 500.0))

    def test_package_total_uses_ek2c_when_claim_line_payable_zero(
        self, monkeypatch
    ) -> None:
        def _ek2c_entry(code, *, as_of_date=None):
            if str(code) == "609270":
                return {"price_try": 1000.0}
            return None

        monkeypatch.setattr(
            "src.bilun.domain.billing.claim_strategy.get_ek2c_entry",
            _ek2c_entry,
        )
        claim = _claim(
            facility_tier="egitim_arastirma",
            package_candidate=False,
        )
        lines = [
            _proc(
                procedure_code="600150",
                expected_payable_try=Decimal("4000"),
                billed_amount_try=Decimal("4000"),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="609270",
                procedure_category="paket",
                expected_payable_try=Decimal("0"),
                billed_amount_try=Decimal("3500"),
            ),
        ]
        drg = recommend_drg_uplift_from_claims(_ctx(claim, *lines))
        assert drg.confirmed_uplift_try > 0
        assert drg.opportunities[0]["package_price_methodology"] == "ek2c_code"
        assert drg.opportunities[0]["package_total_try"] == pytest.approx(1000.0)

    def test_sentetik_0001_mandatory_claim_not_in_drg_uplift(self) -> None:
        from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset

        dataset = load_sut_claim_dataset()
        ctx = build_patient_claim_context("SENTETIK-HASTA-0001", dataset)
        assert ctx is not None

        report = compute_patient_billing_report(
            "SENTETIK-HASTA-0001",
            claim_context=ctx,
            copay_exemption={"exempt": False},
        )
        assert report.drg_uplift.confirmed_uplift_try == 0.0
        assert report.session_uplift.confirmed_uplift_try == 0.0

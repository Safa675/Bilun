"""Tests for billing honest-gap integrity (no fabricated TRY in heuristics)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


def test_drug_optimizer_does_not_fabricate_tier_savings(monkeypatch) -> None:
    from src.bilun.domain.billing import drug as drug_mod

    record = {
        "drug_name": "Brand Drug 100 mg",
        "equivalence_group": "EQ-001",
        "discount_status": "REFERANS",
        "discount_tier_1": 0.40,
        "passivation_date": "",
    }
    cheaper_alt = {
        "drug_name": "Generic Drug 100 mg",
        "equivalence_group": "EQ-001",
        "discount_status": "ESDEĞER",
        "discount_tier_1": 0.10,
        "passivation_date": "",
    }

    monkeypatch.setattr(
        drug_mod,
        "lookup_drug_bulk",
        lambda names: {names[0]: record},
    )
    monkeypatch.setattr(
        drug_mod,
        "_get_ek4a_by_equiv_group",
        lambda: {"EQ-001": [record, cheaper_alt]},
    )

    result = drug_mod._optimize_drug_costs("P1", ["Brand Drug 100 mg"])

    assert result.generic_substitution_savings == 0.0
    assert len(result.drug_recommendations) == 1
    rec = result.drug_recommendations[0]
    assert rec["issue"] == "generic_available"
    assert rec["savings_try"] is None
    assert rec["savings_try"] != 70.0  # old basic/specialty midpoint delta


def test_copay_exemption_adds_non_monetary_insight() -> None:
    from src.bilun.domain.billing.copay import _optimize_copay

    result = _optimize_copay(
        "P1",
        {
            "exempt": True,
            "qualifying_diagnoses": [{"disease": "Diabetes", "range": "E10-E14"}],
        },
    )

    assert result.is_exempt is True
    assert result.total_copay_savings_try == 0.0
    assert result.exactness_status == "missing_exact_inputs"
    assert len(result.rate_corrections) == 1
    correction = result.rate_corrections[0]
    assert "EK-1A exemption may apply" in correction["detail"]
    assert "Diabetes" in correction["detail"]
    assert "copay_component_try" not in correction
    assert "billed_try" not in correction


def test_materials_heuristic_path_skips_global_preauth_dump() -> None:
    from src.bilun.domain.billing.materials import _precheck_materials

    result = _precheck_materials("P1", {"I"})

    assert result.pre_auth_required == []
    assert result.miat_restricted == []
    assert result.gazette_ceiling_by_specialty
    assert any(spec.startswith("EK-3") for spec in result.gazette_ceiling_by_specialty)


def test_strategy_adds_chapter_review_without_try() -> None:
    from src.bilun.domain.billing.strategy import _recommend_billing_strategy

    result = _recommend_billing_strategy("P1", {"I", "C"})

    assert result.exactness_status == "missing_exact_inputs"
    assert result.total_savings == 0.0
    assert len(result.recommendations) == 2
    for rec in result.recommendations:
        assert rec["recommendation"] == "review_package_eligibility"
        assert rec["savings_try"] is None


def test_orchestrator_total_includes_only_exact_blocks(monkeypatch) -> None:
    import src.bilun.domain.billing.orchestrator as billing_mod

    monkeypatch.setattr(
        billing_mod,
        "_optimize_lab_billing",
        lambda *_args, **_kwargs: SimpleNamespace(
            total_savings=10.0,
            flagged_tests=[],
            exactness_status="exact",
            required_inputs_missing=[],
        ),
    )
    monkeypatch.setattr(
        billing_mod,
        "_optimize_drug_costs",
        lambda *_args, **_kwargs: SimpleNamespace(
            total_savings=999.0,
            drug_recommendations=[{"drug_name": "X"}],
            exactness_status="missing_exact_inputs",
            required_inputs_missing=["dispensed_drug_claim_lines"],
        ),
    )
    monkeypatch.setattr(
        billing_mod,
        "_optimize_copay",
        lambda *_args, **_kwargs: SimpleNamespace(
            total_copay_savings_try=5.0,
            is_exempt=False,
            exactness_status="exact",
            required_inputs_missing=[],
        ),
    )
    monkeypatch.setattr(
        billing_mod,
        "_recommend_billing_strategy",
        lambda *_args, **_kwargs: SimpleNamespace(
            recommendations=[],
            exactness_status="missing_exact_inputs",
            unavailable_reason="Needs exact claim lines.",
            required_inputs_missing=["itemized_billed_procedure_lines"],
            total_savings=0.0,
        ),
    )
    monkeypatch.setattr(
        billing_mod,
        "_precheck_materials",
        lambda *_args, **_kwargs: SimpleNamespace(
            pre_auth_required=[],
            miat_restricted=[],
            exactness_status="partial_exact",
            required_inputs_missing=["billed_material_codes"],
        ),
    )

    report = billing_mod.compute_patient_billing_report("P1", chapters={"I"})

    assert report.total_recoverable_try == 15.0

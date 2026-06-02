"""Tests for billing bugfixes: per-visit lab grouping and copay/drug dedupe."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


def test_lab_duplicate_detection_groups_by_visit_not_patient_history() -> None:
    from src.bilun.domain.billing.lab import _optimize_lab_billing

    tests = ["glucose", "glucose", "glucose", "glucose"]
    visit_ids = ["V1", "V2", "V3", "V4"]

    result = _optimize_lab_billing(
        "P1",
        tests,
        patient_lab_visit_ids=visit_ids,
    )

    assert result.duplicate_test_savings == 0.0
    assert not any(flag["flag_type"] == "duplicate_test" for flag in result.flagged_tests)


def test_lab_duplicate_detection_without_visit_ids_skips_duplicate_review() -> None:
    from src.bilun.domain.billing.lab import _optimize_lab_billing

    tests = ["glucose", "glucose", "glucose", "glucose"]

    result = _optimize_lab_billing("P1", tests)

    assert result.duplicate_test_savings == 0.0
    assert not any(
        flag["flag_type"] == "clinical_review_duplicate" for flag in result.flagged_tests
    )


def test_lab_duplicate_detection_flags_within_same_visit() -> None:
    from src.bilun.domain.billing.lab import _optimize_lab_billing

    tests = ["glucose", "glucose", "glucose"]
    visit_ids = ["V1", "V1", "V1"]

    result = _optimize_lab_billing(
        "P1",
        tests,
        patient_lab_visit_ids=visit_ids,
    )

    assert result.duplicate_test_savings == 0.0
    dup_flags = [
        flag for flag in result.flagged_tests if flag["flag_type"] == "clinical_review_duplicate"
    ]
    assert len(dup_flags) == 1
    assert dup_flags[0]["savings_try"] is None
    assert "encounter V1" in dup_flags[0]["detail"]
    assert "clinical review" in dup_flags[0]["detail"].lower()


def test_lab_hemogram_bundling_groups_by_visit_id() -> None:
    from src.bilun.domain.billing.lab import _optimize_lab_billing

    tests = ["Hemoglobin", "Hematokrit", "Hemoglobin", "Hematokrit"]
    visit_ids = ["V1", "V2", "V3", "V4"]

    result = _optimize_lab_billing(
        "P1",
        tests,
        patient_lab_visit_ids=visit_ids,
    )

    assert result.hemogram_bundling_savings == 0.0


def test_lab_hemogram_bundling_flags_excess_within_visit() -> None:
    from src.bilun.domain.billing.lab import _optimize_lab_billing

    tests = ["Hemoglobin", "Hematokrit", "Hemoglobin"]
    visit_ids = ["V1", "V1", "V1"]

    result = _optimize_lab_billing(
        "P1",
        tests,
        patient_lab_visit_ids=visit_ids,
    )

    assert result.hemogram_bundling_savings > 0.0


def test_copay_total_excludes_rx_component() -> None:
    from src.bilun.domain.billing.claim_copay import optimize_copay_from_claims

    ctx = SimpleNamespace(
        procedure_lines=[
            SimpleNamespace(
                copay_rate_applicable=True,
                procedure_code="P001",
                procedure_name="Visit proc",
                billed_amount_try=Decimal("100"),
                expected_payable_try=Decimal("80"),
            )
        ],
        drug_lines=[
            SimpleNamespace(
                billed_amount_try=Decimal("50"),
                expected_payable_try=Decimal("40"),
            )
        ],
    )

    result = optimize_copay_from_claims(
        ctx,
        {"exempt": True, "qualifying_diagnoses": [{"disease": "Diabetes", "range": "E10-E14"}]},
    )

    assert result.visit_copay_savings_try == 20.0
    assert result.rx_copay_savings_try == 10.0
    assert result.total_copay_savings_try == 20.0


def test_exempt_drug_claims_exclude_copay_waiver_from_tier_savings() -> None:
    from src.bilun.domain.billing.drug_claims import optimize_drug_from_claims

    ctx = SimpleNamespace(
        patient_id="P1",
        drug_lines=[
            SimpleNamespace(
                drug_name="Drug A",
                drug_code="D001",
                drug_claim_line_id="DL1",
                billed_amount_try=Decimal("100"),
                expected_payable_try=Decimal("80"),
                discount_tier_expected=Decimal("0.20"),
            )
        ],
    )

    result = optimize_drug_from_claims(ctx, is_exempt=True)

    assert result.generic_substitution_savings == 0.0
    assert not any(rec.get("issue") == "discount_tier_applied" for rec in result.drug_recommendations)


def test_orchestrator_recoverable_total_counts_rx_once_with_visit_copay(monkeypatch) -> None:
    import src.bilun.domain.billing.orchestrator as billing_mod

    monkeypatch.setattr(
        billing_mod,
        "_optimize_lab_billing",
        lambda *_args, **_kwargs: SimpleNamespace(
            total_savings=0.0,
            flagged_tests=[],
            exactness_status="exact",
            required_inputs_missing=[],
        ),
    )
    monkeypatch.setattr(
        billing_mod,
        "optimize_drug_from_claims",
        lambda *_args, **_kwargs: SimpleNamespace(
            total_savings=0.0,
            drug_recommendations=[],
            exactness_status="exact",
            required_inputs_missing=[],
        ),
    )
    monkeypatch.setattr(
        billing_mod,
        "_optimize_copay",
        lambda *_args, **_kwargs: SimpleNamespace(
            total_copay_savings_try=20.0,
            rx_copay_savings_try=10.0,
            is_exempt=True,
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
            total_savings=0.0,
            required_inputs_missing=["itemized_billed_procedure_lines"],
        ),
    )
    monkeypatch.setattr(
        billing_mod,
        "_precheck_materials",
        lambda *_args, **_kwargs: SimpleNamespace(
            pre_auth_required=[],
            miat_restricted=[],
            miat_interval_violations=[],
            bundled_separate_billing=[],
            exactness_status="partial_exact",
            required_inputs_missing=["billed_material_codes"],
        ),
    )

    report = billing_mod.compute_patient_billing_report("P1", chapters={"I"})

    assert report.total_recoverable_try == 30.0

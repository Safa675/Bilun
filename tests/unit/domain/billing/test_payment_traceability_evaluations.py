"""Payment-rule metadata follows the existing predicate and stays information only."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing import payment_traceability_evaluations as payment_adapter
from src.bilun.domain.billing.payment_traceability_evaluations import (
    _evaluate_condition,
    evaluate_payment_method_traceability,
)
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.payment_method import (
    check_payment_method_traceability_for_context,
    load_payment_method_rules,
)

pytestmark = pytest.mark.unit
_DAY = date(2026, 1, 1)


def _header(claim_id: str, *, provider_type: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id=f"E-{claim_id}",
        claim_type="ayakta",
        facility_tier="ozel",
        provider_type=provider_type,
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


def _procedure(claim_id: str) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=f"L-{claim_id}",
        claim_id=claim_id,
        patient_id="P1",
        episode_id=f"E-{claim_id}",
        procedure_date=_DAY,
        procedure_code="999999999",
        procedure_name="Synthetic procedure outside the annex",
        procedure_category="examination",
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


def _context() -> PatientClaimContext:
    return PatientClaimContext(
        patient_id="P1",
        claims=(
            _header("C1", provider_type="workplace_health_or_polyclinic_or_homecare_center"),
            _header("C2", provider_type="private"),
        ),
        procedure_lines=(_procedure("C2"),),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


def test_all_42_authored_ids_are_evaluated_at_each_real_claim_scope() -> None:
    ctx = _context()
    batch = evaluate_payment_method_traceability("P1", ctx)
    authored_ids = {row["rule_id"] for row in load_payment_method_rules()["rules"]}

    assert len(authored_ids) == 42
    assert len(batch.evaluations) == 84
    assert len({row.evaluation_id for row in batch.evaluations}) == 84
    for claim_id in ("C1", "C2"):
        claim_rows = [row for row in batch.evaluations if row.claim_id == claim_id]
        assert {row.rule_id for row in claim_rows} == authored_ids
        assert all(row.patient_id == "P1" for row in claim_rows)

        # Matched rows retain the old payload exactly, including info severity,
        # raw billable, and raw material_outcome, while claim identity stays on
        # the typed wrapper rather than changing legacy row shape.
        legacy = check_payment_method_traceability_for_context(ctx.slice_for_claim(claim_id))
        assert [
            match.legacy_row for match in batch.legacy_rows if match.claim_id == claim_id
        ] == legacy
        assert {match.rule_id for match in batch.matches if match.claim_id == claim_id} <= {
            row["rule_id"] for row in legacy
        }
        assert all(
            match.candidate_classification == "information_only"
            and match.source_file.endswith("payment_method_2_2.json")
            and match.source_locators
            for match in batch.matches
            if match.claim_id == claim_id
        )


def test_match_clean_nonmatch_missing_and_unsupported_are_distinct() -> None:
    batch = evaluate_payment_method_traceability("P1", _context())
    by_key = {(row.claim_id, row.rule_id): row for row in batch.evaluations}

    no_pay_id = "2.2.(6).workplace_polyclinic_homecare_no_pay"
    no_pay = by_key["C1", no_pay_id]
    assert (no_pay.evaluation_status, no_pay.decision) == ("evaluated", "matched")
    matched = next(
        match for match in batch.matches if match.claim_id == "C1" and match.rule_id == no_pay_id
    )
    assert matched.legacy_row["billable"] is False
    assert matched.legacy_row["material_outcome"] == "no_pay"
    assert matched.legacy_row["severity"] == "info"
    assert matched.candidate_classification == "information_only"

    cap = by_key["C1", "2.2.1.B-1.(11).private_daily_visit_cap"]
    assert (cap.evaluation_status, cap.decision) == ("evaluated", "not_matched")
    assert by_key["C2", cap.rule_id].decision == "matched"

    missing = by_key["C1", "2.2.(12).no_pay_without_documentation"]
    assert missing.evaluation_status == "missing_inputs"
    assert missing.decision is None
    assert missing.missing_inputs == ["provider_contract_status"]

    unsupported = by_key["C1", "2.2.1.B-1.(6).followup_specialty_no_visit_fee"]
    assert unsupported.evaluation_status == "unavailable"
    assert unsupported.decision is None
    assert "unsupported predicate: visit_sequence" in (unsupported.reason or "")

    annex_id = "2.2.1.B-1.a"
    assert by_key["C1", annex_id].evaluation_status == "missing_inputs"
    assert by_key["C1", annex_id].missing_inputs == ["procedure_code"]
    assert by_key["C2", annex_id].evaluation_status == "unavailable"
    assert "annex membership not confirmed" in (by_key["C2", annex_id].reason or "")


def test_absent_claim_context_accounts_for_every_authored_id() -> None:
    batch = evaluate_payment_method_traceability("P1", None)
    assert len(batch.evaluations) == 42
    assert not batch.matches
    assert not batch.legacy_rows
    assert all(
        row.claim_id is None
        and row.evaluation_status == "missing_inputs"
        and row.missing_inputs == ["claim_context"]
        for row in batch.evaluations
    )


def test_context_cannot_be_attributed_to_a_different_patient() -> None:
    with pytest.raises(ValueError, match="another patient"):
        evaluate_payment_method_traceability("P2", _context())

    ctx = _context()
    foreign_header = replace(ctx.claims[0], patient_id="P2")
    with pytest.raises(ValueError, match="another patient"):
        evaluate_payment_method_traceability(
            "P1", replace(ctx, claims=(foreign_header, ctx.claims[1]))
        )


@pytest.mark.parametrize(
    ("header_change", "rule_id", "expected_status", "missing"),
    [
        (
            {"claim_type": ""},
            "2.2.1.B-1.(11).private_daily_visit_cap",
            "missing_inputs",
            ["claim_type"],
        ),
        ({"claim_type": "unknown"}, "2.2.1.B-1.(11).private_daily_visit_cap", "unavailable", []),
        (
            {"provider_type": ""},
            "2.2.1.B-1.(11).private_daily_visit_cap",
            "missing_inputs",
            ["provider_type"],
        ),
    ],
)
def test_raw_header_gates_metadata_but_retains_legacy_rows(
    header_change: dict[str, str], rule_id: str, expected_status: str, missing: list[str]
) -> None:
    original = _context().slice_for_claim("C2")
    assert original is not None
    changed = replace(original, claims=(replace(original.claims[0], **header_change),))
    batch = evaluate_payment_method_traceability("P1", changed)
    evaluation = next(row for row in batch.evaluations if row.rule_id == rule_id)
    assert evaluation.evaluation_status == expected_status
    assert evaluation.decision is None
    assert evaluation.missing_inputs == missing
    assert not any(row.rule_id == rule_id for row in batch.matches)
    assert [row.legacy_row for row in batch.legacy_rows] == (
        check_payment_method_traceability_for_context(changed)
    )
    if header_change == {"claim_type": ""}:
        assert any(row.rule_id == rule_id for row in batch.legacy_rows)


def test_validated_catalog_source_view_is_cached_once_per_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_loader = payment_adapter.load_broad_rule_catalog
    calls = 0

    def counted_loader():
        nonlocal calls
        calls += 1
        return original_loader()

    payment_adapter._payment_catalog_sources.cache_clear()
    monkeypatch.setattr(payment_adapter, "load_broad_rule_catalog", counted_loader)
    try:
        evaluate_payment_method_traceability("P1", _context())
        evaluate_payment_method_traceability("P1", _context())
        assert calls == 1
        with pytest.raises(TypeError):
            payment_adapter._payment_catalog_sources()["new_rule"] = ("file", ())
    finally:
        payment_adapter._payment_catalog_sources.cache_clear()


def test_catalog_validation_failure_blocks_first_adapter_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def corrupt_catalog():
        raise ValueError("Broad prose authored identity sequence changed")

    payment_adapter._payment_catalog_sources.cache_clear()
    monkeypatch.setattr(payment_adapter, "load_broad_rule_catalog", corrupt_catalog)
    try:
        with pytest.raises(ValueError, match="authored identity sequence changed"):
            evaluate_payment_method_traceability("P1", _context())
    finally:
        payment_adapter._payment_catalog_sources.cache_clear()


@pytest.mark.parametrize(
    ("condition", "flat_context", "decision", "missing"),
    [
        ({"procedure_code_any": ["A"]}, {"procedure_code": "A"}, "matched", []),
        ({"procedure_code_any": ["B"]}, {"procedure_code": "A"}, "not_matched", []),
        ({"procedure_code_any": ["A"]}, {}, "missing_inputs", ["procedure_code_any"]),
        ({"procedure_category": "ftr"}, {"procedure_category_any": ["ftr"]}, "matched", []),
        (
            {"procedure_category": "ftr"},
            {"procedure_category_any": ["imaging"]},
            "not_matched",
            [],
        ),
        ({"invented_scalar": "x"}, {"invented_scalar": "x"}, "unavailable", []),
        ({"documentation_on_request": False}, {}, "missing_inputs", ["documentation_on_request"]),
        (
            {"care_setting": "inpatient", "invented_scalar": "x"},
            {"care_setting": "outpatient"},
            "not_matched",
            [],
        ),
        (
            {"invented_scalar": "x", "care_setting": "inpatient"},
            {"care_setting": "outpatient"},
            "unavailable",
            [],
        ),
    ],
)
def test_statuses_follow_existing_predicate_fallback_reads(
    condition: dict, flat_context: dict, decision: str, missing: list[str]
) -> None:
    observed_decision, observed_missing, _ = _evaluate_condition(condition, flat_context)
    assert observed_decision == decision
    assert observed_missing == missing

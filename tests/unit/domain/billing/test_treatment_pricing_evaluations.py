"""Treatment observations retain every raw match without certifying proxies."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from src.bilun.domain.billing import treatment_pricing_evaluations as adapter
from src.bilun.domain.billing.broad_rule_catalog import load_broad_rule_catalog
from src.bilun.domain.prose_rules import treatment_pricing as legacy
from tests.unit.domain.prose_rules.test_treatment_pricing_for_context import (
    _make_ctx,
    _make_drug,
    _make_header,
    _make_procedure,
)

pytestmark = pytest.mark.unit
_ROBOTIC = "2.4.4.F-5.(3).robotic_rehab_ek2c_pricing"
_PREFIX = "2.4.4.D-1.(7).hemodialysis_ek2c_pricing"
_SAFE_TRIGGER_KEYS = {
    "procedure_category",
    "procedure_category_any",
    "procedure_code_any",
    "diagnosis_any",
    "diagnosis_in",
    "diagnosis_not_in",
    "provider_type",
}
_TRIGGER_RULES = [
    r
    for r in legacy.load_treatment_pricing_rules()["rules"]
    if set(r["condition"]) <= _SAFE_TRIGGER_KEYS
]


def _context():
    ctx = _make_ctx(header=_make_header(provider_type="private", primary_icd10="N18.9"))
    return replace(
        ctx,
        claims=ctx.claims + (_make_header(claim_id="C2", provider_type="public"),),
        procedure_lines=(
            _make_procedure(code="P5010046", category="hemodialysis"),
            replace(_make_procedure(category="robotic_rehab"), procedure_line_id="PL2"),
            _make_procedure(claim_id="C2", category="post_anesthesia_care", code="999999999"),
        ),
    )


def _row(batch, rule_id, claim_id="C1"):
    return next(r for r in batch.evaluations if r.rule_id == rule_id and r.claim_id == claim_id)


def _assert_raw_parity(batch, ctx):
    for claim in ctx.claims:
        assert [r.legacy_row for r in batch.legacy_rows if r.claim_id == claim.claim_id] == (
            legacy.check_treatment_pricing_for_context(ctx.slice_for_claim(claim.claim_id))
        )


def test_every_authored_identity_has_one_status_per_claim_and_all_raw_matches_remain():
    ctx = _context()
    batch = adapter.evaluate_treatment_pricing("P1", ctx)
    sources = [r for r in load_broad_rule_catalog() if r.family == "treatment_pricing_2_4"]
    assert len(sources) == 202
    assert len(batch.evaluations) == len({r.evaluation_id for r in batch.evaluations}) == 404
    for claim_id in ("C1", "C2"):
        assert {r.rule_id for r in batch.evaluations if r.claim_id == claim_id} == {
            r.rule_id for r in sources
        }
    assert all(set(r.missing_inputs) <= set(r.required_inputs) for r in batch.evaluations)
    assert _row(batch, _PREFIX).decision == "matched"
    assert _row(batch, _PREFIX, "C2").decision == "not_matched"
    assert _row(batch, _ROBOTIC).decision == "matched"
    assert len([r for r in batch.matches if r.claim_id == "C1"]) >= 2
    _assert_raw_parity(batch, ctx)
    for match in batch.matches:
        source = next(r for r in sources if r.rule_id == match.rule_id)
        assert match.authored_action == source.action
        assert match.billable is source.billable
        assert match.source_file == source.source_file
        assert match.source_locators == source.source_locators
        assert match.candidate_classification == source.candidate_classification
        assert not hasattr(match, "risk_amount")


@pytest.mark.parametrize("rule", _TRIGGER_RULES, ids=lambda r: r["rule_id"])
def test_generated_real_field_triggers_preserve_legacy_payload_and_metadata(rule):
    condition = rule["condition"]
    category = (
        condition.get("procedure_category")
        or (condition.get("procedure_category_any") or ["general"])[0]
    )
    code = (condition.get("procedure_code_any") or ["999999999"])[0]
    diagnosis = (condition.get("diagnosis_any") or condition.get("diagnosis_in") or ["Z00.0"])[0]
    ctx = _make_ctx(
        header=_make_header(
            provider_type=condition.get("provider_type", "private"), primary_icd10=diagnosis
        ),
        procedure_lines=(_make_procedure(category=category, code=code),),
    )
    original = legacy.check_treatment_pricing_for_context(ctx)
    assert any(r["rule_id"] == rule["rule_id"] for r in original)
    batch = adapter.evaluate_treatment_pricing("P1", ctx)
    assert _row(batch, rule["rule_id"]).decision == "matched"
    assert [r.legacy_row for r in batch.legacy_rows] == original


@pytest.mark.parametrize("ctx", [None, replace(_context(), claims=(), procedure_lines=())])
def test_absent_context_has_all_202_missing_statuses(ctx):
    batch = adapter.evaluate_treatment_pricing("P1", ctx)
    assert len(batch.evaluations) == 202
    assert all(
        r.evaluation_status == "missing_inputs" and r.claim_id is None for r in batch.evaluations
    )
    assert not batch.matches and not batch.legacy_rows


def test_header_only_claim_accounts_for_all_202_ids_without_fabricated_clinical_data():
    ctx = _make_ctx(header=_make_header(primary_icd10="", provider_type="", facility_tier=""))
    batch = adapter.evaluate_treatment_pricing("P1", ctx)
    assert len(batch.evaluations) == 202
    assert {r.rule_id for r in batch.evaluations} == {
        r["rule_id"] for r in legacy.load_treatment_pricing_rules()["rules"]
    }
    assert not batch.matches
    _assert_raw_parity(batch, ctx)


@pytest.mark.parametrize(
    "key",
    [
        "sessions_per_day",
        "sessions",
        "same_day_physio_rehab",
        "sessions_within_year",
        "sessions_same_region_within_1y",
        "sessions_per_patient_per_year",
        "daily_exams_per_physician",
        "daily_billing_hours_per_physician",
        "days_from_report_to_treatment",
        "diagnosis_category_any",
        "diagnosis_category_not_in",
        "prescriber_specialty_any",
        "supervised_by_pmr_specialty",
        "concomitant_service",
        "billed_with_other_physiotherapy",
        "origin_is_traffic_accident",
    ],
)
def test_documented_proxy_conditions_are_unavailable_even_when_legacy_can_evaluate(key):
    header = _make_header(provider_type="private", primary_icd10="M77.0")
    procedures = (
        replace(_make_procedure(category="physiotherapy_rehab"), procedure_specialty_code="pmr"),
        replace(
            _make_procedure(category="physiotherapy_rehab"),
            procedure_line_id="PL2",
            procedure_specialty_code="pmr",
        ),
        replace(
            _make_procedure(category="muayene"),
            procedure_line_id="PL3",
            procedure_date=header.claim_start_date + timedelta(days=2),
        ),
    )
    ctx = _make_ctx(header=header, procedure_lines=procedures)
    assert key in legacy._build_treatment_pricing_context(ctx) or key == "diagnosis_category_not_in"
    batch = adapter.evaluate_treatment_pricing("P1", ctx)
    affected = [r for r in legacy.load_treatment_pricing_rules()["rules"] if key in r["condition"]]
    assert affected
    for rule in affected:
        assert _row(batch, rule["rule_id"]).evaluation_status == "unavailable"
        assert not any(r.rule_id == rule["rule_id"] for r in batch.matches)
    _assert_raw_parity(batch, ctx)


@pytest.mark.parametrize("board", [None, False, True])
def test_pharmacy_report_flag_does_not_establish_treatment_board_evidence(board):
    ctx = _make_ctx(
        procedure_lines=(_make_procedure(category="thermal_spa"),),
        drug_lines=(_make_drug(board_report=board),),
    )
    batch = adapter.evaluate_treatment_pricing("P1", ctx)
    affected = [
        r
        for r in legacy.load_treatment_pricing_rules()["rules"]
        if set(r["condition"]) & {"health_board_report_present", "health_report_present"}
    ]
    for rule in affected:
        row = _row(batch, rule["rule_id"])
        assert row.evaluation_status in {"missing_inputs", "unavailable"}
        assert row.decision is None
        assert "treatment_board_report" in row.required_inputs
    _assert_raw_parity(batch, ctx)


@pytest.mark.parametrize(
    "tier,status",
    [
        ("", "missing_inputs"),
        ("3", "unavailable"),
        ("ozel", "unavailable"),
        ("third_step_public", "evaluated"),
    ],
)
def test_facility_tier_vocabulary_is_not_guessed(tier, status):
    ctx = _make_ctx(
        header=_make_header(facility_tier=tier),
        procedure_lines=(_make_procedure(category="genetic_metabolic_test"),),
    )
    batch = adapter.evaluate_treatment_pricing("P1", ctx)
    assert _row(batch, "2.4.4.G-1.tier3_public_facility_only").evaluation_status == status
    _assert_raw_parity(batch, ctx)


@pytest.mark.parametrize("actual", [float("nan"), float("inf"), "not numeric"])
def test_invalid_numeric_input_stays_unavailable_without_changing_raw_predicate(actual):
    condition = {"patient_age": {"min": 18}}
    raw, status, _, reason = adapter._observe_condition(condition, {"patient_age": actual})
    assert raw is legacy._condition_matches(condition, {"patient_age": actual})
    assert status == "unavailable"
    assert reason == "invalid_numeric_input"


@pytest.mark.parametrize("actual,matched", [(17, False), (18, True), (19, True)])
def test_numeric_boundary_observation_reuses_original_predicate(actual, matched):
    raw, status, _, _ = adapter._observe_condition(
        {"patient_age": {"min": 18}}, {"patient_age": actual}
    )
    assert raw is matched
    assert status == "evaluated"


def test_missing_annex_and_unknown_shape_do_not_become_clean_negatives(monkeypatch):
    from src.bilun.domain.prose_rules import catalog_membership

    monkeypatch.setattr(catalog_membership, "any_procedure_in_annex", lambda *_: False)
    raw, status, _, reason = adapter._observe_condition(
        {"procedure_in_annex": "EK-2/C"}, {"procedure_code_any": ["999999999"]}
    )
    assert (raw, status, reason) == (False, "unavailable", "annex_membership_not_confirmed")
    raw, status, _, reason = adapter._observe_condition({"not_supported": "value"}, {})
    assert (raw, status, reason) == (False, "unavailable", "unsupported_predicate_shape")


@pytest.mark.parametrize("kind", ["patient", "header", "line", "orphan", "no_headers", "duplicate"])
def test_foreign_or_ambiguous_context_is_rejected(kind):
    ctx = _context()
    if kind == "patient":
        ctx = replace(ctx, patient_id="P2")
    elif kind == "header":
        ctx = replace(ctx, claims=(replace(ctx.claims[0], patient_id="P2"),))
    elif kind == "line":
        ctx = replace(ctx, procedure_lines=(replace(ctx.procedure_lines[0], patient_id="P2"),))
    elif kind == "orphan":
        ctx = replace(ctx, procedure_lines=(replace(ctx.procedure_lines[0], claim_id="other"),))
    elif kind == "no_headers":
        ctx = replace(ctx, claims=())
    else:
        ctx = replace(ctx, claims=ctx.claims + (ctx.claims[0],))
    with pytest.raises(ValueError):
        adapter.evaluate_treatment_pricing("P1", ctx)


def test_catalog_cache_and_mutable_payload_isolation(monkeypatch):
    original = adapter.load_broad_rule_catalog
    calls = 0

    def counted():
        nonlocal calls
        calls += 1
        return original()

    adapter._treatment_catalog_sources.cache_clear()
    monkeypatch.setattr(adapter, "load_broad_rule_catalog", counted)
    try:
        first = adapter.evaluate_treatment_pricing("P1", _context())
        match = next(r for r in first.matches if r.rule_id == _ROBOTIC)
        match.authored_action["billable"] = False
        match.legacy_row["rule_id"] = "corrupted"
        assert all(r.legacy_row["rule_id"] != "corrupted" for r in first.legacy_rows)
        second = adapter.evaluate_treatment_pricing("P1", _context())
        assert (
            next(r for r in second.matches if r.rule_id == _ROBOTIC).authored_action["billable"]
            is True
        )
        assert calls == 1
    finally:
        adapter._treatment_catalog_sources.cache_clear()

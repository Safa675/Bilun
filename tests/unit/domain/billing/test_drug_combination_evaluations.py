"""Claim-local drug combination metadata keeps the original matcher observable."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing import drug_combination_evaluations as adapter
from src.bilun.domain.billing.broad_rule_catalog import load_broad_rule_catalog
from src.bilun.domain.claims.models import ClaimDiagnosis, ClaimHeader, DrugClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules import drug_combination as legacy

pytestmark = pytest.mark.unit
_DAY = date(2026, 7, 10)
_DOAC = "4.2.15.D-1.(4).doac_combo_no_pay"
_EPO = "4.2.9.A.(1).epoetin_out_of_indication"
_PREGABALIN = "4.2.25.(3).pregabalin_2nd_3rd_step"


def _header(claim_id: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id=f"E-{claim_id}",
        claim_type="ayakta",
        facility_tier="second_step",
        provider_type="sozlesmeli",
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


def _drug(claim_id: str, line_id: str, name: str) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id=line_id,
        prescription_id=f"RX-{claim_id}",
        claim_id=claim_id,
        patient_id="P1",
        episode_id=f"E-{claim_id}",
        drug_claim_date=_DAY,
        drug_name=name,
        drug_code="",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("90"),
        discount_tier_expected=Decimal("0"),
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _context() -> PatientClaimContext:
    return PatientClaimContext(
        patient_id="P1",
        claims=(_header("C1"), _header("C2")),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(
            _drug("C2", "D3", "APİKSABAN"),
            _drug("C1", "D1", "PRADAXA (DABIGATRAN)"),
            _drug("C1", "D2", "XARELTO (RIVAROKSABAN)"),
        ),
        diagnoses=(),
    )


def _single(*names: str) -> PatientClaimContext:
    ctx = _context().slice_for_claim("C1")
    assert ctx is not None
    return replace(ctx, drug_lines=tuple(_drug("C1", f"D{i}", n) for i, n in enumerate(names)))


def _evaluation(batch, rule_id: str, claim_id: str = "C1"):
    return next(r for r in batch.evaluations if r.rule_id == rule_id and r.claim_id == claim_id)


def test_all_53_ids_are_accounted_for_per_claim_and_raw_payloads_match() -> None:
    ctx = _context()
    batch = adapter.evaluate_drug_combinations("P1", ctx)
    entries = [r for r in load_broad_rule_catalog() if r.family == "drug_combination_4_2"]
    assert len(entries) == 53
    assert len(batch.evaluations) == 106
    assert len({r.evaluation_id for r in batch.evaluations}) == 106
    for claim_id in ("C1", "C2"):
        assert {r.rule_id for r in batch.evaluations if r.claim_id == claim_id} == {
            r.rule_id for r in entries
        }
    assert [r.legacy_row for r in batch.legacy_rows] == legacy.check_drug_combination_for_context(
        ctx
    )
    assert _evaluation(batch, _DOAC).decision == "matched"
    assert _evaluation(batch, _DOAC, "C2").decision == "not_matched"
    for match in batch.matches:
        source = next(r for r in entries if r.rule_id == match.rule_id)
        assert match.source_file == source.source_file
        assert match.source_locators == source.source_locators
        assert match.authored_action == source.action
        assert match.billable is source.billable
        assert match.candidate_classification == source.candidate_classification
        assert not hasattr(match, "risk_amount")


def test_no_cross_claim_drug_pair_is_invented() -> None:
    ctx = replace(
        _context(),
        drug_lines=(_drug("C1", "D1", "dabigatran"), _drug("C2", "D2", "rivaroksaban")),
    )
    batch = adapter.evaluate_drug_combinations("P1", ctx)
    assert not batch.legacy_rows
    assert not batch.matches
    assert _evaluation(batch, _DOAC).decision == "not_matched"
    assert _evaluation(batch, _DOAC, "C2").decision == "not_matched"


@pytest.mark.parametrize(
    "rule_id,names,diagnosis",
    [
        (_EPO, ("eritropoietin",), "N18.9"),
        (
            "4.2.9.C-c.(6).cinacalcet_etelcalsetid_combo_no_pay",
            ("cinacalcet", "etelkalsetid"),
            "Z00.0",
        ),
        (
            "4.2.9.E.(7).cinacalcet_etelcalsetid_combo_no_pay",
            ("cinacalcet", "etelcalsetid"),
            "Z00.0",
        ),
        ("4.2.14.C.(myeloma).pi_combo_no_pay", ("iksazomib", "karfilzomib"), "C900"),
        (_DOAC, ("dabigatran", "rivaroksaban"), "Z00.0"),
        ("4.2.17.A.(9).active_vitamin_d_osteoporosis_no_pay", ("kalsitriol",), "M81.0"),
        (_PREGABALIN, ("pregabalin",), "Z00.0"),
        ("4.2.34.(3).ms_dmt_combo_no_pay", ("beta_interferon", "glatiramer_acetate"), "Z00.0"),
    ],
)
def test_each_legacy_wireable_rule_keeps_its_exact_positive_payload(
    rule_id, names, diagnosis
) -> None:
    ctx = _single(*names)
    ctx = replace(ctx, claims=(replace(ctx.claims[0], primary_icd10=diagnosis),))
    original = legacy.check_drug_combination_for_context(ctx)
    assert any(r["rule_id"] == rule_id for r in original)
    batch = adapter.evaluate_drug_combinations("P1", ctx)
    assert [r.legacy_row for r in batch.legacy_rows] == original
    row = _evaluation(batch, rule_id)
    if rule_id == _EPO:
        assert (row.evaluation_status, row.decision) == ("unavailable", None)
    else:
        assert (row.evaluation_status, row.decision) == ("evaluated", "matched")


def test_raw_matches_keep_the_original_drug_claim_encounter_order() -> None:
    ctx = replace(
        _context(),
        drug_lines=(
            _drug("C2", "D3", "dabigatran"),
            _drug("C2", "D4", "rivaroksaban"),
            _drug("C1", "D1", "dabigatran"),
            _drug("C1", "D2", "rivaroksaban"),
        ),
    )
    batch = adapter.evaluate_drug_combinations("P1", ctx)
    assert [r.claim_id for r in batch.legacy_rows] == ["C2", "C1"]
    assert [r.legacy_row for r in batch.legacy_rows] == legacy.check_drug_combination_for_context(
        ctx
    )


def test_all_eight_syntactically_wireable_rules_are_counted_without_certifying_semantics() -> None:
    rules = legacy.load_drug_combination_rules()["rules"]
    assert sum(set(r["condition"]) <= legacy._WIREABLE_KEYS for r in rules) == 8
    ctx = _single("eritropoietin")
    batch = adapter.evaluate_drug_combinations("P1", ctx)
    row = _evaluation(batch, _EPO)
    assert row.evaluation_status == "unavailable"
    assert row.reason == "semantic_indication_not_derived"
    assert row.decision is None
    assert any(r.rule_id == _EPO for r in batch.legacy_rows)
    assert not any(r.rule_id == _EPO for r in batch.matches)
    assert [r.legacy_row for r in batch.legacy_rows] == legacy.check_drug_combination_for_context(
        ctx
    )


def test_blocked_keys_are_visible_even_after_an_earlier_legacy_nonmatch() -> None:
    ctx = _single("unrelated drug")
    batch = adapter.evaluate_drug_combinations("P1", ctx)
    blocked = legacy._BLOCKED_KEYS | legacy._DEFER_NO_SOURCE_KEYS
    checked = 0
    for rule in legacy.load_drug_combination_rules()["rules"]:
        if set(rule["condition"]) & blocked:
            row = _evaluation(batch, rule["rule_id"])
            assert row.evaluation_status == "unavailable"
            assert row.reason == "unsupported_condition_inputs"
            assert row.decision is None
            checked += 1
    assert checked == 45


@pytest.mark.parametrize(
    "key",
    [
        "unknown_predicate",
        "two_distinct_agents_same_class_concurrent",
        "two_distinct_active_ingredients_concurrent",
    ],
)
def test_unsupported_or_weak_predicates_do_not_become_typed_matches(monkeypatch, key) -> None:
    ruleset = deepcopy(legacy.load_drug_combination_rules())
    target = next(r for r in ruleset["rules"] if r["rule_id"] == _DOAC)
    target["condition"] = {key: True}
    monkeypatch.setattr(adapter, "load_drug_combination_rules", lambda: ruleset)
    monkeypatch.setattr(legacy, "load_drug_combination_rules", lambda: ruleset)
    ctx = _single("dabigatran", "rivaroksaban")
    batch = adapter.evaluate_drug_combinations("P1", ctx)
    row = _evaluation(batch, _DOAC)
    assert row.evaluation_status == "unavailable"
    assert row.decision is None
    assert not any(r.rule_id == _DOAC for r in batch.matches)
    assert [r.legacy_row for r in batch.legacy_rows] == legacy.check_drug_combination_for_context(
        ctx
    )


@pytest.mark.parametrize(
    "tier,status,decision",
    [
        ("second_step", "evaluated", "matched"),
        ("third_step", "evaluated", "matched"),
        ("first_step", "evaluated", "not_matched"),
        ("", "missing_inputs", None),
        ("2", "unavailable", None),
        ("ozel", "unavailable", None),
    ],
)
def test_facility_tier_uses_raw_supported_tokens_without_guessing(tier, status, decision) -> None:
    ctx = _single("pregabalin")
    ctx = replace(ctx, claims=(replace(ctx.claims[0], facility_tier=tier),))
    batch = adapter.evaluate_drug_combinations("P1", ctx)
    row = _evaluation(batch, _PREGABALIN)
    assert (row.evaluation_status, row.decision) == (status, decision)
    assert [r.legacy_row for r in batch.legacy_rows] == legacy.check_drug_combination_for_context(
        ctx
    )


@pytest.mark.parametrize("ctx", [None, replace(_context(), claims=(), drug_lines=())])
def test_absent_context_is_not_a_clean_pass(ctx) -> None:
    batch = adapter.evaluate_drug_combinations("P1", ctx)
    assert len(batch.evaluations) == 53
    assert all(
        r.claim_id is None and r.evaluation_status == "missing_inputs" for r in batch.evaluations
    )
    assert not batch.matches
    assert not batch.legacy_rows


def test_no_drug_feed_still_has_53_missing_evaluations_for_every_real_claim() -> None:
    batch = adapter.evaluate_drug_combinations("P1", replace(_context(), drug_lines=()))
    assert len(batch.evaluations) == 106
    assert all(r.evaluation_status == "missing_inputs" for r in batch.evaluations)
    assert all(r.missing_inputs == ["drug_lines"] for r in batch.evaluations)
    assert not batch.matches
    assert not batch.legacy_rows


def test_blank_drug_names_do_not_certify_a_negative() -> None:
    ctx = _single("dabigatran", "")
    batch = adapter.evaluate_drug_combinations("P1", ctx)
    row = _evaluation(batch, _DOAC)
    assert row.evaluation_status == "missing_inputs"
    assert row.missing_inputs == ["drug_name"]
    assert row.decision is None


def test_missing_diagnoses_do_not_certify_negated_or_positive_diagnosis_conditions() -> None:
    ctx = _single("kalsitriol")
    ctx = replace(ctx, claims=(replace(ctx.claims[0], primary_icd10=""),))
    batch = adapter.evaluate_drug_combinations("P1", ctx)
    rule_id = "4.2.17.A.(9).active_vitamin_d_osteoporosis_no_pay"
    row = _evaluation(batch, rule_id)
    assert row.evaluation_status == "missing_inputs"
    assert row.missing_inputs == ["diagnoses"]
    assert row.decision is None


@pytest.mark.parametrize("kind", ["patient", "header", "line", "orphan", "no_headers", "duplicate"])
def test_foreign_and_ambiguous_ownership_is_rejected(kind) -> None:
    ctx = _context()
    if kind == "patient":
        ctx = replace(ctx, patient_id="P2")
    elif kind == "header":
        ctx = replace(ctx, claims=(replace(ctx.claims[0], patient_id="P2"),))
    elif kind == "line":
        ctx = replace(ctx, drug_lines=(replace(ctx.drug_lines[0], patient_id="P2"),))
    elif kind == "orphan":
        ctx = replace(ctx, drug_lines=(replace(ctx.drug_lines[0], claim_id="other"),))
    elif kind == "no_headers":
        ctx = replace(ctx, claims=())
    else:
        ctx = replace(ctx, claims=ctx.claims + (ctx.claims[0],))
    with pytest.raises(ValueError):
        adapter.evaluate_drug_combinations("P1", ctx)


def test_original_predicate_runs_once_per_rule_per_drug_claim(monkeypatch) -> None:
    calls = 0
    original = adapter._check_combo_condition

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(adapter, "_check_combo_condition", counted)
    adapter.evaluate_drug_combinations("P1", _context())
    assert calls == 106


def test_payload_mutation_cannot_poison_corpus_or_separate_raw_rows() -> None:
    ctx = _single("dabigatran", "rivaroksaban")
    first = adapter.evaluate_drug_combinations("P1", ctx)
    match = next(r for r in first.matches if r.rule_id == _DOAC)
    match.authored_action["billable"] = True
    match.legacy_row["rule_id"] = "corrupted"
    assert all(r.legacy_row["rule_id"] != "corrupted" for r in first.legacy_rows)
    second = adapter.evaluate_drug_combinations("P1", ctx)
    intact = next(r for r in second.matches if r.rule_id == _DOAC)
    assert intact.authored_action["billable"] is False
    assert intact.legacy_row["rule_id"] == _DOAC


def test_catalog_sources_are_loaded_once(monkeypatch) -> None:
    original = adapter.load_broad_rule_catalog
    calls = 0

    def counted():
        nonlocal calls
        calls += 1
        return original()

    adapter._combination_catalog_sources.cache_clear()
    monkeypatch.setattr(adapter, "load_broad_rule_catalog", counted)
    try:
        adapter.evaluate_drug_combinations("P1", _context())
        adapter.evaluate_drug_combinations("P1", _context())
        assert calls == 1
    finally:
        adapter._combination_catalog_sources.cache_clear()


def test_typed_identity_and_outcomes_are_order_independent() -> None:
    ctx = _context()
    a = adapter.evaluate_drug_combinations("P1", ctx)
    b = adapter.evaluate_drug_combinations(
        "P1",
        replace(
            ctx, claims=tuple(reversed(ctx.claims)), drug_lines=tuple(reversed(ctx.drug_lines))
        ),
    )
    assert a.evaluations == b.evaluations
    assert a.matches == b.matches


def test_diagnoses_remain_claim_scoped() -> None:
    ctx = replace(_context(), drug_lines=(_drug("C1", "D1", "kalsitriol"),))
    diagnosis = ClaimDiagnosis(
        diagnosis_id="DX1",
        claim_id="C2",
        patient_id="P1",
        episode_id="E-C2",
        icd10_code="M81.0",
        is_primary=False,
        diagnosis_role="secondary",
        diagnosis_date=_DAY,
        exemption_eligible=False,
    )
    ctx = replace(ctx, diagnoses=(diagnosis,))
    batch = adapter.evaluate_drug_combinations("P1", ctx)
    row = _evaluation(batch, "4.2.17.A.(9).active_vitamin_d_osteoporosis_no_pay")
    assert row.decision == "not_matched"
    assert [r.legacy_row for r in batch.legacy_rows] == legacy.check_drug_combination_for_context(
        ctx
    )

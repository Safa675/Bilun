"""Dental metadata preserves line identity, legacy ordering, and unknown facts."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing import dental_rule_evaluations as adapter
from src.bilun.domain.billing.broad_rule_catalog import load_broad_rule_catalog
from src.bilun.domain.claims.models import ClaimHeader, MaterialClaimLine, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules import dental_2_4_1 as legacy

pytestmark = pytest.mark.unit
_DAY = date(2026, 7, 10)
_PRECIOUS = "2.4.1.(1).precious_metal_no_pay"
_IMPLANT = "2.4.1.(2).bone_implant_no_pay_default"
_BOARD = "2.4.1.(2).bone_implant_exception_board_report"
_AGE = "2.4.1.(4a).orthodontics_over_18_no_pay"


def _header(claim_id: str, provider_type: str = "private") -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id=f"E-{claim_id}",
        claim_type="ayakta",
        facility_tier="3",
        provider_type=provider_type,
        department="dental",
        admission_date=None,
        discharge_date=None,
        claim_start_date=_DAY,
        claim_end_date=_DAY,
        primary_icd10="K00.0",
        expected_total_billed_try=Decimal("100"),
        expected_total_payable_try=Decimal("90"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _procedure(claim_id: str, line_id: str, category: str) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id=f"E-{claim_id}",
        procedure_date=_DAY,
        procedure_code="999999999",
        procedure_name="Test procedure",
        procedure_category=category,
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


def _material(claim_id: str, line_id: str, procedure_id: str, name: str) -> MaterialClaimLine:
    return MaterialClaimLine(
        material_line_id=line_id,
        claim_id=claim_id,
        procedure_line_id=procedure_id,
        patient_id="P1",
        material_date=_DAY,
        material_code="",
        material_name=name,
        material_type="consumable",
        specialty_category="general",
        quantity=1,
        unit_price_try=Decimal("120"),
        billed_amount_try=Decimal("120"),
        expected_payable_try=Decimal("100"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _context() -> PatientClaimContext:
    return PatientClaimContext(
        patient_id="P1",
        claims=(_header("C1"), _header("C2", "universite")),
        procedure_lines=(
            _procedure("C1", "P1", "dental_restoration"),
            _procedure("C2", "P2", "dental_implant"),
        ),
        material_lines=(
            replace(
                _material("C2", "M2", "P2", "altın köprü"), medical_necessity_board_report=False
            ),
            _material("C1", "M1", "P1", "altın köprü"),
        ),
        drug_lines=(),
        diagnoses=(),
    )


def _single() -> PatientClaimContext:
    ctx = _context().slice_for_claim("C1")
    assert ctx is not None
    return ctx


def _row(batch, rule_id: str, line_id: str = "M1"):
    return next(r for r in batch.evaluations if r.rule_id == rule_id and r.line_id == line_id)


def _assert_raw_parity(batch, ctx) -> None:
    # Compare one actual material at a time: the legacy wrapper's payload has
    # no line ID, and two equal material names must not be reverse-joined.
    expected = []
    for material in ctx.material_lines:
        claim_ctx = ctx.slice_for_claim(material.claim_id)
        assert claim_ctx is not None
        result = legacy.check_dental_2_4_1_for_context(
            replace(claim_ctx, material_lines=(material,))
        )
        expected.extend((material.claim_id, material.material_line_id, r) for r in result)
    assert [(r.claim_id, r.material_line_id, r.legacy_row) for r in batch.legacy_rows] == expected


def test_same_name_materials_keep_distinct_source_ids_and_original_order() -> None:
    ctx = _context()
    batch = adapter.evaluate_dental_rules("P1", ctx)
    assert len(batch.evaluations) == len({r.evaluation_id for r in batch.evaluations}) == 38
    assert [(r.claim_id, r.material_line_id, r.rule_id) for r in batch.legacy_rows] == [
        ("C2", "M2", _IMPLANT),
        ("C1", "M1", _PRECIOUS),
    ]
    assert [r.line_id for r in batch.evaluations[:19]] == ["M2"] * 19
    assert all(r.line_kind == "material" for r in batch.evaluations)
    assert all(set(r.missing_inputs) <= set(r.required_inputs) for r in batch.evaluations)
    _assert_raw_parity(batch, ctx)


def test_raw_payloads_stay_exact_and_typed_candidates_do_not_confirm_money() -> None:
    batch = adapter.evaluate_dental_rules("P1", _context())
    assert len(batch.matches) == 2
    for match in batch.matches:
        source = next(r for r in load_broad_rule_catalog() if r.rule_id == match.rule_id)
        assert match.source_file == source.source_file
        assert match.source_locators == source.source_locators
        assert match.authored_action == source.action
        assert match.billable is source.billable
        assert match.candidate_classification == source.candidate_classification
        assert not hasattr(match, "risk_amount")
        assert not hasattr(match, "savings_try")
        assert match.legacy_row["risk_amount"] == 120.0


@pytest.mark.parametrize(
    "second_category,second_winner",
    [("dental_restoration", _PRECIOUS), ("dental_implant", _IMPLANT)],
)
def test_identical_names_within_one_claim_never_collapse_lines(
    second_category, second_winner
) -> None:
    ctx = _single()
    ctx = replace(
        ctx,
        procedure_lines=ctx.procedure_lines + (_procedure("C1", "P2", second_category),),
        material_lines=ctx.material_lines
        + (
            replace(
                _material("C1", "M2", "P2", "altın köprü"),
                billed_amount_try=Decimal("456"),
                medical_necessity_board_report=False,
            ),
        ),
    )
    batch = adapter.evaluate_dental_rules("P1", ctx)
    assert len(batch.evaluations) == len({r.evaluation_id for r in batch.evaluations}) == 38
    assert [(r.material_line_id, r.rule_id) for r in batch.matches] == [
        ("M1", _PRECIOUS),
        ("M2", second_winner),
    ]
    assert [r.legacy_row["risk_amount"] for r in batch.legacy_rows] == [120.0, 456.0]
    _assert_raw_parity(batch, ctx)


def test_first_legacy_winner_suppresses_all_later_rules_without_evaluating_them(
    monkeypatch,
) -> None:
    calls = 0
    original = adapter._condition_matches

    def counted(*args):
        nonlocal calls
        calls += 1
        return original(*args)

    monkeypatch.setattr(adapter, "_condition_matches", counted)
    batch = adapter.evaluate_dental_rules("P1", _single())
    assert calls == 1
    assert _row(batch, _PRECIOUS).decision == "matched"
    for row in batch.evaluations[1:]:
        assert row.evaluation_status == "unavailable"
        assert row.decision == "suppressed_by_prior_match"
        assert row.reason == f"prior_rule:{_PRECIOUS}"


@pytest.mark.parametrize(
    "board,status,raw_default",
    [(None, "missing_inputs", True), (False, "evaluated", True), (True, "evaluated", False)],
)
def test_optional_board_default_is_preserved_only_in_raw_output_when_unknown(
    board, status, raw_default
) -> None:
    ctx = _single()
    ctx = replace(
        ctx,
        procedure_lines=(replace(ctx.procedure_lines[0], procedure_category="dental_implant"),),
        material_lines=(
            replace(
                ctx.material_lines[0], material_name="implant", medical_necessity_board_report=board
            ),
        ),
    )
    batch = adapter.evaluate_dental_rules("P1", ctx)
    row = _row(batch, _IMPLANT)
    assert row.evaluation_status == status
    assert any(r.rule_id == _IMPLANT for r in batch.legacy_rows) is raw_default
    if board is None:
        assert row.missing_inputs == ["medical_necessity_board_report"]
        assert row.decision is None
        assert not batch.matches
        assert _row(batch, _BOARD).decision == "suppressed_by_prior_match"
    elif board is False:
        assert row.decision == "matched"
    else:
        assert row.decision == "not_matched"
        assert _row(batch, _BOARD).evaluation_status == "missing_inputs"
        assert "board_from" in _row(batch, _BOARD).missing_inputs
        assert "board_includes" in _row(batch, _BOARD).missing_inputs
    _assert_raw_parity(batch, ctx)


def test_missing_age_does_not_become_an_evaluated_age_restriction() -> None:
    ctx = _single()
    ctx = replace(
        ctx,
        procedure_lines=(replace(ctx.procedure_lines[0], procedure_category="orthodontics"),),
        material_lines=(replace(ctx.material_lines[0], material_name="orthodontic material"),),
    )
    batch = adapter.evaluate_dental_rules("P1", ctx)
    row = _row(batch, _AGE)
    assert row.evaluation_status == "missing_inputs"
    assert "patient_age" in row.missing_inputs
    assert row.decision is None
    _assert_raw_parity(batch, ctx)


def test_present_age_is_not_boolean_coerced_into_a_verified_range_match(monkeypatch) -> None:
    ctx = _single()
    original = legacy._build_dental_materials

    def rows(scoped):
        return [
            {
                **row,
                "procedure_category": "orthodontics",
                "patient_age": 12,
                "treatment_started_before_18": False,
            }
            for row in original(scoped)
        ]

    monkeypatch.setattr(adapter, "_build_dental_materials", rows)
    monkeypatch.setattr(legacy, "_build_dental_materials", rows)
    batch = adapter.evaluate_dental_rules("P1", ctx)
    # Legacy bool(12)==bool({'min':18}) is True; the adapter must withhold it.
    assert any(r.rule_id == _AGE for r in batch.legacy_rows)
    assert _row(batch, _AGE).evaluation_status == "unavailable"
    assert _row(batch, _AGE).reason == "dental_predicate_shape_not_supported"
    assert not any(r.rule_id == _AGE for r in batch.matches)
    _assert_raw_parity(batch, ctx)


def test_facility_derivation_uses_each_materials_own_claim(monkeypatch) -> None:
    ctx = _context()
    original = legacy._build_dental_materials
    built = {c.claim_id: original(ctx.slice_for_claim(c.claim_id)) for c in ctx.claims}
    assert built["C1"][0]["facility_type"] == "private"
    assert built["C2"][0]["facility_type"] == "training_research_hospital"
    observed = []

    def recording_builder(claim_ctx):
        assert len(claim_ctx.claims) == 1
        rows = original(claim_ctx)
        observed.append((claim_ctx.claims[0].claim_id, rows[0]["facility_type"]))
        return rows

    monkeypatch.setattr(adapter, "_build_dental_materials", recording_builder)
    batch = adapter.evaluate_dental_rules("P1", ctx)
    assert observed == [("C1", "private"), ("C2", "training_research_hospital")]
    _assert_raw_parity(batch, ctx)


def test_multiclaim_projection_parity_is_with_claim_scoped_legacy_calls(monkeypatch) -> None:
    # Make a facility condition reachable without adding absent clinical
    # inputs; the actual bridge and original predicate/serializer stay intact.
    ruleset = deepcopy(legacy.load_dental_2_4_1_rules())
    rule_id = "2.4.1.A.(1).public_facility_ek2c_pricing"
    rule = next(r for r in ruleset["rules"] if r["rule_id"] == rule_id)
    rule["condition"] = {"procedure_category": "dental_treatment", "facility_type": "private"}
    monkeypatch.setattr(adapter, "load_dental_2_4_1_rules", lambda: ruleset)
    monkeypatch.setattr(legacy, "load_dental_2_4_1_rules", lambda: ruleset)
    ctx = _context()
    ctx = replace(
        ctx,
        procedure_lines=tuple(
            replace(p, procedure_category="dental_treatment") for p in ctx.procedure_lines
        ),
    )
    # The direct wrapper uses the first header when passed a whole patient;
    # production bill evaluation passes a claim slice. This adapter preserves
    # that bill contract, not the direct wrapper's cross-claim header leak.
    assert len(legacy.check_dental_2_4_1_for_context(ctx)) == 2
    original = [
        row
        for claim_id in dict.fromkeys(m.claim_id for m in ctx.material_lines)
        for row in legacy.check_dental_2_4_1_for_context(ctx.slice_for_claim(claim_id))
    ]
    assert len(original) == 1
    batch = adapter.evaluate_dental_rules("P1", ctx)
    assert [r.legacy_row for r in batch.legacy_rows] == original
    assert _row(batch, rule_id, "M1").decision == "matched"
    row = _row(batch, rule_id, "M2")
    assert (row.evaluation_status, row.decision) == ("evaluated", "not_matched")
    assert not any(r.material_line_id == "M2" for r in batch.matches)
    _assert_raw_parity(batch, ctx)


def test_material_category_fallback_is_retained_when_procedure_is_absent() -> None:
    ctx = _single()
    ctx = replace(
        ctx,
        procedure_lines=(),
        material_lines=(replace(ctx.material_lines[0], specialty_category="dental_restoration"),),
    )
    batch = adapter.evaluate_dental_rules("P1", ctx)
    assert _row(batch, _PRECIOUS).decision == "matched"
    _assert_raw_parity(batch, ctx)


@pytest.mark.parametrize("delta", [-1, 1])
def test_material_builder_count_mismatch_cannot_misattribute_identity(monkeypatch, delta) -> None:
    rows = legacy._build_dental_materials(_single())
    rows = [] if delta < 0 else rows + deepcopy(rows)
    monkeypatch.setattr(adapter, "_build_dental_materials", lambda _: rows)
    with pytest.raises(ValueError):
        adapter.evaluate_dental_rules("P1", _single())


@pytest.mark.parametrize(
    "kind",
    [
        "patient",
        "header",
        "material",
        "orphan",
        "no_headers",
        "duplicate_header",
        "duplicate_material",
        "duplicate_procedure",
    ],
)
def test_ambiguous_or_foreign_source_identity_is_rejected(kind) -> None:
    ctx = _context()
    if kind == "patient":
        ctx = replace(ctx, patient_id="P2")
    elif kind == "header":
        ctx = replace(ctx, claims=(replace(ctx.claims[0], patient_id="P2"),))
    elif kind == "material":
        ctx = replace(ctx, material_lines=(replace(ctx.material_lines[0], patient_id="P2"),))
    elif kind == "orphan":
        ctx = replace(ctx, material_lines=(replace(ctx.material_lines[0], claim_id="other"),))
    elif kind == "no_headers":
        ctx = replace(ctx, claims=())
    elif kind == "duplicate_header":
        ctx = replace(ctx, claims=ctx.claims + (ctx.claims[0],))
    elif kind == "duplicate_material":
        ctx = replace(ctx, material_lines=ctx.material_lines + (ctx.material_lines[0],))
    else:
        ctx = replace(ctx, procedure_lines=ctx.procedure_lines + (ctx.procedure_lines[0],))
    with pytest.raises(ValueError):
        adapter.evaluate_dental_rules("P1", ctx)


def test_empty_material_feed_uses_claim_scope_instead_of_invented_line_ids() -> None:
    batch = adapter.evaluate_dental_rules("P1", replace(_context(), material_lines=()))
    assert len(batch.evaluations) == 38
    assert all(r.line_kind == "claim" and r.line_id is None for r in batch.evaluations)
    assert all(
        r.evaluation_status == "missing_inputs" and r.missing_inputs == ["material_lines"]
        for r in batch.evaluations
    )
    assert not batch.matches
    assert not batch.legacy_rows


@pytest.mark.parametrize(
    "ctx", [None, replace(_context(), claims=(), material_lines=(), procedure_lines=())]
)
def test_absent_context_keeps_19_missing_statuses(ctx) -> None:
    batch = adapter.evaluate_dental_rules("P1", ctx)
    assert len(batch.evaluations) == 19
    assert all(
        r.claim_id is None and r.line_id is None and r.evaluation_status == "missing_inputs"
        for r in batch.evaluations
    )


def test_catalog_sources_are_cached_and_mutable_payloads_are_detached(monkeypatch) -> None:
    original = adapter.load_broad_rule_catalog
    calls = 0

    def counted():
        nonlocal calls
        calls += 1
        return original()

    adapter._dental_catalog_sources.cache_clear()
    monkeypatch.setattr(adapter, "load_broad_rule_catalog", counted)
    try:
        first = adapter.evaluate_dental_rules("P1", _single())
        first.matches[0].authored_action["billable"] = True
        first.matches[0].legacy_row["rule_id"] = "corrupted"
        assert first.legacy_rows[0].legacy_row["rule_id"] == _PRECIOUS
        second = adapter.evaluate_dental_rules("P1", _single())
        assert second.matches[0].authored_action["billable"] is False
        assert second.matches[0].legacy_row["rule_id"] == _PRECIOUS
        assert calls == 1
    finally:
        adapter._dental_catalog_sources.cache_clear()

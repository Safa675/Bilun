"""Gap-closing status metadata preserves legacy decisions and authored meaning."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing import gap_closing_evaluations as adapter
from src.bilun.domain.billing.broad_rule_catalog import load_broad_rule_catalog
from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules import gap_closing as legacy

pytestmark = pytest.mark.unit
_DAY = date(2026, 7, 10)


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


def _context() -> PatientClaimContext:
    return PatientClaimContext(
        patient_id="P1",
        claims=(_header("C1"), _header("C2")),
        procedure_lines=(
            _procedure("C1", "L1", "inpatient_surgery"),
            _procedure("C1", "L2", "physiotherapy_rehab"),
            _procedure("C2", "L3", "imaging"),
        ),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


def _single_context() -> PatientClaimContext:
    ctx = _context().slice_for_claim("C1")
    assert ctx is not None
    return ctx


def _legacy_rows(ctx: PatientClaimContext) -> list[dict]:
    return legacy.check_gap_closing_misc_for_context(
        ctx
    ) + legacy.check_gap_closing_treatment_for_context(ctx)


def test_all_89_rule_identities_and_original_rows_are_preserved_per_claim() -> None:
    ctx = _context()
    batch = adapter.evaluate_gap_closing("P1", ctx)
    entries = [r for r in load_broad_rule_catalog() if r.family in adapter._FAMILY_COUNTS]
    assert len(entries) == 89
    assert len(batch.evaluations) == 178
    assert len({row.evaluation_id for row in batch.evaluations}) == 178
    for claim_id in ("C1", "C2"):
        claim_ctx = ctx.slice_for_claim(claim_id)
        assert claim_ctx is not None
        assert {r.rule_id for r in batch.evaluations if r.claim_id == claim_id} == {
            r.rule_id for r in entries
        }
        assert [r.legacy_row for r in batch.legacy_rows if r.claim_id == claim_id] == _legacy_rows(
            claim_ctx
        )
    for row in batch.matches:
        authored = next(r for r in entries if r.rule_id == row.rule_id)
        assert row.authored_action == authored.action
        assert row.billable is authored.billable
        assert row.candidate_classification == authored.candidate_classification
        assert row.source_file == authored.source_file
        assert row.source_locators == authored.source_locators


def test_scalar_fallback_retains_matches_on_a_multi_category_claim_only() -> None:
    batch = adapter.evaluate_gap_closing("P1", _context())
    rule_id = "2.4.4.F-3.(1).private_physio_2_4_4_F_rules"
    by_claim = {r.claim_id: r for r in batch.evaluations if r.rule_id == rule_id}
    assert by_claim["C1"].decision == "matched"
    assert by_claim["C2"].decision == "not_matched"
    matches = [r for r in batch.matches if r.rule_id == rule_id]
    assert len(matches) == 1
    assert matches[0].claim_id == "C1"
    assert matches[0].candidate_classification == "positive_or_permission_candidate"


def test_missing_unsupported_and_known_nonmatch_are_distinct() -> None:
    ctx = _single_context()
    ctx = replace(ctx, claims=(replace(ctx.claims[0], provider_type="contracted"),))
    batch = adapter.evaluate_gap_closing("P1", ctx)
    by_id = {r.rule_id: r for r in batch.evaluations}
    missing = by_id["1.5.2.(3).contracted_provider_must_accept"]
    assert missing.evaluation_status == "missing_inputs"
    assert missing.missing_inputs == ["patient_turned_away"]
    unsupported = by_id["2.5.3.A-2.(2).overseas_duration_cannot_exceed_report"]
    assert unsupported.evaluation_status == "unavailable"
    assert "unsupported predicate: overseas_treatment_days" in unsupported.reason
    clean = by_id["2.4.4.H.(1).icu_standards_required"]
    assert (clean.evaluation_status, clean.decision) == ("evaluated", "not_matched")


def test_adverse_authored_duty_is_a_candidate_not_an_invented_payment_denial(monkeypatch) -> None:
    ctx = _single_context()
    ctx = replace(ctx, claims=(replace(ctx.claims[0], provider_type="contracted"),))
    flat = legacy._build_gap_closing_context(ctx)
    injected = {**flat, "patient_turned_away": True}
    monkeypatch.setattr(adapter, "_build_gap_closing_context", lambda _: injected)
    batch = adapter.evaluate_gap_closing("P1", ctx)
    rule_id = "1.5.2.(3).contracted_provider_must_accept"
    match = next(r for r in batch.matches if r.rule_id == rule_id)
    authored = next(
        r for r in legacy.load_gap_closing_misc_rules()["rules"] if r["rule_id"] == rule_id
    )
    assert match.authored_action == authored["action"]
    assert match.billable is False
    assert match.candidate_classification == "adverse_candidate"
    assert match.legacy_row == legacy._violation_from_rule(authored, "gap_closing_misc")
    assert not hasattr(match, "finding_type")
    assert not hasattr(match, "risk_amount_try")


@pytest.mark.parametrize(
    ("change", "rule_id", "status", "missing"),
    [
        ({"claim_type": ""}, "1.8.2.copay_required_outpatient", "missing_inputs", ["claim_type"]),
        ({"claim_type": "unknown"}, "1.8.2.copay_required_outpatient", "unavailable", []),
        (
            {"provider_type": ""},
            "2.4.4.F-3.(1).private_physio_2_4_4_F_rules",
            "missing_inputs",
            ["provider_type"],
        ),
        (
            {"facility_tier": ""},
            "2.2.2.B.(5).training_research_hospital_ek2c_star_30pct_uplift",
            "missing_inputs",
            ["facility_tier"],
        ),
        (
            {"provider_type": "hospital"},
            "1.5.2.(3).contracted_provider_must_accept",
            "unavailable",
            [],
        ),
    ],
)
def test_missing_raw_header_and_derived_contract_facts_do_not_become_typed_matches(
    change, rule_id, status, missing
) -> None:
    original = _single_context()
    ctx = replace(original, claims=(replace(original.claims[0], **change),))
    batch = adapter.evaluate_gap_closing("P1", ctx)
    evaluation = next(r for r in batch.evaluations if r.rule_id == rule_id)
    assert evaluation.evaluation_status == status
    assert evaluation.missing_inputs == missing
    assert evaluation.decision is None
    assert not any(r.rule_id == rule_id for r in batch.matches)
    assert [r.legacy_row for r in batch.legacy_rows] == _legacy_rows(ctx)


def test_raw_gate_suppresses_a_defaulted_match_without_losing_legacy_payload(monkeypatch) -> None:
    original = _single_context()
    ctx = replace(original, claims=(replace(original.claims[0], claim_type=""),))
    flat = {**legacy._build_gap_closing_context(ctx), "exemption_ek1a_or_ek4d": False}
    monkeypatch.setattr(adapter, "_build_gap_closing_context", lambda _: flat)
    batch = adapter.evaluate_gap_closing("P1", ctx)
    rule_id = "1.8.2.copay_required_outpatient"
    assert any(r.rule_id == rule_id for r in batch.legacy_rows)
    assert not any(r.rule_id == rule_id for r in batch.matches)
    assert (
        next(r for r in batch.evaluations if r.rule_id == rule_id).evaluation_status
        == "missing_inputs"
    )


def test_absence_of_an_emergency_tag_is_not_verified_negative_clinical_evidence() -> None:
    batch = adapter.evaluate_gap_closing("P1", _single_context())
    row = next(r for r in batch.evaluations if r.rule_id == "2.3.(1).emergency_24h_window")
    assert row.evaluation_status == "unavailable"
    assert "does not establish non-emergency" in row.reason


@pytest.mark.parametrize("flag", [None, False, True])
def test_unknown_health_report_flag_is_not_a_known_absent_report(flag) -> None:
    ctx = _single_context()
    drug = DrugClaimLine(
        drug_claim_line_id="D1",
        prescription_id="RX1",
        claim_id="C1",
        patient_id="P1",
        episode_id="E-C1",
        drug_claim_date=_DAY,
        drug_name="Test",
        drug_code="",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("1"),
        billed_amount_try=Decimal("1"),
        expected_payable_try=Decimal("1"),
        discount_tier_expected=Decimal("0"),
        denial_reason_expected="",
        rule_trace_expected="",
        drug_specialty_board_report_present=flag,
    )
    ctx = replace(ctx, drug_lines=(drug,))
    flat = legacy._build_gap_closing_context(ctx)
    gate = adapter._metadata_gate({"health_report_present": True}, ctx, flat)
    if flag is None:
        assert gate[0:2] == ("missing_inputs", ["drug_specialty_board_report_present"])
    else:
        assert gate is None


@pytest.mark.parametrize("empty", [None, replace(_context(), claims=(), procedure_lines=())])
def test_absent_context_accounts_for_all_rules_without_matches(empty) -> None:
    batch = adapter.evaluate_gap_closing("P1", empty)
    assert len(batch.evaluations) == 89
    assert not batch.matches
    assert not batch.legacy_rows
    assert all(
        r.claim_id is None and r.evaluation_status == "missing_inputs" for r in batch.evaluations
    )


@pytest.mark.parametrize(
    "kind", ["patient", "header", "line", "foreign_claim", "duplicate_claim", "orphan_line"]
)
def test_context_ownership_is_validated(kind) -> None:
    ctx = _context()
    if kind == "patient":
        ctx = replace(ctx, patient_id="P2")
    elif kind == "header":
        ctx = replace(ctx, claims=(replace(ctx.claims[0], patient_id="P2"),))
    elif kind == "line":
        ctx = replace(ctx, procedure_lines=(replace(ctx.procedure_lines[0], patient_id="P2"),))
    elif kind == "foreign_claim":
        ctx = replace(ctx, procedure_lines=(replace(ctx.procedure_lines[0], claim_id="OTHER"),))
    elif kind == "duplicate_claim":
        ctx = replace(ctx, claims=(ctx.claims[0], ctx.claims[0]))
    else:
        ctx = replace(ctx, claims=())
    with pytest.raises(ValueError):
        adapter.evaluate_gap_closing("P1", ctx)


def test_catalog_sources_are_cached_and_returned_payload_mutation_is_isolated(monkeypatch) -> None:
    calls = 0
    original = adapter.load_broad_rule_catalog

    def counted():
        nonlocal calls
        calls += 1
        return original()

    adapter._gap_catalog_sources.cache_clear()
    monkeypatch.setattr(adapter, "load_broad_rule_catalog", counted)
    try:
        first = adapter.evaluate_gap_closing("P1", _context())
        assert first.matches
        before = deepcopy(first.matches[0].authored_action)
        first.matches[0].authored_action["billable"] = "corrupted"
        first.matches[0].legacy_row["rule_id"] = "corrupted"
        second = adapter.evaluate_gap_closing("P1", _context())
        assert second.matches[0].authored_action == before
        assert second.matches[0].legacy_row["rule_id"] == second.matches[0].rule_id
        assert first.legacy_rows[0].legacy_row["rule_id"] != "corrupted"
        assert calls == 1
        with pytest.raises(TypeError):
            adapter._gap_catalog_sources()["fake"] = None
    finally:
        adapter._gap_catalog_sources.cache_clear()


def test_catalog_validation_failure_blocks_use(monkeypatch) -> None:
    def invalid():
        raise ValueError("Invalid authored source")

    adapter._gap_catalog_sources.cache_clear()
    monkeypatch.setattr(adapter, "load_broad_rule_catalog", invalid)
    try:
        with pytest.raises(ValueError, match="Invalid authored source"):
            adapter.evaluate_gap_closing("P1", _context())
    finally:
        adapter._gap_catalog_sources.cache_clear()


def test_reordered_claim_inputs_preserve_identity_and_output_order() -> None:
    ctx = _context()
    forward = adapter.evaluate_gap_closing("P1", ctx)
    reverse = adapter.evaluate_gap_closing(
        "P1",
        replace(
            ctx,
            claims=tuple(reversed(ctx.claims)),
            procedure_lines=tuple(reversed(ctx.procedure_lines)),
        ),
    )
    assert forward == reverse


@pytest.mark.parametrize(
    "rule_id",
    [
        "1.8.5.(5).emergency_except_green_area_no_copay",
        "1.9.1.(6).er_stabilization_24h_before_extra_fee",
    ],
)
def test_emergency_care_setting_predicate_is_unavailable_for_real_emergency_signal(rule_id) -> None:
    ctx = _single_context()
    ctx = replace(ctx, claims=(replace(ctx.claims[0], department="acil servis"),))
    flat = legacy._build_gap_closing_context(ctx)
    assert flat["care_setting"] == "outpatient"
    assert flat["is_emergency"] is True
    batch = adapter.evaluate_gap_closing("P1", ctx)
    evaluation = next(row for row in batch.evaluations if row.rule_id == rule_id)
    assert evaluation.evaluation_status == "unavailable"
    assert evaluation.decision is None
    assert evaluation.reason == "emergency_care_setting_not_derived"
    assert not any(row.rule_id == rule_id for row in batch.matches)
    assert [row.legacy_row for row in batch.legacy_rows] == _legacy_rows(ctx)


def test_yatarak_is_available_as_inpatient_to_typed_gap_metadata() -> None:
    ctx = _single_context()
    ctx = replace(ctx, claims=(replace(ctx.claims[0], claim_type="yatarak"),))
    batch = adapter.evaluate_gap_closing("P1", ctx)
    row = next(r for r in batch.evaluations if r.rule_id == "1.8.2.copay_required_outpatient")
    assert (row.evaluation_status, row.decision) == ("evaluated", "not_matched")
    assert [r.legacy_row for r in batch.legacy_rows] == _legacy_rows(ctx)


def test_private_ownership_does_not_certify_a_contract_dependent_candidate(monkeypatch) -> None:
    ctx = _single_context()
    # Legacy context currently assumes every nonempty non-uncontracted type is
    # contracted; the typed layer must not turn ownership into contract proof.
    flat = {**legacy._build_gap_closing_context(ctx), "patient_turned_away": True}
    assert flat["facility_contracted"] is True
    monkeypatch.setattr(adapter, "_build_gap_closing_context", lambda _: flat)
    monkeypatch.setattr(legacy, "_build_gap_closing_context", lambda _: flat)
    batch = adapter.evaluate_gap_closing("P1", ctx)
    rule_id = "1.5.2.(3).contracted_provider_must_accept"
    assert any(r.rule_id == rule_id for r in batch.legacy_rows)
    assert not any(r.rule_id == rule_id for r in batch.matches)
    row = next(r for r in batch.evaluations if r.rule_id == rule_id)
    assert row.evaluation_status == "unavailable"
    assert "contracting status is not established" in row.reason
    assert [row.legacy_row for row in batch.legacy_rows] == _legacy_rows(ctx)

"""Guideline observations never become confirmed SUT violations or money."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing import fatura_inceleme_evaluations as adapter
from src.bilun.domain.billing.broad_rule_catalog import load_broad_rule_catalog
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules import fatura_inceleme as legacy

pytestmark = pytest.mark.unit
_DAY = date(2026, 7, 10)
_SUNNET = "ORTAK-10.sunnet_z412"
_INFUSION = "ORTAK-16.iv_infuzyon_530160"
_EMERGENCY = "ORTAK-7.acil_kontrol_muayene"
_CARDIOLOGY = "KARDİYOLOJİ-2.spect_gated_ayri_ayri_odeme"


def _header(claim_id: str, department: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id=f"E-{claim_id}",
        claim_type="ayakta",
        facility_tier="3",
        provider_type="sozlesmeli",
        department=department,
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


def _procedure(claim_id: str, line_id: str, code: str, category: str = "") -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id=f"E-{claim_id}",
        procedure_date=_DAY,
        procedure_code=code,
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
        claims=(_header("C1", "Kardiyoloji"), _header("C2", "Acil Servis")),
        procedure_lines=(
            _procedure("C1", "L1", "800800"),
            _procedure("C2", "L2", "999999999", "kontrol_muayene"),
        ),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


def _single() -> PatientClaimContext:
    ctx = _context().slice_for_claim("C1")
    assert ctx is not None
    return ctx


def _row(batch, rule_id: str, claim_id: str = "C1"):
    return next(r for r in batch.evaluations if r.rule_id == rule_id and r.claim_id == claim_id)


def _assert_raw_parity(batch, ctx) -> None:
    for claim in ctx.claims:
        scoped = ctx.slice_for_claim(claim.claim_id)
        assert [r.legacy_row for r in batch.legacy_rows if r.claim_id == claim.claim_id] == (
            legacy.check_fatura_inceleme_for_context(scoped)
        )


def test_all_91_identities_and_original_rows_are_preserved_per_claim() -> None:
    ctx = _context()
    batch = adapter.evaluate_fatura_inceleme("P1", ctx)
    sources = [r for r in load_broad_rule_catalog() if r.family == "fatura_inceleme_prose"]
    assert len(sources) == 91
    assert len(batch.evaluations) == len({r.evaluation_id for r in batch.evaluations}) == 182
    assert all(set(r.missing_inputs) <= set(r.required_inputs) for r in batch.evaluations)
    for claim_id in ("C1", "C2"):
        assert {r.rule_id for r in batch.evaluations if r.claim_id == claim_id} == {
            r.rule_id for r in sources
        }
    _assert_raw_parity(batch, ctx)
    assert _row(batch, _CARDIOLOGY).decision == "matched"
    assert _row(batch, _CARDIOLOGY, "C2").decision == "not_matched"
    assert _row(batch, _EMERGENCY, "C2").decision == "matched"


def test_all_candidates_keep_guideline_authority_and_require_source_review() -> None:
    batch = adapter.evaluate_fatura_inceleme("P1", _context())
    assert batch.matches
    assert {r.billable for r in batch.matches} == {True, False}
    for match in batch.matches:
        source = next(r for r in load_broad_rule_catalog() if r.rule_id == match.rule_id)
        assert match.outcome == "review_only"
        assert match.requires_source_review is True
        assert match.source_authority == "sgk_fatura_inceleme_guideline"
        assert match.sut_takes_precedence is True
        assert match.source_file == source.source_file
        assert match.source_locators == source.source_locators
        assert all(ref.startswith("F") for ref in match.source_locators)
        assert match.fatura_inceleme_ref == source.fatura_inceleme_ref
        assert match.authored_action == source.action
        assert match.candidate_classification == source.candidate_classification
        assert not hasattr(match, "risk_amount")
        assert not hasattr(match, "savings_try")
        assert not hasattr(match, "sut_section")


def test_ortak_needs_no_department_but_branch_rules_do() -> None:
    ctx = _single()
    ctx = replace(
        ctx,
        claims=(replace(ctx.claims[0], department=""),),
        procedure_lines=(_procedure("C1", "L1", "999999999", "muayene"),),
    )
    batch = adapter.evaluate_fatura_inceleme("P1", ctx)
    assert _row(batch, "ORTAK-13.gecmis_muayene_sorgu").decision == "matched"
    row = _row(batch, _CARDIOLOGY)
    assert row.evaluation_status == "missing_inputs"
    assert row.missing_inputs == ["department", "procedure_specialty_code"]
    _assert_raw_parity(batch, ctx)


@pytest.mark.parametrize(
    "department,expected_reason",
    [
        ("", "first_procedure_specialty_proxy"),
        ("Dermatoloji", "first_procedure_specialty_proxy"),
    ],
)
def test_first_procedure_specialty_matches_stay_raw_and_unavailable(
    department, expected_reason
) -> None:
    ctx = _single()
    ctx = replace(
        ctx,
        claims=(replace(ctx.claims[0], department=department),),
        procedure_lines=(replace(ctx.procedure_lines[0], procedure_specialty_code="Kardiyoloji"),),
    )
    batch = adapter.evaluate_fatura_inceleme("P1", ctx)
    assert any(r.rule_id == _CARDIOLOGY for r in batch.legacy_rows)
    assert not any(r.rule_id == _CARDIOLOGY for r in batch.matches)
    row = _row(batch, _CARDIOLOGY)
    assert row.evaluation_status == "unavailable"
    assert row.reason == expected_reason
    _assert_raw_parity(batch, ctx)


def test_unknown_department_is_not_a_verified_different_branch() -> None:
    ctx = _single()
    ctx = replace(ctx, claims=(replace(ctx.claims[0], department="undecoded ward"),))
    row = _row(adapter.evaluate_fatura_inceleme("P1", ctx), _CARDIOLOGY)
    assert row.evaluation_status == "unavailable"
    assert row.reason == "branch_evidence_unrecognized"


def test_mixed_specialty_order_cannot_turn_uncertainty_into_a_clean_negative() -> None:
    ctx = _single()
    ctx = replace(
        ctx,
        claims=(replace(ctx.claims[0], department="Dermatoloji"),),
        procedure_lines=(
            replace(ctx.procedure_lines[0], procedure_specialty_code="Kardiyoloji"),
            replace(_procedure("C1", "L2", "999999999"), procedure_specialty_code="Dermatoloji"),
        ),
    )
    forward = adapter.evaluate_fatura_inceleme("P1", ctx)
    reversed_ctx = replace(ctx, procedure_lines=tuple(reversed(ctx.procedure_lines)))
    reverse = adapter.evaluate_fatura_inceleme("P1", reversed_ctx)
    assert any(r.rule_id == _CARDIOLOGY for r in forward.legacy_rows)
    assert not any(r.rule_id == _CARDIOLOGY for r in reverse.legacy_rows)
    assert _row(forward, _CARDIOLOGY).evaluation_status == "unavailable"
    assert _row(reverse, _CARDIOLOGY).evaluation_status == "unavailable"
    assert _row(reverse, _CARDIOLOGY).reason == "procedure_specialty_branch_uncertain"
    _assert_raw_parity(forward, ctx)
    _assert_raw_parity(reverse, reversed_ctx)


def test_unknown_authored_branch_is_unavailable(monkeypatch) -> None:
    ruleset = deepcopy(legacy.load_fatura_inceleme_rules())
    next(r for r in ruleset["rules"] if r["rule_id"] == _CARDIOLOGY)["branch"] = "UNKNOWN"
    monkeypatch.setattr(adapter, "load_fatura_inceleme_rules", lambda: ruleset)
    row = _row(adapter.evaluate_fatura_inceleme("P1", _single()), _CARDIOLOGY)
    assert row.evaluation_status == "unavailable"
    assert row.reason == "authored_branch_unrecognized"


@pytest.mark.parametrize("department", ["göğüs cerrahisi", "toraks cerrahisi"])
def test_overlapping_department_keywords_do_not_certify_both_branches(department) -> None:
    ctx = _single()
    ctx = replace(
        ctx,
        claims=(replace(ctx.claims[0], department=department),),
        procedure_lines=(
            _procedure("C1", "L1", "608630"),
            _procedure("C1", "L2", "608320"),
        ),
    )
    batch = adapter.evaluate_fatura_inceleme("P1", ctx)
    for rule_id in (
        "GÖĞÜS_CERRAHİSİ-2.intraplevral_lavaj_ilk_ve_sonraki",
        "GÖĞÜS_HASTALIKLARI-1.firca_biyopsisi_bronkoskopi_608310",
    ):
        assert any(r.rule_id == rule_id for r in batch.legacy_rows)
        assert not any(r.rule_id == rule_id for r in batch.matches)
        row = _row(batch, rule_id)
        assert row.evaluation_status == "unavailable"
        assert row.reason == "branch_keyword_overlap_unresolved"
    _assert_raw_parity(batch, ctx)


def test_circumcision_with_qualifying_diagnosis_cannot_become_a_confirmed_denial() -> None:
    # Official guideline ORTAK-10 permits Z41.2. The legacy predicate only
    # tests procedure category and still emits billable=False for this case.
    ctx = _single()
    ctx = replace(
        ctx,
        claims=(replace(ctx.claims[0], primary_icd10="Z41.2"),),
        procedure_lines=(_procedure("C1", "L1", "999999999", "sunnet"),),
    )
    batch = adapter.evaluate_fatura_inceleme("P1", ctx)
    raw = next(r for r in batch.legacy_rows if r.rule_id == _SUNNET)
    assert raw.legacy_row["billable"] is False
    row = _row(batch, _SUNNET)
    assert row.evaluation_status == "unavailable"
    assert row.reason == "guideline_diagnosis_condition_not_evaluated"
    assert "diagnosis_z41_2" in row.required_inputs
    assert set(row.missing_inputs) <= set(row.required_inputs)
    assert not any(r.rule_id == _SUNNET for r in batch.matches)
    _assert_raw_parity(batch, ctx)


def test_infusion_code_alone_cannot_establish_absence_of_iv_drug_use() -> None:
    ctx = replace(_single(), procedure_lines=(_procedure("C1", "L1", "530160"),))
    batch = adapter.evaluate_fatura_inceleme("P1", ctx)
    assert any(r.rule_id == _INFUSION for r in batch.legacy_rows)
    row = _row(batch, _INFUSION)
    assert row.evaluation_status == "unavailable"
    assert row.reason == "iv_drug_use_not_derived"
    assert "iv_infusion_drug_use" in row.required_inputs
    assert row.missing_inputs == ["iv_infusion_drug_use"]
    assert not any(r.rule_id == _INFUSION for r in batch.matches)
    _assert_raw_parity(batch, ctx)


@pytest.mark.parametrize("claim_type", ["yatarak", "YATARAK", "yatan", "yatış"])
def test_yatarak_reads_as_inpatient_in_the_legacy_builder_and_the_typed_rows(claim_type: str) -> None:
    """#335: the builder reads the one claim-type vocabulary, as gap_closing does; the stop-gap that kept a raw
    `yatarak` setting unavailable (`care_setting_normalization_unavailable`) is gone."""
    ctx = _single()
    ctx = replace(ctx, claims=(replace(ctx.claims[0], claim_type=claim_type),))
    assert legacy._build_fatura_inceleme_context(ctx)["care_setting"] == "inpatient"
    batch = adapter.evaluate_fatura_inceleme("P1", ctx)
    row = _row(batch, "ORTAK-25.yatis_oncesi_hazirlik_paket")
    assert row.reason != "care_setting_normalization_unavailable"
    yatis = adapter.evaluate_fatura_inceleme("P1", replace(ctx, claims=(replace(ctx.claims[0], claim_type="yatis"),)))
    assert (row.evaluation_status, row.decision, row.reason) == (
        (twin := _row(yatis, "ORTAK-25.yatis_oncesi_hazirlik_paket")).evaluation_status,
        twin.decision,
        twin.reason,
    )
    _assert_raw_parity(batch, ctx)


def test_absent_emergency_marker_is_not_verified_negative_evidence() -> None:
    row = _row(adapter.evaluate_fatura_inceleme("P1", _single()), _EMERGENCY)
    assert row.evaluation_status == "unavailable"
    assert row.decision is None


def test_multiclaim_branch_and_procedure_evidence_never_mix() -> None:
    ctx = _context()
    ctx = replace(
        ctx,
        claims=(
            replace(ctx.claims[0], department="Dermatoloji"),
            replace(ctx.claims[1], department="Kardiyoloji"),
        ),
    )
    batch = adapter.evaluate_fatura_inceleme("P1", ctx)
    assert not any(r.rule_id == _CARDIOLOGY for r in batch.legacy_rows)
    assert _row(batch, _CARDIOLOGY).decision == "not_matched"
    assert _row(batch, _CARDIOLOGY, "C2").decision == "not_matched"
    _assert_raw_parity(batch, ctx)


@pytest.mark.parametrize("ctx", [None, replace(_context(), claims=(), procedure_lines=())])
def test_absent_claim_context_has_91_missing_statuses(ctx) -> None:
    batch = adapter.evaluate_fatura_inceleme("P1", ctx)
    assert len(batch.evaluations) == 91
    assert all(
        r.claim_id is None and r.evaluation_status == "missing_inputs" for r in batch.evaluations
    )
    assert not batch.matches
    assert not batch.legacy_rows


@pytest.mark.parametrize("kind", ["patient", "header", "line", "orphan", "no_headers", "duplicate"])
def test_ownership_rejects_foreign_and_ambiguous_context(kind) -> None:
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
        adapter.evaluate_fatura_inceleme("P1", ctx)


def test_catalog_source_metadata_is_cached_once(monkeypatch) -> None:
    original = adapter.load_broad_rule_catalog
    calls = 0

    def counted():
        nonlocal calls
        calls += 1
        return original()

    adapter._fatura_catalog_sources.cache_clear()
    monkeypatch.setattr(adapter, "load_broad_rule_catalog", counted)
    try:
        adapter.evaluate_fatura_inceleme("P1", _context())
        adapter.evaluate_fatura_inceleme("P1", _context())
        assert calls == 1
    finally:
        adapter._fatura_catalog_sources.cache_clear()


def test_mutable_payloads_are_detached_from_cached_sources_and_raw_rows() -> None:
    first = adapter.evaluate_fatura_inceleme("P1", _context())
    match = next(r for r in first.matches if r.rule_id == _CARDIOLOGY)
    match.authored_action["billable"] = False
    match.legacy_row["rule_id"] = "corrupted"
    assert all(r.legacy_row["rule_id"] != "corrupted" for r in first.legacy_rows)
    second = adapter.evaluate_fatura_inceleme("P1", _context())
    intact = next(r for r in second.matches if r.rule_id == _CARDIOLOGY)
    assert intact.authored_action["billable"] is True
    assert intact.legacy_row["rule_id"] == _CARDIOLOGY


def test_branch_and_predicate_observer_are_not_run_twice(monkeypatch) -> None:
    branch_calls = condition_calls = 0
    branch = adapter._branch_matches
    condition = adapter._evaluate_condition

    def count_branch(*args):
        nonlocal branch_calls
        branch_calls += 1
        return branch(*args)

    def count_condition(*args):
        nonlocal condition_calls
        condition_calls += 1
        return condition(*args)

    monkeypatch.setattr(adapter, "_branch_matches", count_branch)
    monkeypatch.setattr(adapter, "_evaluate_condition", count_condition)
    ctx = _context()
    expected = sum(
        legacy._branch_matches(
            r.get("branch"), legacy._build_fatura_inceleme_context(ctx.slice_for_claim(c.claim_id))
        )
        for c in ctx.claims
        for r in legacy.load_fatura_inceleme_rules()["rules"]
    )
    adapter.evaluate_fatura_inceleme("P1", ctx)
    assert branch_calls == 182
    assert condition_calls == expected


# EI-24: five authored rules name no billed evidence. Four have no condition at all and GÖĞÜS-6 only the
# inpatient setting, so their branch and setting matched every bill of the department.
_ASPIRATION = "GÖĞÜS_HASTALIKLARI-6.yatan_hasta_derin_trakeal_aspirasyon"
_NO_EVIDENCE = (
    _ASPIRATION,
    "KARDİYOLOJİ-4.ayni_seans_periferik_anjiografi",
    "KARDİYOLOJİ-9.kalp_kat_sirasi_cerrahi_sadece_cerrahi",
    "KALP_VE_DAMAR_CERRAHİSİ-1.kag_sonrasi_cabg_islem_yok_kesinti",
    "KALP_VE_DAMAR_CERRAHİSİ-4.ek2b_lazer_tedavi_kdc_odenmez",
)
_NO_EVIDENCE_REASON = "authored_condition_names_no_billed_evidence"


def _bill(department: str, claim_type: str = "ayakta", code: str = "520030") -> PatientClaimContext:
    ctx = _single()
    return replace(
        ctx,
        claims=(replace(ctx.claims[0], department=department, claim_type=claim_type),),
        procedure_lines=(_procedure("C1", "L1", code),),
    )


def test_exactly_five_authored_rules_name_no_billed_evidence() -> None:
    rules = legacy.load_fatura_inceleme_rules()["rules"]
    conditions = {r["rule_id"]: r["condition"] for r in rules}
    assert {rule_id: conditions[rule_id] for rule_id in _NO_EVIDENCE} == {
        _ASPIRATION: {"care_setting": "inpatient"},
        **{rule_id: {} for rule_id in _NO_EVIDENCE[1:]},
    }
    assert sorted(r for r, c in conditions.items() if not legacy._names_billed_evidence(c)) == sorted(_NO_EVIDENCE)
    # a setting beside a billed fact, or a fact of another kind, names evidence
    assert legacy._names_billed_evidence({"care_setting": "inpatient", "procedure_code_any": ["608320"]})
    assert legacy._names_billed_evidence({"payment_method_path": "itemized"})
    assert not legacy._names_billed_evidence({})


@pytest.mark.parametrize(
    "department,claim_type,rule_ids",
    [
        ("Göğüs Hastalıkları", "yatis", (_ASPIRATION,)),
        ("Kardiyoloji", "ayakta", _NO_EVIDENCE[1:3]),
        ("Kardiyoloji", "yatis", _NO_EVIDENCE[1:3]),
        ("KVC", "yatis", _NO_EVIDENCE[3:]),
    ],
)
def test_a_rule_naming_no_billed_evidence_is_unavailable_on_every_bill_of_its_branch(
    department, claim_type, rule_ids
) -> None:
    """The bill bills an examination and nothing the guideline's case is about: no match, no review, no raw row."""
    ctx = _bill(department, claim_type)
    batch = adapter.evaluate_fatura_inceleme("P1", ctx)
    for rule_id in rule_ids:
        row = _row(batch, rule_id)
        assert row.evaluation_status == "unavailable"
        assert row.decision is None
        assert row.reason == _NO_EVIDENCE_REASON
        assert row.missing_inputs == []
        assert not any(r.rule_id == rule_id for r in batch.matches)
        assert not any(r.rule_id == rule_id for r in batch.legacy_rows)
    assert not {v["rule_id"] for v in legacy.check_fatura_inceleme_for_context(ctx)} & set(_NO_EVIDENCE)
    _assert_raw_parity(batch, ctx)


def test_a_rule_keyed_on_a_billed_code_still_matches_beside_one_that_names_none() -> None:
    batch = adapter.evaluate_fatura_inceleme("P1", _single())  # Kardiyoloji, 800800 billed
    assert _row(batch, _CARDIOLOGY).decision == "matched"
    assert any(r.rule_id == _CARDIOLOGY for r in batch.matches)
    assert _row(batch, _NO_EVIDENCE[1]).reason == _NO_EVIDENCE_REASON
    assert {r.rule_id for r in batch.legacy_rows} & set(_NO_EVIDENCE) == set()
    _assert_raw_parity(batch, _single())


@pytest.mark.parametrize(
    "department,claim_type,rule_id",
    [
        ("Göğüs Hastalıkları", "ayakta", _ASPIRATION),  # the setting excludes it: an outpatient bill
        ("Dermatoloji", "yatis", _ASPIRATION),  # the branch excludes it
        ("Dermatoloji", "ayakta", _NO_EVIDENCE[1]),
        ("Göğüs Hastalıkları", "yatis", _NO_EVIDENCE[3]),
    ],
)
def test_a_rule_naming_no_billed_evidence_stays_a_clean_negative_outside_its_branch_or_setting(
    department, claim_type, rule_id
) -> None:
    ctx = _bill(department, claim_type)
    batch = adapter.evaluate_fatura_inceleme("P1", ctx)
    row = _row(batch, rule_id)
    assert (row.evaluation_status, row.decision) == ("evaluated", "not_matched")
    _assert_raw_parity(batch, ctx)


def test_a_rule_naming_no_billed_evidence_gives_no_raw_row_behind_an_uncertain_branch_either() -> None:
    """The first procedure's specialty matches the branch, the department does not: still no raw row."""
    ctx = _bill("", "ayakta")
    ctx = replace(ctx, procedure_lines=(replace(ctx.procedure_lines[0], procedure_specialty_code="Kardiyoloji"),))
    batch = adapter.evaluate_fatura_inceleme("P1", ctx)
    row = _row(batch, _NO_EVIDENCE[1])
    assert (row.evaluation_status, row.reason) == ("unavailable", "first_procedure_specialty_proxy")
    assert not {r.rule_id for r in batch.legacy_rows} & set(_NO_EVIDENCE)
    _assert_raw_parity(batch, ctx)

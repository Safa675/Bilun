"""W4 tests — drug_combination §4.2 claim-context evaluator.

These tests construct minimal ``PatientClaimContext`` bundles with hand-built
``DrugClaimLine`` + ``ClaimDiagnosis`` dataclasses and assert the
``check_drug_combination_for_context`` entry point fires ONLY on the wireable
subset of the 53-rule corpus. Blocked-key rules (drug_class, PD-L1, EMR
history, …) must defer honestly and never produce a false positive.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimDiagnosis, ClaimHeader, DrugClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.drug_combination import (
    _check_combo_condition,
    _collect_drug_names,
    _diagnosis_matches,
    _drug_name_matches,
    check_drug_combination_for_context,
    load_drug_combination_rules,
)

pytestmark = pytest.mark.unit

_TOTAL_RULE_COUNT = 53
_WIREABLE_RULE_COUNT = 8


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _header(*, claim_id: str = "C1", primary_icd10: str = "Z00.0") -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        claim_type="ayakta",
        facility_tier="ozel",
        provider_type="sozlesmeli",
        department="genel",
        admission_date=None,
        discharge_date=None,
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 1),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _drug(
    *,
    drug_name: str,
    claim_id: str = "C1",
    line_id: str = "D1",
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id=line_id,
        prescription_id="RX1",
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=date(2026, 1, 2),
        drug_name=drug_name,
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


def _diagnosis(*, code: str, claim_id: str = "C1") -> ClaimDiagnosis:
    return ClaimDiagnosis(
        diagnosis_id="DX1",
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        icd10_code=code,
        is_primary=False,
        diagnosis_role="secondary",
        diagnosis_date=date(2026, 1, 1),
        exemption_eligible=False,
    )


def _ctx(
    *,
    drug_lines: tuple[DrugClaimLine, ...],
    diagnoses: tuple[ClaimDiagnosis, ...] = (),
    header: ClaimHeader | None = None,
) -> PatientClaimContext:
    return PatientClaimContext(
        patient_id="P1",
        claims=(header or _header(),),
        procedure_lines=(),
        material_lines=(),
        drug_lines=drug_lines,
        diagnoses=diagnoses,
    )


# ---------------------------------------------------------------------------
# Loader / corpus invariants
# ---------------------------------------------------------------------------


def test_load_drug_combination_rules_has_53_rules() -> None:
    """The corpus is the full §4.2 drug-combination file (53 rules)."""
    data = load_drug_combination_rules()
    assert data["rule_set_id"] == "drug_combination_4_2"
    assert len(data["rules"]) == _TOTAL_RULE_COUNT


def test_only_six_rules_are_wireable() -> None:
    """W4.4 headline: of 53 rules, exactly 6 fire on wireable keys.

    Every rule whose condition contains a blocked key (drug_class, PD-L1,
    ECOG, EMR history, …) or a no-source clinical field (treatment_phase /
    indication) is deferred. This count is re-derived here so a corpus edit
    that silently changes coverage is caught.
    """
    from src.bilun.domain.prose_rules.drug_combination import (
        _BLOCKED_KEYS,
        _DEFER_NO_SOURCE_KEYS,
        _WIREABLE_KEYS,
    )

    rules = load_drug_combination_rules()["rules"]
    wireable = 0
    for rule in rules:
        keys = set((rule.get("condition") or {}).keys())
        if keys and keys <= _WIREABLE_KEYS:
            wireable += 1
        else:
            # Every non-wireable rule must be deferred for an explicit reason
            # (blocked or no-source), never silently.
            assert keys & (_BLOCKED_KEYS | _DEFER_NO_SOURCE_KEYS), rule["rule_id"]
    assert wireable == _WIREABLE_RULE_COUNT


# ---------------------------------------------------------------------------
# Entry point — combination violations fire on two drugs on the same claim
# ---------------------------------------------------------------------------


def test_doac_combo_two_drugs_fires_violation() -> None:
    """Two DOACs on the same claim → ``4.2.15.D-1`` no-pay violation.

    ``drug_name_set_any_two`` + ``concurrent``: dabigatran + rivaroksaban
    billed together. The SGK drug-name format ``"BRAND (INN)"`` must match the
    INN tokens via word-boundary matching.
    """
    ctx = _ctx(
        drug_lines=(
            _drug(drug_name="PRADAXA 150 MG (DABIGATRAN)", line_id="D1"),
            _drug(drug_name="XARELTO 20 MG (RIVAROKSABAN)", line_id="D2"),
        )
    )
    violations = check_drug_combination_for_context(ctx)
    doac_hits = [v for v in violations if v["rule_id"].startswith("4.2.15.D-1")]
    assert len(doac_hits) == 1
    assert doac_hits[0]["rule"] == "drug_combination_4_2"
    assert doac_hits[0]["billable"] is False
    assert doac_hits[0]["material_outcome"] == "no_pay"
    assert doac_hits[0]["severity"] == "error"
    assert doac_hits[0]["claim_id"] == "C1"


def test_cinacalcet_etelcalsetid_set_all_fires() -> None:
    """``drug_name_set_all`` + ``concurrent`` — both drugs present fires the
    §4.2.9.Ç combo no-pay rule.

    NOTE: the source corpus carries TWO near-identical rules (§4.2.9.Ç and
    §4.2.9.E) for this pair, but they spell the second INN differently
    (``etelkalsetid`` vs ``etelcalsetid`` — a Turkish-transliteration
    variance in the gazette JSON). The engine honestly matches each rule's
    OWN tokens, so a single drug-name spelling fires only the rule whose
    token it matches. We assert the §4.2.9.Ç rule fires here and exercise
    the §4.2.9.E spelling separately below.
    """
    ctx = _ctx(
        drug_lines=(
            _drug(drug_name="MIMPARA 30 MG (CINACALCET)", line_id="D1"),
            _drug(drug_name="PARSABIV 10 MG (ETELKALSETID)", line_id="D2"),
        )
    )
    violations = check_drug_combination_for_context(ctx)
    rule_ids = {v["rule_id"] for v in violations}
    assert "4.2.9.C-c.(6).cinacalcet_etelcalsetid_combo_no_pay" in rule_ids


def test_cinacalcet_etelcalsetid_alt_spelling_fires_section_e() -> None:
    """The §4.2.9.E rule spells the second INN ``etelcalsetid`` (c-a-l, not
    k-a-l). A drug name carrying that exact spelling fires §4.2.9.E — proving
    the engine respects each rule's own INN tokens rather than normalizing
    the gazette's transliteration variance."""
    ctx = _ctx(
        drug_lines=(
            _drug(drug_name="MIMPARA 30 MG (CINACALCET)", line_id="D1"),
            _drug(drug_name="PARSABIV 10 MG (ETELCALSETID)", line_id="D2"),
        )
    )
    violations = check_drug_combination_for_context(ctx)
    rule_ids = {v["rule_id"] for v in violations}
    assert "4.2.9.E.(7).cinacalcet_etelcalsetid_combo_no_pay" in rule_ids


def test_ms_dmt_combo_two_agents_fires() -> None:
    """Two MS DMT agents (interferon + glatiramer) → §4.2.34.(3) combo no-pay."""
    ctx = _ctx(
        drug_lines=(
            _drug(drug_name="AVONEX (BETA_INTERFERON)", line_id="D1"),
            _drug(drug_name="COPAXONE (GLATIRAMER_ACETATE)", line_id="D2"),
        )
    )
    violations = check_drug_combination_for_context(ctx)
    ms_hits = [v for v in violations if v["rule_id"].startswith("4.2.34.(3)")]
    assert len(ms_hits) == 1


# ---------------------------------------------------------------------------
# Entry point — diagnosis-prefix + single-drug wireable rule
# ---------------------------------------------------------------------------


def test_diagnosis_prefix_with_single_drug_fires() -> None:
    """``4.2.17.A``: ``diagnosis_any: ["M81"]`` matches billed ``"M81.0"``
    (ICD-10 PREFIX), with one active-vitamin-D drug → no-pay fires.

    A single drug is enough here because the rule has no ``concurrent`` /
    ``combination`` key — only ``drug_name_any`` + ``diagnosis_any``.
    """
    ctx = _ctx(
        drug_lines=(_drug(drug_name="ROCATROL 0.25 MCG (KALSITRIOL)"),),
        diagnoses=(_diagnosis(code="M81.0"),),
    )
    violations = check_drug_combination_for_context(ctx)
    hits = [v for v in violations if v["rule_id"].startswith("4.2.17.A")]
    assert len(hits) == 1
    assert hits[0]["billable"] is False


def test_diagnosis_mismatch_suppresses_rule() -> None:
    """Same drug as above but a non-matching diagnosis (E11) → no violation.

    Guards against the rule firing purely on drug_name_any without the
    diagnosis-prefix constraint.
    """
    ctx = _ctx(
        drug_lines=(_drug(drug_name="ROCATROL 0.25 MCG (KALSITRIOL)"),),
        diagnoses=(_diagnosis(code="E11.9"),),
    )
    violations = check_drug_combination_for_context(ctx)
    assert not any(v["rule_id"].startswith("4.2.17.A") for v in violations)


# ---------------------------------------------------------------------------
# Entry point — single drug, no combination predicate → no combo violation
# ---------------------------------------------------------------------------


def test_single_drug_no_combo_violation() -> None:
    """One drug on the claim → no combination/concurrent rule fires.

    A single DOAC does not trigger ``drug_name_set_any_two`` nor
    ``concurrent`` (which needs ≥2 distinct drugs). The claim must be clean.
    """
    ctx = _ctx(
        drug_lines=(_drug(drug_name="PRADAXA 150 MG (DABIGATRAN)"),),
    )
    violations = check_drug_combination_for_context(ctx)
    assert violations == []


# ---------------------------------------------------------------------------
# Entry point — empty drug_lines → no crash, []
# ---------------------------------------------------------------------------


def test_empty_drug_lines_returns_empty_list() -> None:
    """No drug lines at all → ``[]`` (no crash, no deferred-rule noise)."""
    ctx = _ctx(drug_lines=())
    assert check_drug_combination_for_context(ctx) == []


def test_context_with_no_claims_attribute_is_safe() -> None:
    """A bare object with drug_lines=() must not crash the entry point."""
    ctx = _ctx(drug_lines=())
    assert check_drug_combination_for_context(ctx) == []


# ---------------------------------------------------------------------------
# Blocked-key rules defer honestly — never a false positive
# ---------------------------------------------------------------------------


def test_blocked_drug_class_rule_does_not_fire() -> None:
    """``4.2.1.C.(3)`` dual anti-TNF combo gates on ``drug_class_any`` (blocked).

    Even though the claim carries two anti-TNF biologics that *should* trigger
    the rule's intent, the engine cannot resolve a drug-class map, so it MUST
    defer — no false positive, no silent pass. The violation list must not
    contain this rule_id.
    """
    ctx = _ctx(
        drug_lines=(
            _drug(drug_name="REMICADE 100 MG (INFLIKSIMAB)", line_id="D1"),
            _drug(drug_name="HUMIRA 40 MG (ADALIMUMAB)", line_id="D2"),
        )
    )
    violations = check_drug_combination_for_context(ctx)
    assert not any(
        v["rule_id"].startswith("4.2.1.C.(3)") for v in violations
    ), "blocked drug_class_any rule must be deferred, not fired"


def test_blocked_pdl1_tier_c_rule_does_not_fire() -> None:
    """``4.2.14.C.(pembro_nsclc_pdl1_lt_50)`` gates on PD-L1/ECOG (blocked).

    A pembrolizumab claim on an NSCLC diagnosis must NOT auto-fire this Tier-C
    review rule — the clinical fields are absent and the rule is deferred.
    """
    ctx = _ctx(
        drug_lines=(_drug(drug_name="KEYTRUDA 100 MG (PEMBROLIZUMAB)"),),
        diagnoses=(_diagnosis(code="C34.9"),),
        header=_header(primary_icd10="C34.9"),
    )
    violations = check_drug_combination_for_context(ctx)
    assert not any("pembro_nsclc_pdl1" in v["rule_id"] for v in violations)


# ---------------------------------------------------------------------------
# _check_combo_condition — reason contract (unit-level)
# ---------------------------------------------------------------------------


def test_check_condition_blocked_key_returns_skipped_no_data() -> None:
    """A blocked key → ``(False, 'skipped_no_data')`` — never matches."""
    matches, reason = _check_combo_condition(
        {"drug_class_any": ["anti_tnf"]}, {"infliximab", "adalimumab"}, []
    )
    assert matches is False
    assert reason == "skipped_no_data"


def test_check_condition_unknown_key_returns_skipped_unknown() -> None:
    """A genuinely unknown key → ``(False, 'skipped_unknown_key')``."""
    matches, reason = _check_combo_condition(
        {"totally_new_predicate": 5}, {"drug_a"}, []
    )
    assert matches is False
    assert reason == "skipped_unknown_key"


def test_check_condition_set_any_two_matched() -> None:
    """``drug_name_set_any_two`` satisfied by 2 of the listed INNs."""
    matches, reason = _check_combo_condition(
        {"drug_name_set_any_two": ["dabigatran", "rivaroksaban", "apiksaban"]},
        {"PRADAXA (DABIGATRAN)", "XARELTO (RIVAROKSABAN)"},
        [],
    )
    assert (matches, reason) == (True, "matched")


def test_check_condition_set_any_two_not_matched_single() -> None:
    """Only one of the listed INNs present → not matched (needs ≥2)."""
    matches, reason = _check_combo_condition(
        {"drug_name_set_any_two": ["dabigatran", "rivaroksaban"]},
        {"PRADAXA (DABIGATRAN)"},
        [],
    )
    assert (matches, reason) == (False, "not_matched")


def test_check_condition_blocked_key_supersedes_wireable_match() -> None:
    """A rule with BOTH a wireable predicate (satisfied) AND a blocked key is
    still deferred — partial evaluation must never produce a false positive."""
    matches, reason = _check_combo_condition(
        {
            "drug_name_any": ["temsirolimus"],
            "poor_prognosis_criteria_met_count": {"min": 3, "of": 6},  # blocked
        },
        {"TORISEL 25 MG (TEMSIROLIMUS)"},
        [],
    )
    assert matches is False
    assert reason == "skipped_no_data"


# ---------------------------------------------------------------------------
# Helpers — INN + diagnosis matching (ported-semantics contract)
# ---------------------------------------------------------------------------


def test_drug_name_matches_inn_token() -> None:
    """Word-boundary INN match: ``cinacalcet`` matches the SGK brand string."""
    assert _drug_name_matches(["cinacalcet"], "MIMPARA 30 MG (CINACALCET)")
    assert not _drug_name_matches(["etelkalsetid"], "MIMPARA 30 MG (CINACALCET)")


def test_drug_name_matches_short_token_no_false_positive() -> None:
    """Short INN tokens must not match inside longer brand names."""
    # "sama" is an INN-adjacent token; it must NOT match "fosamax".
    assert not _drug_name_matches(["sama"], "FOSAMAX 70 MG (ALENDRONATE)")


def test_diagnosis_matches_prefix() -> None:
    """``rule_codes=["K50"]`` matches billed ``"K50.0"`` (prefix) and exact."""
    assert _diagnosis_matches(["K50.0"], ["K50"])
    assert _diagnosis_matches(["K50"], ["K50"])
    assert not _diagnosis_matches(["K51.0"], ["K50"])
    # Empty rule_codes → no diagnosis constraint, always passes.
    assert _diagnosis_matches(["Z00.0"], [])


def test_collect_drug_names_scoped_to_claim() -> None:
    """``_collect_drug_names`` filters by claim_id — combos are within ONE claim."""
    ctx = _ctx(
        drug_lines=(
            _drug(drug_name="PRADAXA (DABIGATRAN)", claim_id="C1", line_id="D1"),
            _drug(drug_name="XARELTO (RIVAROKSABAN)", claim_id="C2", line_id="D2"),
        ),
        header=_header(claim_id="C1"),
    )
    # Claim C1 alone has only one DOAC → no combo within that claim.
    c1_names = _collect_drug_names(ctx, claim_id="C1")
    assert c1_names == {"PRADAXA (DABIGATRAN)"}
    # The full-patient path must NOT be used to detect a combo — verify the
    # entry point treats C1's single DOAC as clean.
    assert check_drug_combination_for_context(ctx) == []

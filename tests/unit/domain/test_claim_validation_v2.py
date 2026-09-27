"""Single-pass v2 retains raw compatibility without certifying adapter defaults."""

from copy import deepcopy

import pytest

from src.bilun.domain import claim_validation_v2 as service
from src.bilun.domain import rule_engine
from src.bilun.domain.billing import engine
from src.bilun.domain.billing.broad_rule_materializer import BROAD_FAMILY_ORDER
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.validation_serialization import serialize_legacy_validation_result

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("claim", [
    {"materials": []},
    {"claim_id": "C1", "materials": [{"name": "Bistüri ucu", "unit_price": 100}]},
    {"claim_id": "C1", "materials": [{"name": "altın kanal tedavisi", "billed_amount": 100}]},
    {"claim_id": "C1", "materials": [{"name": "Trastuzumab", "billed_amount": 100}],
     "drug_context": {"primary_icd10": "C50.9"}},
    {"materials": [{"name": "Trastuzumab", "billed_amount": 100}],
     "drug_context": {"primary_icd10": "C50.9"}},
    {"claim_id": "C1", "materials": [{"name": "dabigatran"}, {"name": "rivaroksaban"}],
     "drug_context": {"primary_icd10": "Z00.0"}},
    {"materials": [{"name": "dabigatran"}, {"name": "rivaroksaban"}],
     "drug_context": {"primary_icd10": "Z00.0"}},
])
def test_complete_historical_payload_parity_without_rerunning_broad_wrappers(monkeypatch, claim):
    monkeypatch.setattr(rule_engine.time, "perf_counter", lambda: 100)
    expected = serialize_legacy_validation_result(rule_engine.validate_claim(claim))
    calls = []
    original = service.materialize_broad_rules

    def materialize(*args):
        calls.append(args[0])
        return original(*args)

    monkeypatch.setattr(service, "materialize_broad_rules", materialize)
    for name in (
        "check_dental_2_4_1_for_context", "check_gap_closing_misc_for_context",
        "check_gap_closing_treatment_for_context", "check_fatura_inceleme_for_context",
        "check_payment_method_traceability_for_context", "check_drug_combination_for_context",
        "check_treatment_pricing_for_context",
    ):
        monkeypatch.setattr(engine, name, lambda _: pytest.fail("Broad wrapper ran twice"))
    source = deepcopy(claim)
    actual = service.validate_claim_v2(claim, supplied_claim=claim)
    assert actual["legacy_result"] == expected
    assert len(calls) == 1
    assert claim == source
    assert actual["contract_version"] == 2
    assert actual["violations"] == []
    assert actual["is_valid"] is None


def test_compact_coverage_counts_every_authored_id_at_actual_material_scope():
    claim = {"materials": [{"name": "same"}, {"name": "same"}]}
    result = service.validate_claim_v2(claim, supplied_claim=claim)
    assert result["coverage"]["authored_rule_count"] == 496
    assert result["coverage"]["evaluation_count"] == 477 + 19 * 2
    assert sum(result["coverage"]["disposition_counts"].values()) == 515
    assert "evaluations" not in result
    assert len({x["evidence_id"] for x in result["advisories"]}) == len(result["advisories"])


def test_prepared_engine_requires_complete_family_mapping_and_preserves_guards():
    ctx = build_context_from_material_dict({"materials": [{"name": "plain"}]})
    with pytest.raises(ValueError, match="exactly seven"):
        engine.analyze_claim(ctx, prepared_broad_rows={})
    prepared = {family: () for family in BROAD_FAMILY_ORDER}
    prepared["drug_combination_4_2"] = ({"rule": "must_not_run_drug"},)
    prepared["treatment_pricing_2_4"] = ({"rule": "must_not_run_treatment"},)
    rows = engine.analyze_claim(ctx, prepared_broad_rows=prepared)
    assert not any(row["rule"].startswith("must_not_run") for row in rows)


@pytest.mark.parametrize("name,family,reason", [
    ("Bistüri ucu", "bundling", "ek3b1_exception_setting_and_exact_line_proof_required"),
    ("İnflow kateter", "exclusion", "ek3b2_exception_applicability_and_exact_line_proof_required"),
])
def test_annex_observations_require_family_specific_proof_before_compliance(name, family, reason):
    claim = {"materials": [{"name": name, "billed_amount": 100}]}
    result = service.validate_claim_v2(claim, supplied_claim=claim)
    assert result["violations"] == []
    assert any(row["rule"] == family for row in result["legacy_result"]["violations"])
    review = next(row for row in result["advisories"] if row["rule"] == family)
    assert review["reason"] == reason
    assert "risk_amount" not in review
    assert "savings_try" not in review


@pytest.mark.parametrize("name,family", [
    ("Cerrahi steril eldiven", "bundling"),
    ("Viskosüplemantasyon ürünleri", "exclusion"),
])
def test_corrected_annex_predicates_do_not_reappear_as_review_or_legacy_denials(name, family):
    claim = {"materials": [{"name": name, "billed_amount": 100}]}
    result = service.validate_claim_v2(claim, supplied_claim=claim)
    assert not any(row["rule"] == family for row in result["legacy_result"]["violations"])
    assert not any(row["rule"] == family for row in result["advisories"])
    # Independent identity requirement remains; it is not the corrected annex predicate.
    assert any(row.get("details", {}).get("rule_id") == "3.1.1.(11).missing_material_code"
               for row in result["legacy_result"]["violations"])

"""Request defaults never become observed clinical, charge, or date facts."""

from dataclasses import replace
from decimal import Decimal

import pytest

from src.bilun.domain.billing.dental_rule_evaluations import evaluate_dental_rules
from src.bilun.domain.billing.rule_findings import RuleEvaluation
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.validation_provenance import build_validation_provenance

pytestmark = pytest.mark.unit


def _request(billed=None):
    material = {"name": "altın kanal tedavisi", "unit_price": 100, "quantity": 1}
    if billed is not None:
        material["billed_amount"] = billed
    return {"claim_id": "C1", "materials": [material]}


def _provenance(claim):
    return build_validation_provenance(build_context_from_material_dict(claim), claim)


def test_default_dates_care_setting_category_and_price_are_not_verified_facts():
    data = _provenance(_request())
    observed = data.observation_context
    typed = data.typed_context
    assert observed.claims[0].claim_type == "ayakta"
    assert observed.material_lines[0].billed_amount_try == Decimal("100")
    assert observed.material_lines[0].specialty_category == "dental_restoration"
    assert typed.claims[0].claim_type == ""
    assert typed.claims[0].claim_start_date is None
    assert typed.material_lines[0].material_date is None
    assert typed.material_lines[0].billed_amount_try is None
    assert typed.material_lines[0].specialty_category == ""
    assert data.request_id.startswith("validation_request:")
    assert typed.patient_id == observed.patient_id == data.request_id


def test_supplied_zero_is_distinct_from_missing_and_legacy_price_fallback():
    data = _provenance(_request(0))
    assert data.observation_context.material_lines[0].billed_amount_try == Decimal("100")
    assert data.typed_context.material_lines[0].billed_amount_try == Decimal("0")
    assert "materials[0].billed_amount" in data.supplied_fields


def test_request_and_positional_identities_are_stable_without_joining_equal_names():
    claim = _request()
    claim["materials"].append(dict(claim["materials"][0]))
    first, second = _provenance(claim), _provenance(dict(reversed(list(claim.items()))))
    assert first.request_id == second.request_id
    assert first.observation_context == second.observation_context
    assert len({row.material_line_id for row in first.observation_context.material_lines}) == 2
    assert (
        first.typed_context.material_lines[0].material_line_id
        == first.observation_context.material_lines[0].material_line_id
    )


@pytest.mark.parametrize("decision", ["matched", "not_matched"])
def test_fabricated_care_setting_cannot_produce_either_typed_conclusion(decision):
    data = _provenance(_request())
    observation = RuleEvaluation(
        patient_id=data.request_id,
        claim_id=data.observation_context.claims[0].claim_id,
        rule_id="test-condition",
        evaluation_status="evaluated",
        required_inputs=["care_setting"],
        missing_inputs=[],
        decision=decision,
    )
    typed = data.gate_evaluation(observation)
    assert typed.evaluation_id == observation.evaluation_id
    assert typed.evaluation_status == "missing_inputs"
    assert typed.decision is None
    assert typed.reason == "request_input_provenance_unavailable"
    assert typed.missing_inputs == ["care_setting"]
    assert observation.decision == decision


def test_name_inferred_dental_category_is_held_for_real_adapter_match_and_nonmatch():
    data = _provenance(_request())
    batch = evaluate_dental_rules(data.request_id, data.observation_context)
    first = batch.evaluations[0]
    assert first.decision == "matched"
    assert data.gate_evaluation(first).evaluation_status == "missing_inputs"
    changed = replace(first, decision="not_matched")
    assert data.gate_evaluation(changed).evaluation_status == "missing_inputs"


@pytest.mark.parametrize("decision", ["matched", "not_matched"])
def test_authored_dependencies_cannot_be_omitted_from_provenance_gate(decision):
    data = _provenance(_request())
    first = evaluate_dental_rules(data.request_id, data.observation_context).evaluations[0]
    shortened = replace(first, required_inputs=[], decision=decision)
    gated = data.gate_evaluation(shortened)
    assert gated.evaluation_status == "missing_inputs"
    assert gated.decision is None
    assert "procedure_category" in gated.required_inputs
    assert "procedure_category" in gated.missing_inputs


def test_supplied_material_code_alias_is_a_real_code_fact():
    claim = _request()
    claim["materials"][0]["material_code"] = "TEST-CODE"
    data = _provenance(claim)
    observation = RuleEvaluation(
        patient_id=data.request_id,
        claim_id=data.observation_context.claims[0].claim_id,
        rule_id="code-only",
        line_kind="material",
        line_id=data.observation_context.material_lines[0].material_line_id,
        evaluation_status="evaluated",
        required_inputs=["material_code"],
        missing_inputs=[],
        decision="not_matched",
    )
    assert data.typed_context.material_lines[0].material_code == "TEST-CODE"
    assert data.gate_evaluation(observation) == observation


def test_a_raw_name_only_observation_can_use_the_exact_supplied_material_name():
    data = _provenance(_request())
    observation = RuleEvaluation(
        patient_id=data.request_id,
        claim_id=data.observation_context.claims[0].claim_id,
        rule_id="name-only",
        line_kind="material",
        line_id=data.observation_context.material_lines[0].material_line_id,
        evaluation_status="evaluated",
        required_inputs=["material_name_any"],
        missing_inputs=[],
        decision="not_matched",
    )
    assert data.gate_evaluation(observation) == observation


def test_provenance_cannot_be_applied_to_an_unrelated_observation():
    data = _provenance(_request())
    row = RuleEvaluation(
        patient_id="other",
        claim_id="C1",
        rule_id="name-only",
        evaluation_status="evaluated",
        required_inputs=[],
        missing_inputs=[],
        decision="not_matched",
    )
    with pytest.raises(ValueError, match="another request"):
        data.gate_evaluation(row)


def test_supplied_facts_must_correspond_to_actual_observed_positions():
    claim = _request()
    legacy = build_context_from_material_dict(claim)
    claim["materials"][0]["name"] = "different material"
    with pytest.raises(ValueError, match="observed source position"):
        build_validation_provenance(legacy, claim)


def test_drug_date_and_zero_defaults_remain_missing_without_rejoining_duplicate_names():
    claim = {
        "claim_id": "C1",
        "drug_context": {"primary_icd10": "C50.9"},
        "materials": [
            {"name": "", "unit_price": 1},
            {"name": "Trastuzumab", "unit_price": 100},
            {"name": "Trastuzumab", "unit_price": 100, "billed_amount": 0},
        ],
    }
    data = _provenance(claim)
    assert len(data.typed_context.drug_lines) == 2
    assert data.typed_context.drug_lines[0].billed_amount_try is None
    assert data.typed_context.drug_lines[1].billed_amount_try == Decimal("0")
    assert all(row.drug_claim_date is None for row in data.typed_context.drug_lines)
    assert len({row.drug_claim_line_id for row in data.typed_context.drug_lines}) == 2

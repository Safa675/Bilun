"""SMA explicit history, medicine scope, service dates, and partial-result honesty."""
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta
import json

import pytest

from src.bilun.domain.claims.clinical_evidence import SmaEvidence, parse_clinical_evidence
from src.bilun.domain.prose_rules._drug_indication.clinical_sma import evaluate_sma_safety
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _drug_line

DAY = date(2026, 10, 2)
FIELDS = ('brain_spinal_history_impeding_procedure', 'csf_shunt_or_catheter',
          'bacterial_meningitis_history', 'viral_encephalitis_history',
          'hypoxic_ischemic_encephalopathy', 'hypoxic_birth_neurological_sequelae')


def evidence(**kwargs):
    return SmaEvidence(applies_on=DAY, assessment_date=DAY, sma_type='type_2',
                       lumbar_puncture_suitability_documented=True,
                       **{**dict.fromkeys(FIELDS, False), **kwargs})


def line(drug='nusinersen', facts=None, day=DAY):
    return replace(_drug_line(drug_name=drug, report_present=True),
                   drug_claim_date=day, sma_evidence=facts if facts is not None else evidence())


def test_known_absent_history_clears_only_the_supported_restrictions():
    result = evaluate_sma_safety(line())
    assert result['criterion_status'] == 'criterion_clear'
    assert not result['clinical_eligibility_complete']


@pytest.mark.parametrize('field', FIELDS)
def test_each_documented_exclusion_fails_nusinersen(field):
    assert evaluate_sma_safety(line(facts=evidence(**{field: True})))['criterion_status'] == 'restriction_not_met'


@pytest.mark.parametrize('field', FIELDS)
def test_each_missing_history_fact_remains_unknown(field):
    result = evaluate_sma_safety(line(facts=evidence(**{field: None})))
    assert result['criterion_status'] == 'unknown'
    assert 'sma_evidence.' + field in result['missing_inputs']


@pytest.mark.parametrize('field', FIELDS[:4])
def test_nusinersen_specific_history_does_not_restrict_risdiplam(field):
    result = evaluate_sma_safety(line('risdiplam', evidence(**{field: True})))
    assert result['criterion_status'] == 'criterion_clear'
    assert result['source_refs'] == ['4.2.49.(5)#597ea9c2']


@pytest.mark.parametrize('field', FIELDS[4:])
def test_hypoxic_history_restricts_both_medications(field):
    assert evaluate_sma_safety(line('risdiplam', evidence(**{field: True})))['criterion_status'] == 'restriction_not_met'


@pytest.mark.parametrize('sma_type', ['type_2', 'type_3'])
def test_lumbar_report_required_only_for_nusinersen_type_2_or_3(sma_type):
    facts = replace(evidence(), sma_type=sma_type, lumbar_puncture_suitability_documented=False)
    assert evaluate_sma_safety(line(facts=facts))['criterion_status'] == 'restriction_not_met'
    assert evaluate_sma_safety(line('risdiplam', facts))['criterion_status'] == 'criterion_clear'
    assert evaluate_sma_safety(line(facts=replace(facts, sma_type='type_1')))['criterion_status'] == 'criterion_clear'


@pytest.mark.parametrize('day', [None, 'bad-date', datetime(2026, 10, 2), date(2025, 5, 5), date(2026, 10, 3)])
def test_missing_invalid_or_unsupported_service_date_never_evaluates_history(day):
    result = evaluate_sma_safety(line(facts=evidence(csf_shunt_or_catheter=True), day=day))
    assert result['criterion_status'] == 'not_evaluated'
    assert result['missing_inputs']
    assert result['checks'] == []


def test_effective_date_inclusive_and_explicit_assessment_scope_required():
    day = date(2025, 5, 6)
    facts = replace(evidence(), applies_on=day, assessment_date=day)
    assert evaluate_sma_safety(line(facts=facts, day=day))['criterion_status'] == 'criterion_clear'
    for bad in (replace(facts, applies_on=day-timedelta(days=1)),
                replace(facts, assessment_date=day+timedelta(days=1)),
                replace(facts, assessment_date=None)):
        assert evaluate_sma_safety(line(facts=bad, day=day))['criterion_status'] == 'not_evaluated'


@pytest.mark.parametrize('value', ['false', 0, 1, [], {}, 'yes'])
def test_boolean_coercion_cannot_manufacture_absent_history(value):
    raw = asdict(evidence());raw['csf_shunt_or_catheter'] = value
    parsed = parse_clinical_evidence(raw, SmaEvidence)
    assert parsed.csf_shunt_or_catheter is None
    assert evaluate_sma_safety(line(facts=parsed))['criterion_status'] == 'unknown'


def test_json_transport_preserves_explicit_false_and_dates():
    raw = asdict(evidence())
    raw['applies_on'] = raw['assessment_date'] = DAY.isoformat()
    assert parse_clinical_evidence(json.dumps(raw), SmaEvidence) == evidence()


def test_public_evaluation_cannot_convert_cleared_partial_criteria_to_payment_pass():
    result = evaluate_drug_indication_line_detailed(drug_line=line(), claim=replace(_claim(), primary_icd10='G12.1'), diagnoses=[])
    assert result['clinical_restrictions'][0]['criterion_status'] == 'criterion_clear'
    assert result['evaluation_status'] == 'missing_inputs'
    assert result['violation']['severity'] == 'review'
    assert 'remaining_sut_clinical_criteria' in result['missing_inputs']
    assert result['clinical_eligibility_complete'] is False
    assert not any('amount' in key or 'payable' in key for key in result['violation'])


def test_absent_evidence_and_explicit_empty_corpus_stay_unavailable():
    drug = replace(line(), sma_evidence=None)
    result = evaluate_drug_indication_line_detailed(drug_line=drug, claim=replace(_claim(), primary_icd10='G12.1'), diagnoses=[])
    assert result['violation']['severity'] == 'review'
    assert 'sma_evidence.applies_on' in result['missing_inputs']
    empty = evaluate_drug_indication_line_detailed(drug_line=drug, claim=_claim(), diagnoses=[], rules=[])
    assert empty['evaluation_status'] == 'unavailable'
    assert empty['violation'] is None

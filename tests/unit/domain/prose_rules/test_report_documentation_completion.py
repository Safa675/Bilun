"""Independent report content remains tri-state, source/phase-scoped and private."""
from dataclasses import asdict, fields
from datetime import date
import json
from pathlib import Path

import pytest

from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.claims.clinical_evidence import (
    EnteralEvidence, RenalEvidence, parse_clinical_evidence,
)
from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line
from src.bilun.domain.prose_rules._drug_indication.clinical_enteral import evaluate_enteral_reports
from src.bilun.domain.prose_rules._drug_indication.clinical_renal import evaluate_renal
from src.bilun.shared.models import ClaimValidationRequest, MaterialItem
from tests.unit.api.test_validation_contract_v2 import client, _login  # noqa: F401
from tests.unit.domain.prose_rules.test_enteral_ravulizumab_clinical import enteral
from tests.unit.domain.prose_rules.test_renal_runtime_observations import line as renal, observe, source
from tests.unit.domain.prose_rules.test_pediatric_gh_initiation import evaluate as pediatric

DAY = date(2026, 10, 2)
ENTERAL = 'malnutrition_conditions_documented_in_report'
PHOSPHATE = 'prior_phosphate_therapy_documented_in_report'
CASES = [
    ('enteral_evidence', EnteralEvidence, ENTERAL, enteral, evaluate_enteral_reports),
    ('renal_evidence', RenalEvidence, PHOSPHATE, renal, evaluate_renal),
]


@pytest.mark.parametrize('prefix,cls,field,factory,evaluator', CASES)
@pytest.mark.parametrize('fact,status', [(True, 'criterion_clear'), (False, 'restriction_not_met'), (None, 'unknown')])
def test_report_documentation_is_a_distinct_necessary_fact(prefix, cls, field, factory, evaluator, fact, status):
    out = evaluator(factory(**{field: fact}))
    assert out['criterion_status'] == status
    assert out['clinical_eligibility_complete'] is False
    assert {'field': prefix + '.' + field, 'status': 'unknown' if fact is None else 'pass' if fact else 'fail'} in out['checks']
    assert (prefix + '.' + field in out['missing_inputs']) is (fact is None)


@pytest.mark.parametrize('prefix,cls,field,factory,evaluator', CASES)
@pytest.mark.parametrize('bad', ['true', 'false', 0, 1, {}, [], float('nan')])
def test_invalid_documentation_facts_stay_unknown_in_dataclass_request_and_row_transport(prefix, cls, field, factory, evaluator, bad):
    raw = asdict(factory()); facts = raw[prefix]; facts[field] = bad
    assert getattr(parse_clinical_evidence(facts, cls), field) is None
    assert getattr(parse_clinical_evidence(cls(**facts), cls), field) is None
    req = ClaimValidationRequest.model_validate({'materials': [{'name': raw['drug_name'], prefix: facts}],
        'drug_context': {'service_date': DAY}})
    for mode in ('python', 'json'):
        typed = build_context_from_material_dict(req.model_dump(mode=mode)).drug_lines[0]
        assert getattr(getattr(typed, prefix), field) is None
    errors = []
    assert getattr(getattr(parse_drug_line(raw, errors), prefix), field) is None
    assert errors == []
    assert evaluator(factory(**{field: bad}))['criterion_status'] == 'unknown'


@pytest.mark.parametrize('prefix,cls,field,factory,evaluator', CASES)
@pytest.mark.parametrize('fact', [True, False, None])
def test_json_and_typed_transport_preserve_documentation_fact(prefix, cls, field, factory, evaluator, fact):
    raw = asdict(factory(**{field: fact})); errors = []
    direct = parse_drug_line(raw, errors)
    raw[prefix] = json.dumps(raw[prefix], default=lambda d: d.isoformat())
    encoded = parse_drug_line(raw, errors)
    assert errors == []
    assert getattr(getattr(direct, prefix), field) is fact
    assert getattr(direct, prefix) == getattr(encoded, prefix)


def test_enteral_report_content_does_not_substitute_for_clinical_conditions_or_report_presence():
    for patch in ({'malnutrition_criteria_met': False}, {'specialist_report_present': False}):
        assert evaluate_enteral_reports(enteral(**patch))['criterion_status'] == 'restriction_not_met'
    for patch in ({'malnutrition_criteria_met': None}, {'specialist_report_present': None}):
        assert evaluate_enteral_reports(enteral(**patch))['criterion_status'] == 'unknown'


@pytest.mark.parametrize('fact', [False, None])
def test_enteral_initiation_wording_is_not_imported_into_renewal_or_exemption(fact):
    renewal = evaluate_enteral_reports(enteral(phase='renewal', report_author_specialty='pediatric_neurology', **{ENTERAL: fact}))
    assert renewal['criterion_status'] == 'criterion_clear'
    assert not any(c['field'].endswith(ENTERAL) for c in renewal['checks'])
    still_needed = evaluate_enteral_reports(enteral(phase='renewal', report_author_specialty='pediatric_neurology', malnutrition_criteria_met=False, **{ENTERAL: fact}))
    assert still_needed['criterion_status'] == 'restriction_not_met'
    exempt = evaluate_enteral_reports(enteral(malnutrition_path='exemption', **{ENTERAL: fact}))
    assert exempt['criterion_status'] == 'not_evaluated' and exempt['checks'] == []


@pytest.mark.parametrize('phase', ['initiation', 'restart'])
@pytest.mark.parametrize('fact,status', [(True, 'criterion_clear'), (False, 'restriction_not_met'), (None, 'unknown')])
def test_phosphate_initiation_and_restart_import_both_duration_and_report_content(phase, fact, status):
    drug = renal(phase=phase, phosphorus_mg_dl=5, **{PHOSPHATE: fact})
    assert evaluate_renal(drug)['criterion_status'] == status
    assert evaluate_renal(renal(phase=phase, phosphorus_mg_dl=5, other_phosphate_therapy_months=2.99, **{PHOSPHATE: True}))['criterion_status'] == 'restriction_not_met'
    assert evaluate_renal(renal(phase=phase, phosphorus_mg_dl=5, other_phosphate_therapy_months=None, **{PHOSPHATE: True}))['criterion_status'] == 'unknown'


@pytest.mark.parametrize('phase', ['initiation', 'restart'])
@pytest.mark.parametrize('alternative', [
    {'calcium_phosphorus_product': 72},
    {'adynamic_bone_disease': True, 'pth_pg_ml': 99},
    {'kt_v': 1.5, 'corrected_calcium_phosphorus_product': 56},
    {'kt_v': 1.5, 'pth_pg_ml': 300},
])
def test_one_phosphate_alternative_still_suffices(phase, alternative):
    facts = dict.fromkeys(['calcium_phosphorus_product', 'adynamic_bone_disease', 'pth_pg_ml', 'kt_v', 'corrected_calcium_phosphorus_product'])
    assert evaluate_renal(renal(phase=phase, phosphorus_mg_dl=5, **{**facts, **alternative}))['criterion_status'] == 'criterion_clear'


def test_phosphate_continuation_does_not_require_or_observe_initiation_documentation():
    out, collector = observe(renal(phase='continuation', phosphorus_mg_dl=3.5, **{PHOSPHATE: False}))
    assert out['criterion_status'] == 'criterion_clear'
    assert not any(c['field'].endswith(PHOSPHATE) for c in out['checks'])
    assert not any(PHOSPHATE in json.dumps(r) for r in collector.receipts)
    assert collector.summary(source())['predicate_attempted_count'] == 2


@pytest.mark.parametrize('fact,status', [(True, 'passed'), (False, 'failed'), (None, 'missing_inputs')])
def test_phosphate_documentation_has_an_actual_source_bound_observation_without_raw_values(fact, status):
    drug = renal(**{PHOSPHATE: fact}); out, collector = observe(drug)
    assert out == evaluate_renal(drug)
    receipt = next(r for r in collector.receipts if r.get('predicate_id') == 'phosphate.initial.prior_therapy_report')
    assert receipt['status'] == status
    assert receipt['source_refs'] == ['4.2.9.B.(1)#00052268']
    assert ('renal_evidence.' + PHOSPHATE in receipt['observed_input_fields']) is (fact is not None)
    assert receipt['missing_input_fields'] == (['renal_evidence.' + PHOSPHATE] if fact is None else [])
    assert 'value' not in receipt and 'raw_evidence' not in receipt
    report = collector.summary(source())
    assert report['predicate_attempted_count'] == 10
    assert report['predicate_evaluated_count'] == (9 if fact is None else 10)
    assert report['source_clauses_fully_evaluated_count'] is None


def request(prefix, factory, field, fact):
    drug = factory(**{field: fact})
    return ClaimValidationRequest.model_validate({'claim_id': 'documentation-http', 'materials': [
        {'name': drug.drug_name, prefix: {**asdict(getattr(drug, prefix)), 'private_note': 'NEVER_EXPOSE'}}],
        'drug_context': {'service_date': DAY, 'primary_icd10': 'E44.0' if prefix == 'enteral_evidence' else 'N18.5',
                         'board_report_present': True, 'report_duration_months': 6}}).model_dump(mode='json')


@pytest.mark.parametrize('prefix,cls,field,factory,evaluator', CASES)
@pytest.mark.parametrize('fact,status', [(True, 'criterion_clear'), (False, 'restriction_not_met'), (None, 'unknown')])
@pytest.mark.parametrize('claim_id', ['', 'documentation-http'])
@pytest.mark.parametrize('service_date', [DAY, date(2026, 10, 4)])
def test_actual_http_preserves_documentation_status_missing_labels_and_privacy(client, prefix, cls, field, factory, evaluator, fact, status, claim_id, service_date):  # noqa: F811
    _login(client); raw = request(prefix, factory, field, fact); raw['claim_id'] = claim_id
    facts = raw['materials'][0][prefix]
    raw['drug_context']['service_date'] = facts['applies_on'] = facts['assessment_date'] = service_date.isoformat()
    responses = [client.post('/api/validate-claim', json=raw, headers={'X-Bilun-Validation-Contract': '2'}) for _ in range(2)]
    for response in responses:
        assert response.status_code == 200, response.text
        data = response.json(); row = next(r for r in data['advisories'] if r['rule'] == 'drug_indication')
        outcome = next(r for r in row['clinical_restrictions'] if r['constraint_set'] == ('enteral_pediatric_reports_2026' if prefix == 'enteral_evidence' else 'renal_source_constraints'))
        assert outcome['criterion_status'] == status
        assert outcome['source_authority']['status'] == 'admitted'
        assert outcome['source_authority']['service_date'] == service_date.isoformat()
        assert (prefix + '.' + field in row['missing_inputs']) is (fact is None)
        assert data['is_valid'] is None and row['clinical_eligibility_complete'] is False
        assert row['disposition'] == 'review_only'
        serialized = json.dumps(data)
        assert 'NEVER_EXPOSE' not in serialized and 'private_note' not in serialized
        assert not any(token in serialized for token in ['"raw_evidence"', '"receipts"', '"execution_scope"'])
    first, second = [r.json() for r in responses]
    assert first['advisories'] == second['advisories']


@pytest.mark.parametrize('prefix,cls,field,factory,evaluator', CASES)
@pytest.mark.parametrize('date_mode', ['pre_source', 'after_verified', 'mismatched_scope', 'future_assessment', 'missing_service'])
def test_actual_http_blocks_unverified_or_inconsistent_dates_before_documentation(client, prefix, cls, field, factory, evaluator, date_mode):  # noqa: F811
    _login(client); raw = request(prefix, factory, field, False)
    facts = raw['materials'][0][prefix]
    if date_mode in ('pre_source', 'after_verified'):
        day = '2026-10-06' if date_mode == 'after_verified' else '2026-09-04' if prefix == 'enteral_evidence' else '2026-10-01'
        raw['drug_context']['service_date'] = facts['applies_on'] = facts['assessment_date'] = day
    elif date_mode == 'mismatched_scope':
        facts['applies_on'] = '2026-10-01'
    elif date_mode == 'future_assessment':
        facts['assessment_date'] = '2026-10-03'
    else:
        raw['drug_context']['service_date'] = None
    response = client.post('/api/validate-claim', json=raw, headers={'X-Bilun-Validation-Contract': '2'})
    assert response.status_code == 200, response.text
    row = next(r for r in response.json()['advisories'] if r['rule'] == 'drug_indication')
    outcome = next(r for r in row['clinical_restrictions'] if r['constraint_set'] == ('enteral_pediatric_reports_2026' if prefix == 'enteral_evidence' else 'renal_source_constraints'))
    assert outcome['criterion_status'] == 'not_evaluated' and outcome['checks'] == []
    assert response.json()['is_valid'] is None


def test_puberty_contract_states_exact_source_assessment_without_raw_measurement_fields():
    description = MaterialItem.model_json_schema()['properties']['gh_pubertal_status']['description']
    contract = json.loads((Path(__file__).resolve().parents[4] / 'reports/sut-expansion/pediatric-gh-initiation-input-contract.json').read_text())
    assert contract['hints']['gh_pubertal_status'] == description
    assert 'testicular volume >=4 ml in boys or T2 thelarche in girls' in description
    assert 'otherwise leave unknown' in description
    assert contract['puberty_assessment_contract']['additional_attestation_required'] is False
    assert not any('testicular' in name or 'tanner' in name for name in MaterialItem.model_fields)
    assert {f.name for f in fields(EnteralEvidence)} >= {ENTERAL, 'malnutrition_criteria_met'}
    assert {f.name for f in fields(RenalEvidence)} >= {PHOSPHATE, 'other_phosphate_therapy_months'}


def test_puberty_unknown_and_reconciliation_are_not_inferred_from_height_reference_sex():
    unknown = pediatric(gh_pubertal_status=None, gh_height_reference_sex='male')
    assert 'gh_pubertal_status' in unknown['missing_inputs']
    for sex in ('male', 'female', None):
        inconsistent = pediatric(gh_pubertal_status='pubertal', gh_reported_growth_age_band='4_1_prepubertal', gh_height_reference_sex=sex)
        assert 'gh_growth_stage_reconciliation' in inconsistent['missing_inputs']


@pytest.mark.parametrize('fact,status', [(True, 'criterion_clear'), (False, 'restriction_not_met'), (None, 'unknown')])
def test_actual_http_phosphate_restart_requires_prior_therapy_report_content(client, fact, status):  # noqa: F811
    _login(client); raw = request('renal_evidence', renal, PHOSPHATE, fact)
    raw['materials'][0]['renal_evidence'].update(phase='restart', phosphorus_mg_dl=5)
    response = client.post('/api/validate-claim', json=raw, headers={'X-Bilun-Validation-Contract': '2'})
    assert response.status_code == 200, response.text
    row = next(r for r in response.json()['advisories'] if r['rule'] == 'drug_indication')
    outcome = next(r for r in row['clinical_restrictions'] if r['constraint_set'] == 'renal_source_constraints')
    assert outcome['criterion_status'] == status
    assert '4.2.9.B.(1)#00052268' in outcome['source_refs']
    assert '4.2.9.B.(4)#e346bde0' in outcome['source_refs']
    assert outcome['runtime_coverage']['predicate_attempted_count'] == 11


@pytest.mark.parametrize('fact', [False, None])
def test_actual_http_enteral_renewal_keeps_its_separate_source_contract(client, fact):  # noqa: F811
    _login(client); raw = request('enteral_evidence', enteral, ENTERAL, fact)
    raw['materials'][0]['enteral_evidence'].update(phase='renewal', report_author_specialty='pediatric_neurology')
    response = client.post('/api/validate-claim', json=raw, headers={'X-Bilun-Validation-Contract': '2'})
    assert response.status_code == 200, response.text
    row = next(r for r in response.json()['advisories'] if r['rule'] == 'drug_indication')
    outcome = next(r for r in row['clinical_restrictions'] if r['constraint_set'] == 'enteral_pediatric_reports_2026')
    assert outcome['criterion_status'] == 'criterion_clear'
    assert not any(c['field'].endswith(ENTERAL) for c in outcome['checks'])
    assert 'enteral_evidence.' + ENTERAL not in row['missing_inputs']


@pytest.mark.parametrize('prefix,cls,field,factory,evaluator', CASES)
@pytest.mark.parametrize('fact', [True, False, None])
def test_canonical_public_and_cache_roundtrip_keep_status_without_document_values(prefix, cls, field, factory, evaluator, fact):
    import duckdb
    from src.bilun.api.public_responses import project_public_response
    from src.bilun.api.schemas import DrugIndicationReviewResponse
    from src.bilun.domain.billing.drug_indication_findings import evaluate_drug_indication_findings
    from src.bilun.domain.claims.patient_context import PatientClaimContext
    from tests.unit.domain.prose_rules.test_drug_indication import _claim

    drug = factory(**{field: fact}); claim = _claim(primary_icd10='E44.0' if prefix == 'enteral_evidence' else 'N18.5')
    ctx = PatientClaimContext(patient_id='P1', claims=(claim,), procedure_lines=(), material_lines=(), drug_lines=(drug,), diagnoses=())
    batch = evaluate_drug_indication_findings('P1', ctx)
    payload = {'evaluations': [r.to_dict() for r in batch.evaluations], 'findings': [r.to_dict() for r in batch.findings], 'violations': list(batch.legacy_violations)}
    DrugIndicationReviewResponse.model_validate(payload)
    for rows in payload.values():
        for row in rows:
            row['raw_evidence'] = {prefix: {field: fact, 'private_report_text': 'DO_NOT_PUBLISH'}}
            for outcome in row['clinical_restrictions']:
                outcome['raw_evidence'] = row['raw_evidence']
                outcome['checks'][0]['raw_value'] = 'DO_NOT_PUBLISH'
    public = project_public_response({'drug_indication': payload}, 'get_billing_report')
    serialized = json.dumps(public)
    assert 'DO_NOT_PUBLISH' not in serialized and 'raw_evidence' not in serialized and 'raw_value' not in serialized
    for rows in public['drug_indication'].values():
        for row in rows:
            outcome = next(r for r in row['clinical_restrictions'] if r['constraint_set'] == ('enteral_pediatric_reports_2026' if prefix == 'enteral_evidence' else 'renal_source_constraints'))
            assert outcome['criterion_status'] == evaluator(drug)['criterion_status']
            assert row['clinical_eligibility_complete'] is False
    with duckdb.connect(':memory:') as db:
        db.execute('CREATE TABLE reports(payload JSON)')
        db.execute('INSERT INTO reports VALUES (?)', [serialized])
        assert json.loads(db.execute('SELECT payload FROM reports').fetchone()[0]) == public

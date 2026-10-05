"""Bounded original85 facts do not certify source units, standards or payment."""

from tests.unit._helpers.reviewed_clause_ids import reviewed_clause_id
from dataclasses import asdict, replace
from datetime import date, timedelta
import json
from pathlib import Path

import duckdb
import polars as pl
import pytest

from scripts.sut.prose.clause_identity import content_hash, resolve_gate_b_ref_to_clause_ids
from src.bilun.api.public_responses import project_public_response
from src.bilun.domain.billing.drug_indication_findings import evaluate_drug_indication_findings
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.claims.clinical_evidence import AntifungalEvidence, SmaEvidence, parse_clinical_evidence
from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules._drug_indication.clinical_sma import (
    RISDIPLAM_DOCUMENTARY_FIELDS, RISDIPLAM_TYPE1_MONITORING, evaluate_sma_safety,
)
from src.bilun.domain.prose_rules._drug_indication.clinical_antifungal import evaluate_antifungal
from src.bilun.domain.prose_rules._drug_indication.runtime_observations import ClinicalObservationCollector
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
from src.bilun.domain.sut.runtime_coverage_schema import RuntimeCoverageResponse
from src.bilun.shared.models import ClaimValidationRequest
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _drug_line
from tests.unit.api.test_validation_contract_v2 import client, _login  # noqa: F401

ROOT = Path(__file__).resolve().parents[4]
DAY = date(2026, 10, 2)
ANC_REVIEW = 'itraconazole_source_neutrophil_unit_verification'
SMA_REVIEW = 'risdiplam_age_disease_assessment_standards_review'


def facts(family, **changes):
    values = dict(applies_on=DAY, assessment_date=DAY)
    if family == 'sma':
        values.update(sma_type='type_1', risdiplam_treatment_period='during_treatment',
                      hypoxic_ischemic_encephalopathy=False,
                      hypoxic_birth_neurological_sequelae=False,
                      **dict.fromkeys(RISDIPLAM_DOCUMENTARY_FIELDS, True))
        cls = SmaEvidence
    else:
        values.update(intent='prophylaxis', formulation='oral_solution',
                      hematological_malignancy=True, bone_marrow_transplant=False,
                      neutropenia_development_expected=True,
                      indication='deep_fungal_infection_prophylaxis', anc_per_mm3=499)
        cls = AntifungalEvidence
    return cls(**{**values, **changes})


def drug(family, **changes):
    return replace(_drug_line(drug_name='risdiplam' if family == 'sma' else 'itraconazole',
                              report_present=True), drug_claim_date=DAY,
                   **{family + '_evidence': facts(family, **changes)})


def observe(family, line):
    collector = ClinicalObservationCollector(line, family, family + '.documentary.v1')
    evaluator = evaluate_sma_safety if family == 'sma' else evaluate_antifungal
    result = evaluator(line, observer=collector)
    assert evaluator(line) == result
    summary = collector.summary(pl.read_parquet(ROOT / 'data/gazette/sut_clauses.parquet'))
    RuntimeCoverageResponse.model_validate(summary)
    return result, collector, summary


def test_original_pinned_source_and_scoped_risdiplam_reference():
    source = json.loads((ROOT / 'data/gazette/clinical_sources/sma_antifungal_2026_10.json').read_text())
    raw = json.loads((ROOT / 'data/gazette/source_evidence/sma_antifungal_documentary_facts.json').read_text())
    assert raw['docx_sha256'] == '227b508558840f6c8083c6b6cc8c4efcbf1fcf342e115df5519b0f3e63d7f573'
    assert raw['git_blob_sha1'] == '4a61a58f4121e04566836bef04977b24cc3e28a3'
    paragraphs = {p['docx_paragraph_index_zero_based']: p for p in raw['paragraphs']}
    for physical, extracted in [(6425, 6497), (7361, 7433), (7365, 7437)]:
        row = next(r for r in source['clauses'] if r['paragraph_index'] == extracted)
        assert content_hash(paragraphs[physical]['text']) == row['content_hash']
        assert not any(r['struck'] for r in paragraphs[physical]['runs'])
    assert '<500 hücre/ml' in paragraphs[6425]['text']
    frame = pl.read_parquet(ROOT / 'data/gazette/sut_clauses.parquet')
    assert resolve_gate_b_ref_to_clause_ids('4.2.23.b#1b49d136', frame, encode_eligible_only=True) == [reviewed_clause_id('C006181')]
    ids = resolve_gate_b_ref_to_clause_ids(RISDIPLAM_TYPE1_MONITORING, frame, encode_eligible_only=True)
    assert len(ids) == 1
    assert ids == [reviewed_clause_id('C007119')]  # Baseline and October physical indexes differ.
    selected = frame.filter(pl.col('clause_id').is_in(ids)).row(0, named=True)
    assert content_hash(selected['in_force_text']) == '481b9b26'
    assert selected['paragraph_index'] > frame.filter(pl.col('clause_key') == '4.2.49.A#c2df3999')['paragraph_index'][0]
    assert resolve_gate_b_ref_to_clause_ids(RISDIPLAM_TYPE1_MONITORING, frame.reverse(), encode_eligible_only=True) == ids


@pytest.mark.parametrize('family,count,passed,review', [('sma', 9, 9, SMA_REVIEW), ('antifungal', 4, 3, ANC_REVIEW)])
def test_bounded_passes_never_clear_source_review(family, count, passed, review):
    result, collector, summary = observe(family, drug(family))
    assert result['criterion_status'] == 'unknown' and result['missing_inputs'] == [review]
    assert result['clinical_eligibility_complete'] is False
    assert summary['predicate_attempted_count'] == count
    assert summary['predicate_passed_count'] == passed
    assert summary['routes_blocked_source_count'] == 1
    assert summary['source_clauses_fully_evaluated_count'] is None
    assert summary['source_clauses_touched_count'] == (2 if family == 'sma' else 1)
    assert not any('anc_per_mm3' in x for r in collector.receipts for x in r['observed_input_fields'])
    if family == 'sma':
        assert RISDIPLAM_TYPE1_MONITORING in result['source_refs']
        assert all(r['source_refs'] == [RISDIPLAM_TYPE1_MONITORING] for r in collector.receipts
                   if r.get('predicate_id', '').startswith('sma.risdiplam_'))


CASES = [('sma', field, False) for field in RISDIPLAM_DOCUMENTARY_FIELDS] + [
    ('antifungal', 'neutropenia_development_expected', False),
    ('antifungal', 'indication', 'other'),
    ('antifungal', 'indication', 'aspergillus_candida_prophylaxis'),
]


@pytest.mark.parametrize('family,field,negative', CASES)
def test_each_explicit_negative_is_a_restriction_failure(family, field, negative):
    result, _, summary = observe(family, drug(family, **{field: negative}))
    assert result['criterion_status'] == 'restriction_not_met'
    assert {'field': family + '_evidence.' + field, 'status': 'fail'} in result['checks']
    assert (SMA_REVIEW if family == 'sma' else ANC_REVIEW) in result['missing_inputs']
    assert summary['predicate_failed_count'] >= 1


@pytest.mark.parametrize('family,field,negative', CASES)
@pytest.mark.parametrize('value', [None, 'true', 'false', 0, 1, {}, []])
def test_missing_and_malformed_facts_remain_unknown(family, field, negative, value):
    result, _, summary = observe(family, drug(family, **{field: value}))
    assert result['criterion_status'] == 'unknown'
    assert family + '_evidence.' + field in result['missing_inputs']
    assert summary['predicate_missing_inputs_count'] == 1


def test_existing_neutropenia_facts_do_not_substitute_for_expected_development():
    result, collector, _ = observe('antifungal', drug('antifungal',
        neutropenia_development_expected=None, prolonged_neutropenia_expected=True,
        current_neutropenia=True, expected_neutropenia_days=30))
    assert 'antifungal_evidence.neutropenia_development_expected' in result['missing_inputs']
    used = {x for r in collector.receipts for x in r['observed_input_fields']}
    assert not used & {'antifungal_evidence.' + x for x in
                       ('prolonged_neutropenia_expected', 'current_neutropenia', 'expected_neutropenia_days')}


@pytest.mark.parametrize('field,value', [('formulation', 'oral_tablet'), ('intent', 'treatment')])
def test_other_itraconazole_branches_do_not_read_prophylaxis_facts(field, value):
    _, collector, _ = observe('antifungal', drug('antifungal', **{field: value}))
    assert not any(r.get('predicate_id', '').startswith('itraconazole.prophylaxis') for r in collector.receipts)


@pytest.mark.parametrize('sma_type', ['type_2', 'type_3', 'newborn_screening'])
def test_other_risdiplam_subtypes_do_not_inherit_type1_row(sma_type):
    result, collector, summary = observe('sma', drug('sma', sma_type=sma_type,
        **dict.fromkeys(RISDIPLAM_DOCUMENTARY_FIELDS, False)))
    assert result['criterion_status'] == 'criterion_clear'
    assert result['source_refs'] == ['4.2.49.(5)#597ea9c2']
    assert summary['predicate_attempted_count'] == 2
    assert not any(r.get('predicate_id', '').startswith('sma.risdiplam_') for r in collector.receipts)


def test_missing_risdiplam_subtype_does_not_guess_type1():
    result, _, summary = observe('sma', drug('sma', sma_type=None))
    assert result['criterion_status'] == 'unknown' and result['missing_inputs'] == ['sma_evidence.sma_type']
    assert summary['predicate_attempted_count'] == 2 and summary['routes_blocked_inputs_count'] == 1
    assert RISDIPLAM_TYPE1_MONITORING not in result['source_refs']


@pytest.mark.parametrize('medicine', ['nusinersen', 'onasemnogene abeparvovec'])
def test_documentary_facts_do_not_leak_to_other_medicines(medicine):
    line = replace(drug('sma', **dict.fromkeys(RISDIPLAM_DOCUMENTARY_FIELDS, False)), drug_name=medicine)
    result = evaluate_drug_indication_line_detailed(drug_line=line, claim=_claim(primary_icd10='G12.0'), diagnoses=[])
    for item in result.get('clinical_restrictions', []):
        assert RISDIPLAM_TYPE1_MONITORING not in item['source_refs']
        assert not any('risdiplam_' in c['field'] for c in item['checks'])


@pytest.mark.parametrize('family', ['sma', 'antifungal'])
@pytest.mark.parametrize('kind', ['missing_service', 'future_source', 'before_source', 'scope_mismatch', 'future_assessment', 'missing_assessment'])
def test_dates_block_all_documentary_comparisons(family, kind):
    day = DAY
    if kind == 'missing_service':
        day = None
    elif kind == 'future_source':
        day = date(2026, 10, 6)  # First unsupported day after the October 5 review.
    elif kind == 'before_source':
        day = date(2025, 5, 5) if family == 'sma' else DAY - timedelta(days=1)
    updates = {'applies_on': DAY-timedelta(days=1)} if kind == 'scope_mismatch' else (
        {'assessment_date': DAY+timedelta(days=1)} if kind == 'future_assessment' else
        {'assessment_date': None} if kind == 'missing_assessment' else {})
    if kind in ('future_source', 'before_source'):
        # Test source authority itself, independently of claim/evidence mismatch.
        updates.update(applies_on=day, assessment_date=day)
    line = replace(drug(family, **updates), drug_claim_date=day)
    result, _, summary = observe(family, line)
    assert result['criterion_status'] == 'not_evaluated' and result['checks'] == []
    assert summary['predicate_attempted_count'] == 0


@pytest.mark.parametrize('family', ['sma', 'antifungal'])
def test_request_adapter_and_row_json_preserve_documentary_facts(family):
    line = drug(family)
    payload = {'materials': [{'name': line.drug_name, family+'_evidence': asdict(getattr(line, family+'_evidence'))}],
               'drug_context': {'service_date': DAY, 'primary_icd10': 'G12.0' if family == 'sma' else 'C92.0', 'board_report_present': True}}
    request = ClaimValidationRequest.model_validate(payload)
    context = build_context_from_material_dict(request.model_dump())
    assert getattr(context.drug_lines[0], family+'_evidence') == getattr(line, family+'_evidence')
    raw = asdict(line); raw[family+'_evidence'] = json.dumps(request.model_dump(mode='json')['materials'][0][family+'_evidence'])
    errors = []; parsed = parse_drug_line(raw, errors)
    assert not errors and getattr(parsed, family+'_evidence') == getattr(line, family+'_evidence')
    assert parse_clinical_evidence(raw[family+'_evidence'], SmaEvidence if family == 'sma' else AntifungalEvidence) == getattr(line, family+'_evidence')


@pytest.mark.parametrize('family', ['sma', 'antifungal'])
@pytest.mark.parametrize('case', ['positive', 'negative', 'missing'])
def test_candidate_order_public_cache_and_private_data(family, case):
    field = RISDIPLAM_DOCUMENTARY_FIELDS[0] if family == 'sma' else 'neutropenia_development_expected'
    line = drug(family, **({} if case == 'positive' else {field: False if case == 'negative' else None})); claim = _claim(primary_icd10='G12.0' if family == 'sma' else 'C92.0')
    rules = json.loads((ROOT / 'data/gazette/prose_rules/drug_indication_prose.json').read_text())['rules']
    forward = evaluate_drug_indication_line_detailed(drug_line=line, claim=claim, diagnoses=[], rules=rules)
    reverse = evaluate_drug_indication_line_detailed(drug_line=line, claim=claim, diagnoses=[], rules=list(reversed(rules)))
    assert forward == reverse
    context = PatientClaimContext(patient_id='P1', claims=(claim,), procedure_lines=(), material_lines=(), drug_lines=(line,), diagnoses=())
    batch = evaluate_drug_indication_findings('P1', context)
    payload = {'evaluations': [r.to_dict() for r in batch.evaluations], 'findings': [r.to_dict() for r in batch.findings], 'violations': list(batch.legacy_violations)}
    public = project_public_response({'drug_indication': payload}, 'get_billing_report')
    for category in ('evaluations', 'findings', 'violations'):
        rows = public['drug_indication'][category]
        assert len(rows) == 1
        restriction = next(r for r in rows[0]['clinical_restrictions'] if r['constraint_set'] == ('sma_safety_2025' if family == 'sma' else 'antifungal_source_constraints'))
        assert restriction['criterion_status'] == ('restriction_not_met' if case == 'negative' else 'unknown')
        assert restriction['runtime_coverage']['predicate_attempted_count'] == (9 if family == 'sma' else 4)
    text = json.dumps(public)
    for private in ('execution_scope', 'receipts', 'assessment_date', 'anc_per_mm3', 'observed_input_fields'):
        assert private not in text
    with duckdb.connect(':memory:') as db:
        db.execute('CREATE TABLE reports(payload JSON)'); db.execute('INSERT INTO reports VALUES (?)', [text])
        assert json.loads(db.execute('SELECT payload FROM reports').fetchone()[0]) == public


@pytest.mark.parametrize('family', ['sma', 'antifungal'])
@pytest.mark.parametrize('case', ['passing', 'negative', 'missing'])
@pytest.mark.parametrize('claim_id', ['', 'documentary-http'])
@pytest.mark.parametrize('via_helper', [False, True])
def test_real_http_result_missing_projection_and_observer(client, family, case, claim_id, via_helper):  # noqa: F811
    _login(client)
    field = RISDIPLAM_DOCUMENTARY_FIELDS[0] if family == 'sma' else 'neutropenia_development_expected'
    evidence = facts(family, **({} if case == 'passing' else {field: False if case == 'negative' else None}))
    request = ClaimValidationRequest.model_validate({'claim_id': claim_id, 'materials': [{
        'name': 'risdiplam' if family == 'sma' else 'itraconazole', family+'_evidence': asdict(evidence)}],
        'drug_context': {'service_date': DAY, 'primary_icd10': 'G12.0' if family == 'sma' else 'C92.0', 'board_report_present': True}})
    if via_helper:
        import shutil
        import subprocess
        node = shutil.which('node')
        if not node or 'experimental-strip-types' not in subprocess.run([node, '--help'], capture_output=True, text=True).stdout:
            pytest.skip('Actual TypeScript helper transport requires Node with type stripping')
        script = "import {drugMaterialPayload} from './frontend/src/components/tabs/sut/sections/drugInputs.ts';let raw='';for await (const chunk of process.stdin)raw+=chunk;const payload=JSON.parse(raw);payload.materials=payload.materials.map(m=>drugMaterialPayload(m,true));process.stdout.write(JSON.stringify(payload));"
        output = subprocess.run([node, '--experimental-strip-types', '--input-type=module', '-e', script],
            input=request.model_dump_json(), cwd=ROOT, capture_output=True, text=True, check=True)
        request = ClaimValidationRequest.model_validate_json(output.stdout)
        assert getattr(request.materials[0], family+'_evidence') == evidence
    bodies = []
    for _ in range(2):
        response = client.post('/api/validate-claim', json=request.model_dump(mode='json'), headers={'X-Bilun-Validation-Contract': '2'})
        assert response.status_code == 200, response.text
        body = response.json(); bodies.append({k: v for k, v in body.items() if k != 'validation_time_ms'})
        row = next(r for r in body['advisories'] if r['rule'] == 'drug_indication')
        restriction = row['clinical_restrictions'][0]
        assert restriction['criterion_status'] == ('restriction_not_met' if case == 'negative' else 'unknown')
        assert (SMA_REVIEW if family == 'sma' else ANC_REVIEW) in restriction['missing_inputs']
        if case == 'missing':
            assert family+'_evidence.'+field in row['missing_inputs']
        summary = restriction['runtime_coverage']
        assert summary['predicate_attempted_count'] == (9 if family == 'sma' else 4)
        assert summary['source_clauses_fully_evaluated_count'] is None
        assert row['disposition'] == 'review_only' and body['is_valid'] is None
        assert 'execution_scope' not in response.text and 'receipts' not in response.text
    assert bodies[0] == bodies[1]


def test_new_authored_bindings_match_actual_executed_predicates():
    inventory = json.loads((ROOT / 'reports/sut-expansion/sma-antifungal-runtime-bindings.json').read_text())
    mapping = {row['predicate_id']: row for row in inventory['predicate_bindings']}
    expected = {'sma.' + field for field in RISDIPLAM_DOCUMENTARY_FIELDS} | {
        'itraconazole.prophylaxis.neutropenia_development_expected',
        'itraconazole.prophylaxis.deep_fungal_indication',
    }
    reached = {}
    for family in ('sma', 'antifungal'):
        _, collector, _ = observe(family, drug(family))
        reached.update({r['predicate_id']: r for r in collector.receipts if r.get('predicate_id') in expected})
    assert set(reached) == expected
    for key, receipt in reached.items():
        assert mapping[key]['source_refs'] == receipt['source_refs']
        assert mapping[key]['input_field'] in receipt['observed_input_fields']
        assert mapping[key]['clause_predicate_complete'] is False


@pytest.mark.parametrize('anc', [0, 499, 500, 999999])
def test_supplied_anc_never_clears_or_fails_disputed_threshold(anc):
    result, _, summary = observe('antifungal', drug('antifungal', anc_per_mm3=anc))
    assert result['criterion_status'] == 'unknown' and result['missing_inputs'] == [ANC_REVIEW]
    assert summary['predicate_attempted_count'] == 4


def test_sma_effective_date_is_inclusive_for_documented_type1_facts():
    start = date(2025, 5, 6)
    line = replace(drug('sma', applies_on=start, assessment_date=start), drug_claim_date=start)
    result, _, summary = observe('sma', line)
    assert result['criterion_status'] == 'unknown' and result['missing_inputs'] == [SMA_REVIEW]
    assert summary['predicate_attempted_count'] == 9


@pytest.mark.parametrize('period', [None, 'initiation', 'continuation', 'unknown', '', True, 1, {}, []])
def test_unknown_or_malformed_period_cannot_fail_unreached_monitoring(period):
    result, collector, summary = observe('sma', drug('sma', risdiplam_treatment_period=period,
        **dict.fromkeys(RISDIPLAM_DOCUMENTARY_FIELDS, False)))
    assert result['criterion_status'] == 'unknown'
    assert result['missing_inputs'] == ['sma_evidence.risdiplam_treatment_period']
    assert summary['predicate_attempted_count'] == 2
    assert summary['predicate_failed_count'] == 0
    assert summary['routes_blocked_inputs_count'] == 1
    assert RISDIPLAM_TYPE1_MONITORING not in result['source_refs']
    assert not any(r.get('predicate_id', '').startswith('sma.risdiplam_') for r in collector.receipts)
    assert not any(c['field'].split('.')[-1] in RISDIPLAM_DOCUMENTARY_FIELDS for c in result['checks'])


@pytest.mark.parametrize('documented', [True, False, None])
def test_not_started_skips_documentary_obligations_and_source_standards(documented):
    result, collector, summary = observe('sma', drug('sma', risdiplam_treatment_period='not_started',
        **dict.fromkeys(RISDIPLAM_DOCUMENTARY_FIELDS, documented)))
    assert result['criterion_status'] == 'criterion_clear' and result['missing_inputs'] == []
    assert summary['predicate_attempted_count'] == 2
    assert summary['predicate_failed_count'] == 0
    assert summary['routes_skipped_count'] == 2
    assert summary['routes_blocked_source_count'] == 0
    assert RISDIPLAM_TYPE1_MONITORING not in result['source_refs']
    assert not any(r.get('predicate_id', '').startswith('sma.risdiplam_') for r in collector.receipts)


@pytest.mark.parametrize('period', ['not_started', None, 'initiation', 'during_treatment'])
def test_period_gate_preserves_independent_hypoxic_safety_failure(period):
    result, _, _ = observe('sma', drug('sma', risdiplam_treatment_period=period,
                                     hypoxic_ischemic_encephalopathy=True))
    assert result['criterion_status'] == 'restriction_not_met'
    assert {'field': 'sma_evidence.hypoxic_ischemic_encephalopathy', 'status': 'fail'} in result['checks']


@pytest.mark.parametrize('period,status', [('not_started', 'criterion_clear'),
                                         (None, 'unknown'), ('initiation', 'unknown')])
def test_period_gate_preserves_public_cache_and_http_review(client, period, status):  # noqa: F811
    _login(client)
    line = drug('sma', risdiplam_treatment_period=period,
                **dict.fromkeys(RISDIPLAM_DOCUMENTARY_FIELDS, False))
    claim = _claim(primary_icd10='G12.0')
    rules = json.loads((ROOT / 'data/gazette/prose_rules/drug_indication_prose.json').read_text())['rules']
    forward = evaluate_drug_indication_line_detailed(drug_line=line, claim=claim, diagnoses=[], rules=rules)
    reverse = evaluate_drug_indication_line_detailed(drug_line=line, claim=claim, diagnoses=[], rules=list(reversed(rules)))
    assert forward == reverse
    assert forward['violation']['severity'] == 'review'
    assert forward['clinical_restrictions'][0]['criterion_status'] == status
    context = PatientClaimContext(patient_id='P1', claims=(claim,), procedure_lines=(), material_lines=(), drug_lines=(line,), diagnoses=())
    batch = evaluate_drug_indication_findings('P1', context)
    payload = {'evaluations': [r.to_dict() for r in batch.evaluations],
               'findings': [r.to_dict() for r in batch.findings], 'violations': list(batch.legacy_violations)}
    public = project_public_response({'drug_indication': payload}, 'get_billing_report')
    for category in ('evaluations', 'findings', 'violations'):
        item = public['drug_indication'][category][0]['clinical_restrictions'][0]
        assert item['criterion_status'] == status
        assert item['runtime_coverage']['predicate_attempted_count'] == 2
        assert not any('risdiplam_' in c['field'] for c in item['checks'])
    with duckdb.connect(':memory:') as db:
        db.execute('CREATE TABLE reports(payload JSON)')
        db.execute('INSERT INTO reports VALUES (?)', [json.dumps(public)])
        assert json.loads(db.execute('SELECT payload FROM reports').fetchone()[0]) == public
    req = ClaimValidationRequest.model_validate({'materials': [{'name': 'risdiplam', 'sma_evidence': asdict(line.sma_evidence)}],
        'drug_context': {'service_date': DAY, 'primary_icd10': 'G12.0', 'board_report_present': True}})
    response = client.post('/api/validate-claim', json=req.model_dump(mode='json'), headers={'X-Bilun-Validation-Contract': '2'})
    assert response.status_code == 200
    body = response.json(); row = next(r for r in body['advisories'] if r['rule'] == 'drug_indication')
    assert row['disposition'] == 'review_only' and body['is_valid'] is None
    item = row['clinical_restrictions'][0]
    assert item['criterion_status'] == status and item['runtime_coverage']['predicate_attempted_count'] == 2
    if period != 'not_started':
        assert 'sma_evidence.risdiplam_treatment_period' in row['missing_inputs']
    assert 'execution_scope' not in response.text and 'receipts' not in response.text


@pytest.mark.parametrize('family', ['sma', 'antifungal'])
def test_live_expanded_observer_versions_have_distinct_summary_identity(monkeypatch, family):
    from src.bilun.domain.prose_rules._drug_indication import runtime_observations
    captured = []
    original = runtime_observations.ClinicalObservationCollector.summary

    def capture(self, *args, **kwargs):
        captured.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(runtime_observations.ClinicalObservationCollector, 'summary', capture)
    result = evaluate_drug_indication_line_detailed(drug_line=drug(family),
        claim=_claim(primary_icd10='G12.0' if family == 'sma' else 'C92.0'), diagnoses=[])
    collector = next(c for c in captured if c.family == family)
    assert collector.version == f'{family}.atomic.v2.2026-10-03'
    assert {r['evaluator_version'] for r in collector.receipts} == {collector.version}
    report = result['clinical_restrictions'][0]['runtime_coverage']
    assert 'evaluator_version' not in report and 'receipts' not in report
    # Same executed facts and source references, different evaluator contract.
    collector.receipts = [{**r, 'evaluator_version': f'{family}.atomic.v1.2026-10-02'} for r in collector.receipts]
    old = original(collector, pl.read_parquet(ROOT / 'data/gazette/sut_clauses.parquet'))
    assert old['predicate_attempted_count'] == report['predicate_attempted_count']
    assert old['receipt_sha256'] != report['receipt_sha256']

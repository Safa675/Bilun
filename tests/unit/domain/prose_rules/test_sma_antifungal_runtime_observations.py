"""Measured SMA/antifungal paths preserve clinical results and source boundaries."""
from dataclasses import asdict, replace
from datetime import date, timedelta
import json

import duckdb
import pytest

from src.bilun.domain.claims.clinical_evidence import AntifungalEvidence
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules._drug_indication.clinical_sma import evaluate_sma_safety
from src.bilun.domain.prose_rules._drug_indication.clinical_antifungal import evaluate_antifungal
from src.bilun.domain.prose_rules._drug_indication.runtime_observations import ClinicalObservationCollector
from src.bilun.domain.sut.runtime_coverage_schema import RuntimeCoverageResponse
from src.bilun.domain.billing.drug_indication_findings import evaluate_drug_indication_findings
from src.bilun.api.public_responses import project_public_response
from src.bilun.shared.models import ClaimValidationRequest
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _drug_line
from tests.unit.domain.prose_rules.test_sma_clinical_safety import line as sma_line, evidence as sma_facts
from tests.unit.domain.prose_rules.test_antifungal_clinical_constraints import micro, posa
from tests.unit.domain.prose_rules.test_renal_runtime_observations import source

DAY=date(2026,10,2)


def af_line(drug='anidulafungin',**values):
 return replace(_drug_line(drug_name=drug,report_present=True),drug_claim_date=DAY,
  antifungal_evidence=AntifungalEvidence(applies_on=DAY,assessment_date=DAY,**values))


def observe(line,family):
 collector=ClinicalObservationCollector(line,family,f'{family}.atomic.v1.2026-10-02')
 evaluator=evaluate_sma_safety if family=='sma' else evaluate_antifungal
 outcome=evaluator(line,observer=collector)
 assert outcome==evaluator(line)
 report=collector.summary(source());RuntimeCoverageResponse.model_validate(report)
 assert report['available'] is True and report['source_clauses_fully_evaluated_count'] is None
 return outcome,collector,report


@pytest.mark.parametrize('drug,sma_type,predicates,clauses,skipped',[
 ('nusinersen','type_2',7,5,0),('nusinersen','type_3',7,5,0),
 ('nusinersen','type_1',6,4,1),('nusinersen','newborn_screening',6,4,1),
 ('risdiplam','type_2',2,1,2),
])
def test_sma_actual_medicine_and_type_paths(drug,sma_type,predicates,clauses,skipped):
 outcome,_,report=observe(sma_line(drug,replace(sma_facts(),sma_type=sma_type)),'sma')
 assert outcome['criterion_status']=='criterion_clear'
 assert report['predicate_attempted_count']==report['predicate_passed_count']==predicates
 assert report['source_clauses_touched_count']==clauses
 assert report['routes_skipped_count']==skipped


def test_unknown_sma_type_blocks_only_unreached_lumbar_branch():
 _,collector,report=observe(sma_line(facts=replace(sma_facts(),sma_type=None)),'sma')
 assert report['predicate_attempted_count']==6 and report['routes_blocked_inputs_count']==1
 assert report['input_facts_missing_count']==1
 assert not any(r.get('predicate_id','').endswith('lumbar_puncture_suitability') for r in collector.receipts)


@pytest.mark.parametrize('day',[None,date(2025,5,5),date(2026,10,3)])
def test_sma_scope_gates_observe_zero_history_comparisons(day):
 outcome,_,report=observe(sma_line(day=day),'sma')
 assert outcome['criterion_status']=='not_evaluated'
 assert report['predicate_attempted_count']==0
 assert report['routes_blocked_source_count']+report['routes_blocked_inputs_count']==1


def test_anidulafungin_observes_five_comparisons_and_one_source():
 _,_,report=observe(af_line(intent='treatment',indication='invasive_candidiasis',adult=True,anc_per_mm3=500,anc_lab_result_present=True),'antifungal')
 assert report['predicate_attempted_count']==report['predicate_passed_count']==5
 assert report['source_clauses_touched_count']==1
 assert report['input_facts_available_count']==9


def test_micafungin_eager_alternatives_and_skipped_duration_are_truthful():
 outcome,collector,report=observe(af_line('micafungin',**micro()),'antifungal')
 assert outcome['criterion_status']=='criterion_clear'
 assert report['predicate_attempted_count']==8
 assert report['predicate_passed_count']==3 and report['predicate_failed_count']==5
 assert report['routes_skipped_count']==1 and report['source_clauses_touched_count']==1
 assert report['input_facts_available_count']==12
 assert not any('antifungal_evidence.expected_neutropenia_days' in r['observed_input_fields'] for r in collector.receipts)


@pytest.mark.parametrize('days',[7,8])
def test_post_neutropenic_comparison_and_final_no_pay_branch(days):
 outcome,_,report=observe(af_line('micafungin',**micro(neutropenia_end_date=DAY-timedelta(days=days))),'antifungal')
 assert outcome['criterion_status']==('criterion_clear' if days==7 else 'restriction_not_met')
 assert report['predicate_attempted_count']==(8 if days==7 else 10)
 assert report['source_clauses_touched_count']==(1 if days==7 else 2)


def test_one_unknown_neutropenia_fact_used_twice_counts_once():
 _,_,report=observe(af_line('micafungin',**micro(current_neutropenia=None)),'antifungal')
 assert report['predicate_missing_inputs_count']==2
 assert report['input_facts_missing_count']==1


def test_invalid_end_date_is_a_route_block_not_a_fabricated_elapsed_comparison():
 _,collector,report=observe(af_line('micafungin',**micro(neutropenia_end_date=DAY+timedelta(days=1))),'antifungal')
 assert report['routes_blocked_inputs_count']==1
 assert not any(r.get('predicate_id','').endswith('within_seven_days') for r in collector.receipts)


def test_itraconazole_unit_authority_never_becomes_an_anc_predicate():
 _,collector,report=observe(af_line('itraconazole',intent='prophylaxis',formulation='oral_solution',hematological_malignancy=True,bone_marrow_transplant=False,anc_per_mm3=499),'antifungal')
 assert report['predicate_attempted_count']==4 and report['routes_blocked_source_count']==1
 assert not any('anc_per_mm3' in field for r in collector.receipts for field in r['observed_input_fields'])
 assert report['source_clauses_touched_count']==1


@pytest.mark.parametrize('formulation,predicates,skipped',[('oral_tablet',6,1),('parenteral',7,0),(None,6,0)])
def test_posaconazole_formulation_controls_only_the_reached_check(formulation,predicates,skipped):
 _,_,report=observe(af_line('posaconazole',**{**posa(), 'formulation':formulation,'oral_form_unusable':True}),'antifungal')
 assert report['predicate_attempted_count']==predicates and report['routes_skipped_count']==skipped
 assert report['routes_blocked_inputs_count']==(1 if formulation is None else 0)


@pytest.mark.parametrize('indication,count',[('oropharyngeal_candidiasis',3),('invasive_aspergillosis',3),('fusariosis',2),('chromoblastomycosis',2),('mycetoma',2),('coccidioidomycosis',6)])
def test_posaconazole_treatment_counts_only_its_reached_indication(indication,count):
 _,_,report=observe(af_line('posaconazole',intent='treatment',indication=indication),'antifungal')
 assert report['predicate_attempted_count']==count
 assert report['source_clauses_touched_count']==1


@pytest.mark.parametrize('line',[
 af_line('unknown',intent='treatment'),af_line('micafungin anidulafungin',intent='treatment'),
 af_line('posaconazole',intent='treatment',indication='other'),
 af_line('itraconazole',intent='treatment',formulation='oral_tablet'),
])
def test_unsupported_scope_records_no_unreached_comparison(line):
 _,_,report=observe(line,'antifungal')
 assert report['predicate_attempted_count']==0 and report['routes_blocked_source_count']==1


def test_absent_itraconazole_intent_does_not_count_unused_formulation():
 _,collector,report=observe(af_line('itraconazole',formulation='oral_solution'),'antifungal')
 assert report['predicate_attempted_count']==0 and report['routes_blocked_inputs_count']==1
 assert not any('antifungal_evidence.formulation' in r['observed_input_fields'] for r in collector.receipts)


@pytest.mark.parametrize('family,drug,diagnosis',[
 ('sma',sma_line(),'G12.0'),
 ('antifungal',af_line(intent='treatment',indication='invasive_candidiasis',adult=True,anc_per_mm3=500,anc_lab_result_present=True),'B37.7'),
])
def test_actual_public_and_cache_path_contains_only_its_family_summary(family,drug,diagnosis):
 claim=_claim(primary_icd10=diagnosis)
 context=PatientClaimContext(patient_id='P1',claims=(claim,),procedure_lines=(),material_lines=(),drug_lines=(drug,),diagnoses=())
 batch=evaluate_drug_indication_findings('P1',context)
 payload={'evaluations':[r.to_dict() for r in batch.evaluations],'findings':[r.to_dict() for r in batch.findings],'violations':list(batch.legacy_violations)}
 public=project_public_response({'drug_indication':payload},'get_billing_report')
 for category in ('evaluations','findings','violations'):
  report=public['drug_indication'][category][0]['clinical_restrictions'][0]['runtime_coverage']
  assert report['available'] is True and report['instrumented_families']==[family]
  assert report['source_clauses_fully_evaluated_count'] is None
  assert 'execution_scope' not in report and 'receipts' not in report
 with duckdb.connect(':memory:') as db:
  db.execute('CREATE TABLE reports(payload JSON)');db.execute('INSERT INTO reports VALUES (?)',[json.dumps(public)])
  assert json.loads(db.execute('SELECT payload FROM reports').fetchone()[0])==public
 raw={'materials':[{'name':drug.drug_name,f'{family if family=="sma" else "antifungal"}_evidence':asdict(drug.sma_evidence if family=='sma' else drug.antifungal_evidence)}],
      'drug_context':{'service_date':DAY,'primary_icd10':diagnosis,'board_report_present':True}}
 from src.bilun.api.routes.validation import validate_claim_endpoint
 request=ClaimValidationRequest.model_validate(raw)
 result=validate_claim_endpoint(request,contract_version='2')
 row=next(r for r in result['advisories'] if r['rule']=='drug_indication')
 assert row['clinical_restrictions'][0]['runtime_coverage']['instrumented_families']==[family]
 assert row['disposition']=='review_only' and result['is_valid'] is None


from tests.unit.api.test_validation_contract_v2 import client, _login  # noqa: E402,F401


@pytest.mark.parametrize('family,drug,diagnosis,count',[
 ('sma',sma_line(),'G12.0',7),
 ('sma',sma_line('risdiplam'),'G12.0',2),
 ('antifungal',af_line(intent='treatment',indication='invasive_candidiasis',adult=True,anc_per_mm3=500,anc_lab_result_present=True),'B37.7',5),
 ('antifungal',af_line('micafungin',**micro()),'C91.0',8),
 ('antifungal',af_line('posaconazole',**{**posa(),'formulation':'parenteral','oral_form_unusable':True}),'C92.0',7),
 ('antifungal',af_line('itraconazole',intent='prophylaxis',formulation='oral_solution',hematological_malignancy=True,bone_marrow_transplant=False,anc_per_mm3=499),'C92.0',4),
])
@pytest.mark.parametrize('claim_id',['','observed-family-http'])
def test_real_http_named_anonymous_and_repeated_family_summaries(client,family,drug,diagnosis,count,claim_id):  # noqa: F811
 _login(client)
 evidence=drug.sma_evidence if family=='sma' else drug.antifungal_evidence
 req=ClaimValidationRequest.model_validate({'claim_id':claim_id,'materials':[{'name':drug.drug_name,f'{family}_evidence':asdict(evidence)}],
  'drug_context':{'service_date':DAY,'primary_icd10':diagnosis,'board_report_present':True}})
 reports=[]
 for _ in range(2):
  response=client.post('/api/validate-claim',json=req.model_dump(mode='json'),headers={'X-Bilun-Validation-Contract':'2'})
  assert response.status_code==200,response.text
  result=response.json();row=next(r for r in result['advisories'] if r['rule']=='drug_indication')
  report=row['clinical_restrictions'][0]['runtime_coverage'];reports.append(report)
  assert report['available'] is True and report['instrumented_families']==[family]
  assert report['predicate_attempted_count']==count
  assert report['source_clauses_fully_evaluated_count'] is None
  assert row['disposition']=='review_only' and result['is_valid'] is None
  assert 'execution_scope' not in report and 'receipts' not in report
 assert reports[0]==reports[1]

from dataclasses import asdict, replace
import json
import duckdb
import pytest
from tests.unit.api.test_validation_contract_v2 import client, _login  # noqa: F401
from tests.unit.domain.prose_rules.test_renal_runtime_observations import line, DAY
from tests.unit.domain.prose_rules.test_drug_indication import _claim
from src.bilun.domain.claims.clinical_evidence import EnteralEvidence
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
from src.bilun.domain.billing.drug_indication_findings import evaluate_drug_indication_findings
from src.bilun.api.public_responses import project_public_response
from src.bilun.api.schemas import DrugIndicationReviewResponse
from src.bilun.shared.models import ClaimValidationRequest

ADULT='4.2.8.A.adult_malnutrition_1200kcal_3mo_report'
NAME='enteral beslenme ürünü sevelamer'

def compound(dialysis):
 return replace(line(dialysis=dialysis),drug_name=NAME,drug_report_duration_months=3,
                enteral_evidence=EnteralEvidence(pediatric=False))

def check(row,dialysis):
 assert row['selected_rule_id']==(ADULT if dialysis else 'renal_source_constraints')
 assert row['clinical_eligibility_complete'] is False
 outcomes={r['constraint_set']:r for r in row['clinical_restrictions']}
 guard=outcomes['source_context_clinical_review']
 assert guard['criterion_status']=='unknown' and guard['checks']==[]
 assert guard.get('runtime_coverage') is None
 renal=outcomes['renal_source_constraints']
 assert renal['criterion_status']==('criterion_clear' if dialysis else 'restriction_not_met')
 coverage=renal['runtime_coverage']
 assert coverage['available'] is True and coverage['instrumented_families']==['renal']
 assert coverage['predicate_attempted_count']==coverage['predicate_evaluated_count']==10
 assert coverage['predicate_failed_count']==(6 if dialysis else 7)
 assert coverage['source_clauses_touched_count']==6
 assert coverage['source_clauses_fully_evaluated_count'] is None
 assert 'execution_scope' not in coverage and 'receipts' not in coverage

@pytest.mark.parametrize('dialysis',[True,False])
def test_composed_clear_failure_public_canonical_and_duckdb(dialysis):
 drug=compound(dialysis);claim=_claim(primary_icd10='E43')
 detail=evaluate_drug_indication_line_detailed(drug_line=drug,claim=claim,diagnoses=[])
 check(detail,dialysis)
 assert detail['violation']['severity']==('review' if dialysis else 'error')
 assert detail['violation']['sut_section']==('4.2.8.A' if dialysis else '4.2.9')
 context=PatientClaimContext(patient_id='P1',claims=(claim,),procedure_lines=(),material_lines=(),drug_lines=(drug,),diagnoses=())
 batch=evaluate_drug_indication_findings('P1',context)
 payload={'evaluations':[e.to_dict() for e in batch.evaluations],
          'findings':[f.to_dict() for f in batch.findings],'violations':list(batch.legacy_violations)}
 DrugIndicationReviewResponse.model_validate(payload)
 public=project_public_response({'drug_indication':payload},'get_billing_report')
 for kind in ('evaluations','findings','violations'):
  check(public['drug_indication'][kind][0],dialysis)
  if kind=='violations':
   assert public['drug_indication'][kind][0]['sut_section']==('4.2.8.A' if dialysis else '4.2.9')
 with duckdb.connect(':memory:') as db:
  db.execute('CREATE TABLE reports(payload JSON)')
  db.execute('INSERT INTO reports VALUES (?)',[json.dumps(public)])
  cached=json.loads(db.execute('SELECT payload FROM reports').fetchone()[0])
 assert cached==public
 for kind in ('evaluations','findings','violations'):
  check(cached['drug_indication'][kind][0],dialysis)

@pytest.mark.parametrize('dialysis',[True,False])
@pytest.mark.parametrize('claim_id',['','source-runtime-named'])
def test_real_http_composed_source_and_observation(client,dialysis,claim_id):  # noqa: F811
 _login(client)
 req=ClaimValidationRequest.model_validate({'claim_id':claim_id,'materials':[{'name':NAME,
    'renal_evidence':asdict(compound(dialysis).renal_evidence),'enteral_evidence':{'pediatric':False}}],
    'drug_context':{'service_date':DAY,'primary_icd10':'E43','board_report_present':True,'report_duration_months':3}})
 def post():
  response=client.post('/api/validate-claim',json=req.model_dump(mode='json'),headers={'X-Bilun-Validation-Contract':'2'})
  assert response.status_code==200,response.text
  return response.json()
 first,second=post(),post()
 for data in (first,second):
  row=next(r for r in data['advisories'] if r['rule']=='drug_indication')
  check(row,dialysis)
  assert row['disposition']=='review_only' and data['is_valid'] is None
 firstrow=next(r for r in first['advisories'] if r['rule']=='drug_indication')
 secondrow=next(r for r in second['advisories'] if r['rule']=='drug_indication')
 assert firstrow['clinical_restrictions']==secondrow['clinical_restrictions']

"""Real request-path receipts, without deriving execution from static/check totals."""
from dataclasses import replace
from datetime import date
import json

import duckdb
import polars as pl
import pytest

from src.bilun.domain.claims.clinical_evidence import RenalEvidence
from src.bilun.domain.prose_rules._drug_indication.clinical_renal import evaluate_renal
from src.bilun.domain.prose_rules._drug_indication.runtime_observations import ClinicalObservationCollector
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.billing.drug_indication_findings import evaluate_drug_indication_findings
from src.bilun.api.public_responses import project_public_response
from src.bilun.api.schemas import DrugIndicationReviewResponse
from src.bilun.domain.sut.runtime_coverage_contract import bounded_runtime_coverage
from tests.unit.domain.prose_rules.test_drug_indication import _claim,_drug_line

DAY=date(2026,10,2)
VERSION='renal.atomic.v2.2026-10-02'


def line(**changes):
    facts=RenalEvidence(applies_on=DAY,assessment_date=DAY,indication='phosphate_binding',
        phase='initiation',dialysis=True,other_phosphate_therapy_months=3,
        prior_phosphate_therapy_documented_in_report=True,
        calcium_phosphorus_product=72,corrected_calcium_phosphorus_product=55,
        pth_pg_ml=150,adynamic_bone_disease=False,kt_v=1.4)
    return replace(_drug_line(drug_name='sevelamer',report_present=True),drug_claim_date=DAY,
                   renal_evidence=replace(facts,**changes))


def observe(drug):
    collector=ClinicalObservationCollector(drug,'renal',VERSION)
    outcome=evaluate_renal(drug,observer=collector)
    return outcome,collector


def source():
    from pathlib import Path
    return pl.read_parquet(Path(__file__).resolve().parents[4]/'data/gazette/sut_clauses.parquet')


def test_actual_eager_or_path_records_every_reached_comparison_not_just_winning_branch():
    outcome,collector=observe(line())
    assert outcome==evaluate_renal(line())  # Instrumentation cannot alter the clinical result.
    report=collector.summary(source())
    assert outcome['criterion_status']=='criterion_clear'
    assert report['predicate_attempted_count']==report['predicate_evaluated_count']==10
    assert report['predicate_passed_count']==4 and report['predicate_failed_count']==6
    assert report['input_facts_available_count']==14  # 8 clinical plus 6 date/route/name context facts.
    assert report['source_clauses_touched_count']==6
    assert report['source_clauses_fully_evaluated_count'] is None
    assert len({r['predicate_id'] for r in collector.receipts})==10
    assert report['clinical_eligibility_complete'] is False


def test_one_fact_used_by_two_real_predicates_does_not_inflate_available_fact_count():
    _,collector=observe(line(pth_pg_ml=None))
    report=collector.summary(source())
    assert report['predicate_attempted_count']==10 and report['predicate_evaluated_count']==8
    assert report['predicate_missing_inputs_count']==2
    assert report['input_facts_missing_count']==1
    assert report['input_facts_available_count']==13


@pytest.mark.parametrize('day,status',[ (None,'blocked_inputs'),(date(2026,10,1),'blocked_source'),
                                     (date(2026,10,6),'blocked_source')])
def test_date_block_never_fabricates_downstream_comparison_attempts(day,status):
    # Align the supplied evidence so the source/date gate is the only blocker.
    outcome,collector=observe(replace(line(applies_on=day,assessment_date=day),drug_claim_date=day))
    report=collector.summary(source())
    assert report['predicate_attempted_count']==report['predicate_evaluated_count']==0
    assert collector.receipts[0]['kind']=='route' and collector.receipts[0]['status']==status
    assert outcome['checks']==[]
    assert outcome['source_authority']['status']=='review_required'
    assert outcome['missing_inputs']==(['drug_claim_date'] if day is None
                                      else ['verified_source_for_service_date'])


@pytest.mark.parametrize('service', [date(2026,10,3), date(2026,10,4), date(2026,10,5)])
@pytest.mark.parametrize('matching_evidence', [False, True])
def test_reviewed_admission_still_requires_applicable_evidence(service, matching_evidence):
    evidence_day = service if matching_evidence else DAY
    outcome,collector=observe(replace(line(applies_on=evidence_day,assessment_date=evidence_day),
                                      drug_claim_date=service))
    report=collector.summary(source())
    assert outcome['source_authority']['status']=='admitted'
    assert outcome['clinical_eligibility_complete'] is False
    assert report['source_clauses_fully_evaluated_count'] is None
    if evidence_day==DAY:
        assert outcome['criterion_status']=='not_evaluated'
        assert outcome['missing_inputs']==['renal_evidence.applies_on']
        assert outcome['checks']==[]
        assert report['predicate_attempted_count']==report['predicate_evaluated_count']==0
        assert len(collector.receipts)==1
        assert collector.receipts[0]['kind']=='route'
        assert collector.receipts[0]['status']=='blocked_inputs'
        assert collector.receipts[0]['missing_input_fields']==['renal_evidence.applies_on']
    else:
        assert outcome['criterion_status']=='criterion_clear'
        assert outcome['missing_inputs']==[]
        assert len(outcome['checks'])==10
        assert report['predicate_attempted_count']==report['predicate_evaluated_count']==10


def test_unknown_phase_blocks_before_comparison_and_missing_fact_is_explicit():
    _,collector=observe(line(phase=None))
    report=collector.summary(source())
    assert report['predicate_attempted_count']==0
    assert report['routes_blocked_inputs_count']==1
    assert 'renal_evidence.phase' in collector.receipts[0]['missing_input_fields']


def test_unsupported_cinacalcet_restart_is_source_block_not_missing_patient_fact():
    drug=replace(line(indication='dialysis_shpt',phase='restart'),drug_name='cinacalcet')
    _,collector=observe(drug)
    report=collector.summary(source())
    assert report['routes_blocked_source_count']==1 and report['input_facts_missing_count']==0
    assert report['predicate_attempted_count']==0


def test_invalid_body_input_still_emits_an_unknown_predicate_receipt():
    drug=replace(line(indication='renal_nutrition',ckd_stage=5,albumin_g_dl=3,
        weight_loss_last_3_months_percent=0,bmi=0),drug_name='keto analogları')
    _,collector=observe(drug)
    bmi=next(r for r in collector.receipts if r.get('predicate_id')=='nutrition.initial.bmi')
    assert bmi['status']=='missing_inputs' and bmi['missing_input_fields']==['renal_evidence.bmi']
    assert collector.summary(source())['available'] is True


def test_invalid_stage_is_input_block_and_not_an_executed_sut_threshold():
    drug=replace(line(indication='renal_nutrition',ckd_stage=4.5),drug_name='keto analogları')
    _,collector=observe(drug)
    report=collector.summary(source())
    assert report['routes_blocked_inputs_count']==1
    assert report['predicate_attempted_count']==0


def test_unrelated_families_never_receive_renal_measurements():
    drug=replace(_drug_line(drug_name='nusinersen'),drug_claim_date=DAY)
    result=evaluate_drug_indication_line_detailed(drug_line=drug,claim=_claim(primary_icd10='G12.0'),diagnoses=[])
    assert result['clinical_restrictions']
    assert all('renal' not in (x.get('runtime_coverage') or {}).get('instrumented_families', [])
               for x in result['clinical_restrictions'])


def test_real_request_billing_public_model_and_duckdb_roundtrip_keep_measured_counts():
    drug=line();claim=_claim(primary_icd10='N18.5')
    ctx=PatientClaimContext(patient_id='P1',claims=(claim,),procedure_lines=(),material_lines=(),
        drug_lines=(drug,),diagnoses=())
    batch=evaluate_drug_indication_findings('P1',ctx)
    payload={'evaluations':[e.to_dict() for e in batch.evaluations],
             'findings':[e.to_dict() for e in batch.findings], 'violations':list(batch.legacy_violations)}
    model=DrugIndicationReviewResponse.model_validate(payload)
    assert model.evaluations[0].clinical_restrictions[0].runtime_coverage.predicate_evaluated_count==10
    for key in ('evaluations','findings','violations'):
        row=payload[key][0]['clinical_restrictions'][0]['runtime_coverage']
        assert row['input_facts_available_count']==14
        row['private_raw_clinical_values']={'PTH':150}
    public=project_public_response({'drug_indication':payload},'get_billing_report')
    assert 'private_raw_clinical_values' not in json.dumps(public)
    expected_keys = ['4.2.9.B.(1)#00052268', '4.2.9.B.a#2cbf02e7', '4.2.9.B.b#1438d4b8',
                     '4.2.9.B.c#44af65a8', '4.2.9.B.ç#4843bec7', '4.2.9.B.(2)#8c267281']
    expected_rows = source().filter(pl.col('clause_key').is_in(expected_keys) & pl.col('is_in_force'))
    assert expected_rows.height == len(expected_keys)
    # Corpus renewal may move positional IDs; the six content-pinned clauses remain the same.
    expected_ids = sorted(expected_rows['clause_id'].to_list())
    for key in ('evaluations','findings','violations'):
        report=public['drug_indication'][key][0]['clinical_restrictions'][0]['runtime_coverage']
        assert report['predicate_evaluated_count']==10
        assert report['source_clause_ids']==expected_ids
        assert report['source_clauses_fully_evaluated_count'] is None
    with duckdb.connect(':memory:') as db:
        db.execute('CREATE TABLE reports(payload JSON)')
        db.execute('INSERT INTO reports VALUES (?)',[json.dumps(public)])
        cached=json.loads(db.execute('SELECT payload FROM reports').fetchone()[0])
    assert cached==public


def test_bounded_summary_rejects_inconsistent_counts_and_strips_raw_values():
    _,collector=observe(line());report=collector.summary(source())
    report['private_value']=150
    bounded=bounded_runtime_coverage(report)
    assert bounded['available'] is True and 'private_value' not in bounded
    report['predicate_attempted_count']=999
    assert bounded_runtime_coverage(report)['available'] is False


def test_no_raw_numeric_values_or_patient_names_in_receipts():
    _,collector=observe(line())
    allowed_keys={'family','claim_id','drug_claim_line_id','evaluator_version','kind','predicate_id',
                  'source_refs','clause_predicate_complete','status','observed_input_fields','missing_input_fields','execution_scope'}
    assert all(set(receipt)==allowed_keys for receipt in collector.receipts)
    def values(obj):
        if isinstance(obj,dict):
            return [v for item in obj.values() for v in values(item)]
        if isinstance(obj,list):
            return [v for item in obj for v in values(item)]
        return [obj]
    # Source hashes/protocol identifiers can contain digits. Actual numeric
    # patient facts never occur as numeric leaves or named-value dictionaries.
    assert all(type(value) in (str,bool) for value in values(collector.receipts))
    assert all('values' not in receipt for receipt in collector.receipts)


def test_real_v2_request_exposes_only_observed_runtime_summary():
    from dataclasses import asdict
    from src.bilun.shared.models import ClaimValidationRequest
    raw={'claim_id':'RUNTIME1','materials':[{'name':'sevelamer','renal_evidence':asdict(line().renal_evidence)}],
         'drug_context':{'service_date':DAY.isoformat(),'primary_icd10':'N18.5','board_report_present':True}}
    request=ClaimValidationRequest.model_validate(raw)
    from src.bilun.api.routes.validation import validate_claim_endpoint
    result=validate_claim_endpoint(request,contract_version='2')
    advisory=next(row for row in result['advisories'] if row['rule']=='drug_indication')
    runtime=advisory['clinical_restrictions'][0]['runtime_coverage']
    assert runtime['available'] is True and runtime['predicate_evaluated_count']==10
    assert runtime['instrumented_families']==['renal']
    assert advisory['clinical_eligibility_complete'] is False
    assert advisory['disposition']=='review_only'
    assert 'receipts' not in runtime and 'observations' not in runtime
    assert result['is_valid'] is None


def test_distinct_lines_keep_separate_receipt_identity_but_same_clauses():
    a,ca=observe(line())
    other=replace(line(),drug_claim_line_id='another-line')
    cb=ClinicalObservationCollector(other,'renal',VERSION,execution_scope=ca.execution_scope)
    b=evaluate_renal(other,observer=cb)
    from src.bilun.domain.sut.runtime_coverage import build_runtime_coverage
    combined=build_runtime_coverage(ca.receipts+cb.receipts,
        instrumented_families=['renal'],execution_scope=ca.execution_scope,
        allowed_contexts={(ca.claim_id,ca.line_id),(cb.claim_id,cb.line_id)},
        source_clauses=source())
    assert combined['predicate_evaluated_count']==20
    assert combined['input_facts_available_count']==28
    assert combined['source_clauses_touched_count']==6
    duplicate=build_runtime_coverage(ca.receipts+ca.receipts,
        instrumented_families=['renal'],execution_scope=ca.execution_scope,
        allowed_contexts={(ca.claim_id,ca.line_id)},source_clauses=source())
    assert duplicate['predicate_evaluated_count']==10


def test_anonymous_ad_hoc_claim_is_measured_only_inside_registered_request_scope():
    from src.bilun.domain.sut.runtime_coverage import build_runtime_coverage
    drug=replace(line(),claim_id='')
    _,a=observe(drug);_,b=observe(drug)
    assert a.execution_scope != b.execution_scope
    report=a.summary(source())
    assert report['available'] is True and report['predicate_evaluated_count']==10
    assert 'execution_scope' not in report
    assert a.summary(source())['receipt_sha256']==b.summary(source())['receipt_sha256']
    mixed=build_runtime_coverage(a.receipts+b.receipts,instrumented_families=['renal'],
        execution_scope=a.execution_scope,allowed_contexts={('',a.line_id)},source_clauses=source())
    assert mixed['available'] is False
    unregistered=build_runtime_coverage(a.receipts,instrumented_families=['renal'],
        execution_scope=a.execution_scope,allowed_contexts={('foreign',a.line_id)},source_clauses=source())
    assert unregistered['available'] is False


def test_blank_claim_without_explicit_scope_is_never_accepted():
    from src.bilun.domain.sut.runtime_coverage import build_runtime_coverage
    drug=replace(line(),claim_id='');_,collector=observe(drug)
    rows=[{k:v for k,v in row.items() if k!='execution_scope'} for row in collector.receipts]
    report=build_runtime_coverage(rows,instrumented_families=['renal'],
        allowed_contexts={('',collector.line_id)},source_clauses=source())
    assert report['available'] is False


@pytest.mark.parametrize('change',[
    {'schema_version':True},{'predicate_attempted_count':True},
    {'predicate_evaluated_count':999},{'source_clauses_touched_count':999},
    {'clinical_eligibility_complete':True},{'private_raw_input':{'lab':150}},
])
def test_strict_shared_dto_rejects_inconsistent_or_unapproved_runtime_fields(change):
    from pydantic import ValidationError
    from src.bilun.domain.sut.runtime_coverage_schema import RuntimeCoverageResponse
    _,collector=observe(line());report=collector.summary(source())
    with pytest.raises(ValidationError):
        RuntimeCoverageResponse.model_validate({**report,**change})


def test_actual_v2_anonymous_request_is_measured_without_inventing_claim_identity():
    from dataclasses import asdict
    from src.bilun.shared.models import ClaimValidationRequest
    from src.bilun.api.routes.validation import validate_claim_endpoint
    raw={'materials':[{'name':'sevelamer','renal_evidence':asdict(line().renal_evidence)}],
         'drug_context':{'service_date':DAY.isoformat(),'primary_icd10':'N18.5','board_report_present':True}}
    request=ClaimValidationRequest.model_validate(raw)
    assert request.claim_id==''
    result=validate_claim_endpoint(request,contract_version='2')
    row=next(a for a in result['advisories'] if a['rule']=='drug_indication')
    report=row['clinical_restrictions'][0]['runtime_coverage']
    assert report['available'] is True and report['predicate_evaluated_count']==10
    assert 'execution_scope' not in report and result['claim_id']==''


@pytest.mark.parametrize('change', [
    {'instrumented_families': ['PRIVATE PATIENT INFORMATION']},
    {'instrumented_families': ['renal\n']},
    {'instrumented_families': ['renal'] * 9},
    {'instrumented_families': ['r' * 65]},
    {'instrumented_families': 'renal'},
    {'instrumented_families': [None]},
    {'instrumented_families': [{}]},
    {'source_metrics_available': True},
    {'source_metrics_available': False},
    {'complete_clause_mapping_available': True},
    {'complete_clause_mapping_available': False},
    {'source_clause_ids': ['not source identity']},
    {'source_clause_ids': ['C004224']},
    {'source_clause_ids': []},
    {'fully_evaluated_source_clause_ids': ['private text']},
    {'fully_evaluated_source_clause_ids': []},
    {'receipt_sha256': 'a' * 64},
    {'predicate_attempted_count': 0},
    {'source_clauses_touched_count': 0},
    {'unavailable_reason': 'x' * 501},
    {'source_unavailable_reason': 'x' * 501},
    {'complete_clause_mapping_unavailable_reason': 'x' * 501},
    {'unavailable_reason': []},
    {'clinical_eligibility_complete': 0},
    {'private_raw_input': {'lab': 150}},
])
def test_unavailable_runtime_dto_rejects_unbounded_or_measured_claims(change):
    from pydantic import ValidationError
    from src.bilun.domain.sut.runtime_coverage_schema import RuntimeCoverageResponse
    raw = {'schema_version': 1, 'available': False, 'instrumented_families': ['renal'],
           'unavailable_reason': 'No execution observations.'}
    with pytest.raises(ValidationError):
        RuntimeCoverageResponse.model_validate({**raw, **change})


def test_unavailable_runtime_dto_round_trip_and_sanitized_failure_stay_unmeasured():
    from src.bilun.domain.sut.runtime_coverage_schema import RuntimeCoverageResponse
    raw = {'schema_version': 1, 'available': False, 'instrumented_families': ['renal'],
           'unavailable_reason': 'No execution observations.'}
    model = RuntimeCoverageResponse.model_validate(raw)
    assert RuntimeCoverageResponse.model_validate(model.model_dump()) == model
    hostile = {**raw, 'instrumented_families': ['PRIVATE PATIENT INFORMATION'],
               'source_metrics_available': True, 'source_clause_ids': ['private text']}
    sanitized = bounded_runtime_coverage(hostile)
    clean = RuntimeCoverageResponse.model_validate(sanitized).model_dump()
    assert clean['available'] is False
    assert clean['instrumented_families'] == []
    assert clean['source_metrics_available'] is None
    assert clean['source_clause_ids'] is None
    assert clean['predicate_attempted_count'] is None
    assert 'PRIVATE' not in str(clean) and 'private text' not in str(clean)


def test_unavailable_runtime_dto_requires_explicit_instrumented_scope():
    from pydantic import ValidationError
    from src.bilun.domain.sut.runtime_coverage_schema import RuntimeCoverageResponse
    with pytest.raises(ValidationError):
        RuntimeCoverageResponse.model_validate({'schema_version': 1, 'available': False})


@pytest.mark.parametrize('kind', [
    'families', 'source_ids', 'complete_source_ids', 'reason', 'source_reason', 'mapping_reason',
])
def test_available_runtime_dto_rejects_normalized_copy_that_differs_from_raw(kind):
    from pydantic import ValidationError
    from src.bilun.domain.sut.runtime_coverage_schema import RuntimeCoverageResponse
    _, collector = observe(line())
    raw = collector.summary(source())
    if kind == 'families':
        raw['instrumented_families'] *= 2
    elif kind == 'source_ids':
        raw['source_clause_ids'].append(raw['source_clause_ids'][0])
    elif kind == 'complete_source_ids':
        identity = raw['source_clause_ids'][0]
        raw.update(complete_clause_mapping_available=True,
                   fully_evaluated_source_clause_ids=[identity, identity],
                   source_clauses_fully_evaluated_count=1)
    else:
        key = {'reason': 'unavailable_reason', 'source_reason': 'source_unavailable_reason',
               'mapping_reason': 'complete_clause_mapping_unavailable_reason'}[kind]
        raw[key] = 'x' * 501
    # The public sanitizer can normalize these, but strict validation must not
    # accept a normalized copy and then expose the unbounded/duplicate raw data.
    assert bounded_runtime_coverage(raw)['available'] is True
    with pytest.raises(ValidationError):
        RuntimeCoverageResponse.model_validate(raw)

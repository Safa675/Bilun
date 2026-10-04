from copy import deepcopy

import polars as pl
import pytest

from src.bilun.domain.sut.runtime_coverage import build_runtime_coverage

CONTEXTS = {('claim', 'line')}


def receipt(**changes):
    return {'kind':'predicate','family':'renal','claim_id':'claim','drug_claim_line_id':'line',
        'evaluator_version':'v1','predicate_id':'pth_stop','source_refs':['C000001'],
        'status':'passed','observed_input_fields':['renal_evidence.pth_pg_ml'],
        'missing_input_fields':[],'clause_predicate_complete':False,**changes}


def source():
    return pl.DataFrame({'clause_id':['C000001','C000002'], 'clause_type':['bent','section_heading'],
        'is_in_force':[True,True]})


def build(rows,**kwargs):
    return build_runtime_coverage(rows,instrumented_families=['renal'],allowed_contexts=CONTEXTS,**kwargs)


def test_no_observations_are_unmeasured_but_explicit_empty_collection_is_zero():
    assert build(None)['available'] is False
    empty=build([])
    assert empty['available'] is True and empty['predicate_attempted_count']==0
    assert empty['predicate_evaluated_count']==0 and empty['input_facts_available_count']==0
    assert empty['source_clauses_touched_count'] is None
    no_families=build_runtime_coverage([],instrumented_families=[],allowed_contexts=set())
    assert no_families['available'] is True and no_families['receipt_count']==0


def test_actual_partition_and_distinct_fact_versus_predicate_units():
    rows=[receipt(),receipt(predicate_id='pth_different_source_check',status='failed'),
          receipt(predicate_id='missing_calcium',status='missing_inputs',observed_input_fields=[],
                  missing_input_fields=['renal_evidence.corrected_calcium_mg_dl'])]
    report=build(rows,source_clauses=source())
    assert report['predicate_attempted_count']==3
    assert report['predicate_evaluated_count']==2
    assert report['predicate_passed_count']==report['predicate_failed_count']==report['predicate_missing_inputs_count']==1
    assert report['input_facts_available_count']==1 and report['input_facts_missing_count']==1
    assert report['source_clauses_touched_count']==1
    assert report['source_clauses_fully_evaluated_count'] is None
    assert report['clinical_eligibility_complete'] is False


def test_duplicate_and_order_invariance():
    rows=[receipt(),receipt(predicate_id='other',status='failed')]
    assert build(rows)==build(list(reversed(rows))+deepcopy(rows))


def test_conflicting_duplicate_identity_is_unavailable_not_last_write_wins():
    report=build([receipt(),receipt(status='failed')])
    assert report['available'] is False
    assert 'predicate_evaluated_count' not in report
    assert 'Conflicting receipts' in report['unavailable_reason']


def test_same_predicate_on_distinct_lines_counts_separately_and_rejects_foreign_lines():
    other=receipt(drug_claim_line_id='line2')
    assert build([receipt(),other])['available'] is False
    report=build_runtime_coverage([receipt(),other],instrumented_families=['renal'],
                                  allowed_contexts=CONTEXTS|{('claim','line2')})
    assert report['predicate_evaluated_count']==2 and report['input_facts_available_count']==2


@pytest.mark.parametrize('kind',['blocked_source','blocked_inputs','skipped_not_applicable'])
def test_route_block_or_skip_never_invents_predicate_attempts(kind):
    row=receipt(kind='route',status=kind,route_id='source_date',reasons=['scope_not_supported'])
    for key in ('predicate_id','source_refs','clause_predicate_complete'):row.pop(key)
    row['observed_input_fields']=[]
    if kind=='blocked_inputs':row['missing_input_fields']=['renal_evidence.phase']
    report=build([row])
    assert report['predicate_attempted_count']==report['predicate_evaluated_count']==0
    assert sum(report[key] for key in ('routes_blocked_source_count','routes_blocked_inputs_count','routes_skipped_count'))==1


@pytest.mark.parametrize('changes',[
    {'clinical_value':500}, {'status':'compliant'}, {'claim_id':''}, {'clause_predicate_complete':1},
    {'status':'missing_inputs'}, {'source_refs':[]}, {'family':'unregistered'},
    {'missing_input_fields':['renal_evidence.pth_pg_ml']},
])
def test_malformed_or_raw_value_receipts_fail_closed(changes):
    assert build([receipt(**changes)])['available'] is False


def test_conflicting_fact_presence_across_predicates_fails_closed():
    unknown=receipt(predicate_id='other',status='missing_inputs',observed_input_fields=[],
                    missing_input_fields=['renal_evidence.pth_pg_ml'])
    assert build([receipt(),unknown])['available'] is False


@pytest.mark.parametrize('ref',['C999999','C000002','invalid'])
def test_unverified_or_structural_source_never_counts_as_evaluated_clause(ref):
    report=build([receipt(source_refs=[ref])],source_clauses=source())
    assert report['available'] is True and report['predicate_evaluated_count']==1
    assert report['source_metrics_available'] is False
    assert report['source_clauses_touched_count'] is None and report['source_clause_ids'] is None


def test_complete_clause_requires_external_reviewed_mapping_not_a_receipt_claim():
    row=receipt(clause_predicate_complete=True)
    assert build([row],source_clauses=source())['source_clauses_fully_evaluated_count'] is None
    wrong={('renal','v1','pth_stop'):['C000002']}
    assert build([row],source_clauses=source(),complete_clause_predicates=wrong)['source_clauses_fully_evaluated_count'] is None
    mapping={('renal','v1','pth_stop'):['C000001']}
    report=build([row],source_clauses=source(),complete_clause_predicates=mapping)
    assert report['source_clauses_fully_evaluated_count']==1
    assert report['fully_evaluated_source_clause_ids']==['C000001']


def test_reviewed_mapping_never_counts_unknown_clause_as_fully_evaluated():
    row=receipt(status='missing_inputs',observed_input_fields=[],
        missing_input_fields=['renal_evidence.pth_pg_ml'],clause_predicate_complete=True)
    report=build([row],source_clauses=source(),
                 complete_clause_predicates={('renal','v1','pth_stop'):['C000001']})
    assert report['source_clauses_fully_evaluated_count']==0
    assert report['source_clauses_touched_count']==1


@pytest.mark.parametrize('field',['pth=500','patient has high PTH','renal_evidence.pth 500'])
def test_raw_values_cannot_be_hidden_in_field_identifiers(field):
    assert build([receipt(observed_input_fields=[field])])['available'] is False


def test_duplicate_source_rows_are_not_unique_verified_authority():
    duplicated=pl.concat([source(),source().head(1)])
    report=build([receipt()],source_clauses=duplicated)
    assert report['source_metrics_available'] is False
    assert report['source_clause_ids'] is None


@pytest.mark.parametrize('status',[[],{},0,None,True])
@pytest.mark.parametrize('kind',['predicate','route'])
def test_malformed_state_types_are_unavailable_without_crashing(status,kind):
    row=receipt(status=status)
    if kind=='route':
        for key in ('predicate_id','source_refs','clause_predicate_complete'):row.pop(key)
        row.update(kind='route',route_id='source_date',reasons=['scope_not_supported'])
    report=build([row])
    assert report['available'] is False
    assert report['unavailable_reason']=='Unknown observation state'


@pytest.mark.parametrize('kind',['prose','amendment','chapter','section_heading',None])
def test_opaque_identity_cannot_bypass_executable_source_kind(kind):
    frame=source().with_columns(pl.lit(kind,dtype=pl.String).alias('clause_type'))
    report=build([receipt()],source_clauses=frame)
    assert report['predicate_evaluated_count']==1
    assert report['source_metrics_available'] is False
    assert report['source_clause_ids'] is None


@pytest.mark.parametrize('active',[False,None,1,'true'])
def test_source_current_status_requires_explicit_boolean_true(active):
    frame=source().with_columns(pl.lit(active).alias('is_in_force'))
    report=build([receipt()],source_clauses=frame)
    assert report['predicate_evaluated_count']==1 and report['source_metrics_available'] is False


@pytest.mark.parametrize('flag',['is_heading','is_amendment'])
@pytest.mark.parametrize('value',[True,None,1])
def test_contradictory_or_unknown_structural_flags_are_not_executable_authority(flag,value):
    report=build([receipt()],source_clauses=source().with_columns(pl.lit(value).alias(flag)))
    assert report['source_metrics_available'] is False


@pytest.mark.parametrize('column',['clause_type','is_in_force'])
def test_missing_source_kind_or_status_never_defaults_to_executable(column):
    report=build([receipt()],source_clauses=source().drop(column))
    assert report['source_metrics_available'] is False


@pytest.mark.parametrize('status,missing',[
    ('blocked_source',['verified_source_for_service_date']),
    ('skipped_not_applicable',['renal_evidence.phase']),
    ('blocked_inputs',[]),
])
def test_route_states_cannot_mislabel_source_reason_as_missing_clinical_fact(status,missing):
    row=receipt(kind='route',status=status,route_id='scope',reasons=['scope_not_supported'],
                observed_input_fields=[],missing_input_fields=missing)
    for key in ('predicate_id','source_refs','clause_predicate_complete'):row.pop(key)
    assert build([row])['available'] is False


def test_non_scalar_source_kind_cannot_crash_source_metrics():
    frame=source().with_columns(pl.lit(['bent']).alias('clause_type'))
    report=build([receipt()],source_clauses=frame)
    assert report['source_metrics_available'] is False


def test_real_active_amended_clause_is_not_confused_with_full_repeal():
    from pathlib import Path
    frame=pl.read_parquet(Path(__file__).resolve().parents[4]/'data/gazette/sut_clauses.parquet')
    source_ref='4.2.9.Ç.(1)#d5f6d259'
    matched=frame.filter(pl.col('clause_key')==source_ref)
    assert matched.height==1
    row=matched.row(0,named=True)
    assert row['is_in_force'] is True and row['is_superseded_marker'] is True
    assert row['clause_type']=='fikra' and row['is_amendment'] is False
    result=build([receipt(source_refs=[source_ref])],source_clauses=frame)
    assert result['source_metrics_available'] is True
    assert result['source_clause_ids']==[row['clause_id']]


def test_whole_inactive_superseded_clause_still_has_no_runtime_source_count():
    frame=source().with_columns(pl.lit(False).alias('is_in_force'),
                               pl.lit(True).alias('is_superseded_marker'))
    result=build([receipt()],source_clauses=frame)
    assert result['source_metrics_available'] is False

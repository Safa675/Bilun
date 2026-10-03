"""Receipts include actual clear None paths, missing facts and gate bypasses."""
from dataclasses import replace
from datetime import date
import json
import pytest
from src.bilun.domain.prose_rules.drug_indication import list_drug_indication_rules
from src.bilun.domain.prose_rules._drug_indication.runtime_observations import ClinicalObservationCollector
from src.bilun.domain.prose_rules._drug_indication.growth_hormone import evaluate_growth_hormone_continuation
from src.bilun.domain.prose_rules._drug_indication.prader_willi import evaluate_pws_clinical_checks
from src.bilun.domain.prose_rules._drug_indication.ckd_growth_hormone import evaluate_ckd_gh_checks
from src.bilun.domain.prose_rules._drug_indication.mecasermin import evaluate_mecasermin_checks
from src.bilun.domain.claims.growth_hormone import CKD_GH_BOOLEAN_FIELDS, PWS_FIELDS
from tests.unit.domain.prose_rules.test_growth_hormone_continuation import line

pytestmark=pytest.mark.unit
CASES=[('turner','4.2.6.turner_somatropin_pediatric_board',evaluate_growth_hormone_continuation),
       ('pediatric','4.2.6.pediatric_gh_monitoring_board',evaluate_growth_hormone_continuation),
       ('pws','4.2.6.pws_somatropin_tertiary_board',evaluate_pws_clinical_checks),
       ('ckd','4.2.6.ckd_gh_nephro_endo_board',evaluate_ckd_gh_checks),
       ('mecasermin',None,evaluate_mecasermin_checks)]

def fixture(family,rule_id,function,**values):
    rules=list_drug_indication_rules()
    rule=next(r for r in rules if r['rule_id']==rule_id) if rule_id else next(r for r in rules if r.get('mecasermin_source_scope') and r.get('gh_treatment_phase')=='continuation')
    drug=replace(line(),**{'gh_patient_group':'pediatric','gh_height_reference_sex':'female',
        **dict.fromkeys(PWS_FIELDS,False),**dict.fromkeys(CKD_GH_BOOLEAN_FIELDS,False),
        'pws_genetic_diagnosis_confirmed':True,'ckd_growth_disorder_confirmed':True,
        'ckd_parathyroid_hormone_pg_ml':499,'gh_daily_dose_mg_per_kg':0.05,
        'mecasermin_laron_syndrome_confirmed':True,'pretreatment_annual_growth_velocity_cm':1,
        'height_percentile':20,'mecasermin_daily_dose_mcg_per_kg':120,'drug_claim_date':date(2026,10,2),**values})
    observer=ClinicalObservationCollector(drug,'growth_hormone','gh.atomic.v1.2026-10-02',execution_scope='synthetic-request')
    plain=function(rule=rule,drug_line=drug)
    result=function(rule=rule,drug_line=drug,observer=observer)
    assert result==plain
    return result,observer

@pytest.mark.parametrize('case',CASES,ids=[x[0] for x in CASES])
def test_clear_reached_comparisons_recorded_including_none_returns(case):
    result,o=fixture(*case)
    predicates=[r for r in o.receipts if r['kind']=='predicate']
    assert predicates and all(r['status']=='passed' for r in predicates)
    if case[0] in {'turner','pediatric'}:assert result is None
    s=o.summary();assert s['predicate_passed_count']==len(predicates)
    assert s['source_clauses_fully_evaluated_count'] is None
    assert s['source_metrics_available'] is False

@pytest.mark.parametrize('case',CASES,ids=[x[0] for x in CASES])
@pytest.mark.parametrize('when',[None,date(2024,5,16)])
def test_date_blocks_never_invent_clinical_execution(case,when):
    _,o=fixture(*case,drug_claim_date=when)
    assert not any(r['kind']=='predicate' for r in o.receipts)
    assert o.summary()['routes_blocked_inputs_count' if when is None else 'routes_blocked_source_count']==1

def test_turner_initiation_bypass_not_counted_as_pass():
    result,o=fixture(*CASES[0],gh_treatment_phase='initiation',epiphyses_closed=True)
    assert result is None
    assert o.summary()['predicate_attempted_count']==0 and o.summary()['routes_skipped_count']==1

def test_missing_turner_fact_is_unknown_not_pass():
    _,o=fixture(*CASES[0],height_cm=None)
    hit=next(r for r in o.receipts if r.get('predicate_id')=='gh.turner.continuation.height_below_limit')
    assert hit['status']=='missing_inputs' and hit['missing_input_fields']==['height_cm']
    assert 'height_cm' not in hit['observed_input_fields']

def test_early_ckd_exclusion_does_not_claim_unreached_dose():
    _,o=fixture(*CASES[3],gh_treatment_phase='initiation',ckd_active_cancer=True)
    assert not any(r.get('predicate_id')=='gh.ckd.dose.within_source_range' for r in o.receipts)
    assert o.summary()['predicate_failed_count']==1

def test_ckd_continuation_records_dose_and_initiation_bypass():
    _,o=fixture(*CASES[3])
    assert [r['predicate_id'] for r in o.receipts if r['kind']=='predicate']==['gh.ckd.dose.within_source_range']
    assert o.summary()['routes_skipped_count']==1

@pytest.mark.parametrize('index,field',[(2,'pws_genetic_diagnosis_confirmed'),(3,'ckd_growth_disorder_confirmed'),(4,'mecasermin_laron_syndrome_confirmed')])
@pytest.mark.parametrize('value',[False,None])
def test_false_and_unknown_scope_distinct_without_available_missing_overlap(index,field,value):
    _,o=fixture(*CASES[index],**{field:value});s=o.summary()
    assert s['predicate_attempted_count']==0
    assert s['routes_skipped_count' if value is False else 'routes_blocked_inputs_count']==1

def test_receipts_have_no_clinical_values_or_names():
    _,o=fixture(*CASES[0],drug_name='PRIVATE_NAME_SENTINEL',height_cm=123.456789)
    serialized=json.dumps(o.receipts)
    assert 'PRIVATE_NAME_SENTINEL' not in serialized and '123.456789' not in serialized
    assert all(r['clause_predicate_complete'] is False for r in o.receipts if r['kind']=='predicate')

@pytest.mark.parametrize('case',CASES,ids=[x[0] for x in CASES])
def test_shared_caller_sequence_has_no_conflicting_route_receipts(case):
    from src.bilun.domain.prose_rules._drug_indication.prader_willi import evaluate_pws_preconditions
    from src.bilun.domain.prose_rules._drug_indication.ckd_growth_hormone import evaluate_ckd_gh_preconditions
    from src.bilun.domain.prose_rules._drug_indication.mecasermin import evaluate_mecasermin_preconditions
    rules=list_drug_indication_rules()
    rule=next(r for r in rules if r['rule_id']==case[1]) if case[1] else next(r for r in rules if r.get('mecasermin_source_scope') and r.get('gh_treatment_phase')=='continuation')
    drug=replace(line(),gh_patient_group='pediatric',gh_height_reference_sex='female',
        pws_genetic_diagnosis_confirmed=True,ckd_growth_disorder_confirmed=True,
        mecasermin_laron_syndrome_confirmed=True,drug_claim_date=date(2026,10,2))
    o=ClinicalObservationCollector(drug,'growth_hormone','gh.atomic.v1.2026-10-02',execution_scope='sequence')
    for pre in [evaluate_pws_preconditions,evaluate_ckd_gh_preconditions,evaluate_mecasermin_preconditions]:
        if pre(rule=rule,drug_line=drug,observer=o) is not None:break
    else:
        for fn in [evaluate_growth_hormone_continuation,evaluate_pws_clinical_checks,evaluate_ckd_gh_checks,evaluate_mecasermin_checks]:
            if fn(rule=rule,drug_line=drug,observer=o) is not None:break
    assert o.summary()['available'] is True

def test_mecasermin_needs_reviewed_corrected_source_view_not_arbitrary_prose():
    from pathlib import Path
    import polars as pl
    from scripts.sut.prose.clause_type_overrides import apply_clause_type_overrides, load_clause_type_overrides
    _,o=fixture(*CASES[4])
    root=Path(__file__).resolve().parents[4]
    raw=pl.read_parquet(root/'data/gazette/sut_clauses.parquet')
    assert o.summary(raw)['source_metrics_available'] is False
    reviewed={key:spec for key,spec in load_clause_type_overrides().items()
              if key in {'4.2.6.B-3#dde3c8f6','4.2.6.B-3#11e1f077','4.2.6.B-3#de2f2b31'}}
    assert len(reviewed)==3
    summary=o.summary(apply_clause_type_overrides(raw,reviewed))
    assert summary['source_metrics_available'] is True
    assert summary['source_clauses_touched_count']==4
    assert summary['source_clauses_fully_evaluated_count'] is None

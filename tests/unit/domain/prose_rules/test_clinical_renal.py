"""Renal source boundaries, tri-state input safety and branch isolation."""
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import polars as pl
import pytest

from src.bilun.domain.claims.clinical_evidence import RenalEvidence, parse_clinical_evidence
from src.bilun.domain.prose_rules._drug_indication.clinical_renal import (
    evaluate_renal, PHOSPHATE_INITIAL, PHOSPHATE_STOP, PHOSPHATE_RESTART,
    CINACALCET_INITIAL, CINACALCET_STOP, CINACALCET_PRIMARY,
    NUTRITION_INITIAL, NUTRITION_STOP, NUTRITION_RESTART,
)
from tests.unit.domain.prose_rules.test_drug_indication import _drug_line

DAY = date(2026, 10, 2)


def check(name='sevelamer', **facts):
    facts = {'applies_on': DAY, 'assessment_date': DAY, **facts}
    line = SimpleNamespace(drug_name=name, drug_claim_date=DAY,
                           renal_evidence=parse_clinical_evidence(facts, RenalEvidence))
    return evaluate_renal(line)


def phosphate(**facts):
    base = dict(indication='phosphate_binding', phase='initiation', dialysis=True,
        other_phosphate_therapy_months=3, prior_phosphate_therapy_documented_in_report=True,
        calcium_phosphorus_product=71,
        corrected_calcium_phosphorus_product=55, pth_pg_ml=150,
        adynamic_bone_disease=False, kt_v=1.4)
    return check(**{**base, **facts})


def nutrition(**facts):
    base = dict(indication='renal_nutrition', phase='initiation', albumin_g_dl=3.4,
                ckd_stage=5, weight_loss_last_3_months_percent=10, bmi=20)
    return check('keto analogları', **{**base, **facts})


@pytest.mark.parametrize('changes, expected', [
    ({}, 'restriction_not_met'),
    ({'calcium_phosphorus_product':72}, 'criterion_clear'),
    ({'pth_pg_ml':99, 'adynamic_bone_disease':True}, 'criterion_clear'),
    ({'pth_pg_ml':100, 'adynamic_bone_disease':True}, 'restriction_not_met'),
    ({'kt_v':1.40001, 'corrected_calcium_phosphorus_product':55.00001}, 'criterion_clear'),
    ({'kt_v':1.4, 'corrected_calcium_phosphorus_product':56}, 'restriction_not_met'),
    ({'kt_v':1.5, 'corrected_calcium_phosphorus_product':55}, 'restriction_not_met'),
    ({'kt_v':1.40001, 'pth_pg_ml':300}, 'criterion_clear'),
    ({'kt_v':1.40001, 'pth_pg_ml':299.999}, 'restriction_not_met'),
    ({'calcium_phosphorus_product':72, 'other_phosphate_therapy_months':2.999}, 'restriction_not_met'),
    ({'calcium_phosphorus_product':72, 'dialysis':False}, 'restriction_not_met'),
])
def test_phosphate_four_alternatives_and_global_prerequisites(changes, expected):
    assert phosphate(**changes)['criterion_status'] == expected


def test_one_known_true_alternative_does_not_require_other_alternatives():
    result = check(indication='phosphate_binding', phase='initiation', dialysis=True,
                   other_phosphate_therapy_months=3, prior_phosphate_therapy_documented_in_report=True,
                   calcium_phosphorus_product=72)
    assert result['criterion_status'] == 'criterion_clear'
    assert result['missing_inputs'] == []
    assert result['clinical_eligibility_complete'] is False


@pytest.mark.parametrize('phosphorus, expected', [(4,'restriction_not_met'),(4.00001,'criterion_clear')])
def test_phosphate_restart_requires_strict_phosphorus_and_original_criteria(phosphorus, expected):
    assert phosphate(phase='restart', calcium_phosphorus_product=72,
                     phosphorus_mg_dl=phosphorus)['criterion_status'] == expected
    assert phosphate(phase='restart', phosphorus_mg_dl=5)['criterion_status'] == 'restriction_not_met'


@pytest.mark.parametrize('phosphorus, expected', [(3.499,'restriction_not_met'),(3.5,'criterion_clear')])
def test_phosphate_continuation_uses_stopping_boundary(phosphorus, expected):
    assert check(phase='continuation', indication='phosphate_binding', dialysis=True,
                 phosphorus_mg_dl=phosphorus)['criterion_status'] == expected


@pytest.mark.parametrize('phase, calcium, pth, expected', [
    ('initiation',8.5,600,'criterion_clear'),('initiation',8.499,600,'restriction_not_met'),
    ('initiation',8.5,599.999,'restriction_not_met'),('continuation',8.4,300,'restriction_not_met'),
    ('continuation',8.40001,300,'criterion_clear'),('continuation',8.5,299.999,'restriction_not_met'),
    ('restart',9,700,'unknown'),
])
def test_cinacalcet_dialysis_start_and_stop_are_distinct(phase, calcium, pth, expected):
    assert check('cinacalcet', indication='dialysis_shpt', phase=phase, dialysis=True,
                 corrected_calcium_mg_dl=calcium,pth_pg_ml=pth)['criterion_status'] == expected


def test_cinacalcet_dialysis_low_pth_never_rejects_primary_hpt_branch():
    result = check('cinacalcet', indication='primary_hpt', phase='initiation', pth_pg_ml=100,
        parathyroidectomy_indicated=True,parathyroidectomy_unsuitable_or_contraindicated=True,asa_iv=True)
    assert result['criterion_status'] == 'criterion_clear'
    assert result['source_refs'] == CINACALCET_PRIMARY


def test_primary_hpt_requires_surgical_assessments_even_for_asa_iv():
    result = check('cinacalcet', indication='primary_hpt', asa_iv=True)
    assert result['criterion_status'] == 'unknown'
    assert 'renal_evidence.parathyroidectomy_indicated' in result['missing_inputs']
    result = check('cinacalcet', indication='primary_hpt', asa_iv=True,
                   parathyroidectomy_indicated=False,parathyroidectomy_unsuitable_or_contraindicated=True)
    assert result['criterion_status'] == 'restriction_not_met'


@pytest.mark.parametrize('calcium, expected',[(10.499,'restriction_not_met'),(10.5,'criterion_clear')])
def test_primary_hpt_recurrence_requires_all_three_alternative_conditions(calcium,expected):
    result=check('cinacalcet',indication='primary_hpt',asa_iv=False,postsurgical_recurrence=True,
        bisphosphonate_failed=True,corrected_calcium_mg_dl=calcium,
        parathyroidectomy_indicated=True,parathyroidectomy_unsuitable_or_contraindicated=True)
    assert result['criterion_status']==expected


@pytest.mark.parametrize('changes, expected', [
    ({},'criterion_clear'),({'albumin_g_dl':3.5},'restriction_not_met'),
    ({'weight_loss_last_3_months_percent':9.99},'restriction_not_met'),
    ({'weight_loss_last_3_months_percent':9.99,'bmi':18.999},'criterion_clear'),
    ({'weight_loss_last_3_months_percent':9.99,'bmi':19},'restriction_not_met'),
    ({'ckd_stage':4,'gfr_ml_min':29.99},'criterion_clear'),
    ({'ckd_stage':4,'gfr_ml_min':30},'restriction_not_met'),
    ({'ckd_stage':3,'gfr_ml_min':29},'restriction_not_met'),
    ({'ckd_stage':4.5},'unknown'),
    ({'phase':'restart'},'criterion_clear'),
    ({'phase':'restart','albumin_g_dl':3.5},'restriction_not_met'),
])
def test_nutrition_compound_initiation_and_restart(changes,expected):
    assert nutrition(**changes)['criterion_status']==expected


@pytest.mark.parametrize('months,current,baseline,six_month,expected',[
    (2,3,2,None,'unknown'),(3,4,2,None,'criterion_clear'),(3,4.001,2,None,'restriction_not_met'),
    (6,3,2.4,None,'criterion_clear'),(6,2.999,2.4,None,'restriction_not_met'),
    (6,3,0,None,'unknown'),(12,3,2.4,None,'unknown'),
    (12,2.8,2.4,3,'criterion_clear'), # historical response preserved despite later change
    (12,3.5,2.4,2.99,'restriction_not_met'), # later recovery cannot erase checkpoint failure
    (12,4.1,2.4,3,'restriction_not_met'),
])
def test_nutrition_stopping_uses_correct_historical_checkpoint(months,current,baseline,six_month,expected):
    assert nutrition(phase='continuation',therapy_months=months,albumin_g_dl=current,
        baseline_albumin_g_dl=baseline,six_month_albumin_g_dl=six_month)['criterion_status']==expected


@pytest.mark.parametrize('name,indication',[('cinacalcet','other'),('sevelamer','primary_hpt'),('keto analogları','dialysis_shpt')])
def test_unsupported_indications_are_review_not_rejection(name,indication):
    assert check(name,indication=indication)['criterion_status']=='unknown'


@pytest.mark.parametrize('changes,missing',[
    ({'applies_on':None},'renal_evidence.applies_on'),
    ({'applies_on':date(2026,10,1)},'renal_evidence.applies_on'),
    ({'assessment_date':date(2026,10,3)},'renal_evidence.assessment_date'),
    ({'assessment_date':None},'renal_evidence.assessment_date'),
])
def test_missing_and_future_evidence_never_evaluates(changes,missing):
    outcome=phosphate(calcium_phosphorus_product=72,**changes)
    assert outcome['criterion_status']=='not_evaluated' and outcome['checks']==[]
    assert missing in outcome['missing_inputs']


@pytest.mark.parametrize('service',[None,date(2026,10,1),date(2026,10,3),'bad'])
def test_source_snapshot_does_not_invent_historical_or_future_effectiveness(service):
    line=SimpleNamespace(drug_name='cinacalcet',drug_claim_date=service,
        renal_evidence=RenalEvidence(applies_on=DAY,assessment_date=DAY))
    assert evaluate_renal(line)['criterion_status']=='not_evaluated'


@pytest.mark.parametrize('bad',[None,True,'72',float('nan'),float('inf'),-72])
def test_malformed_numeric_inputs_do_not_become_valid_thresholds(bad):
    result=phosphate(calcium_phosphorus_product=bad)
    assert result['criterion_status']=='unknown'


def test_typed_evidence_is_revalidated_and_compound_drugs_are_not_silently_truncated():
    evidence=RenalEvidence(applies_on=DAY,assessment_date=DAY,indication='phosphate_binding',
        phase='initiation',dialysis=True,other_phosphate_therapy_months=3,calcium_phosphorus_product='72')
    line=replace(_drug_line(drug_name='sevelamer'),drug_claim_date=DAY,renal_evidence=evidence)
    assert evaluate_renal(line)['criterion_status']=='unknown'
    assert check('sevelamer + cinacalcet')['criterion_status']=='unknown'


def test_all_source_refs_resolve_to_one_literal_current_clause():
    from pathlib import Path
    from scripts.sut.prose.clause_identity import resolve_gate_b_ref_to_clause_ids
    root=Path(__file__).resolve().parents[4]
    frame=pl.read_parquet(root/'data/gazette/sut_clauses.parquet')
    refs=PHOSPHATE_INITIAL+PHOSPHATE_STOP+PHOSPHATE_RESTART+CINACALCET_INITIAL+CINACALCET_STOP+CINACALCET_PRIMARY+NUTRITION_INITIAL+NUTRITION_STOP+NUTRITION_RESTART
    for ref in refs:
        assert len(resolve_gate_b_ref_to_clause_ids(ref,frame,encode_eligible_only=True))==1


@pytest.mark.parametrize('changes',[
    {'weight_loss_last_3_months_percent':100,'bmi':20},
    {'weight_loss_last_3_months_percent':101,'bmi':20},
    {'weight_loss_last_3_months_percent':0,'bmi':0},
])
def test_impossible_body_measurements_cannot_clear_nutrition(changes):
    assert nutrition(**changes)['criterion_status']=='unknown'

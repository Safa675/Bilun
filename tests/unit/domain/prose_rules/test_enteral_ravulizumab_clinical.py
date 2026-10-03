"""Bounded necessary predicates, not complete reimbursement determinations."""
from dataclasses import replace
from datetime import date
import math

import pytest

from src.bilun.domain.claims.clinical_evidence import (
    EnteralEvidence, RavulizumabEvidence, parse_clinical_evidence,
)
from src.bilun.domain.prose_rules._drug_indication.clinical_enteral import evaluate_enteral_reports
from src.bilun.domain.prose_rules._drug_indication.clinical_ravulizumab import evaluate_ravulizumab_continuation
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed, list_drug_indication_rules
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.shared.models import ClaimValidationRequest
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _drug_line

DAY = date(2026, 10, 2)


def enteral(**changes):
    evidence = EnteralEvidence(applies_on=DAY, assessment_date=DAY, pediatric=True,
        phase='initiation', malnutrition_path='malnutrition', neurological_disease=True,
        malnutrition_criteria_met=True, specialist_report_present=True,
        malnutrition_conditions_documented_in_report=True,
        report_author_specialty='pediatrics')
    return replace(_drug_line(drug_name='çocuk enteral beslenme', report_present=False,
                              report_duration_months=12), drug_claim_date=DAY,
                   enteral_evidence=replace(evidence, **changes))


def ravu(**changes):
    evidence = RavulizumabEvidence(applies_on=DAY, assessment_date=DAY,
        indication='nmosd', adult=True, therapy_months=6, edss=7.5, edss_in_report=True)
    return replace(_drug_line(drug_name='ravulizumab', report_present=True,
                              report_duration_months=6, prescriber_specialty='nöroloji'),
                   drug_claim_date=DAY, ravulizumab_evidence=replace(evidence, **changes))


@pytest.mark.parametrize('months,neuro,status', [
    (3, False, 'criterion_clear'), (6, False, 'criterion_clear'), (7, False, 'restriction_not_met'),
    (12, True, 'criterion_clear'), (13, True, 'restriction_not_met'),
    (6, None, 'criterion_clear'), (12, None, 'unknown'), (13, None, 'restriction_not_met'),
    (None, True, 'unknown'), (True, True, 'unknown'), (float('nan'), True, 'unknown'),
])
def test_enteral_maximum_and_neurological_exception(months, neuro, status):
    result = evaluate_enteral_reports(replace(enteral(neurological_disease=neuro), drug_report_duration_months=months))
    assert result['criterion_status'] == status


@pytest.mark.parametrize('phase,author,status', [
    ('initiation', 'pediatrics', 'criterion_clear'), ('initiation', 'pediatric_surgery', 'criterion_clear'),
    ('initiation', 'pediatric_neurology', 'restriction_not_met'),
    ('renewal', 'pediatric_neurology', 'criterion_clear'), ('renewal', 'pediatric_endocrinology', 'criterion_clear'),
    ('renewal', 'pediatrics', 'restriction_not_met'), (None, 'pediatrics', 'unknown'),
    ('renewal', None, 'unknown'),
])
def test_report_author_phase_is_not_prescriber(phase, author, status):
    line = replace(enteral(phase=phase, report_author_specialty=author), prescriber_specialty='aile hekimliği')
    assert evaluate_enteral_reports(line)['criterion_status'] == status


def test_exempt_and_adult_paths_are_not_forced_through_malnutrition_rule():
    adult = evaluate_enteral_reports(enteral(pediatric=False))
    assert adult['criterion_status'] == 'not_evaluated'
    assert adult['missing_inputs'] == ['enteral_evidence.adult_path_requires_review']
    assert evaluate_enteral_reports(enteral(pediatric=False), '4.2.8.A.adult_malnutrition_1200kcal_3mo_report') is None
    result = evaluate_enteral_reports(enteral(malnutrition_path='exemption', malnutrition_criteria_met=False))
    assert result['criterion_status'] == 'not_evaluated'
    assert result['missing_inputs'] == ['enteral_evidence.exception_path_requires_review']
    assert result['checks'] == []


@pytest.mark.parametrize('day,status', [('2026-09-04', 'not_evaluated'), ('2026-09-05', 'criterion_clear'),
                                       ('2026-09-06', 'criterion_clear'), ('2026-10-03', 'not_evaluated')])
def test_enteral_provision_date_not_publication_date(day, status):
    service = date.fromisoformat(day)
    line = replace(enteral(applies_on=service, assessment_date=service), drug_claim_date=service)
    assert evaluate_enteral_reports(line)['criterion_status'] == status


@pytest.mark.parametrize('months,edss,stop,status', [
    (5.99, 8, False, 'criterion_clear'), (6, 8, True, 'restriction_not_met'),
    (6.01, 8, True, 'restriction_not_met'), (6, 7.5, False, 'criterion_clear'),
    (12, 9, True, 'restriction_not_met'), (None, 8, None, 'unknown'),
    (6, None, None, 'unknown'), (6, 99, None, 'unknown'), (True, 8, None, 'unknown'),
    (6, float('nan'), None, 'unknown'),
])
def test_ravulizumab_six_month_edss_boundary(months, edss, stop, status):
    result = evaluate_ravulizumab_continuation(ravu(therapy_months=months, edss=edss), ['G36.0'])
    assert result['stop_required'] is stop
    assert result['criterion_status'] == status


@pytest.mark.parametrize('documented,status', [(False,'restriction_not_met'), (None,'unknown'), (True,'criterion_clear')])
def test_edss_must_be_on_each_report_even_before_six_months(documented, status):
    result = evaluate_ravulizumab_continuation(ravu(therapy_months=1, edss_in_report=documented), ['G36.0'])
    assert result['criterion_status'] == status


@pytest.mark.parametrize('day,status', [('2026-07-06','not_evaluated'), ('2026-07-07','criterion_clear'),
                                       ('2026-07-08','criterion_clear'), ('2026-10-03','not_evaluated')])
def test_ravulizumab_source_date(day, status):
    service=date.fromisoformat(day)
    line=replace(ravu(applies_on=service,assessment_date=service),drug_claim_date=service)
    assert evaluate_ravulizumab_continuation(line,['G36.0'])['criterion_status'] == status


@pytest.mark.parametrize('factory,evaluator,prefix',[(enteral,evaluate_enteral_reports,'enteral_evidence'),
                                                   (ravu,evaluate_ravulizumab_continuation,'ravulizumab_evidence')])
def test_scope_unknown_and_future_assessment_are_not_clinical_absence(factory,evaluator,prefix):
    assert evaluator(replace(factory(),drug_claim_date=None))['missing_inputs']==['drug_claim_date']
    late = evaluator(factory(assessment_date=date(2026,10,3)))
    assert late['criterion_status']=='not_evaluated' and prefix+'.assessment_date' in late['missing_inputs']
    assert evaluator(factory(applies_on=date(2026,10,1)))['criterion_status']=='not_evaluated'


def test_non_nmosd_ravulizumab_indications_are_not_subject_to_edss_stop():
    assert evaluate_ravulizumab_continuation(ravu(indication='pnh',edss=9),['D59.5']) is None
    assert evaluate_ravulizumab_continuation(ravu(indication='ahus',edss=9),['D59.3']) is None
    assert evaluate_ravulizumab_continuation(replace(ravu(),ravulizumab_evidence=None),['D59.5']) is None


def test_full_corpus_enteral_twelve_month_specialist_report_is_partial_not_false_board_or_duration_failure():
    result=evaluate_drug_indication_line_detailed(drug_line=enteral(),claim=_claim(primary_icd10='E44.0'),diagnoses=[])
    assert result['clinical_restrictions'][0]['criterion_status']=='criterion_clear'
    assert result['violation']['severity']=='review'
    assert result['violation']['violation_kind'] not in {'report_duration_mismatch','missing_board_report'}
    assert result['clinical_eligibility_complete'] is False
    assert 'remaining_sut_clinical_criteria' in result['missing_inputs']


def test_full_corpus_ravu_stopping_rule_is_not_an_indication_route():
    result=evaluate_drug_indication_line_detailed(drug_line=ravu(edss=8),claim=_claim(primary_icd10='G36.0'),diagnoses=[])
    assert result['clinical_restrictions'][0]['stop_required'] is True
    assert result['violation']['violation_kind']=='clinical_restriction_not_met'
    assert result['violation']['sut_section']=='4.2.14.C(3)(yyy)(2)'
    assert '4.2.14.C.ravulizumab_nmosb_edss8_stop' not in result['eligible_route_rule_ids']


def test_passed_stop_predicate_and_short_valid_report_never_clear_full_eligibility():
    line=replace(ravu(),drug_report_duration_months=3)
    result=evaluate_drug_indication_line_detailed(drug_line=line,claim=_claim(primary_icd10='G36.0'),diagnoses=[])
    assert result['violation']['severity']=='review'
    assert result['clinical_restrictions'][0]['criterion_status']=='criterion_clear'
    assert result['clinical_eligibility_complete'] is False


@pytest.mark.parametrize('name,cls', [('enteral_evidence',EnteralEvidence),('ravulizumab_evidence',RavulizumabEvidence)])
def test_api_and_adapter_round_trip_strict_evidence(name,cls):
    facts={'applies_on':'2026-10-02','assessment_date':'2026-10-02'}
    facts.update({'pediatric':True,'phase':'renewal'} if cls is EnteralEvidence else {'adult':True,'therapy_months':6,'edss':8})
    req=ClaimValidationRequest.model_validate({'drug_context':{'service_date':'2026-10-02'},
                                               'materials':[{'name':'test',name:facts}]})
    for mode in ('python','json'):
        line=build_context_from_material_dict(req.model_dump(mode=mode)).drug_lines[0]
        typed=getattr(line,name)
        assert isinstance(typed,cls) and typed.applies_on==DAY
    bad=parse_clinical_evidence({'pediatric':'false','adult':0,'therapy_months':math.inf,'edss':True},cls)
    assert getattr(bad,'pediatric',None) is None and getattr(bad,'adult',None) is None
    assert getattr(bad,'therapy_months',None) is None and getattr(bad,'edss',None) is None


def test_selected_source_rule_metadata_has_exact_corrections():
    rules={r['rule_id']:r for r in list_drug_indication_rules()}
    enter=rules['4.2.8.A.paediatric_malnutrition_enteral_6mo_report']
    assert enter['gate_b_sources']==['prose:4.2.8.A#99f29955']
    assert enter['report_required'] is False and 'report_duration_months' not in enter
    stop=rules['4.2.14.C.ravulizumab_nmosb_edss8_stop']
    assert '@between:' in stop['gate_b_sources'][0]
    assert 'icd10_ranges' not in stop


@pytest.mark.parametrize('field,factory', [('enteral_evidence',enteral),('ravulizumab_evidence',ravu)])
def test_csv_json_and_dataclass_rows_preserve_new_evidence(field,factory):
    from dataclasses import asdict
    import json
    from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line
    line=factory()
    row=asdict(line)
    errors=[]
    direct=parse_drug_line(row,errors)
    assert not errors
    row[field]=json.dumps(row[field],default=lambda value:value.isoformat())
    encoded=parse_drug_line(row,errors)
    assert not errors
    assert getattr(direct,field)==getattr(encoded,field)==getattr(line,field)


def test_legacy_bridge_passes_new_evidence_without_changing_date(monkeypatch):
    from src.bilun.domain import rule_engine
    from src.bilun.domain.prose_rules import drug_indication as prose
    seen=[]
    monkeypatch.setattr(prose,'list_drug_indication_rules',lambda:[{'rule_id':'test'}])
    monkeypatch.setattr(prose,'evaluate_drug_indication_line',lambda **kw:seen.append(kw['drug_line']))
    rule_engine._run_drug_indication_checks([{'name':'ravulizumab','ravulizumab_evidence':{
        'applies_on':'2026-10-02','adult':False,'therapy_months':0,'edss':0,
    }}],{'drug_context':{'service_date':'2026-10-02'}})
    assert seen[0].drug_claim_date==DAY
    assert seen[0].ravulizumab_evidence.adult is False
    assert seen[0].ravulizumab_evidence.therapy_months==0


def test_canonical_public_evidence_preserves_restriction_without_raw_facts():
    from src.bilun.domain.billing.drug_indication_findings import evaluate_drug_indication_findings
    from src.bilun.domain.claims.patient_context import PatientClaimContext
    from src.bilun.api.schemas import DrugIndicationReviewResponse
    from src.bilun.api.public_responses import project_public_response
    line=ravu(edss=8)
    claim=_claim(primary_icd10='G36.0')
    ctx=PatientClaimContext(patient_id='P1',claims=(claim,),procedure_lines=(),material_lines=(),drug_lines=(line,),diagnoses=())
    batch=evaluate_drug_indication_findings('P1',ctx)
    payload={'findings':[row.to_dict() for row in batch.findings],'evaluations':[row.to_dict() for row in batch.evaluations]}
    model=DrugIndicationReviewResponse.model_validate(payload)
    assert model.evaluations[0].clinical_restrictions[0].criterion_status=='restriction_not_met'
    payload['evaluations'][0]['clinical_restrictions'][0]['raw_evidence']={'edss':8,'private_note':'must not publish'}
    public=project_public_response({'drug_indication':payload},'get_billing_report')
    outcome=public['drug_indication']['evaluations'][0]['clinical_restrictions'][0]
    assert outcome['criterion_status']=='restriction_not_met'
    assert any(row['field']=='ravulizumab_evidence.six_month_edss_stop' and row['status']=='fail' for row in outcome['checks'])
    assert 'raw_evidence' not in outcome
    assert outcome['clinical_eligibility_complete'] is False


def test_boolean_report_duration_is_unknown_at_api_boundary():
    request=ClaimValidationRequest.model_validate({'drug_context':{'report_duration_months':True}})
    assert request.drug_context.report_duration_months is None


@pytest.mark.parametrize('factory,evaluator',[(enteral,evaluate_enteral_reports),(ravu,evaluate_ravulizumab_continuation)])
def test_unbounded_integer_report_duration_is_unknown_not_runtime_failure(factory,evaluator):
    result=evaluator(replace(factory(),drug_report_duration_months=10**1000))
    assert 'drug_report_duration_months' in result['missing_inputs']


def test_adult_fact_cannot_turn_pediatric_rule_into_clearance():
    rules=[r for r in list_drug_indication_rules() if r['rule_id']=='4.2.8.A.paediatric_malnutrition_enteral_6mo_report']
    line=replace(enteral(pediatric=False),drug_specialty_board_report_present=True)
    result=evaluate_drug_indication_line_detailed(drug_line=line,claim=_claim(primary_icd10='E44.0'),diagnoses=[],rules=rules)
    assert result['violation']['severity']=='review'
    assert 'enteral_evidence.adult_path_requires_review' in result['missing_inputs']


@pytest.mark.parametrize('months,author', [(12, 'other'), (13, 'pediatrics'), (13, 'other')])
def test_unknown_pediatric_scope_cannot_fail_pediatric_only_rules_in_full_corpus(months, author):
    line = replace(enteral(pediatric=None, report_author_specialty=author),
                   drug_report_duration_months=months)
    direct = evaluate_enteral_reports(line)
    assert direct['criterion_status'] == 'not_evaluated'
    assert direct['checks'] == []
    assert direct['sut_section'] == '4.2.8.A'
    detailed = evaluate_drug_indication_line_detailed(
        drug_line=line, claim=_claim(primary_icd10='E44.0'), diagnoses=[])
    assert detailed['violation']['severity'] == 'review'
    assert detailed['clinical_restrictions'][0]['criterion_status'] == 'not_evaluated'
    assert 'enteral_evidence.pediatric' in detailed['missing_inputs']
    assert detailed['violation']['violation_kind'] != 'clinical_restriction_not_met'


@pytest.mark.parametrize('adult,status,severity', [(None, 'unknown', 'review'),
                                                 (False, 'restriction_not_met', 'error')])
def test_ravulizumab_adult_scope_precedes_adult_edss_stopping_predicate(adult, status, severity):
    line = ravu(adult=adult, therapy_months=6, edss=8, edss_in_report=False)
    direct = evaluate_ravulizumab_continuation(line, ['G36.0'])
    assert direct['criterion_status'] == status
    assert direct['stop_required'] is None
    assert direct['checks'] == [{'field': 'ravulizumab_evidence.adult',
                                'status': 'unknown' if adult is None else 'fail'}]
    detailed = evaluate_drug_indication_line_detailed(
        drug_line=line, claim=_claim(primary_icd10='G36.0'), diagnoses=[])
    assert detailed['violation']['severity'] == severity
    assert detailed['clinical_restrictions'][0]['stop_required'] is None
    if adult is None:
        assert 'ravulizumab_evidence.adult' in detailed['missing_inputs']

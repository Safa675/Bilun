"""Dated response alternatives and annual reassessment never establish payment."""
from dataclasses import replace
from datetime import date, timedelta
import pytest

from src.bilun.domain.claims.clinical_evidence import FollowupEvidence
from src.bilun.domain.prose_rules._drug_indication.clinical_followup import evaluate_followup
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _drug_line

DAY = date(2026,10,2)


def dupi(**changes):
    values={'applies_on':DAY,'assessment_date':DAY,'phase':'continuation','indication':'atopic_dermatitis',
            'treatment_start_date':DAY-timedelta(weeks=16),'baseline_assessment_date':DAY-timedelta(weeks=16),
            'response_assessment_date':DAY,'week16_checkpoint_documented':True,'baseline_easi':40,'response_easi':20,
            'baseline_dlqi':12,'response_dlqi':12,'baseline_pruritus_nrs':8,'response_pruritus_nrs':8,**changes}
    return replace(_drug_line(drug_name='dupilumab',report_present=True),drug_claim_date=DAY,
                   followup_evidence=FollowupEvidence(**values))


def nint(**changes):
    values={'applies_on':DAY,'assessment_date':DAY,'phase':'continuation','indication':'progressive_fibrosing_ild',
            'previous_report_date':date(2025,10,2),'current_report_date':DAY,
            'previous_fvc_percent_predicted':80,'current_fvc_percent_predicted':73,
            'fvc_assessment_outside_exacerbation':True,'report_documents_fvc_response':True,**changes}
    return replace(_drug_line(drug_name='nintedanib',report_present=True),drug_claim_date=DAY,
                   followup_evidence=FollowupEvidence(**values))


@pytest.mark.parametrize('changes', [{}, {'response_easi':40,'response_dlqi':8},
                                     {'response_easi':40,'response_pruritus_nrs':5}])
def test_each_dupilumab_alternative_independently_clears_threshold(changes):
    assert evaluate_followup(dupi(**changes))['criterion_status']=='criterion_clear'


def test_dupilumab_requires_none_of_three_responses_before_stop():
    assert evaluate_followup(dupi(response_easi=20.01))['criterion_status']=='restriction_not_met'
    assert evaluate_followup(dupi(response_easi=20.01,response_dlqi=None))['criterion_status']=='unknown'
    assert evaluate_followup(dupi(response_easi=None,response_dlqi=8))['criterion_status']=='criterion_clear'


def test_dupilumab_16_week_boundary_and_missing_baseline():
    assert evaluate_followup(dupi(treatment_start_date=DAY-timedelta(days=111)))['criterion_status']=='unknown'
    assert evaluate_followup(dupi())['criterion_status']=='criterion_clear'
    assert evaluate_followup(dupi(baseline_easi=0))['criterion_status']=='unknown'
    assert evaluate_followup(dupi(baseline_assessment_date=None))['criterion_status']=='unknown'
    assert evaluate_followup(dupi(response_assessment_date=DAY+timedelta(days=1)))['criterion_status']=='unknown'


@pytest.mark.parametrize('indication',['progressive_fibrosing_ild','systemic_sclerosis_ild'])
def test_nintedanib_exact_relative_fvc_boundary(indication):
    assert evaluate_followup(nint(indication=indication,current_fvc_percent_predicted=72.01))['criterion_status']=='criterion_clear'
    assert evaluate_followup(nint(indication=indication,current_fvc_percent_predicted=72))['criterion_status']=='restriction_not_met'
    assert evaluate_followup(nint(indication=indication,current_fvc_percent_predicted=71.99))['criterion_status']=='restriction_not_met'
    # Decimal comparison avoids floating rounding around exact10%.
    assert evaluate_followup(nint(indication=indication,previous_fvc_percent_predicted=82,
                                  current_fvc_percent_predicted=73.8))['criterion_status']=='restriction_not_met'


def test_nintedanib_reassessment_12_month_boundary_and_attack_exclusion():
    assert evaluate_followup(nint())['criterion_status']=='criterion_clear'
    assert evaluate_followup(nint(previous_report_date=date(2025,10,1)))['criterion_status']=='restriction_not_met'
    assert evaluate_followup(nint(fvc_assessment_outside_exacerbation=False,current_fvc_percent_predicted=20))['criterion_status']=='unknown'
    assert evaluate_followup(nint(fvc_assessment_outside_exacerbation=None))['criterion_status']=='unknown'
    assert evaluate_followup(nint(report_documents_fvc_response=False))['criterion_status']=='restriction_not_met'


def test_report_dates_missing_reversed_and_future_never_clear():
    for changes in ({'previous_report_date':None},{'current_report_date':None},
                    {'previous_report_date':DAY},{'current_report_date':DAY+timedelta(days=1)}):
        assert evaluate_followup(nint(**changes))['criterion_status']=='unknown'


def test_other_indications_and_treatment_phases_require_their_own_source():
    for line in [dupi(indication='other'),dupi(phase='initiation'),nint(indication='other'),nint(phase='restart')]:
        assert evaluate_followup(line)['criterion_status']=='unknown'
    both=replace(dupi(),drug_name='dupilumab + nintedanib')
    assert evaluate_followup(both)['criterion_status']=='unknown'
    assert evaluate_followup(both)['source_refs']==[]


def test_historical_missing_and_future_service_date_never_infer_source_applicability():
    for day in (None,date(2026,10,1),date(2026,10,3)):
        assert evaluate_followup(replace(dupi(),drug_claim_date=day))['criterion_status']=='not_evaluated'


def test_actual_public_evaluator_keeps_cleared_checkpoint_review_only():
    result=evaluate_drug_indication_line_detailed(drug_line=dupi(),claim=replace(_claim(),primary_icd10='L20.9'),diagnoses=[])
    assert result['clinical_restrictions'][0]['criterion_status']=='criterion_clear'
    assert result['violation']['severity']=='review'
    assert result['clinical_eligibility_complete'] is False
    assert result['violation']['sut_section']=='4.2.57'


def test_source_medication_selectors_do_not_transfer_to_prerequisite_agents():
    from src.bilun.domain.prose_rules.drug_indication import list_drug_indication_rules
    from src.bilun.domain.prose_rules._drug_indication.routing import _drug_rule_candidates
    rules=list_drug_indication_rules()
    rule=next(r for r in rules if r['rule_id']=='4.2.57.atopic_dermatitis_16wk_response_continue')
    for other in ('abrositinib','barisitinib','upadasitinib'):
        assert not _drug_rule_candidates(other,[rule])[0]
    section=[r for r in rules if r['sut_section']=='4.2.46.B']
    assert not _drug_rule_candidates('pirfenidon',section)[0]


def test_followup_request_and_row_roundtrip_keeps_explicit_false_and_dates():
    from dataclasses import asdict
    from src.bilun.shared.models import ClaimValidationRequest
    from src.bilun.domain.claims.adapter import build_context_from_material_dict
    from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line
    raw={'claim_id':'followup','materials':[{'name':'nintedanib','followup_evidence':{
        'applies_on':DAY.isoformat(),'assessment_date':DAY.isoformat(),
        'phase':'continuation','indication':'systemic_sclerosis_ild',
        'fvc_assessment_outside_exacerbation':False}}],
        'drug_context':{'primary_icd10':'M34.9','service_date':DAY.isoformat()}}
    req=ClaimValidationRequest.model_validate(raw)
    ctx=build_context_from_material_dict(req.model_dump())
    actual=ctx.drug_lines[0]
    assert actual.followup_evidence.fvc_assessment_outside_exacerbation is False
    assert actual.followup_evidence.assessment_date==DAY
    errors=[]
    row=parse_drug_line(asdict(actual),errors)
    assert not errors
    assert row.followup_evidence==actual.followup_evidence


def test_followup_exact_clause_refs_match_official_snapshot():
    import json
    from pathlib import Path
    from scripts.sut.prose.clause_identity import content_hash
    root=Path(__file__).resolve().parents[4]
    rows=json.loads((root/'data/gazette/clinical_sources/followup_2026_10.json').read_text())['clauses']
    keys={row['clause_key'] for row in rows}
    assert all(content_hash(row['in_force_text'])==row['content_hash'] for row in rows)
    for line in (dupi(),nint(),nint(indication='systemic_sclerosis_ild')):
        assert set(evaluate_followup(line)['source_refs'])<=keys


def test_fvc_reassessment_anniversary_uses_calendar_months_in_leap_year():
    from src.bilun.domain.prose_rules._drug_indication.clinical_followup import _nintedanib
    from src.bilun.domain.prose_rules._drug_indication.clinical_common import Reader
    # Pure interval predicate tested independently from the source interval gate.
    facts=replace(nint().followup_evidence,previous_report_date=date(2024,2,29),current_report_date=date(2025,2,28))
    assert _nintedanib(Reader(facts,'followup_evidence'),date(2025,2,28)).value is True
    facts=replace(facts,current_report_date=date(2025,3,1))
    assert _nintedanib(Reader(facts,'followup_evidence'),date(2025,3,1)).value is False


@pytest.mark.parametrize('documented',[None,False])
def test_elapsed_time_alone_cannot_certify_actual_16_week_treatment_checkpoint(documented):
    assert evaluate_followup(dupi(week16_checkpoint_documented=documented))['criterion_status']=='unknown'


@pytest.mark.parametrize('field', ['baseline_easi','response_easi','baseline_dlqi','response_dlqi',
                                    'baseline_pruritus_nrs','response_pruritus_nrs'])
def test_invalid_instrument_scores_become_unknown_through_api_row_and_evaluator(field):
    from dataclasses import asdict
    from src.bilun.shared.models import ClaimValidationRequest
    from src.bilun.domain.claims.adapter import build_context_from_material_dict
    from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line
    facts=asdict(dupi(response_easi=40).followup_evidence)
    facts[field]=999
    for key,value in list(facts.items()):
        if isinstance(value,date):facts[key]=value.isoformat()
    request={'claim_id':'score','materials':[{'name':'dupilumab','followup_evidence':facts}],
             'drug_context':{'primary_icd10':'L20','service_date':DAY.isoformat(),'board_report_present':True}}
    parsed=ClaimValidationRequest.model_validate(request)
    assert getattr(parsed.materials[0].followup_evidence,field) is None
    ctx=build_context_from_material_dict(parsed.model_dump())
    assert evaluate_followup(ctx.drug_lines[0])['criterion_status']=='unknown'
    errors=[]
    typed=parse_drug_line(asdict(ctx.drug_lines[0]),errors)
    assert not errors
    assert getattr(typed.followup_evidence,field) is None
    public=evaluate_drug_indication_line_detailed(drug_line=typed,claim=ctx.claims[0],diagnoses=[])
    assert public['violation']['severity']=='review'
    assert 'followup_evidence.'+field in public['missing_inputs']


def test_bad_alternative_cannot_hide_an_independently_valid_response():
    assert evaluate_followup(dupi(baseline_dlqi=999))['criterion_status']=='criterion_clear'
    assert evaluate_followup(dupi(baseline_easi=999,response_dlqi=8))['criterion_status']=='criterion_clear'


@pytest.mark.parametrize('day',[None,date(2026,10,1),date(2026,10,3)])
@pytest.mark.parametrize('factory,section,icd',[(dupi,'4.2.57','L20'),(nint,'4.2.46.B','J84.1')])
def test_early_temporal_review_has_correct_source_section(day,factory,section,icd):
    line=replace(factory(),drug_claim_date=day)
    outcome=evaluate_followup(line)
    assert outcome['sut_section']==section
    public=evaluate_drug_indication_line_detailed(drug_line=line,claim=replace(_claim(),primary_icd10=icd),diagnoses=[])
    assert public['violation']['sut_section']==section


def test_unknown_nintedanib_indication_does_not_fabricate_systemic_sclerosis_scope():
    outcome=evaluate_followup(nint(indication=None))
    assert outcome['sut_section']=='4.2.46'
    assert any(ref.startswith('4.2.46.B') for ref in outcome['source_refs'])
    assert any(ref.startswith('4.2.46.C') for ref in outcome['source_refs'])

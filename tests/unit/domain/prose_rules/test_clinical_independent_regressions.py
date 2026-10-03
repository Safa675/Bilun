from dataclasses import replace
from datetime import date
from src.bilun.domain.claims.clinical_evidence import AntifungalEvidence,SmaEvidence
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
from src.bilun.domain.prose_rules._drug_indication.clinical_antifungal import evaluate_antifungal
from src.bilun.domain.billing.drug_indication_findings import evaluate_drug_indication_findings
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.api.public_responses import project_public_response
from tests.unit.domain.prose_rules.test_drug_indication import _claim,_drug_line
DAY=date(2026,10,2)


def test_sma_safety_does_not_apply_to_onasemnogene():
    line=replace(_drug_line(drug_name='onasemnogene abeparvovek'),drug_claim_date=DAY,
        sma_evidence=SmaEvidence(applies_on=DAY,assessment_date=DAY,
            hypoxic_ischemic_encephalopathy=True,hypoxic_birth_neurological_sequelae=True))
    outcome=evaluate_drug_indication_line_detailed(drug_line=line,claim=_claim(primary_icd10='G12.0'),diagnoses=[])
    assert not any(x['constraint_set']=='sma_safety_2025' for x in outcome.get('clinical_restrictions',[]))


def test_multiple_antifungals_never_evaluate_one_and_cite_another():
    line=replace(_drug_line(drug_name='anidulafungin + mikafungin'),drug_claim_date=DAY,
        antifungal_evidence=AntifungalEvidence(applies_on=DAY,assessment_date=DAY,intent='treatment',
            indication='invasive_candidiasis',adult=True,anc_per_mm3=500,anc_lab_result_present=True))
    outcome=evaluate_antifungal(line)
    assert outcome['criterion_status'] in ('unknown','not_evaluated')


def test_actual_billing_public_projection_retains_clinical_check_evidence():
    line=replace(_drug_line(drug_name='anidulafungin'),drug_claim_date=DAY,
        antifungal_evidence=AntifungalEvidence(applies_on=DAY,assessment_date=DAY,intent='treatment',
            indication='invasive_candidiasis',adult=False,anc_per_mm3=499,anc_lab_result_present=True))
    claim=_claim(primary_icd10='B37.9')
    ctx=PatientClaimContext(patient_id='P1',claims=(claim,),procedure_lines=(),material_lines=(),drug_lines=(line,),diagnoses=())
    batch=evaluate_drug_indication_findings('P1',ctx)
    payload={'evaluations':[x.to_dict() for x in batch.evaluations], 'findings':[x.to_dict() for x in batch.findings], 'violations':list(batch.legacy_violations)}
    public=project_public_response({'drug_indication':payload},'get_billing_report')
    for key in ['evaluations','findings','violations']:
        evidence=public['drug_indication'][key][0]['clinical_restrictions'][0]
        assert evidence['criterion_status']=='restriction_not_met'
        assert evidence['source_refs']==['4.2.23.(5)#1234522e']
        assert evidence['clinical_eligibility_complete'] is False


def test_failed_sma_constraint_keeps_actual_identity_in_canonical_public_and_cache():
    import json
    import duckdb
    from src.bilun.domain.billing.billing_actions import collect_billing_actions
    from src.bilun.domain.billing.cohort_compliance import build_cohort_compliance_index
    from src.bilun.domain.billing.types import BillingActionReport, DrugIndicationReview
    from src.bilun.cache.build_streaming import json_ready
    line=replace(_drug_line(drug_name='nusinersen',report_present=True),drug_claim_date=DAY,
        sma_evidence=SmaEvidence(applies_on=DAY,assessment_date=DAY,sma_type='type_2',
            hypoxic_ischemic_encephalopathy=False,hypoxic_birth_neurological_sequelae=False,
            brain_spinal_history_impeding_procedure=False,csf_shunt_or_catheter=True,
            bacterial_meningitis_history=False,viral_encephalitis_history=False,
            lumbar_puncture_suitability_documented=True))
    claim=_claim(primary_icd10='G12.1')
    ctx=PatientClaimContext(patient_id='P1',claims=(claim,),procedure_lines=(),material_lines=(),drug_lines=(line,),diagnoses=())
    batch=evaluate_drug_indication_findings('P1',ctx)
    assert batch.findings[0].selected_rule_id == 'sma_safety_2025'
    assert batch.evaluations[0].selected_rule_id == 'sma_safety_2025'
    review=DrugIndicationReview(findings=list(batch.findings),evaluations=list(batch.evaluations),violations=list(batch.legacy_violations))
    report=BillingActionReport(patient_id='P1',drug_indication=review)
    actions=collect_billing_actions(report)
    report.recommended_actions=actions
    drug_action=next(a for a in actions if a['surface']=='drug_indication')
    assert drug_action['selected_rule_id']=='sma_safety_2025'
    assert drug_action['clinical_eligibility_complete'] is False
    assert drug_action['sgk_uplift_try'] is None
    assert drug_action['audit_risk_try'] is None
    cohort=build_cohort_compliance_index({'P1':report})
    row=next(r for r in cohort['rows'] if r['source_surface']=='drug_indication')
    assert row['clinical_restrictions']==drug_action['clinical_restrictions']
    assert row['billed_try'] is None
    public_cohort=project_public_response(cohort,'/api/compliance-index')
    assert public_cohort['rows'][0]['clinical_eligibility_complete'] is False
    payload={'drug_indication':review.to_dict(),'recommended_actions':actions}
    with duckdb.connect(':memory:') as db:
        db.execute('CREATE TABLE reports (payload JSON)')
        db.execute('INSERT INTO reports VALUES (?)',[json.dumps(json_ready(payload))])
        cached=json.loads(db.execute('SELECT payload FROM reports').fetchone()[0])
    direct=project_public_response(payload,'get_billing_report')
    assert direct==project_public_response(cached,'get_billing_report')
    for category in ('findings','evaluations','violations'):
        row=direct['drug_indication'][category][0]
        assert row['selected_rule_id']=='sma_safety_2025'
        assert row['clinical_eligibility_complete'] is False
        failed=row['clinical_restrictions'][0]
        assert {'field':'sma_evidence.csf_shunt_or_catheter','status':'fail'} in failed['checks']
        assert '4.2.49.(3)#88014037' in failed['source_refs']


def test_canonical_clinical_evidence_is_bounded_and_drops_unapproved_details():
    from src.bilun.domain.billing.drug_clinical_evidence import bounded_clinical_restrictions
    raw={'constraint_set':'sma_safety_2025','criterion_status':'criterion_clear',
         'checks':[{'field':'sma_evidence.csf_shunt_or_catheter','status':'fail','private':'secret'}]*100,
         'source_refs':['4.2.49.(3)#88014037']*100,'clinical_eligibility_complete':True,'private':'secret'}
    result=bounded_clinical_restrictions([raw])[0].to_dict()
    assert len(result['checks'])==64
    assert result['checks_truncated'] is True
    assert result['source_refs_truncated'] is True
    assert result['clinical_eligibility_complete'] is False
    assert 'private' not in str(result)
    malformed=bounded_clinical_restrictions([{'constraint_set':'sma','criterion_status':{},'checks':[{'field':'x','status':{}}],'source_refs':42}])[0]
    assert malformed.criterion_status=='unknown'


def test_v2_validator_retains_bounded_clinical_advisory_and_not_payment_conclusion():
    from src.bilun.domain.claim_validation_v2 import typed_validation_payload, validate_claim_v2
    raw={'claim_id':'C1','materials':[{'name':'anidulafungin','antifungal_evidence':{
        'applies_on':DAY.isoformat(),'assessment_date':DAY.isoformat(),'intent':'treatment',
        'indication':'invasive_candidiasis','adult':False,'anc_per_mm3':499,'anc_lab_result_present':True}}],
        'drug_context':{'service_date':DAY.isoformat(),'primary_icd10':'B37.9','board_report_present':True}}
    result=typed_validation_payload(validate_claim_v2(raw,supplied_claim=raw))
    row=next(x for x in result['advisories'] if x['rule']=='drug_indication')
    assert row['clinical_eligibility_complete'] is False
    assert row['selected_rule_id']=='antifungal_source_constraints'
    assert row['clinical_restrictions'][0]['criterion_status']=='restriction_not_met'
    assert row['source_status']=='historical_match_unverified'
    assert row['disposition']=='review_only'
    assert result['is_valid'] is None
    assert not any('amount' in k or 'payable' in k for k in row)

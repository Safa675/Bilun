"""Followup HTTP observations retain dated evidence without payment clearance."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.bilun.api.routes.validation import router
from src.bilun.shared.models import ClaimValidationRequest
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.prose_rules._drug_indication.clinical_followup import evaluate_followup


@pytest.mark.parametrize('name,indication,checkpoint,outside,current,day,status,reason', [
    ('dupilumab', 'atopic_dermatitis', False, False, 99, '2026-10-02', 'unknown', 'followup_evidence.week16_checkpoint_documented'),
    ('dupilumab', 'atopic_dermatitis', True, False, 99, '2026-10-02', 'criterion_clear', None),
    ('dupilumab', 'atopic_dermatitis', True, False, 99, None, 'not_evaluated', 'drug_claim_date'),
    ('dupilumab', 'atopic_dermatitis', True, False, 99, '2026-10-03', 'not_evaluated', 'verified_source_for_service_date'),
    ('nintedanib', 'progressive_fibrosing_ild', False, True, 100, '2026-10-02', 'criterion_clear', None),
    ('nintedanib', 'progressive_fibrosing_ild', False, True, 99, '2026-10-02', 'restriction_not_met', None),
    ('nintedanib', 'systemic_sclerosis_ild', False, False, 50, '2026-10-02', 'unknown', 'followup_evidence.fvc_assessment_outside_exacerbation'),
])
def test_followup_http_preserves_domains_dates_false_and_partial_scope(name, indication, checkpoint, outside, current, day, status, reason):
    facts = {'applies_on': '2026-10-02', 'assessment_date': '2026-10-02', 'phase': 'continuation',
        'indication': indication, 'treatment_start_date': '2026-06-12', 'baseline_assessment_date': '2026-06-12',
        'response_assessment_date': '2026-10-02', 'week16_checkpoint_documented': checkpoint,
        'baseline_easi': 72, 'response_easi': 0, 'baseline_dlqi': 30, 'response_dlqi': 0,
        'baseline_pruritus_nrs': 10, 'response_pruritus_nrs': 0, 'previous_report_date': '2025-10-02',
        'current_report_date': '2026-10-02', 'previous_fvc_percent_predicted': 110,
        'current_fvc_percent_predicted': current, 'fvc_assessment_outside_exacerbation': outside,
        'report_documents_fvc_response': True}
    raw = {'claim_id': 'SYNTHETIC-FOLLOWUP', 'materials': [{'name': name, 'followup_evidence': facts,
        'pws_severe_obesity_source_criterion_present': False, 'mecasermin_daily_dose_mcg_per_kg': 0,
        'ravulizumab_evidence': {'edss': 11, 'adult': False}}],
        'drug_context': {'primary_icd10': 'L20.9' if name == 'dupilumab' else 'J84.8' if indication == 'progressive_fibrosing_ild' else 'M34.9',
            'service_date': day, 'board_report_present': True, 'report_duration_months': 12,
            'prescriber_specialty': 'dermatoloji' if name == 'dupilumab' else 'göğüs hastalıkları'}}
    req = ClaimValidationRequest.model_validate(raw)
    for mode in ('python', 'json'):
        line = build_context_from_material_dict(req.model_dump(mode=mode)).drug_lines[0]
        assert line.followup_evidence.response_easi == 0
        assert line.followup_evidence.previous_fvc_percent_predicted == 110
        assert line.followup_evidence.week16_checkpoint_documented is checkpoint
        assert line.followup_evidence.fvc_assessment_outside_exacerbation is outside
        assert line.ravulizumab_evidence.edss is None and line.ravulizumab_evidence.adult is False
        assert line.pws_severe_obesity_source_criterion_present is False
        assert line.mecasermin_daily_dose_mcg_per_kg == 0
        outcome = evaluate_followup(line)
        assert outcome['criterion_status'] == status
        if reason:
            assert reason in outcome['missing_inputs']
    app = FastAPI()
    app.include_router(router, prefix='/api')
    with TestClient(app) as client:
        response = client.post('/api/validate-claim', json=raw, headers={'X-Bilun-Validation-Contract': '2'})
    assert response.status_code == 200
    public = response.json()
    row = next(a for a in public['advisories'] if a['rule'] == 'drug_indication')
    observation = next(o for o in row['clinical_restrictions'] if o['constraint_set'] == 'followup_source_constraints')
    assert observation['criterion_status'] == status
    assert observation['clinical_eligibility_complete'] is False
    assert row['disposition'] == 'review_only' and public['is_valid'] is None
    if reason:
        assert reason in row['missing_inputs']
    assert not any(key in row for key in ('payable_try', 'risk_amount', 'savings_try'))

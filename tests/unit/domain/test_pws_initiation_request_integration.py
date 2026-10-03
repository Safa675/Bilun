"""Public PWS initiation transport preserves source-defined facts and partial scope."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.bilun.api.routes.validation import router
from src.bilun.shared.models import ClaimValidationRequest
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed


@pytest.mark.parametrize('phase,obesity,scoliosis,day,missing,kind', [
    ('initiation', False, False, '2026-10-02', 'pws_initiation_clinical_assessment', None),
    ('initiation', True, False, '2026-10-02', None, 'growth_hormone_initiation_exclusion'),
    ('initiation', False, True, '2026-10-02', 'pws_initiation_clinical_assessment', None),
    ('continuation', True, False, '2026-10-02', 'pws_remaining_clinical_criteria', None),
    ('initiation', None, False, '2026-10-02', 'pws_severe_obesity_source_criterion_present', None),
    ('initiation', True, False, '2024-05-16', 'historical_sut_version', None),
    ('initiation', True, False, None, 'drug_claim_date', None),
    (None, True, False, '2026-10-02', 'gh_treatment_phase', None),
])
def test_pws_http_preserves_explicit_assessment_dates_and_phase_scope(phase, obesity, scoliosis, day, missing, kind):
    raw = {'claim_id': 'SYNTHETIC-PWS-INITIATION', 'materials': [{
        'name': 'SOMATROPIN', 'gh_patient_group': 'pediatric', 'gh_treatment_phase': phase,
        'pws_genetic_diagnosis_confirmed': True, 'epiphyses_closed': False,
        'pws_uncontrolled_diabetes': False, 'pws_untreatable_obstructive_sleep_apnea': False,
        'pws_active_cancer': False, 'pws_active_psychosis': False,
        'pws_progressive_scoliosis': scoliosis,
        'pws_severe_obesity_source_criterion_present': obesity}],
        'drug_context': {'primary_icd10': 'Q87.1', 'service_date': day,
            'board_report_present': True, 'report_duration_months': 6 if phase == 'continuation' else 3,
            'prescriber_specialty': 'çocuk endokrinoloji'}}
    context = build_context_from_material_dict(ClaimValidationRequest.model_validate(raw).model_dump(mode='json'))
    line = context.drug_lines[0]
    assert line.pws_severe_obesity_source_criterion_present is obesity
    assert line.pws_progressive_scoliosis is scoliosis and line.pws_active_cancer is False
    result = evaluate_drug_indication_line_detailed(drug_line=line, claim=context.claims[0], diagnoses=[])
    if kind:
        assert result['violation']['violation_kind'] == kind
    if missing:
        assert missing in result['missing_inputs'] and result['violation']['severity'] == 'review'
    app = FastAPI()
    app.include_router(router, prefix='/api')
    with TestClient(app) as client:
        response = client.post('/api/validate-claim', json=raw, headers={'X-Bilun-Validation-Contract': '2'})
    assert response.status_code == 200
    public = response.json()
    row = next(a for a in public['advisories'] if a['rule'] == 'drug_indication')
    if missing:
        assert missing in row['missing_inputs']
    assert row['disposition'] == 'review_only'
    assert public['is_valid'] is None and not public['violations']
    assert not any(key in row for key in ('payable_try', 'risk_amount', 'savings_try'))

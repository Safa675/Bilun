"""Independent actual HTTP boundary for mecasermin's point-in-time authority."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.bilun.api.routes.validation import router
from src.bilun.shared.models import ClaimValidationRequest
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed


@pytest.mark.parametrize('day,phase,dose,closed,missing,kind', [
    ('2026-08-29', 'initiation', 120, False, 'mecasermin_remaining_clinical_criteria', None),
    ('2026-10-02', 'initiation', 120.001, False, None, 'mecasermin_initial_dose_exceeded'),
    ('2026-10-02', 'continuation', 120, True, None, 'growth_hormone_continuation_stop'),
    ('2026-09-15', 'continuation', 120, True, 'mecasermin_source_version', None),
    ('2026-10-03', 'continuation', 120, True, None, 'growth_hormone_continuation_stop'),
    ('2026-10-04', 'continuation', 120, True, 'mecasermin_source_version', None),
    (None, 'continuation', 120, True, 'drug_claim_date', None),
])
def test_actual_http_preserves_source_points_units_and_partial_review(day, phase, dose, closed, missing, kind):
    raw = {'claim_id': 'SYNTHETIC-MECASERMIN-INTEGRATION', 'materials': [{
        'name': 'INCRELEX (MECASERMIN)', 'mecasermin_laron_syndrome_confirmed': True,
        'gh_treatment_phase': phase, 'epiphyses_closed': closed,
        'annual_growth_velocity_cm': 2, 'pretreatment_annual_growth_velocity_cm': 0,
        'height_cm': 150, 'gh_height_reference_sex': 'female', 'height_percentile': 0,
        'mecasermin_daily_dose_mcg_per_kg': dose, 'gh_daily_dose_mg_per_kg': 0.045}],
        'drug_context': {'primary_icd10': 'E34.31', 'service_date': day,
            'board_report_present': True, 'report_duration_months': 12,
            'prescriber_specialty': 'çocuk endokrinoloji'}}
    context = build_context_from_material_dict(ClaimValidationRequest.model_validate(raw).model_dump(mode='json'))
    line = context.drug_lines[0]
    assert line.mecasermin_daily_dose_mcg_per_kg == dose and line.gh_daily_dose_mg_per_kg == 0.045
    result = evaluate_drug_indication_line_detailed(drug_line=line, claim=context.claims[0], diagnoses=[])
    if kind:
        assert result['violation']['violation_kind'] == kind
    if missing:
        assert missing in result['missing_inputs'] and result['violation']['severity'] == 'review'
    app = FastAPI()
    app.include_router(router, prefix='/api')
    with TestClient(app) as client:
        response = client.post('/api/validate-claim', json=raw,
            headers={'X-Bilun-Validation-Contract': '2'})
    assert response.status_code == 200
    public = response.json()
    row = next(a for a in public['advisories'] if a['rule'] == 'drug_indication')
    if missing:
        assert missing in row['missing_inputs']
    assert row['disposition'] == 'review_only'
    assert public['is_valid'] is None and not public['violations']
    assert not any(key in row for key in ('payable_try', 'risk_amount', 'savings_try'))

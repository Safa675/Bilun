"""Independent combined CKD GH request/date/public-boundary regression."""
from copy import deepcopy

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.bilun.api.routes.validation import router
from src.bilun.shared.models import ClaimValidationRequest
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed


def payload():
    return {
        'claim_id': 'SYNTHETIC-CKD-INTEGRATION',
        'materials': [{'name': 'GENOTROPIN (SOMATROPIN)', 'gh_patient_group': 'pediatric',
            'gh_treatment_phase': 'initiation', 'ckd_growth_disorder_confirmed': True,
            'ckd_persistent_severe_secondary_hyperparathyroidism': False,
            'ckd_proliferative_or_severe_nonproliferative_retinopathy': False,
            'ckd_first_post_transplant_year': False, 'ckd_active_cancer': False,
            'epiphyses_closed': False, 'ckd_parathyroid_hormone_pg_ml': 499.9,
            'gh_daily_dose_mg_per_kg': 0.045}],
        'drug_context': {'primary_icd10': 'N18.5', 'service_date': '2026-10-02',
            'board_report_present': True, 'report_duration_months': 6,
            'prescriber_specialty': 'çocuk endokrinoloji'},
    }


@pytest.mark.parametrize('changes,day,kind,missing', [
    ({}, '2026-10-02', 'needs_growth_hormone_verification', ['ckd_growth_initiation_clinical_assessment']),
    ({'gh_daily_dose_mg_per_kg': 0}, '2026-10-02', 'growth_hormone_dose_out_of_range', []),
    ({'ckd_parathyroid_hormone_pg_ml': 500}, '2026-10-02', 'growth_hormone_initiation_exclusion', []),
    ({'ckd_growth_disorder_confirmed': None}, '2026-10-02', 'needs_growth_hormone_verification', ['ckd_growth_disorder_confirmed']),
    ({'ckd_active_cancer': True}, None, 'needs_growth_hormone_verification', ['drug_claim_date']),
    ({'ckd_active_cancer': True}, '2024-05-16', 'needs_growth_hormone_verification', ['historical_sut_version']),
])
def test_actual_http_keeps_ckd_date_scope_and_partial_review(changes, day, kind, missing):
    raw = payload()
    raw['materials'][0].update(changes)
    raw['drug_context']['service_date'] = day
    context = build_context_from_material_dict(ClaimValidationRequest.model_validate(raw).model_dump(mode='json'))
    outcome = evaluate_drug_indication_line_detailed(drug_line=context.drug_lines[0],
        claim=context.claims[0], diagnoses=list(context.diagnoses))
    assert outcome['violation']['violation_kind'] == kind
    assert outcome['missing_inputs'] == missing
    app = FastAPI()
    app.include_router(router, prefix='/api')
    with TestClient(app) as client:
        response = client.post('/api/validate-claim', json=deepcopy(raw),
            headers={'X-Bilun-Validation-Contract': '2'})
    assert response.status_code == 200
    public = response.json()
    advisory = next(row for row in public['advisories'] if row['rule'] == 'drug_indication')
    assert advisory['missing_inputs'] == missing
    assert advisory['disposition'] == 'review_only'
    assert public['is_valid'] is None and not public['violations']
    assert not any(key in advisory for key in ('payable_try', 'risk_amount', 'savings_try'))

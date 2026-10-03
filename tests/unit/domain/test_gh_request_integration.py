"""Independent GH-only request/adapter/date/evaluator regression coverage."""
from copy import deepcopy
from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.bilun.api.routes import validation
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
from src.bilun.shared.models import ClaimValidationRequest


def payload(name='GENOTROPIN (SOMATROPIN)', code='Q96.9', **evidence):
    return {'claim_id': 'SYNTHETIC-INTEGRATION', 'materials': [{'name': name, **evidence}],
            'drug_context': {'primary_icd10': code, 'service_date': '2026-10-02',
                             'prescriber_specialty': 'çocuk endokrinoloji',
                             'board_report_present': True, 'report_duration_months': 12}}


def evaluate(raw):
    request = ClaimValidationRequest.model_validate(raw)
    ctx = build_context_from_material_dict(request.model_dump(mode='json'))
    line = ctx.drug_lines[0]
    return line, evaluate_drug_indication_line_detailed(
        drug_line=line, claim=ctx.claims[0], diagnoses=list(ctx.diagnoses))


@pytest.mark.parametrize('field,value', [('epiphyses_closed', True),
    ('annual_growth_velocity_cm', 0), ('height_cm', 155), ('bone_age_years', 14)])
def test_json_request_to_real_turner_evaluator_retains_each_decisive_stop(field, value):
    line, result = evaluate(payload(gh_treatment_phase='continuation', **{field: value}))
    assert line.drug_claim_date == date(2026, 10, 2)
    assert getattr(line, field) == value
    assert result['violation']['growth_hormone_stop_criteria'] == [field]
    assert result['violation']['severity'] == 'error'


@pytest.mark.parametrize('sex,height,stop', [('female', 156.99, False), ('female', 157, True),
                                         ('male', 167.99, False), ('male', 168, True)])
def test_pediatric_request_has_own_height_boundary_not_turner_boundary(sex, height, stop):
    _, result = evaluate(payload(code='E23.0', gh_treatment_phase='continuation',
        gh_patient_group='pediatric', gh_height_reference_sex=sex, height_cm=height,
        epiphyses_closed=False, annual_growth_velocity_cm=4.01, bone_age_years=20))
    assert bool(result['violation']) is stop
    if stop:
        assert result['violation']['growth_hormone_stop_criteria'] == ['height_cm']


@pytest.mark.parametrize('when,missing', [(None, 'drug_claim_date'),
                                        ('2024-05-16', 'historical_sut_version')])
def test_known_stop_does_not_override_missing_or_historical_service_date(when, missing):
    raw = payload(gh_treatment_phase='continuation', epiphyses_closed=True)
    raw['drug_context']['service_date'] = when
    _, result = evaluate(raw)
    assert result['violation']['severity'] == 'review'
    assert result['missing_inputs'] == [missing]


@pytest.mark.parametrize('when,status', [('2026-10-09', 'historical_legacy_unverified'),
    ('2026-10-10', 'verified_source_partial_evaluation'), (None, 'missing_service_date')])
def test_form_request_selects_temporal_rules_from_service_date_only(when, status):
    raw = payload(name='pertuzumab', code='C50.9', biomarkers=[{'marker': 'HER2', 'status': 'negative'}])
    raw['drug_context']['service_date'] = when
    _, result = evaluate(raw)
    assert result['temporal_evidence']['status'] == status
    assert result['evaluation_status'] == 'missing_inputs'
    assert result['temporal_evidence']['clinical_eligibility_complete'] is False




@pytest.mark.parametrize('bad', ['', '2026-02-30', '2026-10-02T00:00:00Z', True, 1790899200])
def test_real_http_endpoint_rejects_invalid_date_before_evaluation(bad):
    raw = payload();raw['drug_context']['service_date'] = bad
    app = FastAPI();app.include_router(validation.router, prefix='/api')
    with TestClient(app) as client:
        response = client.post('/api/validate-claim', json=raw,
                               headers={'X-Bilun-Validation-Contract': '2'})
    assert response.status_code == 422
    assert response.json()['detail'][0]['loc'] == ['body', 'drug_context', 'service_date']


def test_actual_http_validation_of_known_stop_stays_review_only_and_unpriced():
    raw = payload(gh_treatment_phase='continuation', epiphyses_closed=True)
    app = FastAPI();app.include_router(validation.router, prefix='/api')
    with TestClient(app) as client:
        response = client.post('/api/validate-claim', json=deepcopy(raw),
                               headers={'X-Bilun-Validation-Contract': '2'})
    assert response.status_code == 200
    result = response.json()
    rows = [row for row in result['advisories'] if row['rule'] == 'drug_indication']
    assert len(rows) == 1 and rows[0]['disposition'] == 'review_only'
    assert result['is_valid'] is None
    assert not result['violations']
    assert not any(key in rows[0] for key in ('risk_amount', 'savings_try', 'payable_try'))


PWS_NEGATIVE = dict(pws_genetic_diagnosis_confirmed=True,
    pws_uncontrolled_diabetes=False, pws_untreatable_obstructive_sleep_apnea=False,
    pws_active_cancer=False, pws_active_psychosis=False, pws_progressive_scoliosis=False,
    epiphyses_closed=False)


@pytest.mark.parametrize('stop', [*list(PWS_NEGATIVE)[1:]])
def test_pws_real_request_preserves_each_explicit_stop_and_public_review(stop):
    raw = payload(code='Q87.1', gh_patient_group='pediatric', gh_treatment_phase='continuation',
                  **{**PWS_NEGATIVE, stop: True})
    raw['drug_context']['report_duration_months'] = 6
    line, result = evaluate(raw)
    assert getattr(line, stop) is True
    assert result['violation']['growth_hormone_stop_criteria'] == [stop]
    public = validation.validate_claim_endpoint(ClaimValidationRequest.model_validate(raw), '2')
    assert public['is_valid'] is None and not public['violations']


def test_pws_known_negative_screen_remains_partial_and_missing_inputs_survive_public_projection():
    raw = payload(code='Q87.1', gh_patient_group='pediatric', gh_treatment_phase='continuation',
                  **PWS_NEGATIVE)
    raw['drug_context']['report_duration_months'] = 6
    _, result = evaluate(raw)
    assert result['violation']['severity'] == 'review'
    assert result['missing_inputs'] == ['pws_remaining_clinical_criteria']
    public = validation.validate_claim_endpoint(ClaimValidationRequest.model_validate(raw), '2')
    drug = next(row for row in public['advisories'] if row['rule'] == 'drug_indication')
    assert drug['missing_inputs'] == ['pws_remaining_clinical_criteria']


def test_pws_untreated_alias_never_substitutes_for_source_untreatable_apnea_fact():
    evidence = dict(PWS_NEGATIVE)
    evidence.pop('pws_untreatable_obstructive_sleep_apnea')
    evidence['pws_untreated_obstructive_sleep_apnea'] = False
    raw = payload(code='Q87.1', gh_patient_group='pediatric', gh_treatment_phase='continuation',
                  **evidence)
    raw['drug_context']['report_duration_months'] = 6
    line, result = evaluate(raw)
    assert line.pws_untreatable_obstructive_sleep_apnea is None
    assert 'pws_untreatable_obstructive_sleep_apnea' in result['missing_inputs']
    assert result['violation']['severity'] == 'review'

"""Real HTTP boundary carries a blocked documentary draft as partial review."""
import json

import pytest

from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.prose_rules._drug_indication.clinical_mesothelioma_documents import (
    evaluate_mesothelioma_documentary_candidate,
)
from tests.unit.api.test_validation_contract_v2 import client, _login  # noqa: F401

KIND = 'pleural_mesothelioma_documents'
pytestmark = pytest.mark.unit


def payload(drug='pemetrexed', day='2026-10-02', **facts):
    return {
        'claim_id': 'mesothelioma-http',
        'materials': [{'name': drug, 'billed_amount': 987654.32, 'mesothelioma_evidence': {
            'applies_on': day, 'assessment_date': day, 'diagnosis_site': 'pleural',
            'board_report_present': True, 'report_distinct_specialist_count': 3,
            'treatment_protocol_documented_in_report': True,
            'prescribed_by_specialist': True, 'private_note': 'NEVER_PUBLISH',
            **facts,
        }}],
        'drug_context': {'primary_icd10': 'C45.0', 'board_report_present': True,
                         'service_date': day},
    }


def post(api_client, raw):
    _login(api_client)
    response = api_client.post('/api/validate-claim', json=raw,
                           headers={'X-Bilun-Validation-Contract': '2'})
    assert response.status_code == 200, response.text
    data = response.json()
    row = next(r for r in data['advisories'] if r['rule'] == 'drug_indication')
    return data, row


def assert_partial_private(data, row, drug):
    assert data['is_valid'] is None
    assert data['validation_status'] == 'review_required'
    assert row['selected_rule_id'] == f'4.2.14.C.{drug}_mesothelioma_board'
    assert row['disposition'] == 'review_only'
    assert row['clinical_eligibility_complete'] is False
    assert all(item['clinical_eligibility_complete'] is False for item in row['clinical_restrictions'])
    assert any(item['constraint_set'] == 'source_context_clinical_review'
               for item in row['clinical_restrictions'])
    encoded = json.dumps(data)
    assert all(token not in encoded for token in (
        'NEVER_PUBLISH', 'private_note', '987654.32', '"raw_evidence"',
        '"receipts"', '"risk_amount"', '"savings_try"', '"sgk_uplift_try"',
    ))


@pytest.mark.parametrize('drug', ['pemetrexed', 'raltitrexed'])
@pytest.mark.parametrize('facts', [{}, {'report_distinct_specialist_count': 2},
                                 {'treatment_protocol_documented_in_report': False},
                                 {'prescribed_by_specialist': False}])
def test_runtime_draft_is_blocked_before_documentary_comparisons(client, drug, facts):  # noqa: F811
    raw = payload(drug, **facts)
    data, row = post(client, raw)
    assert_partial_private(data, row, drug)
    outcome = next(item for item in row['clinical_restrictions'] if item['constraint_set'] == KIND)
    assert outcome['criterion_status'] == 'not_evaluated' and outcome['checks'] == []
    assert outcome['source_authority']['status'] == 'review_required'
    assert outcome['source_authority']['family_id'] == KIND
    assert 'verified_source_for_service_date' in row['missing_inputs']
    assert 'mesothelioma_documentary_interpretation_release' in row['missing_inputs']
    # A repeated real request must not add private execution receipts or new conclusions.
    assert post(client, raw)[1]['clinical_restrictions'] == row['clinical_restrictions']


@pytest.mark.parametrize('site', ['nonpleural', 'unknown', None])
def test_nonpleural_or_unknown_c45_stays_unresolved_at_http_boundary(client, site):  # noqa: F811
    raw = payload(diagnosis_site=site)
    raw['drug_context']['primary_icd10'] = 'C45.1' if site == 'nonpleural' else 'C45.9'
    data, row = post(client, raw)
    assert_partial_private(data, row, 'pemetrexed')
    outcome = next(item for item in row['clinical_restrictions'] if item['constraint_set'] == KIND)
    assert outcome['criterion_status'] == 'not_evaluated' and outcome['checks'] == []
    assert data['violations'] == []


@pytest.mark.parametrize('day', [None, '2026-10-04'])
def test_missing_or_unadmitted_service_date_never_bypasses_runtime_source_gate(client, day):  # noqa: F811
    data, row = post(client, payload(day=day))
    assert_partial_private(data, row, 'pemetrexed')
    outcome = next(item for item in row['clinical_restrictions'] if item['constraint_set'] == KIND)
    assert outcome['criterion_status'] == 'not_evaluated' and outcome['checks'] == []
    assert ('drug_claim_date' if day is None else 'verified_source_for_service_date') in row['missing_inputs']


def test_isolated_all_clear_candidate_does_not_clear_source_review_or_complete_eligibility(client, monkeypatch):  # noqa: F811
    # Explicit test substitution exercises composition after a hypothetical
    # independent release; the production evaluator and release remain blocked.
    monkeypatch.setattr(
        'src.bilun.domain.prose_rules._drug_indication.clinical.evaluate_mesothelioma_documents',
        evaluate_mesothelioma_documentary_candidate,
    )
    raw = payload()
    line = build_context_from_material_dict(raw).drug_lines[0]
    candidate = evaluate_mesothelioma_documentary_candidate(
        line, '4.2.14.C.pemetrexed_mesothelioma_board',
    )
    assert candidate['criterion_status'] == 'criterion_clear'
    data, row = post(client, raw)
    assert_partial_private(data, row, 'pemetrexed')
    outcome = next(item for item in row['clinical_restrictions'] if item['constraint_set'] == KIND)
    assert outcome['criterion_status'] == 'criterion_clear'
    assert 'remaining_sut_clinical_criteria' in row['missing_inputs']


@pytest.mark.parametrize('candidate_substitution', [False, True])
def test_explicit_pleural_fact_and_nonpleural_icd_stay_unresolved(client, monkeypatch, candidate_substitution):  # noqa: F811
    if candidate_substitution:
        monkeypatch.setattr(
            'src.bilun.domain.prose_rules._drug_indication.clinical.evaluate_mesothelioma_documents',
            evaluate_mesothelioma_documentary_candidate,
        )
    raw = payload(diagnosis_site='pleural')
    raw['drug_context']['primary_icd10'] = 'C45.1'
    data, row = post(client, raw)
    assert_partial_private(data, row, 'pemetrexed')
    outcome = next(item for item in row['clinical_restrictions'] if item['constraint_set'] == KIND)
    if candidate_substitution:
        assert outcome['criterion_status'] == 'unknown'
        assert 'mesothelioma_evidence.diagnosis_context_reconciliation' in row['missing_inputs']
    else:
        assert outcome['criterion_status'] == 'not_evaluated' and outcome['checks'] == []

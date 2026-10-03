"""New clinical metadata never bypasses bounded public result projection."""
import json

import pytest

from src.bilun.api.public_responses import project_public_response
from src.bilun.api.routes.validation import validate_claim_endpoint
from src.bilun.domain.billing.drug_clinical_evidence import bounded_clinical_restrictions
from src.bilun.shared.models import ClaimValidationRequest


SECRET = 'SYNTHETIC_PRIVATE_HISTORY_MUST_NOT_ESCAPE'


def hostile_outcome():
    return {'constraint_set': 'sma_safety_2025', 'criterion_status': 'restriction_not_met',
            'checks': [{'field': 'sma_evidence.csf_shunt_or_catheter', 'status': 'fail',
                        'value': SECRET, 'patient_history': {'raw': SECRET}}] * 100,
            'source_refs': ['4.2.49.(3)#88014037'] * 100,
            'missing_inputs': ['sma_evidence.assessment_date', {'private': SECRET}],
            'private_notes': SECRET, 'raw_evidence': {'value': SECRET},
            'clinical_eligibility_complete': True}


@pytest.mark.parametrize('surface', ['get_billing_report', 'get_bill_billing_report',
                                   '/api/billing-report/{patient_id}'])
def test_hostile_nested_data_cannot_hide_inside_new_allowed_metadata(surface):
    bounded = bounded_clinical_restrictions([hostile_outcome()])[0].to_dict()
    assert len(bounded['checks']) == 64 and bounded['checks_truncated'] is True
    assert bounded['source_refs_truncated'] is True
    assert bounded['clinical_eligibility_complete'] is False
    assert SECRET not in json.dumps(bounded)
    # Reinject hostile cached extras after canonical construction; public nested
    # projection must independently enforce its allowlist and scalar contracts.
    bounded['private_notes'] = SECRET
    bounded['checks'][0]['raw_value'] = SECRET
    bounded['checks'].append({'field': {'private': SECRET}, 'status': {'private': SECRET}})
    bounded['source_refs'].append({'private': SECRET})
    row = {'patient_id': 'SYNTHETIC-ONE', 'claim_id': 'SYNTHETIC-CLAIM',
           'drug_claim_line_id': 'SYNTHETIC-LINE', 'clinical_restrictions': [bounded],
           'private_patient_history': SECRET}
    public = project_public_response({'patient_id': 'SYNTHETIC-ONE',
        'drug_indication': {'findings': [row], 'evaluations': [row], 'violations': [row]},
        'private_patient_history': SECRET}, surface)
    assert SECRET not in json.dumps(public)
    for kind in ('findings', 'evaluations', 'violations'):
        assert public['drug_indication'][kind][0]['patient_id'] == 'SYNTHETIC-ONE'
        assert public['drug_indication'][kind][0]['clinical_restrictions'][0]['clinical_eligibility_complete'] is False


def test_actual_request_cannot_echo_private_nested_history_or_raw_measurements():
    request = ClaimValidationRequest.model_validate({
        'claim_id': 'SYNTHETIC-CLAIM',
        'materials': [{'name': 'anidulafungin', 'private_patient_history': SECRET,
            'antifungal_evidence': {'applies_on': '2026-10-02', 'assessment_date': '2026-10-02',
                'intent': 'treatment', 'indication': 'invasive_candidiasis', 'adult': False,
                'anc_per_mm3': 499.125, 'anc_lab_result_present': True, 'private_notes': SECRET}}],
        'drug_context': {'service_date': '2026-10-02', 'primary_icd10': 'B37.9',
                         'board_report_present': True},
    })
    public = validate_claim_endpoint(request, '2')
    text = json.dumps(public)
    assert SECRET not in text and '499.125' not in text
    drug = next(row for row in public['advisories'] if row['rule'] == 'drug_indication')
    assert drug['disposition'] == 'review_only'
    assert drug['clinical_eligibility_complete'] is False
    assert {'field': 'antifungal_evidence.anc_per_mm3', 'status': 'fail'} in drug['clinical_restrictions'][0]['checks']
    assert not any(key in drug for key in ('patient_history', 'raw_value', 'risk_amount', 'savings_try'))


def test_new_metadata_does_not_create_a_public_developer_surface():
    with pytest.raises(ValueError, match='No public response contract'):
        project_public_response({'clinical_restrictions': [hostile_outcome()]}, '/api/rules')

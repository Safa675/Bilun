"""Existing authenticated claim API carries two closed clinical drafts, never payment clearance."""
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date
import json
from types import SimpleNamespace

import pytest

from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line
from src.bilun.domain.prose_rules import adult_gh_draft as gh
from src.bilun.domain.prose_rules._drug_indication import clinical_mds as mds
from src.bilun.shared.models import ClaimValidationRequest
from tests.unit.api.test_validation_contract_v2 import client, _login  # noqa: F401
from tests.unit.domain.prose_rules.test_adult_gh_closed_epiphysis import facts as gh_facts
from tests.unit.domain.claims.test_mds_evidence_transport import facts as mds_facts
from tests.unit.domain.prose_rules.test_drug_indication_4206 import _drug_line

pytestmark = pytest.mark.unit
DAY = date(2026, 10, 5)
RULES = {gh.KIND: '4.2.6.adult_somatropin_board_report', mds.KIND: '4.2.9.mds_esa_hematology_report'}


def wire(value):
    return json.loads(json.dumps(asdict(value), default=lambda item: item.isoformat()))


def payload(family, day='2026-10-05', report=True):
    evidence = wire(gh_facts() if family == gh.KIND else mds_facts(applies_on=DAY, assessment_date=DAY))
    material = {'name': 'somatropin' if family == gh.KIND else 'epoetin alfa',
                'billed_amount': 987654.32, 'adult_gh_evidence' if family == gh.KIND else 'mds_evidence': evidence}
    if family == gh.KIND:
        material.update(gh_patient_group='adult', epiphyses_closed=True, gh_treatment_phase='initiation')
    return {'claim_id': 'combined-http', 'materials': [material], 'drug_context': {
        'primary_icd10': 'E23.0' if family == gh.KIND else 'D46.9',
        'board_report_present': report, 'report_duration_months': 12,
        'prescriber_specialty': 'endokrinoloji' if family == gh.KIND else 'hematoloji',
        'service_date': day}}


def post(api_client, raw):
    _login(api_client)
    response = api_client.post('/api/validate-claim', json=raw, headers={'X-Bilun-Validation-Contract': '2'})
    assert response.status_code == 200, response.text
    return response.json()


def rows(data):
    return [row for row in data['advisories'] if row['rule'] == 'drug_indication']


def restriction(row, family):
    return next(item for item in row['clinical_restrictions'] if item['constraint_set'] == family)


@pytest.mark.parametrize('family', [gh.KIND, mds.KIND])
@pytest.mark.parametrize('report', [True, False, None])
def test_actual_source_and_interpretation_gates_precede_candidate_comparisons(client, monkeypatch, family, report):  # noqa: F811
    def forbidden(*args, **kwargs):
        raise AssertionError('Candidate predicates must not execute through the closed claim route')
    monkeypatch.setattr(gh, '_candidate', forbidden)
    monkeypatch.setattr(mds, '_candidate', forbidden)
    raw = payload(family, report=report)
    field = 'adult_gh_evidence' if family == gh.KIND else 'mds_evidence'
    raw['materials'][0][field].update(private_note='NEVER_PUBLISH', source_date_admission=True,
                                    clinical_interpretation_released=True, runtime_enabled=True)
    raw['materials'][0]['selected_rule_id'] = 'CALLER_CANNOT_SELECT'
    data = post(client, raw); row = rows(data)[0]; item = restriction(row, family)
    assert row['selected_rule_id'] == RULES[family]
    assert row['clinical_eligibility_complete'] is False and row['disposition'] == 'review_only'
    assert item['criterion_status'] == 'not_evaluated' and item['checks'] == []
    assert item['clinical_eligibility_complete'] is False
    assert item['source_authority']['family_id'] == family
    assert item['source_authority']['status'] == 'review_required'
    assert 'verified_source_for_service_date' in row['missing_inputs']
    assert ('adult_gh' if family == gh.KIND else 'mds') + '_clinical_interpretation_release' in row['missing_inputs']
    assert data['is_valid'] is None and data['validation_status'] == 'review_required'
    assert data['violations'] == []
    if family == mds.KIND:
        assert any(value['constraint_set'] == 'source_context_clinical_review' for value in row['clinical_restrictions'])
    encoded = json.dumps(data)
    assert all(token not in encoded for token in ('NEVER_PUBLISH', 'private_note', 'CALLER_CANNOT_SELECT',
        '987654.32', 'risk_amount', 'savings_try', 'raw_evidence', 'runtime_enabled'))
    assert rows(post(client, raw)) == rows(data)


@pytest.mark.parametrize('family', [gh.KIND, mds.KIND])
@pytest.mark.parametrize('day', [None, '2024-05-17', '2026-10-02', '2026-10-06'])
def test_missing_historical_and_future_service_windows_remain_review(client, family, day):  # noqa: F811
    data = post(client, payload(family, day)); row = rows(data)[0]
    assert restriction(row, family)['checks'] == []
    assert data['is_valid'] is None and row['clinical_eligibility_complete'] is False
    assert ('drug_claim_date' if day is None else 'verified_source_for_service_date') in row['missing_inputs']


@pytest.mark.parametrize('family,field,bad,expected', [
    (gh.KIND, 'itt_contraindicated', 'false', None),
    (gh.KIND, 'stimulation_tests', [{ 'test_id': 'T1', 'peak_gh_mcg_l': True }], None),
    (mds.KIND, 'specialist_report_present', 1, None),
    (mds.KIND, 'hb_value', '10.9', None),
    (mds.KIND, 'hb_unit', 'g/L', None),
    (mds.KIND, 'phase', 'renewal', None),
])
def test_shared_request_adapter_and_row_parser_keep_invalid_facts_unknown(client, family, field, bad, expected):  # noqa: F811
    raw = payload(family); key = 'adult_gh_evidence' if family == gh.KIND else 'mds_evidence'
    raw['materials'][0][key][field] = bad
    request = ClaimValidationRequest.model_validate(raw)
    typed = getattr(request.materials[0], key)
    if field == 'stimulation_tests':
        assert typed.stimulation_tests[0].peak_gh_mcg_l is None
    else:
        assert getattr(typed, field) is expected
    dumped = request.model_dump(mode='json')
    line = build_context_from_material_dict(dumped).drug_lines[0]
    assert getattr(line, key) == typed
    row = asdict(replace(_drug_line(drug_name=raw['materials'][0]['name'], report_present=True), drug_claim_date=DAY))
    row[key] = raw['materials'][0][key]; errors = []
    assert getattr(parse_drug_line(row, errors), key) == typed
    row[key] = json.dumps(row[key])
    assert getattr(parse_drug_line(row, errors), key) == typed and errors == []
    assert restriction(rows(post(client, raw))[0], family)['criterion_status'] == 'not_evaluated'


@pytest.mark.parametrize('family', [gh.KIND, mds.KIND])
@pytest.mark.parametrize('invalid', [None, [], True, 'not JSON'])
def test_absent_or_invalid_objects_never_clear_existing_claim(client, family, invalid):  # noqa: F811
    raw = payload(family); key = 'adult_gh_evidence' if family == gh.KIND else 'mds_evidence'
    raw['materials'][0][key] = invalid
    assert getattr(ClaimValidationRequest.model_validate(raw).materials[0], key) is None
    data = post(client, raw)
    assert restriction(rows(data)[0], family)['criterion_status'] == 'not_evaluated'
    assert data['is_valid'] is None


@pytest.mark.parametrize('family,drug,code,scope', [
    (gh.KIND, 'somatrogon', 'E23.0', {}),
    (gh.KIND, 'somatropin', 'Q96.0', {'gh_patient_group': 'pediatric', 'epiphyses_closed': False}),
    (gh.KIND, 'somatropin', 'E23.0', {'epiphyses_closed': False}),
    (gh.KIND, 'somatropin', 'E23.0', {'gh_treatment_phase': 'continuation'}),
    (mds.KIND, 'epoetin alfa', 'N18.5', {}),
    (mds.KIND, 'darbepoetin', 'D46.9', {}),
    (mds.KIND, 'peg epoetin beta', 'D46.9', {}),
    (mds.KIND, 'ARANESP (DARBEPOETIN)', 'D46.9', {}),
    (mds.KIND, 'EPREX', 'D46.9', {}),
    (mds.KIND, 'epoetin zeta', 'D46.9', {}),
    (mds.KIND, 'pemetrexed', 'C45.0', {}),
])
def test_out_of_scope_payloads_are_differentially_identical(client, family, drug, code, scope):  # noqa: F811
    raw = payload(family); raw['materials'][0].update(name=drug, **scope); raw['drug_context']['primary_icd10'] = code
    if code.startswith('N18'):
        raw['materials'][0]['mds_evidence']['indication'] = 'ckd_anemia'
    baseline = deepcopy(raw)
    for key in ('adult_gh_evidence', 'mds_evidence'):
        baseline['materials'][0].pop(key, None)
    with_facts = post(client, raw); without_facts = post(client, baseline)
    # Stable conclusions stay identical; request identity intentionally includes supplied facts.
    normalize = lambda data: [{key:value for key,value in row.items() if key != 'evidence_id'} for row in rows(data)]
    assert normalize(with_facts) == normalize(without_facts)
    assert all(item['constraint_set'] != family for row in rows(with_facts) for item in row['clinical_restrictions'])


@pytest.mark.parametrize('field,bad', [('epiphyses_closed', 'true'), ('gh_patient_group', 'ADULT'), ('gh_treatment_phase', 'restart')])
def test_existing_outer_growth_scope_rejects_invalid_nonnull_instead_of_relaxing_other_gh_contracts(client, field, bad):  # noqa: F811
    raw = payload(gh.KIND);raw['materials'][0][field] = bad; _login(client)
    assert client.post('/api/validate-claim', json=raw, headers={'X-Bilun-Validation-Contract':'2'}).status_code == 422


@pytest.mark.parametrize('family,module,constant', [(gh.KIND, gh, '_ADULT_GH_INTERPRETATION_RELEASED'),
                                                   (mds.KIND, mds, '_MDS_CLINICAL_INTERPRETATION_RELEASED')])
def test_independent_interpretation_gate_remains_closed_even_after_mock_source_admission(client, monkeypatch, family, module, constant):  # noqa: F811
    assert getattr(module, constant) is False
    monkeypatch.setattr(module, 'resolve_source_authority', lambda family, service: SimpleNamespace(
        status='admitted', model_dump=lambda: {'family_id':family,'status':'admitted','service_date':service.isoformat()}))
    item = restriction(rows(post(client, payload(family)))[0], family)
    assert item['criterion_status'] == 'not_evaluated' and item['checks'] == []


def test_both_typed_evidence_groups_roundtrip_on_two_lines_without_cross_family_dispatch(client):  # noqa: F811
    raw = payload(gh.KIND)
    raw['materials'].append(payload(mds.KIND)['materials'][0])
    raw['drug_context']['primary_icd10'] = 'E23.0'
    raw['materials'][0]['mds_evidence'] = raw['materials'][1]['mds_evidence']
    raw['materials'][1]['adult_gh_evidence'] = raw['materials'][0]['adult_gh_evidence']
    request = ClaimValidationRequest.model_validate(raw)
    assert ClaimValidationRequest.model_validate_json(request.model_dump_json()) == request
    # A shared primary diagnosis cannot manufacture an MDS indication selector.
    data = post(client, raw)
    for row in rows(data):
        assert not any(item['constraint_set'] == mds.KIND for item in row['clinical_restrictions'])
        assert row['clinical_eligibility_complete'] is not True


def test_candidate_missing_paths_survive_public_projection_only_with_known_bounded_identifiers(client, monkeypatch):  # noqa: F811
    original = gh.evaluate_adult_gh_closed_epiphysis_candidate
    def review(line, selected):
        outcome = original(line, selected)
        if outcome is not None:
            outcome['missing_inputs'] += ['adult_gh_evidence.stimulation_tests[19].test_id',
                'adult_gh_evidence.stimulation_tests[20].test_id', 'adult_gh_evidence.stimulation_tests[01].kind',
                'adult_gh_evidence.stimulation_tests[0].private_note', 'adult_gh_evidence.PRIVATE_INTERNAL',
                'mds_evidence.hb_value', 'mds_evidence.private_note']
        return outcome
    monkeypatch.setattr('src.bilun.domain.prose_rules._drug_indication.clinical.evaluate_adult_gh_closed_epiphysis', review)
    raw = payload(gh.KIND)
    raw['materials'][0]['adult_gh_evidence']['stimulation_tests'][1]['inadequate_response_documented'] = None
    row = rows(post(client, raw))[0]
    assert 'adult_gh_evidence.stimulation_tests[1].inadequate_response_documented' in row['missing_inputs']
    assert 'adult_gh_evidence.stimulation_tests[19].test_id' in row['missing_inputs']
    assert 'mds_evidence.hb_value' in row['missing_inputs']
    assert all(value not in row['missing_inputs'] for value in (
        'adult_gh_evidence.stimulation_tests[20].test_id', 'adult_gh_evidence.stimulation_tests[01].kind',
        'adult_gh_evidence.stimulation_tests[0].private_note', 'adult_gh_evidence.PRIVATE_INTERNAL', 'mds_evidence.private_note'))
    assert row['selected_rule_id'] == RULES[gh.KIND] and row['clinical_eligibility_complete'] is False


@pytest.mark.parametrize('report_duration,prescriber,kind', [(12, 'endokrinoloji', 'missing_board_report'),
    (24, 'endokrinoloji', 'report_duration_mismatch'), (12, 'dermatoloji', 'prescriber_specialty_mismatch')])
def test_new_gated_observation_preserves_independently_observed_selected_route_error(monkeypatch, report_duration, prescriber, kind):
    from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
    raw = payload(gh.KIND, report=kind != 'missing_board_report')
    raw['drug_context'].update(report_duration_months=report_duration, prescriber_specialty=prescriber)
    ctx = build_context_from_material_dict(raw)
    args = {'drug_line':ctx.drug_lines[0], 'claim':ctx.claims[0], 'diagnoses':[]}
    registered = evaluate_drug_indication_line_detailed(**args)
    monkeypatch.setattr('src.bilun.domain.prose_rules._drug_indication.clinical.evaluate_adult_gh_closed_epiphysis', lambda *args: None)
    baseline = evaluate_drug_indication_line_detailed(**args)
    assert baseline['violation']['violation_kind'] == kind
    for key in ('rule_id', 'violation_kind', 'severity', 'message_tr', 'selected_rule_id'):
        assert registered['violation'].get(key) == baseline['violation'].get(key)
    assert restriction(registered, gh.KIND)['criterion_status'] == 'not_evaluated'


def test_adult_age_and_diagnosis_never_supply_epiphyseal_closure_or_childhood_retest(client):  # noqa: F811
    raw = payload(gh.KIND)
    raw['materials'][0].pop('epiphyses_closed')
    raw['materials'][0]['gh_chronological_age_years'] = 40
    raw['materials'][0]['adult_gh_evidence']['diagnosis_pathway'] = 'childhood_onset_retest'
    raw['materials'][0]['adult_gh_evidence']['gh_stopped_due_to_epiphyseal_closure'] = None
    typed = ClaimValidationRequest.model_validate(raw).materials[0]
    assert typed.epiphyses_closed is None
    assert typed.adult_gh_evidence.gh_stopped_due_to_epiphyseal_closure is None
    data = post(client, raw)
    assert restriction(rows(data)[0], gh.KIND)['criterion_status'] == 'not_evaluated'
    assert data['is_valid'] is None

"""Bounded source authority remains honest through canonical/cache/public/V2 paths."""
from copy import deepcopy
import json

import duckdb
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from src.bilun.api import public_responses
from src.bilun.api.routes.validation import router
from src.bilun.api.schemas import DrugClinicalRestrictionResponse, DrugIndicationReviewResponse
from src.bilun.cache.build_streaming import json_ready
from src.bilun.domain.billing.drug_indication_findings import (
    evaluate_drug_indication_findings, normalize_drug_indication_payload,
)
from src.bilun.domain.prose_rules import drug_indication as prose
from src.bilun.domain.sut.source_authority_schema import (
    ClinicalSourceAuthorityEvidence, bounded_source_authority,
)
from src.bilun.domain.validation_contract import ValidateClaimV2Response, ValidationClinicalRestriction
from tests.unit.domain.billing.test_drug_indication_findings import _context

SECRET = 'PRIVATE_RAW_PATIENT_SOURCE_SENTINEL'


def authority(**changes):
    return ClinicalSourceAuthorityEvidence.model_validate({
        'schema_version': 1, 'status': 'admitted', 'reason': 'covered',
        'family_id': 'sma', 'version_id': 'test-reviewed-version',
        'service_date': '2026-10-03', 'legal_effective_from': '2025-03-25',
        'admission_basis': 'reviewed_continuity', 'admitted_from': '2026-10-03',
        'admitted_through': '2026-10-03', 'source_observed_on': '2026-10-02',
        'official_review_checked_at': '2026-10-03T06:00:00Z',
        'source_docx_sha256': 'a' * 64, 'review_id': 'test-official-review',
        'next_action': 'Review the named source before extending the admitted window.',
        **changes,
    }).model_dump()


def restriction(source=None):
    row = {'constraint_set': 'sma_safety_2025', 'criterion_status': 'unknown',
           'missing_inputs': ['sma_evidence.sma_type'],
           'checks': [{'field': 'sma_evidence.sma_type', 'status': 'unknown'}],
           'source_refs': ['4.2.49.(4)#test'], 'clinical_eligibility_complete': False,
           'verification_status': 'ai_generated_pending_review',
           'checks_truncated': True, 'source_refs_truncated': True}
    if source is not None:
        row['source_authority'] = source
    return row


def detailed(source=None, *, top_level=False):
    row = {'applicability_status': 'matched', 'evaluation_status': 'missing_inputs',
           'observed_icd10_codes': ['G12.1'], 'selected_rule_id': 'test-source-rule',
           'missing_inputs': ['sma_evidence.sma_type'],
           'clinical_restrictions': [] if top_level else [restriction(source)],
           'clinical_eligibility_complete': False}
    if top_level and source is not None:
        row['source_authority'] = source
    row['violation'] = {**row, 'rule': 'drug_indication', 'violation_kind': 'needs_clinical_review',
        'severity': 'review', 'message_tr': 'Limited clinical conditions require review.',
        'drug_name': 'nusinersen', 'material_name': 'nusinersen'}
    return row


def _batch(monkeypatch, source, *, top_level):
    monkeypatch.setattr(prose, 'evaluate_drug_indication_line_detailed',
                        lambda **kwargs: deepcopy(detailed(source, top_level=top_level)))
    context = _context(primary_icd10='G12.1', primary_available=True)
    return evaluate_drug_indication_findings(context.patient_id, context)


def _source(row, top_level):
    return row.get('source_authority') if top_level else row['clinical_restrictions'][0].get('source_authority')


@pytest.mark.parametrize('top_level', [False, True], ids=['nested-clinical', 'mecasermin-top-level'])
@pytest.mark.parametrize('state', ['admitted', 'missing', 'stale'])
def test_authority_survives_canonical_cache_models_and_all_public_billing_surfaces(monkeypatch, top_level, state):
    evidence = authority() if state == 'admitted' else authority(
        status='review_required', admission_basis=None, reason='source_authority_unavailable' if state == 'missing' else 'uncovered_service_date',
        service_date='2026-10-04', next_action='Retrieve and review the official source for the service date.')
    batch = _batch(monkeypatch, evidence, top_level=top_level)
    rows = {'findings': [x.to_dict() for x in batch.findings],
            'evaluations': [x.to_dict() for x in batch.evaluations],
            'violations': list(batch.legacy_violations)}
    encoded = json_ready(batch)
    cache_rows = {kind: encoded['legacy_violations' if kind == 'violations' else kind] for kind in rows}
    with duckdb.connect(':memory:') as db:
        db.execute('CREATE TABLE reports(payload JSON)')
        db.execute('INSERT INTO reports VALUES (?)', [json.dumps(cache_rows)])
        cached_rows = json.loads(db.execute('SELECT payload FROM reports').fetchone()[0])
    cached = DrugIndicationReviewResponse.model_validate(cached_rows).model_dump(mode='json')
    for kind in rows:
        assert _source(rows[kind][0], top_level) == evidence
        assert _source(cached[kind][0], top_level) == evidence
        assert rows[kind][0]['clinical_eligibility_complete'] is False
    for surface in ['get_billing_report', 'get_bill_billing_report', '/api/billing-report/{patient_id}']:
        result = public_responses.project_public_response({'patient_id': 'TEST', 'drug_indication': cached}, surface)
        for kind in rows:
            assert _source(result['drug_indication'][kind][0], top_level) == evidence
            assert result['drug_indication'][kind][0]['clinical_eligibility_complete'] is False
    if not top_level:
        # Repeated cache validation must not erase a prior truncation disclosure.
        normalized = normalize_drug_indication_payload(cached)
        assert normalized['findings'][0]['clinical_restrictions'][0]['checks_truncated'] is True
        assert normalized['findings'][0]['clinical_restrictions'][0]['source_refs_truncated'] is True


@pytest.mark.parametrize('top_level', [False, True])
def test_absent_legacy_authority_is_not_fabricated(monkeypatch, top_level):
    batch = _batch(monkeypatch, None, top_level=top_level)
    rows = {'findings': [batch.findings[0].to_dict()],
            'evaluations': [batch.evaluations[0].to_dict()], 'violations': list(batch.legacy_violations)}
    for kind, entries in normalize_drug_indication_payload(rows).items():
        if kind in rows:
            assert _source(entries[0], top_level) is None
            assert 'source_authority' not in (entries[0] if top_level else entries[0]['clinical_restrictions'][0])


@pytest.mark.parametrize('change', [
    {'raw_evidence': {'patient': SECRET}}, {'next_action': {'patient': SECRET}},
    {'source_docx_sha256': SECRET}, {'clinical_eligibility_complete': True},
    {'status': SECRET}, {'scope': 'all_law'}, {'family_id': ['sma', SECRET]},
    {'next_action': 'x' * 401}, {'schema_version': '1'},
    {'schema_version': True}, {'schema_version': 1.0}, {'clinical_eligibility_complete': 0},
])
@pytest.mark.parametrize('top_level', [False, True])
def test_malformed_authority_fails_closed_without_public_or_cached_leakage(monkeypatch, change, top_level):
    bad = {**authority(), **change}
    assert bounded_source_authority(bad) is None
    batch = _batch(monkeypatch, bad, top_level=top_level)
    for row in [batch.findings[0].to_dict(), batch.evaluations[0].to_dict(), batch.legacy_violations[0]]:
        assert _source(row, top_level) is None
        assert SECRET not in json.dumps(row)
    # Re-inject after canonical construction to exercise cache/public trust boundaries independently.
    raw = detailed(bad, top_level=top_level)
    payload = {'findings': [raw], 'evaluations': [raw], 'violations': [raw]}
    normalized = normalize_drug_indication_payload(payload)
    for kind in payload:
        assert _source(normalized[kind][0], top_level) is None
    public = public_responses.project_public_response({'drug_indication': payload}, 'get_billing_report')
    assert SECRET not in json.dumps(public)
    for kind in payload:
        assert _source(public['drug_indication'][kind][0], top_level) is None


@pytest.mark.parametrize('model', [DrugClinicalRestrictionResponse, ValidationClinicalRestriction])
def test_nested_public_models_use_strict_authority_schema(model):
    valid = restriction(authority())
    parsed = model.model_validate(valid)
    assert parsed.source_authority.clinical_eligibility_complete is False
    with pytest.raises(ValidationError):
        model.model_validate({**valid, 'source_authority': {**authority(), 'patient_history': SECRET}})
    with pytest.raises(ValidationError):
        model.model_validate({**valid, 'clinical_eligibility_complete': True})
    assert model.model_validate(restriction()).source_authority is None


def test_public_schema_and_allowlist_are_complete_and_closed():
    schema = ValidateClaimV2Response.model_json_schema()['$defs']['ClinicalSourceAuthorityEvidence']
    assert schema['additionalProperties'] is False
    assert schema['properties']['clinical_eligibility_complete']['const'] is False
    assert set(public_responses._DEFINITIONS['ClinicalSourceAuthorityEvidence']) == set(schema['properties'])
    assert not {'patient_id', 'raw_evidence', 'patient_history', 'savings_try'} & set(schema['properties'])


@pytest.mark.parametrize('top_level', [False, True])
@pytest.mark.parametrize('state', ['admitted', 'missing', 'stale'])
def test_actual_http_v2_serialization_preserves_authority_and_review_scope(monkeypatch, top_level, state):
    evidence = authority() if state == 'admitted' else authority(
        status='review_required', admission_basis=None, reason='source_authority_unavailable' if state == 'missing' else 'uncovered_service_date',
        service_date='2026-10-04', next_action='Retrieve and review the official source for the service date.')
    monkeypatch.setattr(prose, 'evaluate_drug_indication_line_detailed',
                        lambda **kwargs: deepcopy(detailed(evidence, top_level=top_level)))
    app = FastAPI()
    app.include_router(router, prefix='/api')
    with TestClient(app) as client:
        response = client.post('/api/validate-claim', headers={'X-Bilun-Validation-Contract': '2'}, json={
            'claim_id': 'AUTHORITY-TEST', 'materials': [{'name': 'nusinersen'}],
            'drug_context': {'primary_icd10': 'G12.1', 'board_report_present': True,
                             'service_date': '2026-10-03'},
        })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['is_valid'] is None
    assert result['validation_status'] == 'review_required'
    row = next(x for x in result['advisories'] if x['rule'] == 'drug_indication')
    assert _source(row, top_level) == evidence
    assert row['clinical_eligibility_complete'] is False
    assert row['disposition'] == 'review_only'
    assert row['source_status'] == 'historical_match_unverified'
    assert not {'savings_try', 'risk_amount', 'raw_evidence'} & set(row)
    public = public_responses.project_public_response(result, '/api/validate-claim')
    public_row = next(x for x in public['advisories'] if x['rule'] == 'drug_indication')
    assert _source(public_row, top_level) == evidence


@pytest.mark.parametrize('service_date,expected_status', [
    ('2026-10-02', 'admitted'), ('2026-10-03', 'admitted'),
    ('2026-10-04', 'admitted'), ('2026-10-05', 'review_required'), (None, 'review_required'),
])
def test_real_mecasermin_leaf_to_http_preserves_top_level_authority(service_date, expected_status):
    app = FastAPI()
    app.include_router(router, prefix='/api')
    with TestClient(app) as client:
        response = client.post('/api/validate-claim', headers={'X-Bilun-Validation-Contract': '2'}, json={
            'claim_id': 'MECASERMIN-TRANSPORT',
            'materials': [{'name': 'INCRELEX (MECASERMIN)',
                'mecasermin_laron_syndrome_confirmed': True, 'gh_treatment_phase': 'continuation',
                'epiphyses_closed': True}],
            'drug_context': {'primary_icd10': 'E34.31', 'board_report_present': True,
                             'prescriber_specialty': 'çocuk endokrinoloji', 'report_duration_months': 12,
                             'service_date': service_date},
        })
    assert response.status_code == 200, response.text
    result = response.json()
    row = next(x for x in result['advisories'] if x['rule'] == 'drug_indication')
    assert row['source_authority']['status'] == expected_status
    assert row['source_authority']['family_id'] == 'mecasermin'
    assert row['source_authority']['service_date'] == service_date
    assert row['source_authority']['legal_effective_from'] is None
    assert row['source_authority']['source_observed_on'] == '2026-10-02'
    assert row['source_authority']['clinical_eligibility_complete'] is False
    assert row['clinical_eligibility_complete'] is False
    assert row['disposition'] == 'review_only'
    assert result['drug_runtime_coverage'][0]['runtime_coverage']['available'] is True
    assert result['drug_runtime_coverage'][0]['runtime_coverage']['clinical_eligibility_complete'] is False


@pytest.mark.parametrize('top_level', [False, True])
@pytest.mark.parametrize('legacy', [False, True])
def test_authority_reaches_recommended_actions_and_cohort_without_payment_claim(monkeypatch, top_level, legacy):
    from src.bilun.domain.billing.billing_actions import collect_billing_actions
    from src.bilun.domain.billing.cohort_compliance import build_cohort_compliance_index
    from src.bilun.domain.billing.types import BillingActionReport, DrugIndicationReview

    evidence = authority()
    batch = _batch(monkeypatch, evidence, top_level=top_level)
    report = BillingActionReport(patient_id='TEST', drug_indication=DrugIndicationReview(
        findings=[] if legacy else list(batch.findings), violations=list(batch.legacy_violations),
    ))
    actions = [x for x in collect_billing_actions(report) if x['surface'] == 'drug_indication']
    assert len(actions) == 1
    action = actions[0]
    assert _source(action, top_level) == evidence
    assert action['selected_rule_id'] == 'test-source-rule'
    assert action['clinical_eligibility_complete'] is False
    assert all(action[key] is None for key in ('sgk_uplift_try', 'audit_risk_try', 'compliance_savings_try'))
    public = public_responses.project_public_response({'recommended_actions': actions}, 'get_billing_report')
    assert _source(public['recommended_actions'][0], top_level) == evidence
    index = build_cohort_compliance_index({'TEST': {'recommended_actions': json_ready(actions)}})
    assert len(index['rows']) == 1
    assert _source(index['rows'][0], top_level) == evidence
    assert index['rows'][0]['billed_try'] is None
    assert index['rows'][0]['clinical_eligibility_complete'] is False
    public_index = public_responses.project_public_response(index, '/api/compliance-index')
    assert _source(public_index['rows'][0], top_level) == evidence


@pytest.mark.parametrize('top_level', [False, True])
def test_secondary_transport_independently_rejects_injected_provenance(top_level):
    from src.bilun.domain.billing.billing_actions import _action_row
    from src.bilun.domain.billing.cohort_compliance import build_cohort_compliance_index

    bad = {**authority(), 'patient_history': SECRET}
    evidence = {'source_authority': bad} if top_level else {'clinical_restrictions': [restriction(bad)]}
    action = _action_row(action_id='source-test', surface='drug_indication', kind='review',
                         finding_type='compliance', **evidence)
    assert _source(action, top_level) is None
    assert SECRET not in json.dumps(action)
    # Inject again after action construction to check the cohort boundary itself.
    index = build_cohort_compliance_index({'TEST': {'recommended_actions': [{**action, **evidence}]}})
    assert _source(index['rows'][0], top_level) is None
    assert SECRET not in json.dumps(index)


def test_other_gh_keeps_existing_runtime_metadata_without_new_source_guarantee():
    from tests.unit.domain.prose_rules.test_gh_runtime_callers import clear_payload, context

    ctx = context(clear_payload())
    batch = evaluate_drug_indication_findings(ctx.patient_id, ctx)
    row = batch.evaluations[0].to_dict()
    assert 'source_authority' not in row
    assert row['runtime_coverage']['available'] is True
    assert row['runtime_coverage']['predicate_passed_count'] == 4
    assert row['runtime_coverage']['clinical_eligibility_complete'] is False
    assert not batch.findings

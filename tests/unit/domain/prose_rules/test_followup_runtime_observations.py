"""Measured followup predicates preserve clinical results and source boundaries."""
from dataclasses import asdict, replace
from datetime import date
import json

import polars as pl
import pytest

from src.bilun.api.routes.validation import validate_claim_endpoint
from src.bilun.domain.validation_contract import ValidateClaimV2Response
from src.bilun.domain.prose_rules._drug_indication.clinical import evaluate_clinical_restrictions
from src.bilun.domain.prose_rules._drug_indication.clinical_followup import evaluate_followup
from src.bilun.domain.prose_rules._drug_indication.runtime_observations import ClinicalObservationCollector
from src.bilun.domain.prose_rules.drug_indication import list_drug_indication_rules
from src.bilun.domain.sut.runtime_coverage_schema import RuntimeCoverageResponse
from src.bilun.shared.models import ClaimValidationRequest
from tests.unit.domain.prose_rules.test_clinical_followup import DAY, dupi, nint

VERSION = 'followup.atomic.v2.2026-10-03'


def source():
    from pathlib import Path
    return pl.read_parquet(Path(__file__).resolve().parents[4] / 'data/gazette/sut_clauses.parquet')


def observe(line):
    collector = ClinicalObservationCollector(line, 'followup', VERSION)
    outcome = evaluate_followup(line, observer=collector)
    return outcome, collector, collector.summary(source())


def predicates(collector):
    return {receipt['predicate_id']: receipt for receipt in collector.receipts
            if receipt['kind'] == 'predicate'}


@pytest.mark.parametrize('line,passed,failed,missing', [
    (dupi(), 4, 2, 0),
    (dupi(response_easi=20.01), 3, 3, 0),
    (dupi(response_easi=None), 3, 2, 1),
    (nint(), 4, 0, 0),
    (nint(current_fvc_percent_predicted=72), 3, 1, 0),
    (nint(current_fvc_percent_predicted=None), 3, 0, 1),
])
def test_observed_evaluator_is_exact_clinical_differential(line, passed, failed, missing):
    plain = evaluate_followup(line)
    observed, collector, report = observe(line)

    assert observed == plain
    assert report['available'] is True
    assert report['clinical_eligibility_complete'] is False
    assert report['predicate_attempted_count'] == passed + failed + missing
    assert report['predicate_passed_count'] == passed
    assert report['predicate_failed_count'] == failed
    assert report['predicate_missing_inputs_count'] == missing
    assert report['source_clauses_fully_evaluated_count'] is None
    assert report['source_metrics_available'] is True
    assert report['unresolved_source_ref_count'] == 0
    RuntimeCoverageResponse.model_validate(report)


def test_dupilumab_receipts_identify_each_alternative_and_unknown_input():
    outcome, collector, _ = observe(dupi(response_easi=None))
    seen = predicates(collector)

    assert outcome['criterion_status'] == 'unknown'
    assert seen['dupilumab.response.easi_threshold']['status'] == 'missing_inputs'
    assert seen['dupilumab.response.easi_threshold']['missing_input_fields'] == [
        'followup_evidence.response_easi']
    assert seen['dupilumab.response.dlqi_threshold']['status'] == 'failed'
    assert seen['dupilumab.response.pruritus_nrs_threshold']['status'] == 'failed'
    assert seen['dupilumab.response.easi_threshold']['source_refs'] == [
        '4.2.57.(1)#d711a1b9']


def test_nintedanib_receipts_separate_timing_response_and_report_predicates():
    outcome, collector, _ = observe(nint(current_fvc_percent_predicted=72))
    seen = predicates(collector)

    assert outcome['criterion_status'] == 'restriction_not_met'
    assert seen['nintedanib.reassessment.twelve_month_interval']['status'] == 'passed'
    assert seen['nintedanib.fvc.assessment_outside_exacerbation']['status'] == 'passed'
    assert seen['nintedanib.fvc.response_threshold']['status'] == 'failed'
    assert seen['nintedanib.fvc.report_documents_response']['status'] == 'passed'
    assert seen['nintedanib.fvc.response_threshold']['source_refs'] == [
        '4.2.46.B.a#89e9c50d']


@pytest.mark.parametrize('service_day,route_status,criterion_status', [
    (None, 'blocked_inputs', 'not_evaluated'),
    (date(2026, 10, 1), 'blocked_source', 'not_evaluated'),
    (date(2026, 10, 2), None, 'criterion_clear'),
    (date(2026, 10, 3), None, 'criterion_clear'),
    (date(2026, 10, 4), None, 'criterion_clear'),
    (date(2026, 10, 5), None, 'criterion_clear'),
    (date(2026, 10, 6), 'blocked_source', 'not_evaluated'),
])
def test_existing_source_window_bounds_only_real_followup_comparisons(
        service_day, route_status, criterion_status):
    line = replace(dupi(), drug_claim_date=service_day)
    if service_day is not None:
        line = replace(line, followup_evidence=replace(
            line.followup_evidence, applies_on=service_day, assessment_date=service_day))
    outcome, collector, report = observe(line)

    assert outcome['criterion_status'] == criterion_status
    assert outcome == evaluate_followup(line)
    if route_status:
        assert report['predicate_attempted_count'] == 0
        assert len(collector.receipts) == 1
        assert collector.receipts[0]['kind'] == 'route'
        assert collector.receipts[0]['status'] == route_status
        assert outcome['checks'] == []
    else:
        assert report['predicate_attempted_count'] == 6
        assert report['source_clauses_touched_count'] == 4
        assert outcome['clinical_eligibility_complete'] is False


def test_admitted_source_with_unmatched_evidence_date_blocks_downstream_predicates():
    line = replace(dupi(), drug_claim_date=date(2026, 10, 3))
    outcome, collector, report = observe(line)

    assert outcome['source_authority']['status'] == 'admitted'
    assert outcome == evaluate_followup(line)
    assert outcome['criterion_status'] == 'not_evaluated'
    assert outcome['missing_inputs'] == ['followup_evidence.applies_on']
    assert report['predicate_attempted_count'] == 0
    assert collector.receipts[0]['status'] == 'blocked_inputs'
    assert collector.receipts[0]['missing_input_fields'] == ['followup_evidence.applies_on']


def test_request_local_collectors_do_not_retain_prior_followup_receipts():
    line = dupi()
    _, first, first_report = observe(line)
    rejected = replace(line, drug_claim_date=date(2026, 10, 6))
    rejected = replace(rejected, followup_evidence=replace(
        rejected.followup_evidence, applies_on=date(2026, 10, 6),
        assessment_date=date(2026, 10, 6)))
    _, second, second_report = observe(rejected)

    assert first.execution_scope != second.execution_scope
    assert first is not second and first.receipts is not second.receipts
    assert first_report['predicate_attempted_count'] == 6
    assert second_report['predicate_attempted_count'] == 0
    assert len(first.receipts) == 6
    assert len(second.receipts) == 1


@pytest.mark.parametrize('line,route_id,route_status,observed,missing,phase_observed', [
    (dupi(indication='other'), 'dupilumab.continuation.indication',
     'blocked_source', ['followup_evidence.indication'], [], False),
    (nint(indication='other'), 'nintedanib.continuation.indication',
     'blocked_source', ['followup_evidence.indication'], [], True),
    (dupi(phase=None), 'dupilumab.continuation.phase',
     'blocked_inputs', ['followup_evidence.indication'], ['followup_evidence.phase'], False),
])
def test_unreached_followup_scope_records_only_the_actual_route_gate(
        line, route_id, route_status, observed, missing, phase_observed):
    outcome, collector, report = observe(line)

    assert outcome == evaluate_followup(line)
    assert outcome['criterion_status'] == 'unknown'
    assert report['predicate_attempted_count'] == 0
    assert report['routes_blocked_source_count'] + report['routes_blocked_inputs_count'] == 1
    route = next(receipt for receipt in collector.receipts if receipt['kind'] == 'route')
    assert route['route_id'] == route_id
    assert route['status'] == route_status
    assert set(['drug_name', 'drug_claim_date', *observed]) <= set(route['observed_input_fields'])
    assert ('followup_evidence.phase' in route['observed_input_fields']) is phase_observed
    assert route['missing_input_fields'] == missing


def test_dispatch_and_http_serialize_only_bounded_followup_summary():
    line = dupi()
    rules = list_drug_indication_rules()
    rule = next(row for row in rules
                if row.get('clinical_constraint_set') == 'followup_source_constraints'
                and row.get('clinical_constraint_drugs') == ['dupilumab'])
    expected = evaluate_followup(line)
    dispatched = evaluate_clinical_restrictions(line, [rule])
    measured = next(row for row in dispatched
                    if row['constraint_set'] == 'followup_source_constraints')
    summary = measured.pop('runtime_coverage')

    assert measured == expected
    assert summary['instrumented_families'] == ['followup']
    assert summary['available'] is True
    assert summary['predicate_attempted_count'] == 6
    assert 'receipts' not in summary and 'execution_scope' not in summary

    raw = {'claim_id': 'SYNTHETIC-FOLLOWUP-OBS', 'materials': [{
        'name': 'dupilumab', 'followup_evidence': asdict(line.followup_evidence)}],
        'drug_context': {'primary_icd10': 'L20.9', 'service_date': DAY.isoformat(),
                         'board_report_present': True}}
    request = ClaimValidationRequest.model_validate(raw)
    response = validate_claim_endpoint(request, contract_version='2')
    public = ValidateClaimV2Response.model_validate(response).model_dump(mode='json')
    public = json.loads(json.dumps(public))
    advisory = next(row for row in public['advisories'] if row['rule'] == 'drug_indication')
    public_observation = next(row for row in advisory['clinical_restrictions']
                              if row['constraint_set'] == 'followup_source_constraints')
    public_summary = public_observation['runtime_coverage']
    assert public_summary['available'] is True
    assert public_summary['instrumented_families'] == ['followup']
    assert public_summary['source_clauses_touched_count'] == 4
    assert 'receipts' not in public_summary and 'execution_scope' not in public_summary
    for field in ('criterion_status', 'missing_inputs', 'checks', 'source_refs',
                  'clinical_eligibility_complete', 'verification_status', 'source_authority'):
        assert public_observation[field] == expected[field]
    assert advisory['disposition'] == 'review_only' and public['is_valid'] is None
    assert not any(key in advisory for key in ('payable_try', 'risk_amount', 'savings_try'))

"""Actual pediatric/CKD growth observations on the reviewed GH44 clinical tree."""
from dataclasses import replace
from datetime import date
import itertools
from pathlib import Path

import polars as pl
import pytest

from src.bilun.domain.prose_rules.drug_indication import list_drug_indication_rules
from src.bilun.domain.prose_rules._drug_indication.runtime_observations import ClinicalObservationCollector
from src.bilun.domain.prose_rules._drug_indication.pediatric_gh_initiation import (
    evaluate_pediatric_gh_initiation_checks, evaluate_pediatric_gh_initiation_preconditions,
)
from src.bilun.domain.prose_rules._drug_indication.ckd_growth_hormone import evaluate_ckd_gh_checks, evaluate_ckd_gh_preconditions
from src.bilun.domain.prose_rules._drug_indication.ckd_growth_pathways import evaluate_ckd_growth_pathways
from src.bilun.domain.sut.runtime_coverage_schema import RuntimeCoverageResponse
from tests.unit.domain.prose_rules.test_growth_hormone_continuation import line
from tests.unit.domain.prose_rules.test_pediatric_gh_initiation import BASE as PEDIATRIC
from tests.unit.domain.prose_rules.test_ckd_gh_partial_checks import BASE as CKD
from tests.unit.domain.prose_rules.test_ckd_gh_growth_pathways import CLEAR, BOOLS

DAY = date(2026, 10, 2)
PREFIX = 'gh.pediatric.initiation.'


def setup(family='pediatric', **values):
    rule_id = ('4.2.6.ckd_gh_nephro_endo_board' if family == 'ckd'
               else '4.2.6.A1.somatropin_listed_cases_no_condition' if values.get('gh_initiation_pathway', '').startswith('sga')
               else '4.2.6.A1.neurosecretory_bioinactive_gh_somatropin' if values.get('gh_initiation_pathway') == 'neurosecretory_bioinactive'
               else '4.2.6.pediatric_somatropin_initiation_board')
    rule = next(r for r in list_drug_indication_rules() if r['rule_id'] == rule_id)
    defaults = {**CKD, **CLEAR} if family == 'ckd' else PEDIATRIC
    drug = replace(line(), **{**defaults, 'drug_claim_date': DAY, **values})
    observer = ClinicalObservationCollector(drug, 'growth_hormone', 'gh.atomic.v1.2026-10-02')
    return rule, drug, observer


def observe(family='pediatric', **values):
    rule, drug, observer = setup(family, **values)
    fn = evaluate_ckd_gh_checks if family == 'ckd' else evaluate_pediatric_gh_initiation_checks
    result = fn(rule=rule, drug_line=drug, observer=observer)
    assert result == fn(rule=rule, drug_line=drug)
    summary = observer.summary()
    RuntimeCoverageResponse.model_validate(summary)
    assert summary['available'] is True
    assert summary['source_clauses_fully_evaluated_count'] is None
    return result, observer


def predicates(observer):
    return {r['predicate_id']: r for r in observer.receipts if r['kind'] == 'predicate'}


@pytest.mark.parametrize('band,age,limit', [('0_2_years', 1.5, 10), ('2_1_4_years', 3, 7), ('4_1_prepubertal', 8.2, 5)])
@pytest.mark.parametrize('offset,status', [(-0.01, 'passed'), (0, 'failed'), (0.01, 'failed'), (None, 'missing_inputs')])
def test_only_recorded_age_band_comparison_is_attempted(band, age, limit, offset, status):
    _, o = observe(gh_reported_growth_age_band=band, gh_chronological_age_years=age,
                   annual_growth_velocity_cm=None if offset is None else limit + offset)
    hits = {key: r for key, r in predicates(o).items() if '.standard.velocity_' in key}
    assert list(hits) == [PREFIX + 'standard.velocity_' + band]
    assert next(iter(hits.values()))['status'] == status


@pytest.mark.parametrize('changes', [
    {'gh_reported_growth_age_band': None}, {'gh_pubertal_status': None},
    {'gh_reported_growth_age_band': 'pubertal'},
    {'gh_reported_growth_age_band': '2_1_4_years', 'gh_chronological_age_years': 1.5},
])
def test_missing_or_conflicting_stage_blocks_comparisons(changes):
    _, o = observe(**changes)
    assert not predicates(o)
    assert o.summary()['routes_blocked_inputs_count'] + o.summary()['routes_blocked_source_count'] == 1


@pytest.mark.parametrize('age,band', [(2.05, '0_2_years'), (2.05, '2_1_4_years'), (4.05, '2_1_4_years'), (4.05, '4_1_prepubertal')])
def test_ambiguous_printed_transition_is_not_newly_classified(age, band):
    _, o = observe(gh_chronological_age_years=age, gh_reported_growth_age_band=band)
    assert PREFIX + 'standard.velocity_' + band in predicates(o)


@pytest.mark.parametrize('age,bone,status', [(8.2, 6.2, 'passed'), (8.2, 6.2001, 'failed'), (8.2, None, 'missing_inputs')])
def test_bone_delay_exact_decimal_boundary(age, bone, status):
    _, o = observe(gh_chronological_age_years=age, bone_age_years=bone)
    assert predicates(o)[PREFIX + 'prepubertal.bone_delay_at_least_2']['status'] == status


@pytest.mark.parametrize('assessed', [True, False, None])
def test_puberty_observes_specialist_assessment_and_epiphyses_only(assessed):
    _, o = observe(gh_pubertal_status='pubertal', gh_reported_growth_age_band='pubertal',
                   gh_pubertal_growth_assessment_completed=assessed, gh_chronological_age_years=50,
                   bone_age_years=100, annual_growth_velocity_cm=100)
    assert set(predicates(o)) == {PREFIX + 'pubertal.growth_assessment', PREFIX + 'pubertal.open_epiphyses'}
    observed = {f for r in o.receipts for f in r['observed_input_fields']}
    assert not observed & {'gh_chronological_age_years', 'bone_age_years', 'annual_growth_velocity_cm'}
    assert o.summary()['routes_skipped_count'] == 1


@pytest.mark.parametrize('weight,length,count', [(-2.1, None, 3), (None, -2.1, 4), (-2, -2, 4), (None, None, 4)])
def test_sga_birth_or_short_circuit_and_signed_values(weight, length, count):
    _, o = observe(gh_initiation_pathway='sga_case_1', gh_birth_weight_for_gestational_age_sds=weight,
                   gh_birth_length_for_gestational_age_sds=length, gh_chronological_age_years=4,
                   gh_last_year_growth_velocity_sds=-0.01)
    assert len(predicates(o)) == count
    if weight == -2.1:
        assert PREFIX + 'sga1.birth_length_below_minus_2' not in predicates(o)
        assert 'gh_birth_length_for_gestational_age_sds' not in {f for r in o.receipts for f in r['observed_input_fields'] + r['missing_input_fields']}
    assert all('.standard.' not in key for key in predicates(o))


@pytest.mark.parametrize('confirmed,count', [(True, 3), (False, 1), (None, 1)])
def test_sga_two_birth_scope_before_signed_height_checks(confirmed, count):
    _, o = observe(gh_initiation_pathway='sga_case_2', gh_sga_birth_status_confirmed=confirmed,
                   gh_current_height_sds=-2.5, gh_parent_adjusted_height_sds=-1)
    assert len(predicates(o)) == count
    if confirmed:
        assert all(r['status'] == 'failed' for k, r in predicates(o).items() if not k.endswith('birth_status'))


@pytest.mark.parametrize('path', ['organic_or_surgical', 'neurosecretory_bioinactive'])
def test_exception_paths_explicitly_block_unimplemented_source_checks(path):
    _, o = observe(gh_initiation_pathway=path)
    assert not predicates(o) and o.summary()['routes_blocked_source_count'] == 1


@pytest.mark.parametrize('when,status', [(None, 'routes_blocked_inputs_count'), (date(2024, 5, 16), 'routes_blocked_source_count')])
def test_new_protocol_date_gates_do_not_claim_comparison(when, status):
    _, o = observe(drug_claim_date=when)
    assert not predicates(o) and o.summary()[status] == 1


@pytest.mark.parametrize('percentile,sds,attempts', [(2.9, -2.1, 8), (3, -2, 8), (2.9, -1.9, 8), (2.9, None, 6), (None, -2.1, 6)])
def test_ckd_height_notation_boundary_and_actual_comparisons(percentile, sds, attempts):
    rule, drug, o = setup('ckd', ckd_height_age_sex_percentile=percentile, ckd_height_age_sex_sds=sds)
    result = evaluate_ckd_growth_pathways(drug, observer=o)
    assert result == evaluate_ckd_growth_pathways(drug)
    assert len(predicates(o)) == attempts
    assert o.summary()['available'] is True
    if percentile is None or sds is None:
        assert o.summary()['routes_blocked_source_count'] == 1
        assert not any('.height_' in p for p in predicates(o))


def test_ckd_all_three_valued_alternatives_are_observed_with_no_false_denial():
    for flags in itertools.product([True, False, None], repeat=5):
        _, drug, o = setup('ckd', **dict(zip(BOOLS, flags)))
        result = evaluate_ckd_growth_pathways(drug, observer=o)
        assert result == evaluate_ckd_growth_pathways(drug)
        b = False if False in flags[1:4] else (True if all(v is True for v in flags[1:4]) else None)
        assert ('ckd_growth_source_alternatives' in result['failed_criteria']) is all(v is False for v in (flags[0], b, flags[4]))
        assert len(predicates(o)) == 8
        assert o.summary()['available'] is True


@pytest.mark.parametrize('values', [{'ckd_active_cancer': True}, {'gh_daily_dose_mg_per_kg': 0.051}, {'ckd_first_post_transplant_year': True, 'ckd_post_transplant_one_year_elapsed': True}, {'gh_treatment_phase': 'continuation'}])
def test_ckd_early_or_phase_bypass_does_not_invent_growth_execution(values):
    _, o = observe('ckd', **values)
    assert not any(key.startswith('gh.ckd.growth.') for key in predicates(o))


@pytest.mark.parametrize('pth', [0, 499.9])
def test_supplied_ckd_pth_conflict_is_source_review_not_a_missing_fact(pth):
    result, o = observe('ckd', ckd_persistent_severe_secondary_hyperparathyroidism=True,
                        ckd_parathyroid_hormone_pg_ml=pth, **dict.fromkeys(BOOLS, True))
    assert 'ckd_parathyroid_status_reconciliation' in result['missing_inputs']
    route = next(r for r in o.receipts if r.get('route_id') == 'gh.ckd.pth_reconciliation')
    assert route['status'] == 'blocked_source'
    assert route['missing_input_fields'] == []
    assert {'ckd_persistent_severe_secondary_hyperparathyroidism',
            'ckd_parathyroid_hormone_pg_ml'} <= set(route['observed_input_fields'])
    assert not any('ckd_parathyroid_status_reconciliation' in r['missing_input_fields'] for r in o.receipts)
    assert 'gh.ckd.initiation.no_persistent_severe_shpt' not in predicates(o)
    assert o.summary()['input_facts_missing_count'] == 0
    assert o.summary()['routes_blocked_source_count'] == 1


@pytest.mark.parametrize('family,values', [('pediatric', {}),
    ('pediatric', {'gh_reported_growth_age_band': '0_2_years', 'gh_chronological_age_years': 1.5}),
    ('pediatric', {'gh_reported_growth_age_band': '2_1_4_years', 'gh_chronological_age_years': 3}),
    ('pediatric', {'gh_reported_growth_age_band': 'pubertal', 'gh_pubertal_status': 'pubertal'}),
    ('pediatric', {'gh_initiation_pathway': 'sga_case_1', 'gh_birth_weight_for_gestational_age_sds': None, 'gh_birth_length_for_gestational_age_sds': -2.1}),
    ('pediatric', {'gh_initiation_pathway': 'sga_case_2', 'gh_sga_birth_status_confirmed': True}), ('ckd', {})])
def test_real_precondition_then_check_sequence_is_valid_and_source_bound(family, values):
    rule, drug, o = setup(family, **values)
    pre = evaluate_ckd_gh_preconditions if family == 'ckd' else evaluate_pediatric_gh_initiation_preconditions
    check = evaluate_ckd_gh_checks if family == 'ckd' else evaluate_pediatric_gh_initiation_checks
    assert pre(rule=rule, drug_line=drug, observer=o) is None
    check(rule=rule, drug_line=drug, observer=o)
    raw = pl.read_parquet(Path(__file__).resolve().parents[4]/'data/gazette/sut_clauses.parquet')
    summary = o.summary(raw)
    RuntimeCoverageResponse.model_validate(summary)
    assert summary['available'] is True and summary['source_metrics_available'] is True
    assert summary['source_clauses_fully_evaluated_count'] is None

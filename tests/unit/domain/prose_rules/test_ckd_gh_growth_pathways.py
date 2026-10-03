"""Recorded CKD growth alternatives and concordant-only height references."""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.claims.growth_hormone import CKD_GROWTH_PATHWAY_FIELDS
from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line
from src.bilun.shared.models import MaterialItem
from tests.unit.domain.prose_rules.test_ckd_gh_partial_checks import evaluate
from tests.unit.domain.prose_rules.test_growth_hormone_continuation import line

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[4]
BOOLS = CKD_GROWTH_PATHWAY_FIELDS[3:]
B = ('ckd_post_transplant_one_year_elapsed', 'ckd_steroid_treatment_absent', 'ckd_spontaneous_growth_absent')
CLEAR = dict(ckd_height_age_sex_percentile=2.9, ckd_height_age_sex_sds=-2.1,
             ckd_annual_growth_velocity_percentile=24.9, ckd_persistent_growth_failure_confirmed=True)


def check(**kw):
    return evaluate(**{**CLEAR, **kw})


def failed(result, name):
    return name in result['violation'].get('growth_hormone_failed_criteria', [])


@pytest.mark.parametrize('flags', [{'ckd_persistent_growth_failure_confirmed': True},
    {**dict.fromkeys(B, True), 'ckd_persistent_growth_failure_confirmed': None},
    {'ckd_nephropathic_cystinosis_related_confirmed': True, 'ckd_persistent_growth_failure_confirmed': None}])
def test_any_one_known_source_alternative_makes_other_missing_branches_moot(flags):
    result = check(**flags)
    assert result['missing_inputs'] == ['ckd_growth_initiation_clinical_assessment']
    assert result['violation']['severity'] == 'review'


@pytest.mark.parametrize('field', B)
def test_each_post_transplant_conjunct_is_required_without_a_or_c(field):
    flags = {**dict.fromkeys(BOOLS, False), **dict.fromkeys(B, True), field: False}
    assert failed(check(**flags), 'ckd_growth_source_alternatives')
    flags[field] = None
    result = check(**flags)
    assert result['violation']['severity'] == 'review'
    assert field in result['missing_inputs']


def test_false_branches_do_not_deny_an_unknown_alternative():
    result = check(**dict.fromkeys(BOOLS, None))
    assert result['violation']['severity'] == 'review'
    assert set(BOOLS) <= set(result['missing_inputs'])


def test_known_false_all_source_alternatives_do_not_pass():
    assert failed(check(**dict.fromkeys(BOOLS, False)), 'ckd_growth_source_alternatives')


@pytest.mark.parametrize('pct,violates', [(0, False), (24.999, False), (25, True), (25.001, True), (100, True)])
def test_shared_growth_percentile_has_strict_upper_boundary(pct, violates):
    assert failed(check(ckd_annual_growth_velocity_percentile=pct), 'ckd_annual_growth_velocity_percentile') is violates


@pytest.mark.parametrize('pct,sds,kind', [(2.999, -2.001, 'clear'), (0, -4, 'clear'),
    (3, -2, 'fail'), (3.01, -1.99, 'fail'), (2.9, -1.99, 'discordant'), (3.01, -2.01, 'discordant'),
    (None, -2.01, 'unknown'), (2.9, None, 'unknown'), (None, None, 'unknown')])
def test_source_height_notations_are_not_converted_or_equated(pct, sds, kind):
    result = check(ckd_height_age_sex_percentile=pct, ckd_height_age_sex_sds=sds)
    assert failed(result, 'ckd_height_source_criterion') is (kind == 'fail')
    if kind == 'discordant':
        assert 'ckd_height_reference_reconciliation' in result['missing_inputs']
    if kind == 'unknown':
        assert 'ckd_height_source_notation_verification' in result['missing_inputs']
    if kind != 'fail':
        assert result['violation']['severity'] == 'review'


def test_known_shared_failure_is_decisive_despite_unrelated_unknown_height_and_branches():
    result = check(**{**dict.fromkeys(CKD_GROWTH_PATHWAY_FIELDS), 'ckd_annual_growth_velocity_percentile': 25})
    assert failed(result, 'ckd_annual_growth_velocity_percentile')
    assert result['missing_inputs'] == []


def test_first_year_and_elapsed_year_conflict_precedes_initiation_exclusion():
    result = check(ckd_first_post_transplant_year=True, ckd_post_transplant_one_year_elapsed=True)
    assert result['missing_inputs'] == ['ckd_transplant_timing_reconciliation']
    assert result['violation']['severity'] == 'review'


def test_first_year_false_never_implies_transplant_or_completed_year():
    result = check(ckd_persistent_growth_failure_confirmed=False,
                   ckd_nephropathic_cystinosis_related_confirmed=False,
                   ckd_first_post_transplant_year=False, ckd_steroid_treatment_absent=True,
                   ckd_spontaneous_growth_absent=True)
    assert 'ckd_post_transplant_one_year_elapsed' in result['missing_inputs']
    assert result['violation']['severity'] == 'review'


def test_low_measurements_never_infer_persistent_growth_failure():
    result = check(ckd_persistent_growth_failure_confirmed=None,
                   ckd_height_age_sex_percentile=0, ckd_height_age_sex_sds=-8,
                   ckd_annual_growth_velocity_percentile=0)
    assert 'ckd_persistent_growth_failure_confirmed' in result['missing_inputs']


def test_continuation_bypasses_growth_paths_and_timing_contradictions():
    result = check(gh_treatment_phase='continuation', ckd_height_age_sex_percentile=100,
                   ckd_height_age_sex_sds=3, ckd_annual_growth_velocity_percentile=100,
                   ckd_first_post_transplant_year=True, ckd_post_transplant_one_year_elapsed=True)
    assert result['missing_inputs'] == ['ckd_growth_continuation_clinical_assessment']
    assert all(f not in result['required_inputs'] for f in CKD_GROWTH_PATHWAY_FIELDS)


@pytest.mark.parametrize('when', [None, date(2024,5,16)])
def test_source_date_precedes_growth_failure(when):
    result = check(drug_claim_date=when, ckd_annual_growth_velocity_percentile=100)
    assert result['missing_inputs'] == (['drug_claim_date'] if when is None else ['historical_sut_version'])


def test_unknown_disease_scope_precedes_growth_failure():
    result = check(ckd_growth_disorder_confirmed=None, ckd_annual_growth_velocity_percentile=100)
    assert result['missing_inputs'] == ['ckd_growth_disorder_confirmed']


@pytest.mark.parametrize('field,value', [('ckd_height_age_sex_percentile', -1), ('ckd_height_age_sex_percentile', 100.1),
    ('ckd_annual_growth_velocity_percentile', 101), ('ckd_height_age_sex_sds', '-2'),
    ('ckd_height_age_sex_sds', float('inf')), ('ckd_height_age_sex_sds', float('nan')),
    ('ckd_steroid_treatment_absent', 'false'), ('ckd_post_transplant_one_year_elapsed', 1),
    ('ckd_height_age_sex_percentile', True)])
def test_invalid_facts_rejected_not_coerced(field, value):
    with pytest.raises(ValidationError):
        MaterialItem(name='somatropin', **{field: value})
    errors = []
    parsed = parse_drug_line({**asdict(line()), field: value}, errors)
    assert getattr(parsed, field) is None
    assert errors


def test_false_zero_and_signed_values_survive_flat_and_request_ingestion():
    facts = {**dict.fromkeys(BOOLS, False), 'ckd_height_age_sex_percentile': 0,
             'ckd_height_age_sex_sds': -2.5, 'ckd_annual_growth_velocity_percentile': 0}
    item = MaterialItem(name='somatropin', **facts)
    ctx = build_context_from_material_dict({'claim_id':'CKD-G','materials':[item.model_dump()],
        'drug_context':{'primary_icd10':'N18.5'}})
    parsed = parse_drug_line(asdict(replace(line(), **facts)), [])
    for f,v in facts.items():
        assert getattr(ctx.drug_lines[0], f) == v
        assert getattr(parsed, f) == v
    assert all(getattr(MaterialItem(name='somatropin'), f) is None for f in CKD_GROWTH_PATHWAY_FIELDS)


def test_source_conditions_and_uncertainty_are_pinned():
    source = json.loads((ROOT/'data/gazette/source_evidence/ckd_gh_growth_pathways.json').read_text())
    assert source['height_notation_equivalence_verified'] is False
    assert source['verified_current_heading_from'] == '2024-05-17'
    assert source['source_keys'] == ['4.2.6.A-5.a#7420864e','4.2.6.A-5.b#7b829f92','4.2.6.A-5.c#843b4071']
    for doc in source['sources']:
        for row in doc['paragraphs']:
            assert hashlib.sha256(row['text'].encode()).hexdigest() == row['text_sha256']


def test_missing_annual_velocity_percentile_is_explicit_unknown():
    result = check(ckd_annual_growth_velocity_percentile=None)
    assert result['violation']['severity'] == 'review'
    assert 'ckd_annual_growth_velocity_percentile' in result['missing_inputs']


def test_current_source_first_day_inclusive_for_growth_criterion():
    assert failed(check(drug_claim_date=date(2024,5,17), ckd_annual_growth_velocity_percentile=25),
                  'ckd_annual_growth_velocity_percentile')


@pytest.mark.parametrize('drug', ['somatrogon','büyüme hormonu','mecasermin'])
def test_unrelated_medicine_cannot_get_ckd_growth_comparisons(drug):
    result = check(drug_name=drug, ckd_annual_growth_velocity_percentile=100)
    assert 'ckd_annual_growth_velocity_percentile' not in (result['violation'] or {}).get('growth_hormone_failed_criteria', [])

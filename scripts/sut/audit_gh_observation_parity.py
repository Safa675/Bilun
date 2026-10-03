"""Compare GH receipts against an explicitly supplied reviewed GH44 baseline.

Run from the candidate root with --baseline PATH --manifest PATH. This audit
does not call network services or mutate source files. A JSON result includes
the executed binding map; it is not a full-clause coverage report.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import random
import sys

from src.bilun.domain.claims.growth_hormone import CKD_GH_BOOLEAN_FIELDS, PWS_FIELDS
from src.bilun.domain.prose_rules.drug_indication import list_drug_indication_rules
from src.bilun.domain.prose_rules._drug_indication.runtime_observations import ClinicalObservationCollector
from src.bilun.domain.prose_rules._drug_indication.pediatric_gh_initiation import evaluate_pediatric_gh_initiation_checks
from src.bilun.domain.prose_rules._drug_indication.ckd_growth_pathways import evaluate_ckd_growth_pathways
from src.bilun.domain.sut.runtime_coverage_schema import RuntimeCoverageResponse
from tests.unit.domain.prose_rules.test_gh_runtime_observations import CASES
from tests.unit.domain.prose_rules.test_growth_hormone_continuation import line
from tests.unit.domain.prose_rules.test_pediatric_gh_initiation import BASE as PEDIATRIC
from tests.unit.domain.prose_rules.test_ckd_gh_growth_pathways import CLEAR, BOOLS

MANIFEST_SHA = '10e84db8792b431c76d137e1d8b50008d90f24923125a5e2dba365ad73ebe91f'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    args = parser.parse_args()
    assert hashlib.sha256(args.manifest.read_bytes()).hexdigest() == MANIFEST_SHA
    manifest = json.loads(args.manifest.read_text())
    for row in manifest['files']:
        assert hashlib.sha256((args.baseline/row['path']).read_bytes()).hexdigest() == row['sha256'], row['path']
    rules = list_drug_indication_rules()
    cache = {}
    baseline_hashes = {}

    def original(fn):
        leaf = fn.__module__.split('.')[-1]
        if leaf not in cache:
            path = args.baseline/f'src/bilun/domain/prose_rules/_drug_indication/{leaf}.py'
            baseline_hashes[str(path.relative_to(args.baseline))] = hashlib.sha256(path.read_bytes()).hexdigest()
            name = fn.__module__.rsplit('.', 1)[0] + '._gh44_baseline_' + leaf
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            if leaf == 'ckd_growth_hormone':
                module.evaluate_ckd_growth_pathways = original(evaluate_ckd_growth_pathways)
            cache[leaf] = module
        return getattr(cache[leaf], fn.__name__)

    observed_map = {}
    cases = 0
    summaries = 0

    def check(fn, drug, rule=None):
        nonlocal cases, summaries
        observer = ClinicalObservationCollector(drug, 'growth_hormone', 'gh.atomic.v1.2026-10-02')
        kw = {'rule': rule, 'drug_line': drug} if rule is not None else {'drug_line': drug}
        expected = original(fn)(**kw)
        assert fn(**kw) == expected, (fn.__name__, 'without observer', cases)
        assert fn(**kw, observer=observer) == expected, (fn.__name__, 'with observer', cases)
        summary = observer.summary()
        RuntimeCoverageResponse.model_validate(summary)
        assert summary['available'] is True
        assert summary['source_clauses_fully_evaluated_count'] is None
        for receipt in observer.receipts:
            if receipt['kind'] != 'predicate':
                continue
            item = {k: receipt[k] for k in ('predicate_id', 'source_refs', 'clause_predicate_complete', 'family')}
            key = item['predicate_id']
            assert observed_map.get(key, item) == item
            observed_map[key] = item
        cases += 1
        summaries += 1

    rng = random.Random(20261003)
    defaults = {**dict.fromkeys(PWS_FIELDS, False), **dict.fromkeys(CKD_GH_BOOLEAN_FIELDS, False),
                'gh_patient_group': 'pediatric', 'gh_height_reference_sex': 'female',
                'pws_genetic_diagnosis_confirmed': True, 'ckd_growth_disorder_confirmed': True,
                'mecasermin_laron_syndrome_confirmed': True, 'ckd_parathyroid_hormone_pg_ml': 499,
                'gh_daily_dose_mg_per_kg': 0.05, 'pretreatment_annual_growth_velocity_cm': 1,
                'height_percentile': 20, 'mecasermin_daily_dose_mcg_per_kg': 120, **CLEAR}
    options = {'drug_claim_date': [None,date(2024,5,16),date(2024,5,17),date(2026,8,29),date(2026,10,2),date(2026,9,1)],
        'gh_treatment_phase': [None,'initiation','continuation'], 'epiphyses_closed': [False,True,None],
        'annual_growth_velocity_cm': [None,0,4,4.01,10], 'height_cm': [None,100,155,157,168],
        'bone_age_years': [None,13.9,14,20], 'gh_height_reference_sex': [None,'female','male'],
        'gh_daily_dose_mg_per_kg': [None,0.0449,0.045,0.05,0.0501],
        'ckd_parathyroid_hormone_pg_ml': [None,499.9,500,600],
        'mecasermin_daily_dose_mcg_per_kg': [None,119.9,120,120.1], 'height_percentile': [None,24.9,25,26]}
    for field in [*PWS_FIELDS, *CKD_GH_BOOLEAN_FIELDS, *BOOLS, 'mecasermin_laron_syndrome_confirmed']:
        options[field] = [None, False, True]
    for family, rule_id, fn in CASES:
        selected = [next(r for r in rules if r['rule_id'] == rule_id)] if rule_id else [r for r in rules if r.get('mecasermin_source_scope')]
        for rule in selected:
            for n in range(300):
                values = {**defaults, **{f: rng.choice(v) for f,v in options.items()}}
                if n < 2:
                    values = {**defaults, 'drug_claim_date': date(2026,10,2),
                              'gh_treatment_phase': 'initiation' if n else 'continuation'}
                    if n:
                        values.update(ckd_parathyroid_hormone_pg_ml=600,
                                      ckd_persistent_severe_secondary_hyperparathyroidism=True)
                check(fn, replace(line(), **values), rule)

    for pathway in ('standard','sga_case_1','sga_case_2','organic_or_surgical','neurosecretory_bioinactive'):
        rule = next(r for r in rules if pathway in r.get('gh_initiation_pathways', []))
        for n in range(400):
            values = {**PEDIATRIC, 'drug_claim_date': date(2026,10,2), 'gh_initiation_pathway': pathway,
                'gh_sga_birth_status_confirmed': True, 'gh_birth_weight_for_gestational_age_sds': -2.1,
                'gh_birth_length_for_gestational_age_sds': -2.1, 'gh_current_height_sds': -2.6,
                'gh_parent_adjusted_height_sds': -1.1, 'gh_last_year_growth_velocity_sds': -0.1,
                'gh_pubertal_growth_assessment_completed': True}
            if n:
                values.update(gh_chronological_age_years=rng.choice([None,1.5,2.05,3,4,4.05,8.2]),
                    gh_reported_growth_age_band=rng.choice([None,'0_2_years','2_1_4_years','4_1_prepubertal','pubertal']),
                    gh_pubertal_status=rng.choice([None,'pubertal','prepubertal']),
                    gh_sga_birth_status_confirmed=rng.choice([True,False,None]),
                    gh_pubertal_growth_assessment_completed=rng.choice([True,False,None]),
                    epiphyses_closed=rng.choice([True,False,None]),
                    bone_age_years=rng.choice([None,2,6.2,6.2001]),
                    annual_growth_velocity_cm=rng.choice([None,4.9,5,7,10]))
                for f in ('gh_birth_weight_for_gestational_age_sds','gh_birth_length_for_gestational_age_sds',
                          'gh_current_height_sds','gh_parent_adjusted_height_sds','gh_last_year_growth_velocity_sds'):
                    values[f]=rng.choice([None,-2.6,-2.5,-2.1,-2,-1.1,-1,-0.1,0,0.1])
                if n % 10 == 0:
                    values['drug_claim_date']=rng.choice([None,date(2024,5,16)])
            check(evaluate_pediatric_gh_initiation_checks, replace(line(), **values), rule)
    # Guarantee every printed velocity branch is actually reached.
    rule=next(r for r in rules if 'standard' in r.get('gh_initiation_pathways', []))
    for band,age in [('0_2_years',1.5),('2_1_4_years',3),('4_1_prepubertal',8.2)]:
        check(evaluate_pediatric_gh_initiation_checks, replace(line(), **{**PEDIATRIC,
            'gh_chronological_age_years':age,'gh_reported_growth_age_band':band}), rule)
    for flags in itertools.product([True,False,None], repeat=5):
        for pct,sds in [(2.9,-2.1),(3,-2),(2.9,None),(3,-2.1)]:
            check(evaluate_ckd_growth_pathways, replace(line(), **{**CLEAR, **dict(zip(BOOLS,flags)),
                'ckd_height_age_sex_percentile':pct,'ckd_height_age_sex_sds':sds}))
    assert len(observed_map) == 52, sorted(observed_map)
    print(json.dumps({'baseline_manifest_sha256':MANIFEST_SHA, 'baseline_leaf_sha256':baseline_hashes,
        'cases':cases, 'unchanged_without_observer':cases, 'unchanged_with_observer':cases,
        'valid_summaries':summaries, 'distinct_executed_bindings':len(observed_map),
        'predicates':[observed_map[k] for k in sorted(observed_map)]}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

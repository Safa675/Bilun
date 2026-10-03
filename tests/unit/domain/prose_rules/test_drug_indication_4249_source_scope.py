"""SMA source-context regressions: SUT A/B are types, .1/.2 are medications.

RG 26/04/2025-32882/7, effective 06/05/2025. These verify source and
candidate routing, not unimplemented clinical exclusion/monitoring predicates.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.sut.rule_sources import load_drug_section_rules, validate_rule_set_payload
from src.bilun.domain.prose_rules._drug_indication.routing import _drug_rule_candidates

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[4]
CORPUS = ROOT / 'data/gazette/prose_rules/drug_indication_prose.json'

HEADINGS = {
    '4.2.49.A.1': ('nusinersen', '4.2.49.A#f57da6c0'),
    '4.2.49.A.2': ('risdiplam', '4.2.49.A#c2df3999'),
    '4.2.49.B.1': ('nusinersen', '4.2.49.B#1a8f10e4'),
    '4.2.49.B.2': ('risdiplam', '4.2.49.B#58c3e3be'),
}


def scoped_rules():
    payload = json.loads(CORPUS.read_text())
    return [r for r in payload['rules'] if r['sut_section'] in ('4.2.49.A', '4.2.49.B')]


@pytest.mark.parametrize('rule', scoped_rules(), ids=lambda r: r['rule_id'])
def test_every_sma_rule_routes_only_to_its_heading_medication(rule):
    expected, heading = HEADINGS[rule['source_subsection']]
    other = 'risdiplam' if expected == 'nusinersen' else 'nusinersen'
    assert rule['source_heading_key'] == heading
    assert rule['source_effective_date'] == '2025-05-06'
    assert _drug_rule_candidates(expected, [rule])[0] == [rule]
    assert _drug_rule_candidates(other, [rule])[0] == []
    assert expected in rule['rule_id']
    assert other not in rule['rule_id']
    assert len(rule['supersedes_rule_ids']) == 1
    assert all('#' in cite and not cite.startswith('C00') for cite in rule['gate_b_sources'])


def test_same_text_coverage_and_monitoring_keep_distinct_heading_context():
    rules = scoped_rules()
    for sub in HEADINGS:
        coverage = [r for r in rules if r['source_subsection'] == sub and 'all_criteria' in r['rule_id']]
        monitoring = [r for r in rules if r['source_subsection'] == sub and 'multidisciplinary' in r['rule_id']]
        assert len(coverage) == len(monitoring) == 1
    # Identical paragraph hashes are not sufficient identity across A.1/A.2.
    a_coverage = [r for r in rules if r['sut_section'] == '4.2.49.A' and 'all_criteria' in r['rule_id']]
    assert a_coverage[0]['gate_b_sources'][0].split('@within:')[0] == a_coverage[1]['gate_b_sources'][0].split('@within:')[0]
    assert a_coverage[0]['gate_b_sources'] != a_coverage[1]['gate_b_sources']
    assert a_coverage[0]['source_heading_key'] != a_coverage[1]['source_heading_key']


def test_lumbar_and_csf_source_scopes_never_select_risdiplam():
    rules = [r for r in scoped_rules() if 'shunt' in r['rule_id'] or 'lumbar' in r['rule_id']]
    assert len(rules) == 3
    assert not _drug_rule_candidates('risdiplam', rules)[0]
    assert len(_drug_rule_candidates('nusinersen sodium', rules)[0]) == 3


def test_yaml_and_compiled_sma_corpus_stay_in_sync():
    source = load_drug_section_rules('4.2.49.A') + load_drug_section_rules('4.2.49.B')
    assert sorted(source, key=lambda r: r['rule_id']) == sorted(scoped_rules(), key=lambda r: r['rule_id'])
    validate_rule_set_payload(json.loads(CORPUS.read_text()), 'drug_indication_prose')


@pytest.mark.parametrize('rule', scoped_rules(), ids=lambda r: r['rule_id'])
def test_actual_source_resolver_never_crosses_medication_heading(rule):
    import polars as pl
    from scripts.sut.prose.clause_identity import resolve_gate_b_ref_to_clause_ids
    frame = pl.read_parquet(ROOT / 'data/gazette/sut_clauses.parquet')
    heading = frame.filter(pl.col('clause_key') == rule['source_heading_key'])
    assert heading.height == 1
    start = heading['paragraph_index'][0]
    next_heading = frame.filter((pl.col('clause_type') == 'section_heading') & pl.col('is_in_force') & (pl.col('paragraph_index') > start))['paragraph_index'].min()
    for reference in rule['gate_b_sources']:
        ids = resolve_gate_b_ref_to_clause_ids(reference, frame, encode_eligible_only=True)
        assert len(ids) == 1
        paragraph = frame.filter(pl.col('clause_id').is_in(ids))['paragraph_index'][0]
        assert start < paragraph < next_heading
        shifted = frame.with_columns((pl.col('paragraph_index') + 100).alias('paragraph_index')).reverse()
        assert resolve_gate_b_ref_to_clause_ids(reference, shifted, encode_eligible_only=True) == ids


@pytest.mark.parametrize('heading', ['4.2.49.A#deadbeef', '4.2.49.A#c2df3999@within:4.2.49.A#f57da6c0'])
def test_heading_scope_fails_closed_for_unknown_or_nested_heading(heading):
    import polars as pl
    from scripts.sut.prose.clause_identity import UnknownClauseCiteError, resolve_gate_b_ref_to_clause_ids
    frame = pl.read_parquet(ROOT / 'data/gazette/sut_clauses.parquet')
    with pytest.raises(UnknownClauseCiteError):
        resolve_gate_b_ref_to_clause_ids('4.2.49.A.(1)#e6be0652@within:' + heading, frame)


def test_source_ref_cannot_leak_beyond_containing_heading():
    import polars as pl
    from scripts.sut.prose.clause_identity import UnknownClauseCiteError, resolve_gate_b_ref_to_clause_ids
    frame = pl.read_parquet(ROOT / 'data/gazette/sut_clauses.parquet')
    # CSF shunt restriction belongs to nusinersen, never the next risdiplam heading.
    with pytest.raises(UnknownClauseCiteError):
        resolve_gate_b_ref_to_clause_ids('4.2.49.A.c#75d4ce7f@within:4.2.49.A#c2df3999', frame)

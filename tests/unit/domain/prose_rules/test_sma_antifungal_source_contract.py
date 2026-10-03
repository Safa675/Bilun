"""Check executable family references against captured official clause text."""
import json
from pathlib import Path

import pytest

from scripts.sut.prose.clause_identity import content_hash
from scripts.sut.rule_sources import load_drug_section_rules
from src.bilun.domain.prose_rules._drug_indication.routing import _drug_rule_candidates
from src.bilun.domain.prose_rules._drug_indication.clinical_sma import SOURCE_REFS

ROOT = Path(__file__).resolve().parents[4]


def rules():
    return json.loads((ROOT/'data/gazette/prose_rules/drug_indication_prose.json').read_text())['rules']


def test_captured_government_source_keys_recompute_and_cover_executed_predicates():
    source = json.loads((ROOT/'data/gazette/clinical_sources/sma_antifungal_2026_10.json').read_text())
    keys = set()
    for row in source['clauses']:
        assert row['content_hash'] == content_hash(row['in_force_text'])
        assert row['clause_key'].endswith('#' + row['content_hash'])
        keys.add(row['clause_key'])
    assert set(SOURCE_REFS) <= keys
    assert {'4.2.23.(5)#1234522e', '4.2.23.(1)#7976531d', '4.2.23.(2)#9e75077a',
            '4.2.23.(3)#cf0aee43', '4.2.23.(1)#9dd6786c', '4.2.23.(2)#fe3010eb'} <= keys
    assert source['verified_source_date'] == '2026-10-02'
    assert source['verification_status'] == 'ai_generated_pending_review'


@pytest.mark.parametrize('rule_id,drug,not_drugs,key', [
    ('4.2.23.neutropenia_prophylaxis_nopay', 'mikafungin', ['posakonazol','itrakonazol','vorikonazol','flukonazol'], '4.2.23.(3)#cf0aee43'),
    ('4.2.23.bucket_b.C006102', 'posakonazol', ['amfoterisin'], '4.2.23.(3)#84014798'),
])
def test_repaired_antifungal_selector_and_exact_source(rule_id, drug, not_drugs, key):
    rule = next(r for r in rules() if r['rule_id'] == rule_id)
    assert _drug_rule_candidates(drug, [rule])[0] == [rule]
    assert key in rule['gate_b_sources']
    for other in not_drugs:
        assert _drug_rule_candidates(other, [rule])[0] == []
    assert rule['verification_status'] == 'ai_generated_pending_review'


def test_source_yaml_and_compiled_antifungal_rows_match():
    by_id = {r['rule_id']:r for r in rules()}
    for row in load_drug_section_rules('4.2.23'):
        assert row == by_id[row['rule_id']]


def test_unknown_or_explicit_false_booleans_never_disappear_from_source_contract():
    # Guard the necessary-fact contract: this is intentionally partial, so
    # source prose cannot silently become a complete eligibility assertion.
    for row in rules():
        if row.get('clinical_constraint_set') in {'sma_safety_2025','antifungal_source_constraints'}:
            assert row['verification_status'] == 'ai_generated_pending_review'

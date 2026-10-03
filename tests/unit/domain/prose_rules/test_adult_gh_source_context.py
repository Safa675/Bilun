"""Adult closed-epiphysis intro is source context, not an eligibility predicate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.bilun.domain.prose_rules.drug_indication import list_drug_indication_rules
from tests.unit.domain.prose_rules.test_pediatric_gh_continuation import evaluate

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[4]


def test_parent_and_children_preserve_closed_epiphysis_source_condition_only():
    source = json.loads((ROOT/'data/gazette/source_evidence/adult_gh_closed_epiphysis_context.json').read_text())
    assert source['source_only'] is True
    assert source['runtime_branch_eligibility_implemented'] is False
    assert source['predicate_ids'] == []
    assert source['source_applicability_condition'] == {'field': 'epiphyses_closed', 'value': True,
                                                        'inferred_from_adult_age': False}
    assert source['parent_source_key'] == '4.2.6.A-2.(2)#5589013c'
    assert len(source['child_source_keys']) == 2
    rule = next(r for r in list_drug_indication_rules() if r['rule_id']=='4.2.6.adult_somatropin_board_report')
    assert rule['source_fragment_keys'] == [source['parent_source_key'], *source['child_source_keys']]
    assert source['parent_source_key'] not in rule['gate_b_sources']
    for doc in source['sources']:
        assert len(doc['paragraphs']) == 10
        for row in doc['paragraphs']:
            assert hashlib.sha256(row['text'].encode()).hexdigest() == row['text_sha256']
            assert ''.join(r['text'] for r in row['runs'] if not r['struck']).strip() == row['active_text']


@pytest.mark.parametrize('drug', ['somatrogon', 'NGENLA (SOMATROGON)', 'büyüme hormonu', 'buyume hormonu'])
def test_unidentified_or_non_somatropin_drug_does_not_select_adult_somatropin_rule(drug):
    result = evaluate(drug_name=drug, gh_patient_group='adult', epiphyses_closed=True,
                      prescriber_specialty='endokrinoloji')
    assert result['selected_rule_id'] not in {'4.2.6.adult_somatropin_board_report',
                                             '4.2.6.A2.insulin_tolerance_test_peak_gh_report'}


def test_supported_adult_somatropin_report_behavior_is_preserved():
    result = evaluate(drug_name='GENOTROPIN (SOMATROPIN)', gh_patient_group='adult',
                      epiphyses_closed=True, prescriber_specialty='endokrinoloji')
    assert result['selected_rule_id'] == '4.2.6.adult_somatropin_board_report'
    assert result['violation'] is None

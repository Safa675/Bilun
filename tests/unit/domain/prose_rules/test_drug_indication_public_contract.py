"""Compatibility guarantees at the public drug-indication module boundary."""

from src.bilun.domain.prose_rules import drug_indication as prose
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _drug_line


def test_cached_corpus_and_shallow_rule_lists_keep_their_identity_contract() -> None:
    prose.load_drug_indication_rules.cache_clear()
    try:
        payload = prose.load_drug_indication_rules()
        first = prose.list_drug_indication_rules()
        second = prose.list_drug_indication_rules()

        assert prose.load_drug_indication_rules() is payload
        assert first == second == payload["rules"]
        assert first is not second and first is not payload["rules"]
        assert first and first[0] is second[0] is payload["rules"][0]
        first.pop()
        assert len(second) == len(payload["rules"])

        prose.load_drug_indication_rules.cache_clear()
        reloaded = prose.load_drug_indication_rules()
        assert reloaded is not payload
        assert reloaded == payload
        assert reloaded["rules"][0] is not payload["rules"][0]
    finally:
        prose.load_drug_indication_rules.cache_clear()


def test_explicit_empty_rules_do_not_load_the_default_corpus() -> None:
    inputs = {
        "drug_line": _drug_line(report_present=False),
        "claim": _claim(),
        "diagnoses": (),
    }
    default = prose.evaluate_drug_indication_line_detailed(**inputs, rules=None)
    empty = prose.evaluate_drug_indication_line_detailed(**inputs, rules=[])

    assert default["violation"]["violation_kind"] == "missing_board_report"
    assert empty["applicability_status"] == "not_in_encoded_corpus"
    assert empty["evaluation_status"] == "unavailable"
    assert empty["violation"] is None
    assert prose.evaluate_drug_indication_line(**inputs, rules=[]) is None

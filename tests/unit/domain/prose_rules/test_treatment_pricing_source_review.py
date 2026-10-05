"""An explicit source quarantine must precede treatment predicates."""

from copy import deepcopy

import pytest

from src.bilun.domain.billing import treatment_pricing_evaluations as adapter
from src.bilun.domain.billing.broad_rule_classification import BroadRuleClassifier
from src.bilun.domain.prose_rules import treatment_pricing as legacy
from tests.unit.domain.prose_rules.test_treatment_pricing_for_context import (
    _make_ctx, _make_header, _make_procedure,
)


_ORGAN_RULES = (
    "2.4.2.A.(2).non_covered_donor_organ_tissue_no_pay",
    "2.4.2.A.(4).domestic_organ_transfer_per_2_6",
    "2.4.2.A.(5).cadaver_donor_procurement_p911146_ek2c",
)
_SOURCE_REFS = ([], ["2.4.2.A.(2)#943077b8"], ["2.4.2.A.(2)#2ad7b196"])


def _assert_source_review(row):
    assert row["severity"] == "review"
    assert row["billable"] is None
    assert row["material_outcome"] == "review_required"
    assert row["annex_basis"] is None
    assert row["savings_try"] == row["risk_amount"] == 0
    assert row["details"]["source_status"] == "review_required"
    assert row["details"]["clinical_eligibility_complete"] is False


@pytest.mark.parametrize("rule_id", _ORGAN_RULES)
@pytest.mark.parametrize("source_refs", _SOURCE_REFS)
def test_source_review_precedes_legacy_predicate(monkeypatch, rule_id, source_refs):
    rule = deepcopy(next(r for r in legacy.load_treatment_pricing_rules()["rules"]
                         if r["rule_id"] == rule_id))
    rule.update(source_review_required=True, gate_b_sources=source_refs)

    def predicate_must_not_run(*args):
        pytest.fail("A source-quarantined rule compared treatment facts")

    monkeypatch.setattr(legacy, "_condition_matches", predicate_must_not_run)
    rows = legacy._evaluate({"rule_set_id": "treatment_pricing_2_4", "rules": [rule]}, {})
    assert len(rows) == 1
    _assert_source_review(rows[0])
    authored_message = rule["action"].get("denial_tr") or rule["action"].get("payment_tr")
    assert rows[0]["message"] != authored_message


@pytest.mark.parametrize("rule_id", _ORGAN_RULES)
@pytest.mark.parametrize("source_refs", _SOURCE_REFS)
def test_source_review_precedes_typed_predicate_and_classification(monkeypatch, rule_id, source_refs):
    ruleset = deepcopy(legacy.load_treatment_pricing_rules())
    rule = next(r for r in ruleset["rules"] if r["rule_id"] == rule_id)
    rule.update(source_review_required=True, gate_b_sources=source_refs)
    monkeypatch.setattr(adapter, "load_treatment_pricing_rules", lambda: ruleset)
    original = adapter._observe_condition

    def observe(condition, flat):
        if condition is rule["condition"]:
            pytest.fail("A source-quarantined rule compared treatment facts")
        return original(condition, flat)

    monkeypatch.setattr(adapter, "_observe_condition", observe)
    ctx = _make_ctx(header=_make_header(), procedure_lines=(
        _make_procedure(code="P911146", category="organ_transplant"),
    ))
    batch = adapter.evaluate_treatment_pricing("P1", ctx)
    evaluation = next(e for e in batch.evaluations if e.rule_id == rule_id)
    assert evaluation.evaluation_status == "unavailable"
    assert evaluation.decision is None
    assert evaluation.reason == "source_review_required"
    assert evaluation.missing_inputs == evaluation.required_inputs == []
    assert not any(m.rule_id == rule_id for m in batch.matches)
    raw = next(r for r in batch.legacy_rows if r.rule_id == rule_id)
    _assert_source_review(raw.legacy_row)
    result = BroadRuleClassifier(ctx).classify(evaluation, raw)
    assert result.disposition == "unavailable" and result.finding is None


@pytest.mark.parametrize("marker", ["absent", False, "true", None])
def test_source_marker_is_strict_and_unaffected_rules_preserve_behavior(monkeypatch, marker):
    authored = deepcopy(legacy.load_treatment_pricing_rules())
    rule = next(r for r in authored["rules"]
                if r["rule_id"] == "2.4.4.F-5.(3).robotic_rehab_ek2c_pricing")
    if marker != "absent":
        rule["source_review_required"] = marker
    ruleset = {"rule_set_id": "treatment_pricing_2_4", "rules": [rule]}
    monkeypatch.setattr(adapter, "load_treatment_pricing_rules", lambda: authored)
    ctx = _make_ctx(header=_make_header(), procedure_lines=(
        _make_procedure(code="P000001", category="robotic_rehab"),
    ))
    if marker not in ("absent", False):
        with pytest.raises(ValueError, match="source_review_required"):
            legacy._evaluate(ruleset, {})
        with pytest.raises(ValueError, match="source_review_required"):
            adapter.evaluate_treatment_pricing("P1", ctx)
        return
    assert legacy._evaluate(ruleset, {"procedure_category": "other"}) == []
    rows = legacy._evaluate(ruleset, {"procedure_category": "robotic_rehab"})
    assert len(rows) == 1
    assert rows[0]["billable"] is True and rows[0]["material_outcome"] == "must_bill"
    assert rows[0]["message"] == rule["action"]["payment_tr"]
    assert rows[0]["details"] == {"prose_rule_set": "treatment_pricing_2_4"}
    batch = adapter.evaluate_treatment_pricing("P1", ctx)
    evaluation = next(e for e in batch.evaluations if e.rule_id == rule["rule_id"])
    assert evaluation.evaluation_status == "evaluated" and evaluation.decision == "matched"
    raw = next(r for r in batch.legacy_rows if r.rule_id == rule["rule_id"])
    assert raw.legacy_row == rows[0]

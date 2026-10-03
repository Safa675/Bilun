"""Full-corpus source reviews survive broad routes and supplemental-only selection."""

from copy import deepcopy
from dataclasses import replace
from datetime import date

import pytest

from src.bilun.domain.prose_rules.drug_indication import (
    evaluate_drug_indication_line_detailed,
    list_drug_indication_rules,
)
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _diagnosis, _drug_line

ALIASES = ["eritropoietin", "epoetin", "binocrit", "eprex", "mircera",
           "retacrit", "neo recormon", "metoksipolietilen glikol"]
DAY = date(2026, 10, 2)
MDS = "4.2.9.mds_esa_hematology_report"
VOS = "4.2.75.peds.child_endocrinology_metabolism_1yr_coverage"
REFS = {"prose:4.2.9.A-2#17efb08b", "4.2.9.A.(1)#d8313b78",
        "4.2.9.A.(3)#a9d0cf5b", "4.2.9.A.(4)#ed1d5fdf"}


def _evaluate(drug, *, primary="D46.1", secondary=None, report=True,
              duration=1, day=DAY, corpus=None):
    line = replace(_drug_line(drug_name=drug, report_present=report,
                              report_duration_months=duration,
                              prescriber_specialty="hematoloji"), drug_claim_date=day)
    claim = _claim(primary_icd10=primary)
    diagnoses = [] if secondary is None else [_diagnosis(code=secondary, claim_id=claim.claim_id)]
    return evaluate_drug_indication_line_detailed(
        drug_line=line, claim=claim, diagnoses=diagnoses,
        rules=list_drug_indication_rules() if corpus is None else corpus,
    )


@pytest.mark.parametrize("drug", ALIASES)
@pytest.mark.parametrize("report", [None, False, True])
@pytest.mark.parametrize("duration", [None, 0, 1, 3, 12])
def test_mds_source_review_cannot_be_bypassed_by_report_fields(drug, report, duration):
    corpus = list_drug_indication_rules()
    args = {"report": report, "duration": duration}
    out = _evaluate(drug, **args, corpus=corpus)
    assert out == _evaluate(drug, **args, corpus=list(reversed(corpus)))
    assert out["selected_rule_id"] == MDS
    assert out["violation"]["sut_section"] == "4.2.9.A-2"
    assert out["violation"]["severity"] == "review"
    assert out["clinical_eligibility_complete"] is False
    guard = out["clinical_restrictions"][0]
    assert guard["criterion_status"] == "unknown" and guard["checks"] == []
    assert REFS <= set(guard["source_refs"])
    assert "remaining_sut_clinical_criteria" in out["missing_inputs"]


@pytest.mark.parametrize("drug", ALIASES)
@pytest.mark.parametrize("day", [None, date(2024, 5, 16), date(2026, 10, 3)])
def test_missing_or_historical_dates_never_turn_mds_source_review_into_clearance(drug, day):
    out = _evaluate(drug, day=day)
    assert out["violation"]["severity"] == "review"
    assert out["clinical_eligibility_complete"] is False
    assert out["clinical_restrictions"][0]["checks"] == []


@pytest.mark.parametrize("drug", ALIASES + ["darbepoetin", "aranesp"])
@pytest.mark.parametrize("primary,secondary", [("D46.1", "N18.5"), ("N18.5", "D46.1")])
def test_mixed_mds_ckd_scopes_remain_ambiguous(drug, primary, secondary):
    out = _evaluate(drug, primary=primary, secondary=secondary)
    assert out["applicability_status"] == "ambiguous_route"
    assert out["selected_rule_id"] is None
    assert out["violation"]["violation_kind"] == "ambiguous_route"
    assert "route_discriminator" in out["missing_inputs"]


@pytest.mark.parametrize("drug", ALIASES + ["darbepoetin", "aranesp"])
def test_unmatched_mds_guards_do_not_change_pure_ckd_behavior(drug):
    corpus = list_drug_indication_rules()
    without_mds = [r for r in corpus if r.get("sut_section") != "4.2.9.A-2"]
    before = _evaluate(drug, primary="N18.5", corpus=without_mds)
    after = _evaluate(drug, primary="N18.5", corpus=corpus)
    for key in ("selected_rule_id", "applicability_status", "evaluation_status", "missing_inputs"):
        assert after[key] == before[key]
    assert (after.get("violation") or {}).get("violation_kind") == (
        before.get("violation") or {}).get("violation_kind")
    assert after.get("clinical_restrictions") == before.get("clinical_restrictions")


@pytest.mark.parametrize("report", [None, False, True])
@pytest.mark.parametrize("day", [None, date(2024, 5, 16), DAY])
def test_medicine_scoped_vosoritide_review_survives_full_corpus(report, day):
    corpus = list_drug_indication_rules()
    out = _evaluate("vosoritide", primary="Q77.4", duration=12, report=report, day=day)
    assert out == _evaluate("vosoritide", primary="Q77.4", duration=12, report=report,
                            day=day, corpus=list(reversed(corpus)))
    assert out["selected_rule_id"] == VOS
    assert out["violation"]["sut_section"] == "4.2.75"
    assert out["violation"]["severity"] == "review"
    assert out["clinical_eligibility_complete"] is False
    assert out["clinical_restrictions"][0]["checks"] == []


def test_competing_guarded_supplemental_scopes_remain_ambiguous():
    corpus = deepcopy(list_drug_indication_rules())
    other = deepcopy(next(r for r in corpus if r["rule_id"] == VOS))
    other["rule_id"] = "competing_vosoritide_source_scope"
    other["report_duration_months"] = 6
    corpus.append(other)
    out = _evaluate("vosoritide", primary="Q77.4", duration=None, corpus=corpus)
    assert out["selected_rule_id"] is None
    assert out["violation"]["violation_kind"] == "ambiguous_route"


def test_ordinary_supplemental_rule_does_not_acquire_guarded_source_scope():
    corpus = deepcopy(list_drug_indication_rules())
    rule = next(r for r in corpus if r["rule_id"] == VOS)
    rule.pop("source_clinical_scope_incomplete")
    out = _evaluate("vosoritide", primary="Q77.4", corpus=corpus)
    assert out["applicability_status"] == "not_in_encoded_corpus"
    assert out["selected_rule_id"] is None
    assert out.get("clinical_restrictions") is None

"""Same-report prescribing relation from §4.2.9.A-2#17efb08b stays explicit.

The pinned, strike-aware source proof is exercised by test_mds_clinical_draft.
These follow-up cases isolate its documentary relation without changing phase,
date, substance or three-valued aggregation policy, or either runtime gate.
"""
from dataclasses import asdict
from datetime import date, timedelta
import json

import pytest

from src.bilun.domain.prose_rules._drug_indication import clinical_mds as draft
from tests.unit.domain.claims.test_mds_evidence_transport import DAY, facts
from tests.unit.domain.prose_rules.test_mds_clinical_draft import (
    INITIATION, REPORT, authority, candidate, line,
)

FIELD = "prescription_based_on_same_hematology_report"
PATH = "mds_evidence." + FIELD


def _transport(evidence, transport):
    if transport == "typed":
        return evidence
    payload = asdict(evidence)
    if transport == "mapping":
        return payload
    return json.dumps(payload, default=lambda value: value.isoformat() if type(value) is date else value)


@pytest.mark.parametrize("phase", ["initiation", "continuation"])
@pytest.mark.parametrize("drug,substance", [("epoetin alfa", "epoetin_alfa"), ("epoetin beta", "epoetin_beta")])
@pytest.mark.parametrize("relation,status,check", [
    (True, "criterion_clear", "pass"),
    (False, "restriction_not_met", "fail"),
    (None, "unknown", "unknown"),
])
def test_same_report_relation_is_required_for_both_applicable_phases_and_substances(
    phase, drug, substance, relation, status, check,
):
    evidence = facts(phase=phase, substance=substance, **{FIELD: relation})
    outcome = candidate(evidence, drug=drug)
    assert outcome["criterion_status"] == status
    assert {"field": PATH, "status": check} in outcome["checks"]
    assert outcome["missing_inputs"] == ([PATH] if relation is None else [])
    assert outcome["clinical_eligibility_complete"] is False
    assert outcome["verification_status"] == "ai_generated_pending_review"
    assert "prose:4.2.9.A-2#17efb08b" in outcome["source_refs"]


@pytest.mark.parametrize("transport", ["typed", "mapping", "json"])
@pytest.mark.parametrize("relation,status", [
    (True, "criterion_clear"), (False, "restriction_not_met"), (None, "unknown"),
    (0, "unknown"), (1, "unknown"), ("true", "unknown"), ("false", "unknown"),
    ({}, "unknown"), ([], "unknown"),
])
def test_same_report_fact_is_revalidated_without_truthy_coercion_across_transport(transport, relation, status):
    evidence = _transport(facts(**{FIELD: relation}), transport)
    outcome = candidate(evidence)
    assert outcome["criterion_status"] == status
    assert outcome["missing_inputs"] == ([PATH] if status == "unknown" else [])
    assert outcome["clinical_eligibility_complete"] is False


@pytest.mark.parametrize("relation,status", [(None, "unknown"), (False, "restriction_not_met")])
def test_complete_matching_report_metadata_does_not_infer_or_override_the_relationship(relation, status):
    payload = asdict(facts(prescribed_by_specialty="hematology", **{FIELD: relation}))
    payload.update({
        "board_report_present": True, "prescriber_specialty": "hematoloji",
        "report_id": "same-id", "prescription_report_id": "same-id", "report_valid": True,
    })
    outcome = candidate(payload, drug_specialty_board_report_present=True, prescriber_specialty="hematoloji")
    assert outcome["criterion_status"] == status
    assert {"field": PATH, "status": "unknown" if relation is None else "fail"} in outcome["checks"]
    assert outcome["missing_inputs"] == ([PATH] if relation is None else [])


def test_existing_known_failure_with_missing_relationship_retains_failure_and_missing_fact():
    outcome = candidate(facts(hb_value=11, **{FIELD: None}))
    assert outcome["criterion_status"] == "restriction_not_met"
    assert outcome["missing_inputs"] == [PATH]
    assert {"field": "mds_evidence.hb_value", "status": "fail"} in outcome["checks"]
    assert {"field": PATH, "status": "unknown"} in outcome["checks"]
    assert outcome["clinical_eligibility_complete"] is False


def test_known_false_relationship_with_missing_measurement_retains_existing_failure_priority():
    outcome = candidate(facts(blast_value=None, **{FIELD: False}))
    assert outcome["criterion_status"] == "restriction_not_met"
    assert outcome["missing_inputs"] == ["mds_evidence.blast_value"]
    assert {"field": "mds_evidence.blast_value", "status": "unknown"} in outcome["checks"]
    assert {"field": PATH, "status": "fail"} in outcome["checks"]
    assert outcome["clinical_eligibility_complete"] is False


@pytest.mark.parametrize("date_change,missing", [
    ({"applies_on": DAY - timedelta(days=1)}, "mds_evidence.applies_on"),
    ({"assessment_date": DAY + timedelta(days=1)}, "mds_evidence.assessment_date"),
])
def test_date_scope_still_precedes_even_a_known_false_relationship(monkeypatch, date_change, missing):
    monkeypatch.setattr(draft.Reader, "test", lambda *_: pytest.fail("date scope attempted a predicate"))
    outcome = candidate(facts(**date_change, **{FIELD: False}))
    assert outcome["criterion_status"] == "not_evaluated"
    assert outcome["missing_inputs"] == [missing]
    assert outcome["checks"] == []


@pytest.mark.parametrize("phase,rule,missing", [
    ("restart", REPORT, "mds_evidence.phase_interpretation"),
    ("continuation", INITIATION, "mds_evidence.phase_context_reconciliation"),
])
def test_unsupported_phase_still_stops_before_same_report_predicate(monkeypatch, phase, rule, missing):
    monkeypatch.setattr(draft.Reader, "test", lambda *_: pytest.fail("phase scope attempted a predicate"))
    outcome = candidate(facts(phase=phase, **{FIELD: False}), rule=rule)
    assert outcome["criterion_status"] == "unknown"
    assert outcome["missing_inputs"] == [missing]
    assert all(check["field"] != PATH for check in outcome["checks"])


@pytest.mark.parametrize("changes,codes,missing", [
    ({"indication": None}, None, ["mds_evidence.indication"]),
    ({"substance": "epoetin_beta"}, None,
     ["mds_evidence.substance", "mds_evidence.substance_context_reconciliation"]),
    ({}, ["D46.1", "N18.5"], ["mds_evidence.indication_context_reconciliation"]),
])
def test_existing_diagnosis_and_substance_guards_precede_a_known_false_relationship(
    monkeypatch, changes, codes, missing,
):
    monkeypatch.setattr(draft.Reader, "test", lambda *_: pytest.fail("context guard attempted a predicate"))
    outcome = candidate(facts(**changes, **{FIELD: False}), codes=codes)
    assert outcome["criterion_status"] == "unknown"
    assert outcome["missing_inputs"] == missing
    assert all(check["field"] != PATH for check in outcome["checks"])


@pytest.mark.parametrize("relation", [True, False, None])
def test_pure_ckd_and_excluded_esa_still_receive_no_mds_relationship_outcome(monkeypatch, relation):
    monkeypatch.setattr(draft.Reader, "test", lambda *_: pytest.fail("excluded scope attempted a predicate"))
    ckd = line(evidence=facts(indication="ckd_anemia", **{FIELD: relation}))
    assert draft.evaluate_mds_clinical_candidate(ckd, REPORT, codes=["N18.5"]) is None
    assert draft.evaluate_mds_clinical_draft(ckd, REPORT, codes=["N18.5"]) is None
    for drug in ("darbepoetin", "epoetin", "epoetin zeta"):
        excluded = line(drug, evidence=facts(**{FIELD: relation}))
        assert draft.evaluate_mds_clinical_candidate(excluded, REPORT) is None
        assert draft.evaluate_mds_clinical_draft(excluded, REPORT) is None


@pytest.mark.parametrize("source_status,released,missing", [
    ("admitted", False, ["mds_clinical_interpretation_release"]),
    ("review_required", True, ["verified_source_for_service_date"]),
    ("review_required", False, ["mds_clinical_interpretation_release", "verified_source_for_service_date"]),
])
@pytest.mark.parametrize("relation", [True, False, None])
def test_either_closed_runtime_gate_blocks_all_relationship_predicates(
    monkeypatch, source_status, released, missing, relation,
):
    calls = authority(monkeypatch, source_status)
    monkeypatch.setattr(draft, "_MDS_CLINICAL_INTERPRETATION_RELEASED", released)
    monkeypatch.setattr(draft, "_candidate", lambda *_: pytest.fail("closed runtime entered candidate"))
    outcome = draft.evaluate_mds_clinical_draft(line(evidence=facts(**{FIELD: relation})), REPORT)
    assert calls == [("mds_epoetin", DAY)]
    assert outcome["criterion_status"] == "not_evaluated"
    assert outcome["missing_inputs"] == missing
    assert outcome["checks"] == []
    assert outcome["clinical_eligibility_complete"] is False


def test_actual_unadmitted_family_and_hard_release_stay_closed_for_complete_relationship(monkeypatch):
    assert draft._MDS_CLINICAL_INTERPRETATION_RELEASED is False
    monkeypatch.setattr(draft, "_candidate", lambda *_: pytest.fail("unadmitted family entered candidate"))
    outcome = draft.evaluate_mds_clinical_draft(line(evidence=facts(**{FIELD: True})), REPORT)
    assert outcome["source_authority"]["family_id"] == "mds_epoetin"
    assert outcome["source_authority"]["status"] == "review_required"
    assert outcome["criterion_status"] == "not_evaluated"
    assert outcome["checks"] == []
    assert {"verified_source_for_service_date", "mds_clinical_interpretation_release"} <= set(outcome["missing_inputs"])

"""Strict draft facts and source/release gates for the two mesothelioma branches."""
from dataclasses import asdict
from datetime import date, datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from src.bilun.domain.claims.mesothelioma_evidence import (
    MesotheliomaEvidence,
    parse_mesothelioma_evidence,
)
from src.bilun.domain.prose_rules._drug_indication import clinical_mesothelioma_documents as draft
from src.bilun.domain.prose_rules._drug_indication.clinical import apply_clinical_restrictions

DAY = date(2026, 10, 2)
PEM = "4.2.14.C.pemetrexed_mesothelioma_board"
RAL = "4.2.14.C.raltitrexed_mesothelioma_board"


def facts(**changes):
    return MesotheliomaEvidence(**{
        "applies_on": DAY,
        "assessment_date": DAY,
        "diagnosis_site": "pleural",
        "board_report_present": True,
        "report_distinct_specialist_count": 3,
        "treatment_protocol_documented_in_report": True,
        "prescribed_by_specialist": True,
        **changes,
    })


def line(drug="pemetrexed", *, evidence=None, **changes):
    return SimpleNamespace(**{
        "drug_claim_line_id": "D1",
        "claim_id": "C1",
        "drug_name": drug,
        "drug_code": "",
        "drug_claim_date": DAY,
        "mesothelioma_evidence": facts() if evidence is None else evidence,
        "drug_specialty_board_report_present": True,
        "prescriber_specialty": "tıbbi onkoloji",
        **changes,
    })


def candidate(evidence=None, *, drug="pemetrexed", rule=PEM, codes=None, **changes):
    return draft.evaluate_mesothelioma_documentary_candidate(
        line(drug, evidence=evidence, **changes), rule, codes=codes,
    )


def authority(monkeypatch, status="admitted"):
    calls = []

    def resolve(family, service):
        calls.append((family, service))
        return SimpleNamespace(status=status, model_dump=lambda: {
            "family_id": family,
            "status": status,
            "service_date": service.isoformat() if service else None,
        })

    monkeypatch.setattr(draft, "resolve_source_authority", resolve)
    return calls


def test_mapping_json_and_typed_evidence_have_the_same_strict_facts():
    payload = {**asdict(facts()), "applies_on": DAY.isoformat(), "assessment_date": DAY.isoformat()}
    assert parse_mesothelioma_evidence(payload) == facts()
    assert parse_mesothelioma_evidence(json.dumps(payload)) == facts()
    assert parse_mesothelioma_evidence(MappingProxyType(payload)) == facts()
    assert parse_mesothelioma_evidence(facts()) == facts()


@pytest.mark.parametrize("value", [None, [], True, 3, "not JSON", "[]", "null", "true"])
def test_non_object_evidence_is_absent(value):
    assert parse_mesothelioma_evidence(value) is None


@pytest.mark.parametrize("value", [True, False, 3.0, 2.5, -1, "3", Decimal(3), float("inf"), float("nan")])
def test_specialist_count_rejects_bool_coercion_fractional_and_nonfinite_values(value):
    for supplied in ({"report_distinct_specialist_count": value},
                     facts(report_distinct_specialist_count=value)):
        assert parse_mesothelioma_evidence(supplied).report_distinct_specialist_count is None


@pytest.mark.parametrize("value", [0, 2, 3, 4, 10**1000])
def test_exact_nonnegative_counts_are_retained_without_float_conversion(value):
    assert parse_mesothelioma_evidence({"report_distinct_specialist_count": value}).report_distinct_specialist_count == value


@pytest.mark.parametrize("field", [
    "board_report_present", "treatment_protocol_documented_in_report", "prescribed_by_specialist",
])
@pytest.mark.parametrize("value", [0, 1, "true", "false", {}, []])
def test_booleans_are_revalidated_even_in_typed_objects(field, value):
    assert getattr(parse_mesothelioma_evidence(facts(**{field: value})), field) is None


@pytest.mark.parametrize("value", ["unknown", "C45.0", "Pleural", "other", True, [], {}])
def test_only_explicit_pleural_or_nonpleural_site_values_are_retained(value):
    assert parse_mesothelioma_evidence(facts(diagnosis_site=value)).diagnosis_site is None
    assert parse_mesothelioma_evidence(facts(diagnosis_site="nonpleural")).diagnosis_site == "nonpleural"


@pytest.mark.parametrize("field", ["applies_on", "assessment_date"])
@pytest.mark.parametrize("value", ["2026-10-2", "2026-02-30", "2026-10-02T00:00:00", datetime(2026, 10, 2)])
def test_dates_are_exact_and_typed_objects_do_not_bypass_validation(field, value):
    assert getattr(parse_mesothelioma_evidence(facts(**{field: value})), field) is None


@pytest.mark.parametrize("drug,rule", [("pemetrexed", PEM), ("raltitrexed", RAL)])
def test_candidate_all_documentary_facts_clear_only_necessary_draft_checks(drug, rule):
    outcome = candidate(drug=drug, rule=rule)
    assert outcome["criterion_status"] == "criterion_clear"
    assert len(outcome["checks"]) == 5
    assert all(check["status"] == "pass" for check in outcome["checks"])
    assert outcome["missing_inputs"] == []
    assert outcome["clinical_eligibility_complete"] is False
    assert outcome["verification_status"] == "ai_generated_pending_review"
    assert "runtime_coverage" not in outcome
    core = json.loads(Path("data/gazette/prose_rules/drug_indication_prose.json").read_text())
    selected = next(row for row in core["rules"] if row["rule_id"] == rule)
    assert outcome["source_refs"] == selected["gate_b_sources"]


def test_generic_report_presence_alone_cannot_clear_documentary_facts():
    outcome = candidate({"applies_on": DAY, "assessment_date": DAY, "diagnosis_site": "pleural"})
    assert outcome["criterion_status"] == "unknown"
    assert set(outcome["missing_inputs"]) == {
        "mesothelioma_evidence.board_report_present",
        "mesothelioma_evidence.report_distinct_specialist_count",
        "mesothelioma_evidence.treatment_protocol_documented_in_report",
        "mesothelioma_evidence.prescribed_by_specialist",
    }
    outcome = candidate({"applies_on": DAY, "assessment_date": DAY,
                         "diagnosis_site": "pleural", "board_report_present": True})
    assert outcome["criterion_status"] == "unknown"
    assert len(outcome["missing_inputs"]) == 3


@pytest.mark.parametrize("site", [None, "unknown", "nonpleural", "C45.0"])
def test_nonpleural_or_unknown_scope_stays_unresolved_before_negative_documentary_facts(site):
    outcome = candidate(facts(diagnosis_site=site, board_report_present=False,
                              report_distinct_specialist_count=2,
                              treatment_protocol_documented_in_report=False,
                              prescribed_by_specialist=False))
    assert outcome["criterion_status"] == "unknown"
    assert outcome["missing_inputs"] == ["mesothelioma_evidence.diagnosis_site"]
    assert outcome["checks"] == [{"field": "mesothelioma_evidence.diagnosis_site", "status": "unknown"}]


@pytest.mark.parametrize("code", ["C45.1", "C45.2", "C45.7", " c45.1 "])
def test_pleural_input_cannot_clear_contradictory_observed_nonpleural_coding(code):
    outcome = candidate(facts(report_distinct_specialist_count=2,
                              treatment_protocol_documented_in_report=False), codes=["C45.0", code])
    assert outcome["criterion_status"] == "unknown"
    assert set(outcome["missing_inputs"]) == {
        "mesothelioma_evidence.diagnosis_site", "mesothelioma_evidence.diagnosis_context_reconciliation",
    }
    assert outcome["checks"] == [{"field": "mesothelioma_evidence.diagnosis_site", "status": "unknown"}]


@pytest.mark.parametrize("codes", [None, [], ["C45"], ["C45.0"], ["C45.9"]])
def test_missing_unspecified_and_pleural_codes_never_supply_the_explicit_site_fact(codes):
    assert candidate(facts(diagnosis_site=None), codes=codes)["criterion_status"] == "unknown"
    assert candidate(codes=codes)["criterion_status"] == "criterion_clear"


@pytest.mark.parametrize("count,status", [(0, "restriction_not_met"), (2, "restriction_not_met"),
                                         (3, "criterion_clear"), (4, "unknown"), (10**1000, "unknown")])
def test_two_and_three_specialists_differ_and_wider_boards_need_interpretation(count, status):
    outcome = candidate(facts(report_distinct_specialist_count=count))
    assert outcome["criterion_status"] == status
    if count > 3:
        assert outcome["missing_inputs"] == ["mesothelioma_evidence.report_board_composition_interpretation"]


def test_false_report_with_three_members_and_protocol_is_never_all_clear():
    assert candidate(facts(board_report_present=False))["criterion_status"] == "restriction_not_met"


@pytest.mark.parametrize("field", ["treatment_protocol_documented_in_report", "prescribed_by_specialist"])
def test_missing_and_explicit_absent_documentary_conditions_are_distinct(field):
    missing = candidate(facts(**{field: None}))
    assert missing["criterion_status"] == "unknown"
    assert missing["missing_inputs"] == ["mesothelioma_evidence." + field]
    assert candidate(facts(**{field: False}))["criterion_status"] == "restriction_not_met"


@pytest.mark.parametrize("prescriber", ["hekim", "uzman hekim", "tıbbi onkoloji", "hematoloji"])
def test_prescriber_strings_never_establish_explicit_specialist_prescribing(prescriber):
    outcome = candidate(facts(prescribed_by_specialist=None), prescriber_specialty=prescriber)
    assert outcome["criterion_status"] == "unknown"
    assert outcome["missing_inputs"] == ["mesothelioma_evidence.prescribed_by_specialist"]


@pytest.mark.parametrize("drug,rule", [
    ("raltitrexed", PEM), ("pemetrexed", RAL), ("pemetrexedlike", PEM),
    ("pemetrexed", "4.2.14.C.(15).pemetrexed_nsclc_board"),
    ("raltitrexed", "4.2.14.C.raltitrexed_colorectal_board"), ("pemetrexed", None),
])
def test_only_exact_selected_drug_branch_pairs_receive_the_draft(drug, rule):
    supplied = line(drug)
    assert draft.evaluate_mesothelioma_documentary_candidate(supplied, rule) is None
    assert draft.evaluate_mesothelioma_documents(supplied, rule) is None


@pytest.mark.parametrize("changes,missing", [
    ({"drug_claim_date": None}, "drug_claim_date"),
    ({"evidence": facts(applies_on=DAY - timedelta(days=1))}, "mesothelioma_evidence.applies_on"),
    ({"evidence": facts(assessment_date=None)}, "mesothelioma_evidence.assessment_date"),
    ({"evidence": facts(assessment_date=DAY + timedelta(days=1))}, "mesothelioma_evidence.assessment_date"),
])
def test_candidate_requires_explicit_service_scope_and_nonfuture_assessment(changes, missing):
    outcome = candidate(**changes)
    assert outcome["criterion_status"] == "not_evaluated"
    assert outcome["checks"] == []
    assert outcome["missing_inputs"] == [missing]


def test_existing_source_catalogue_does_not_automatically_admit_the_new_family():
    outcome = draft.evaluate_mesothelioma_documents(line(), PEM)
    assert outcome["source_authority"]["family_id"] == "pleural_mesothelioma_documents"
    assert outcome["source_authority"]["status"] == "review_required"
    assert outcome["criterion_status"] == "not_evaluated"
    assert outcome["checks"] == []
    assert set(outcome["missing_inputs"]) == {
        "verified_source_for_service_date", "mesothelioma_documentary_interpretation_release",
    }
    assert outcome["clinical_eligibility_complete"] is False


def test_admitted_source_alone_cannot_execute_draft_predicates(monkeypatch):
    calls = authority(monkeypatch)
    outcome = draft.evaluate_mesothelioma_documents(line(evidence=facts(board_report_present=False)), PEM)
    assert calls == [("pleural_mesothelioma_documents", DAY)]
    assert outcome["criterion_status"] == "not_evaluated"
    assert outcome["missing_inputs"] == ["mesothelioma_documentary_interpretation_release"]
    assert outcome["checks"] == []


def test_test_only_interpretation_release_still_requires_exact_source_date_and_fact_dates(monkeypatch):
    authority(monkeypatch, "review_required")
    monkeypatch.setattr(draft, "_DOCUMENTARY_INTERPRETATION_RELEASED", True)
    outcome = draft.evaluate_mesothelioma_documents(line(), PEM)
    assert outcome["criterion_status"] == "not_evaluated"
    assert outcome["checks"] == []
    assert outcome["missing_inputs"] == ["verified_source_for_service_date"]
    authority(monkeypatch)
    outcome = draft.evaluate_mesothelioma_documents(line(evidence=facts(applies_on=None)), PEM)
    assert outcome["criterion_status"] == "not_evaluated"
    assert outcome["checks"] == []
    assert outcome["missing_inputs"] == ["mesothelioma_evidence.applies_on"]


def test_test_only_two_gate_release_still_prioritizes_nonpleural_context_reconciliation(monkeypatch):
    authority(monkeypatch)
    monkeypatch.setattr(draft, "_DOCUMENTARY_INTERPRETATION_RELEASED", True)
    outcome = draft.evaluate_mesothelioma_documents(line(), PEM, codes=["C45.1"])
    assert outcome["criterion_status"] == "unknown"
    assert "mesothelioma_evidence.diagnosis_context_reconciliation" in outcome["missing_inputs"]
    assert not any(check["status"] == "fail" for check in outcome["checks"])


def test_test_only_two_gate_release_all_clear_keeps_selected_source_guard_and_partial_review(monkeypatch):
    authority(monkeypatch)
    monkeypatch.setattr(draft, "_DOCUMENTARY_INTERPRETATION_RELEASED", True)
    supplied = line()
    outcome = draft.evaluate_mesothelioma_documents(supplied, PEM)
    assert outcome["criterion_status"] == "criterion_clear"
    assert outcome["clinical_eligibility_complete"] is False
    guard = {
        "constraint_set": "source_context_clinical_review", "criterion_status": "unknown",
        "missing_inputs": ["remaining_sut_clinical_criteria"], "checks": [],
        "source_refs": outcome["source_refs"], "clinical_eligibility_complete": False,
    }
    base = {
        "selected_rule_id": PEM,
        "clinical_restrictions": [guard],
        "violation": {"rule_id": PEM, "selected_rule_id": PEM, "sut_section": "4.2.14.C",
                      "severity": "review", "violation_kind": "needs_clinical_verification"},
    }
    from src.bilun.domain.prose_rules._drug_indication import clinical

    monkeypatch.setattr(clinical, "evaluate_clinical_restrictions", lambda *_: [outcome])
    combined = apply_clinical_restrictions(base, supplied, [])
    assert combined["selected_rule_id"] == PEM
    assert combined["clinical_restrictions"] == [guard, outcome]
    assert combined["violation"]["severity"] == "review"
    assert combined["clinical_eligibility_complete"] is False
    assert combined["violation"]["clinical_eligibility_complete"] is False

"""Service-date, partial-clinical and public-evidence safeguards for October SUT."""
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime
import hashlib
import json

import pytest
from pydantic import ValidationError

from src.bilun.api.public_responses import project_public_response
from src.bilun.api.schemas import DrugIndicationReviewResponse
from src.bilun.domain.billing.drug_indication_findings import evaluate_drug_indication_findings
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed
from src.bilun.domain.prose_rules._drug_indication.temporal import (
    _CATALOG, parse_service_date, temporal_drug_rules,
)
from src.bilun.shared.models import ClaimValidationRequest, DrugContext
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _drug_line


def _successor(name="pertuzumab"):
    return deepcopy(next(rule for rule in temporal_drug_rules() if name in rule["rule_id"]))


def _legacy(name="pertuzumab"):
    return {"rule_id": "historical.fixture", "drug_names": [name], "icd10_codes": ["C50"],
            "report_required": True, "sut_section": "4.2.14.C", "prescriber_specialties": ["onkoloji"]}


def _evaluate(day="2026-10-10", *, name="pertuzumab", rules=None, **changes):
    line = replace(_drug_line(drug_name=name, report_present=True,
                              prescriber_specialty="tıbbi onkoloji"),
                   drug_claim_date=parse_service_date(day), **changes)
    return evaluate_drug_indication_line_detailed(
        drug_line=line, claim=_claim(primary_icd10="C50.9"), diagnoses=[],
        rules=rules if rules is not None else [_legacy(name), _successor(name)],
    )


@pytest.mark.parametrize("bad", [None, "", "2026-02-30", "2026-1-01", "2026-10-10T00:00:00",
                                " 2026-10-10", 1791590400, True, datetime(2026, 10, 10)])
def test_date_parser_never_substitutes_clock_or_timestamp(bad):
    assert parse_service_date(bad) is None


@pytest.mark.parametrize("value", ["2026-10-10", date(2026, 10, 10)])
def test_request_and_adapter_preserve_explicit_service_date(value):
    request = ClaimValidationRequest.model_validate({
        "claim_id": "C1", "materials": [{"name": "pertuzumab"}],
        "drug_context": {"service_date": value, "primary_icd10": "C50.9"},
    })
    assert request.drug_context.service_date == date(2026, 10, 10)
    for payload in (request.model_dump(), request.model_dump(mode="json")):
        assert build_context_from_material_dict(payload).drug_lines[0].drug_claim_date == date(2026, 10, 10)


@pytest.mark.parametrize("bad", ["2026-02-30", "2026-10-10T00:00:00", 1791590400, True])
def test_request_rejects_non_civil_dates(bad):
    with pytest.raises(ValidationError, match="ISO calendar date"):
        DrugContext(service_date=bad)


def test_omitted_date_stays_unknown_in_both_adapters(monkeypatch):
    from src.bilun.domain import rule_engine
    from src.bilun.domain.prose_rules import drug_indication as prose
    payload = {"claim_id": "C1", "materials": [{"name": "pertuzumab"}],
               "drug_context": {"primary_icd10": "C50.9"}}
    assert build_context_from_material_dict(payload).drug_lines[0].drug_claim_date is None
    seen = []
    monkeypatch.setattr(prose, "list_drug_indication_rules", lambda: [_successor()])
    monkeypatch.setattr(prose, "evaluate_drug_indication_line",
                        lambda **kw: seen.append(kw["drug_line"].drug_claim_date))
    rule_engine._run_drug_indication_checks(payload["materials"], payload)
    assert seen == [None]


@pytest.mark.parametrize("name", ["pertuzumab", "trastuzumab_emtansine", "satralizumab"])
def test_source_catalog_dates_and_hashes(name):
    rule = _successor(name)
    assert rule["temporal"]["valid_from"] == "2026-10-10"
    assert rule["verification_status"] == "ai_generated_pending_review"
    assert hashlib.sha256("\n".join(p["text"] for p in rule["source_paragraphs"]).encode()).hexdigest() == rule["source_text_sha256"]


def test_thiotepa_source_review_requires_exact_legacy_target_correction():
    payload = json.loads(_CATALOG.read_text())
    assert not payload["quarantined_rules"]
    assert next(r for r in temporal_drug_rules() if "thiotepa" in r["rule_id"])["historical_source_unverified"]
    correction = next(r for r in temporal_drug_rules() if r.get("temporal_source_correction"))
    assert correction["excluded_rule_ids"] == ["4.2.61.onco.carmustine_offlabel_bmt_conditioning_coverage"]


@pytest.mark.parametrize("day", ["2026-10-02", "2026-10-09"])
def test_historical_fallback_preserves_checks_without_false_compliance(day):
    result = _evaluate(day)
    assert result["selected_rule_id"] == "historical.fixture"
    assert result["temporal_evidence"]["status"] == "historical_legacy_unverified"
    assert result["temporal_evidence"]["valid_from"] is None
    assert result["temporal_evidence"]["valid_until"] == "2026-10-10"
    assert "historical_rule_version" in result["missing_inputs"]
    assert result["violation"]["severity"] == "review"
    failed = _evaluate(day, drug_specialty_board_report_present=False)
    assert failed["violation"]["violation_kind"] == "missing_board_report"
    assert failed["violation"]["temporal_evidence"] == failed["temporal_evidence"]


def test_successor_boundary_is_inclusive_and_does_not_inherit_old_constraints():
    legacy = _legacy()
    legacy["report_duration_months"] = 12
    result = _evaluate("2026-10-10", rules=[legacy, _successor()], drug_report_duration_months=6)
    assert result["selected_rule_id"] == _successor()["rule_id"]
    assert result["evaluation_status"] == "missing_inputs"
    assert result["violation"]["severity"] == "review"
    assert "her2_ihc_3plus_or_fish_sish_cish_positive" in result["missing_inputs"]
    assert result["temporal_evidence"]["clinical_eligibility_complete"] is False
    assert result["violation"]["violation_kind"] != "report_duration_mismatch"


def test_satralizumab_pre_boundary_does_not_invent_nonpayment():
    result = _evaluate("2026-10-09", name="satralizumab", rules=[_successor("satralizumab")])
    assert result["selected_rule_id"] is None
    assert result["temporal_evidence"]["status"] == "not_yet_effective"
    assert result["violation"]["severity"] == "review"
    assert "effective_rule_version" in result["missing_inputs"]


def test_satralizumab_positive_supported_facts_still_need_inpatient_and_clinical_gates():
    result = _evaluate(name="satralizumab", drug_report_duration_months=6,
                       prescriber_specialty="nöroloji", biomarkers=({"marker": "AQP4", "status": "positive"},))
    assert all(check["status"] == "pass" for check in result["temporal_evidence"]["supported_checks"])
    assert "ek4g_inpatient_supply" in result["missing_inputs"]
    assert "age" in result["missing_inputs"] and "edss" in result["missing_inputs"]
    assert result["evaluation_status"] == "missing_inputs"


def test_conflicting_biomarkers_cannot_be_marked_pass():
    result = _evaluate(name="satralizumab", biomarkers=(
        {"marker": "AQP4", "status": "positive"}, {"marker": "AQP4", "status": "negative"},
    ))
    assert next(c for c in result["temporal_evidence"]["supported_checks"] if c["field"] == "biomarkers")["status"] == "fail"


def test_missing_date_never_selects_a_version():
    result = _evaluate(None)
    assert result["selected_rule_id"] is None
    assert result["temporal_evidence"]["version_id"] is None
    assert "drug_claim_date" in result["missing_inputs"]


def test_multiple_versions_select_order_independently_with_exclusive_end():
    first = _successor()
    first["temporal"]["valid_until"] = "2026-11-01"
    second = _successor()
    second["rule_id"] = "next"
    second["temporal"]["version_id"] = "next-version"
    second["temporal"]["valid_from"] = "2026-11-01"
    for rules in ([first, second], [second, first]):
        assert _evaluate("2026-10-31", rules=rules)["selected_rule_id"] == first["rule_id"]
        assert _evaluate("2026-11-01", rules=rules)["selected_rule_id"] == "next"


@pytest.mark.parametrize("case,status", [("overlap", "ambiguous_version"), ("invalid", "invalid_version"),
                                         ("gap", "no_effective_version")])
def test_overlaps_invalid_intervals_and_gaps_fail_closed(case, status):
    first, second = _successor(), _successor()
    second["rule_id"] = "other"
    if case == "invalid":
        first["temporal"]["valid_until"] = "not-a-date"
    elif case == "gap":
        first["temporal"]["valid_until"] = "2026-10-11"
        second["temporal"]["valid_from"] = "2026-11-01"
    result = _evaluate("2026-10-15", rules=[first, second])
    assert result["selected_rule_id"] is None
    assert result["temporal_evidence"]["status"] == status
    assert result["violation"]["severity"] == "review"


def test_explicit_empty_rules_and_unaffected_drugs_do_not_load_temporal_rules():
    assert _evaluate(rules=[])["applicability_status"] == "not_in_encoded_corpus"
    other = _legacy("unaffected")
    result = _evaluate(name="unaffected", rules=[other, _successor()])
    assert result["violation"] is None and "temporal_evidence" not in result


def test_canonical_api_and_public_projection_keep_bounded_temporal_evidence():
    line = replace(_drug_line(drug_name="pertuzumab"), drug_claim_date=date(2026, 10, 10))
    claim = _claim(primary_icd10="C50.9")
    ctx = PatientClaimContext(patient_id="P1", claims=(claim,), procedure_lines=(), material_lines=(),
                              drug_lines=(line,), diagnoses=())
    batch = evaluate_drug_indication_findings("P1", ctx, rules=[_successor()])
    payload = {"evaluations": [x.to_dict() for x in batch.evaluations],
               "findings": [x.to_dict() for x in batch.findings], "violations": list(batch.legacy_violations)}
    model = DrugIndicationReviewResponse.model_validate(payload)
    assert model.evaluations[0].temporal_evidence.service_date == date(2026, 10, 10)
    assert model.findings[0].temporal_evidence.version_id == _successor()["temporal"]["version_id"]
    for key in ("evaluations", "findings", "violations"):
        payload[key][0]["temporal_evidence"]["private_rule_payload"] = {"secret": "blocked"}
    public = project_public_response({"drug_indication": payload}, "get_billing_report")
    for key in ("evaluations", "findings", "violations"):
        evidence = public["drug_indication"][key][0]["temporal_evidence"]
        assert evidence["service_date"] == "2026-10-10"
        assert "private_rule_payload" not in evidence


def test_api_boundaries_serialize_service_date_as_json(monkeypatch):
    from src.bilun.api.routes import validation
    request = ClaimValidationRequest.model_validate({
        "claim_id": "C1", "materials": [{"name": "pertuzumab"}],
        "drug_context": {"service_date": "2026-10-10"},
    })
    seen = []
    monkeypatch.setattr(validation, "validate_claim_v2", lambda payload, **kwargs: seen.append((payload, kwargs)) or {})
    monkeypatch.setattr(validation, "typed_validation_payload", lambda result: result)
    validation.validate_claim_endpoint(request, contract_version="2")
    assert seen[0][0]["drug_context"]["service_date"] == "2026-10-10"
    assert seen[0][1]["supplied_claim"]["drug_context"]["service_date"] == "2026-10-10"
    json.dumps(seen)
    seen.clear()
    monkeypatch.setattr(validation, "sut_validate_claim", lambda payload: seen.append(payload) or {})
    monkeypatch.setattr(validation, "serialize_legacy_validation_result", lambda result: result)
    validation.validate_claim_legacy_endpoint(request)
    assert seen[0]["drug_context"]["service_date"] == "2026-10-10"
    json.dumps(seen)

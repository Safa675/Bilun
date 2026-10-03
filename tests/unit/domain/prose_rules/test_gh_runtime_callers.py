"""Actual GH request paths carry measurements without creating findings or reruns."""

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json

import duckdb
import pytest

from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.billing import engine
from src.bilun.domain.billing.drug_indication_findings import (
    evaluate_drug_indication_findings,
    normalize_drug_indication_payload,
)
from src.bilun.domain.claim_validation_v2 import validate_claim_v2, typed_validation_payload
from src.bilun.domain.prose_rules import drug_indication as prose
from src.bilun.domain.sut.runtime_coverage_export import (
    RequestDrugRuntimeSink,
    bounded_request_drug_runtime,
)
from src.bilun.domain.validation_contract import ValidateClaimV2Response
from src.bilun.api.public_responses import project_public_response
from src.bilun.api.schemas import DrugIndicationReviewResponse
from src.bilun.shared.models import ClaimValidationRequest
from tests.unit.domain.test_gh_request_integration import payload
from tests.unit.api.test_validation_contract_v2 import client, _login  # noqa: F401


def clear_payload(claim_id="runtime-gh"):
    raw = payload(
        gh_treatment_phase="continuation",
        epiphyses_closed=False,
        annual_growth_velocity_cm=5,
        height_cm=154,
        bone_age_years=13,
    )
    raw["claim_id"] = claim_id
    return raw


def context(raw):
    return build_context_from_material_dict(
        ClaimValidationRequest.model_validate(raw).model_dump(mode="json")
    )


def v2(raw):
    req = ClaimValidationRequest.model_validate(raw)
    return typed_validation_payload(
        validate_claim_v2(
            req.model_dump(mode="json"),
            supplied_claim=req.model_dump(mode="json", exclude_unset=True),
        )
    )


def without_runtime(value):
    if isinstance(value, dict):
        return {
            k: without_runtime(v)
            for k, v in value.items()
            if k not in {"runtime_coverage", "drug_runtime_coverage"}
        }
    if isinstance(value, list):
        return [without_runtime(v) for v in value]
    return value


def test_all_clear_line_retains_none_and_canonical_public_cache_measurements(monkeypatch):
    ctx = context(clear_payload())
    line = ctx.drug_lines[0]
    out = prose.evaluate_drug_indication_line_detailed(
        drug_line=line, claim=ctx.claims[0], diagnoses=[]
    )
    assert out["violation"] is None
    assert out["runtime_coverage"]["predicate_passed_count"] == 4
    with monkeypatch.context() as patch:
        patch.setattr(prose, "make_gh_observer", lambda *args: None)
        plain = prose.evaluate_drug_indication_line_detailed(
            drug_line=line, claim=ctx.claims[0], diagnoses=[]
        )
    assert without_runtime(out) == plain
    batch = evaluate_drug_indication_findings(ctx.patient_id, ctx)
    assert not batch.findings and not batch.legacy_violations
    data = {
        "evaluations": [r.to_dict() for r in batch.evaluations],
        "findings": [],
        "violations": [],
    }
    DrugIndicationReviewResponse.model_validate(data)
    public = project_public_response({"drug_indication": data}, "get_billing_report")
    report = public["drug_indication"]["evaluations"][0]["runtime_coverage"]
    assert report["predicate_attempted_count"] == report["predicate_passed_count"] == 4
    assert report["source_clauses_fully_evaluated_count"] is None
    with duckdb.connect(":memory:") as db:
        db.execute("CREATE TABLE reports(payload JSON)")
        db.execute("INSERT INTO reports VALUES (?)", [json.dumps(public)])
        cached = json.loads(db.execute("SELECT payload FROM reports").fetchone()[0])
    assert cached == public


def test_mixed_success_failure_skip_and_uninstrumented_lines_run_once(monkeypatch):
    raw = clear_payload()
    good = raw["materials"][0]
    raw["materials"] = [
        good,
        {**good, "epiphyses_closed": True},
        {**good, "gh_treatment_phase": "initiation"},
        {"name": "ordinary gauze"},
    ]
    ctx = context(raw)
    sink = RequestDrugRuntimeSink(ctx.drug_lines)
    calls = []
    original = prose.evaluate_drug_indication_line_detailed

    def spy(**kwargs):
        calls.append(kwargs["drug_line"].drug_claim_line_id)
        return original(**kwargs)

    monkeypatch.setattr(prose, "evaluate_drug_indication_line_detailed", spy)
    engine.analyze_claim(ctx, drug_runtime_observations=sink)
    assert len(calls) == len(set(calls)) == 4
    rows = sink.payload()
    assert len(rows) == 3
    reports = [r["runtime_coverage"] for r in rows]
    assert [r["predicate_attempted_count"] for r in reports] == [4, 4, 0]
    assert [r["predicate_failed_count"] for r in reports] == [0, 1, 0]
    assert all(r["instrumented_families"] == ["growth_hormone"] for r in reports)
    assert reports[2]["routes_skipped_count"] > 0
    assert all(
        (r["claim_id"], r["drug_claim_line_id"])
        in {(x.claim_id, x.drug_claim_line_id) for x in ctx.drug_lines}
        for r in rows
    )
    with pytest.raises(ValueError):
        engine.analyze_claim(ctx, drug_runtime_observations=sink)


def test_identical_anonymous_line_from_another_request_is_not_the_same_binding():
    first, second = context(clear_payload("")), context(clear_payload(""))
    assert first.drug_lines[0] == second.drug_lines[0]
    assert first.drug_lines[0] is not second.drug_lines[0]
    sink = RequestDrugRuntimeSink(first.drug_lines)
    report = prose.evaluate_drug_indication_line_detailed(
        drug_line=second.drug_lines[0], claim=second.claims[0], diagnoses=[]
    )["runtime_coverage"]
    assert sink.capture(second.drug_lines[0], None, report) is False
    assert sink.payload() == []
    with pytest.raises(ValueError):
        engine.analyze_claim(second, drug_runtime_observations=sink)
    local = prose.evaluate_drug_indication_line_detailed(
        drug_line=first.drug_lines[0], claim=first.claims[0], diagnoses=[]
    )["runtime_coverage"]
    assert sink.capture(first.drug_lines[0], None, local) is True
    assert len(sink.payload()) == 1


def test_foreign_and_conflicting_export_rows_do_not_supply_measurements():
    ctx = context(clear_payload())
    line = ctx.drug_lines[0]
    report = prose.evaluate_drug_indication_line_detailed(
        drug_line=line, claim=ctx.claims[0], diagnoses=[]
    )["runtime_coverage"]
    row = {
        "claim_id": line.claim_id,
        "drug_claim_line_id": line.drug_claim_line_id,
        "selected_rule_id": None,
        "runtime_coverage": report,
    }
    allowed = {(line.claim_id, line.drug_claim_line_id)}
    assert (
        bounded_request_drug_runtime([{**row, "claim_id": "foreign"}], allowed_contexts=allowed)
        == []
    )
    assert len(bounded_request_drug_runtime([row, deepcopy(row)], allowed_contexts=allowed)) == 1
    conflict = bounded_request_drug_runtime(
        [row, {**row, "selected_rule_id": "different"}], allowed_contexts=allowed
    )[0]
    assert conflict["runtime_coverage"]["available"] is False
    assert "predicate_attempted_count" not in conflict["runtime_coverage"]
    private = bounded_request_drug_runtime(
        [{**row, "raw_measurement": 150}], allowed_contexts=allowed
    )[0]
    assert private["runtime_coverage"]["available"] is False and "raw_measurement" not in str(
        private
    )


def test_invalid_cached_summary_becomes_unavailable_and_old_cache_stays_unmeasured():
    old = {"evaluations": [{"drug_claim_line_id": "one"}]}
    assert "runtime_coverage" not in normalize_drug_indication_payload(old)["evaluations"][0]
    bad = {
        "evaluations": [
            {
                "drug_claim_line_id": "one",
                "runtime_coverage": {
                    "schema_version": 1,
                    "available": True,
                    "instrumented_families": ["PRIVATE PATIENT INFO"],
                },
            }
        ]
    }
    result = normalize_drug_indication_payload(bad)["evaluations"][0]["runtime_coverage"]
    assert result["available"] is False and "PRIVATE" not in str(result)


@pytest.mark.parametrize("claim_id", ["", "http-gh"])
def test_real_http_all_clear_is_observed_without_new_advisory(client, claim_id):  # noqa: F811
    _login(client)
    raw = clear_payload(claim_id)
    results = []
    for _ in range(2):
        response = client.post(
            "/api/validate-claim", json=raw, headers={"X-Bilun-Validation-Contract": "2"}
        )
        assert response.status_code == 200, response.text
        result = response.json()
        results.append(result)
        assert not any(r["rule"] == "drug_indication" for r in result["advisories"])
        assert len(result["drug_runtime_coverage"]) == 1
        row = result["drug_runtime_coverage"][0]
        assert (
            row["claim_id"] == claim_id
            and row["runtime_coverage"]["predicate_evaluated_count"] == 4
        )
        assert row["runtime_coverage"]["clinical_eligibility_complete"] is False
        assert "execution_scope" not in json.dumps(result)
    assert results[0]["drug_runtime_coverage"] == results[1]["drug_runtime_coverage"]


def test_concurrent_anonymous_requests_do_not_mix_success_and_failure():
    clear = clear_payload("")
    failed = deepcopy(clear)
    failed["materials"][0]["epiphyses_closed"] = True
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = list(pool.map(v2, [clear, failed]))
    assert a["drug_runtime_coverage"][0]["runtime_coverage"]["predicate_failed_count"] == 0
    assert b["drug_runtime_coverage"][0]["runtime_coverage"]["predicate_failed_count"] == 1
    assert (
        a["drug_runtime_coverage"][0]["runtime_coverage"]["receipt_sha256"]
        != b["drug_runtime_coverage"][0]["runtime_coverage"]["receipt_sha256"]
    )
    assert not any(r["rule"] == "drug_indication" for r in a["advisories"])
    assert any(r["rule"] == "drug_indication" for r in b["advisories"])


def test_sink_adds_no_clinical_or_validity_change_to_v2(monkeypatch):
    raw = clear_payload()
    actual = v2(raw)
    with monkeypatch.context() as patch:
        patch.setattr(prose, "make_gh_observer", lambda *args: None)
        plain = v2(raw)
    for field in ["validation_status", "is_valid", "violations", "advisories", "coverage"]:
        assert actual[field] == plain[field]
    assert actual["drug_runtime_coverage"] and plain["drug_runtime_coverage"] == []


def test_strict_v2_rejects_foreign_duplicate_and_private_runtime_exports():
    from pydantic import ValidationError

    result = v2(clear_payload())
    row = result["drug_runtime_coverage"][0]
    for rows in [
        [{**row, "claim_id": "foreign"}],
        [{**row, "drug_claim_line_id": "DRUG-runtime-gh-999"}],
        [row, deepcopy(row)],
        [{**row, "raw_values": {"height": 150}}],
    ]:
        with pytest.raises(ValidationError):
            ValidateClaimV2Response.model_validate({**result, "drug_runtime_coverage": rows})


def test_request_cannot_supply_its_own_runtime_measurements():
    raw = clear_payload()
    raw["drug_runtime_coverage"] = [{"runtime_coverage": {"predicate_evaluated_count": 999}}]
    result = v2(raw)
    assert result["drug_runtime_coverage"][0]["runtime_coverage"]["predicate_evaluated_count"] == 4


def test_unreadable_override_shape_does_not_change_clinical_result(monkeypatch):
    from scripts.sut.prose import clause_type_overrides

    def malformed():
        raise AttributeError("invalid authored override shape")

    raw = clear_payload()
    plain = v2(raw)
    monkeypatch.setattr(clause_type_overrides, "load_clause_type_overrides", malformed)
    actual = v2(raw)
    for field in ["validation_status", "is_valid", "violations", "advisories", "coverage"]:
        assert actual[field] == plain[field]
    assert actual["drug_runtime_coverage"][0]["runtime_coverage"]["predicate_evaluated_count"] == 4


def test_v2_export_limit_is_the_actual_named_request_scope():
    result = v2(clear_payload())
    material = result["material_applicability"][0]
    row = result["drug_runtime_coverage"][0]
    expanded = {
        **result,
        "material_applicability": [
            {**material, "material_index": i, "material_id": f"{result['request_id']}:material:{i}"}
            for i in range(1001)
        ],
        "drug_runtime_coverage": [
            {**row, "drug_claim_line_id": f"DRUG-{result['claim_id']}-{i + 1:03d}"}
            for i in range(1001)
        ],
    }
    assert len(ValidateClaimV2Response.model_validate(expanded).drug_runtime_coverage) == 1001
    expanded["material_applicability"][1000]["material_name"] = " "
    with pytest.raises(ValueError):
        ValidateClaimV2Response.model_validate(expanded)


def test_sink_cannot_be_reused_after_an_uninstrumented_request():
    raw = clear_payload()
    raw["materials"] = [{"name": "ordinary gauze"}]
    ctx = context(raw)
    sink = RequestDrugRuntimeSink(ctx.drug_lines)
    engine.analyze_claim(ctx, drug_runtime_observations=sink)
    assert sink.payload() == []
    with pytest.raises(ValueError):
        engine.analyze_claim(ctx, drug_runtime_observations=sink)


def test_source_only_adult_route_is_unmeasured_rather_than_zero():
    raw = clear_payload()
    raw["materials"][0]["gh_patient_group"] = "adult"
    raw["drug_context"]["primary_icd10"] = "E23.0"
    result = v2(raw)
    summary = result["drug_runtime_coverage"][0]["runtime_coverage"]
    assert summary["available"] is False
    assert summary.get("predicate_attempted_count") is None
    assert summary.get("source_clauses_touched_count") is None
    assert summary.get("clinical_eligibility_complete") is False


def test_future_selected_protocol_cannot_claim_zero_existing_family_execution():
    ctx = context(clear_payload())
    rules = deepcopy(prose.list_drug_indication_rules())
    for rule in rules:
        if rule.get("growth_hormone_continuation_protocol") == "turner_somatropin_v1":
            rule["growth_hormone_continuation_protocol"] = "turner_somatropin_future"
    result = prose.evaluate_drug_indication_line_detailed(
        drug_line=ctx.drug_lines[0], claim=ctx.claims[0], diagnoses=[], rules=rules
    )
    assert result["runtime_coverage"]["available"] is False
    assert result["runtime_coverage"].get("predicate_attempted_count") is None


def test_old_v2_payload_has_unmeasured_null_instead_of_empty_measured_scope():
    current = v2(clear_payload())
    old = {k: v for k, v in current.items() if k != "drug_runtime_coverage"}
    restored = typed_validation_payload(old)
    assert restored["drug_runtime_coverage"] is None
    assert restored["validation_status"] == current["validation_status"]
    assert restored["is_valid"] is current["is_valid"]


@pytest.mark.parametrize(
    "family,attempted,blocked",
    [
        ("pediatric", 2, 0),
        ("pediatric_block", 0, 1),
        ("ckd", 14, 0),
        ("ckd_block", 12, 1),
    ],
)
@pytest.mark.parametrize("claim_id", ["", "expanded-gh"])
def test_actual_http_new_gh_paths_have_explicit_observations(
    client, family, attempted, blocked, claim_id  # noqa: F811
):
    from tests.unit.domain.prose_rules.test_pediatric_gh_initiation import BASE as PEDIATRIC
    from tests.unit.domain.prose_rules.test_ckd_gh_partial_checks import BASE as CKD
    from tests.unit.domain.prose_rules.test_ckd_gh_growth_pathways import CLEAR

    _login(client)
    if family.startswith("pediatric"):
        facts = {**PEDIATRIC}
        if family.endswith("block"):
            facts["gh_reported_growth_age_band"] = "pubertal"
        raw = payload(code="E23.0", **facts)
    else:
        facts = {**CKD, **CLEAR}
        if family.endswith("block"):
            facts["ckd_height_age_sex_sds"] = None
        raw = payload(code="N18.5", **facts)
        raw["drug_context"]["report_duration_months"] = 6
    raw["claim_id"] = claim_id
    responses = []
    for _ in range(2):
        response = client.post(
            "/api/validate-claim", json=raw, headers={"X-Bilun-Validation-Contract": "2"}
        )
        assert response.status_code == 200, response.text
        result = response.json()
        responses.append(result["drug_runtime_coverage"])
        summary = result["drug_runtime_coverage"][0]["runtime_coverage"]
        assert summary["available"] is True
        assert summary["predicate_attempted_count"] == attempted
        assert summary["routes_blocked_source_count"] == blocked
        assert summary["source_clauses_fully_evaluated_count"] is None
        assert summary["clinical_eligibility_complete"] is False
        assert result["is_valid"] is None
    assert responses[0] == responses[1]

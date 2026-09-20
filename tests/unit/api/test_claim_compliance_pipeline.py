from __future__ import annotations

from collections import Counter
from dataclasses import asdict, replace
from unittest.mock import patch
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.bilun.api.routes import billing, compliance
from src.bilun.db import (
    BILUN_BUILD_SCOPE,
    complete_build,
    connect,
    create_build,
    init_schema,
    read_json_payload,
    read_json_payload_rows,
    set_active_build,
    upsert_single_json_table,
    write_json_payload_rows,
)
from src.bilun.domain.billing import (
    claim_compliance,
    orchestrator,
    patient_report,
    rule_findings,
)
from src.bilun.domain.billing.cohort_compliance import build_cohort_compliance_index
from src.bilun.domain.billing.cohort_runner import (
    compute_all_bill_billing_reports,
    compute_all_billing_reports,
)
from src.bilun.domain.billing.types import ClaimCompliance
from src.bilun.domain.billing.rule_findings import (
    DIAGNOSIS_RULE_ID,
    ICU_RULE_ID,
    evaluate_rule_findings,
)
from src.bilun.domain.claims.dataset import SUTClaimDataset
from src.bilun.domain.claims.patient_context import build_patient_claim_context
from src.bilun.shared import state
from src.bilun.shared.exceptions import register_exception_handlers
from src.bilun.shared.runtime import BilunRuntimeState
from tests.unit.domain.billing.test_claim_compliance import _header, _line

pytestmark = pytest.mark.unit

_MONEY_FIELDS = {
    "amount_try", "billed_try", "payable_try", "savings_try",
    "recoverable_uplift_try", "compliance_savings_try", "risk_amount_try",
    "audit_exposure_try",
}
_EXPECTED_FINDINGS = {
    ("P1", "C-A", ICU_RULE_ID, "A-monitor"),
    ("P1", "C-A", DIAGNOSIS_RULE_ID, None),
    ("P2", "C-G", ICU_RULE_ID, "G-vent"),
}


@pytest.fixture(scope="session", autouse=True)
def _reconcile_drug_manifests_at_session_start():
    yield


@pytest.fixture(scope="module")
def synthetic_rows():
    omitted = _header("C-C", primary_icd10="J96.0")
    omitted.pop("primary_icd10")
    headers = [
        _header("C-A"),
        _header("C-B", primary_icd10="J96.0"),
        omitted,
        _header("C-D", primary_icd10=None),
        _header("C-E", primary_icd10="J96.0"),
        _header("C-F", "P2", claim_type="poliklinik", primary_icd10="J96.0"),
        _header("C-G", "P2", primary_icd10=" \t "),
    ]
    lines = [
        _line("A-anchor", "510090", "C-A"),
        _line("A-vent", "530130", "C-A", procedure_date="2026-01-02"),
        _line("A-monitor", "530330", "C-A"),
        _line("B-vent", "530130", "C-B"),
        _line("C-anchor", "510090", "C-C"),
        _line("D-anchor", "510090", "C-D"),
        _line("E-anchor", "510090", "C-E"),
        _line("E-package-1", "P552001", "C-E", procedure_name="Monitörizasyon"),
        _line("E-package-8", "P552008", "C-E", procedure_name="Monitörizasyon"),
        _line("E-package-9", "p552009", "C-E", procedure_name="Monitörizasyon"),
        _line("F-anchor", "510090", "C-F", "P2"),
        _line("F-vent", "530130", "C-F", "P2"),
        _line("G-anchor", "510090", "C-G", "P2"),
        _line("G-vent", "530130", "C-G", "P2"),
    ]
    for header in headers:
        header["scenario_tag"] = "synthetic_claim_compliance_pipeline"
        header["expected_total_billed_try"] = sum(
            line["billed_amount_try"] for line in lines
            if line["claim_id"] == header["claim_id"]
        )
        header["expected_total_payable_try"] = header["expected_total_billed_try"]
    diagnoses = [{
        "diagnosis_id": "D-G-primary",
        "claim_id": "C-G",
        "patient_id": "P2",
        "episode_id": "E-C-G",
        "icd10_code": "J96.0",
        "is_primary": True,
        "diagnosis_role": "primary",
        "diagnosis_date": "2026-01-01",
        "exemption_eligible": False,
    }]
    return headers, lines, diagnoses


def _ingest(headers, lines, diagnoses=None):
    return SUTClaimDataset.from_rows(
        claim_headers=headers,
        diagnoses=diagnoses or [],
        procedure_lines=lines,
        material_lines=[],
        drug_lines=[],
        expected_outputs=[
            {
                "expected_output_id": f"X-{header['claim_id']}",
                "claim_id": header["claim_id"],
                "patient_id": header["patient_id"],
                "line_type": "claim",
            }
            for header in headers
        ],
    )


def _cache_input(dataset):
    return {
        "sut_claim_dataset": dataset,
        "sut_by_pid": dict.fromkeys(dataset.claims_by_patient, {}),
    }


def _run_with_spies(dataset, *, bills):
    with (
        patch.object(
            orchestrator, "compute_patient_billing_report",
            wraps=patient_report.compute_patient_billing_report,
        ) as report_spy,
        patch.object(
            patient_report, "project_claim_compliance",
            wraps=claim_compliance.project_claim_compliance,
        ) as projection_spy,
        patch.object(
            rule_findings, "detect_icu_bundled_leakage",
            wraps=rule_findings.detect_icu_bundled_leakage,
        ) as icu_spy,
        patch.object(
            rule_findings, "detect_missing_diagnosis",
            wraps=rule_findings.detect_missing_diagnosis,
        ) as diagnosis_spy,
        patch.object(
            rule_findings, "detect_unreported_lab_result",
            wraps=rule_findings.detect_unreported_lab_result,
        ) as lab_spy,
        patch.object(
            rule_findings, "detect_missing_drug_barcode",
            wraps=rule_findings.detect_missing_drug_barcode,
        ) as drug_spy,
        patch.object(
            rule_findings, "detect_material_identity_errors",
            wraps=rule_findings.detect_material_identity_errors,
        ) as material_spy,
    ):
        cache = _cache_input(dataset)
        result = (
            compute_all_bill_billing_reports(cache, max_workers=2)
            if bills else compute_all_billing_reports(cache, max_workers=2)
        )
    scopes = (
        [(claim,) for claim in dataset.claims.values()]
        if bills else list(dataset.claims_by_patient.values())
    )
    expected_scopes = Counter(tuple(sorted(c.claim_id for c in scope)) for scope in scopes)
    assert report_spy.call_count == projection_spy.call_count == len(scopes)
    assert (
        icu_spy.call_count
        == diagnosis_spy.call_count
        == lab_spy.call_count
        == drug_spy.call_count
        == material_spy.call_count
        == len(scopes)
    )
    assert Counter(
        tuple(sorted(c.claim_id for c in call.kwargs["claim_context"].claims))
        for call in report_spy.call_args_list
    ) == expected_scopes
    assert Counter(
        tuple(
            sorted(
                {
                    row.claim_id
                    for row in call.args[1].evaluations
                    if row.claim_id is not None
                }
            )
        )
        for call in projection_spy.call_args_list
    ) == expected_scopes
    for call in report_spy.call_args_list:
        pid = call.args[0]
        ctx = call.kwargs["claim_context"]
        assert ctx.patient_id == pid
        assert all(c is dataset.claims[c.claim_id] and c.patient_id == pid for c in ctx.claims)
        expected_lines = {
            line.procedure_line_id
            for claim in ctx.claims for line in dataset.procedure_lines_by_claim[claim.claim_id]
        }
        assert {line.procedure_line_id for line in ctx.procedure_lines} == expected_lines
        assert all(
            line is dataset.procedure_lines[line.procedure_line_id] and line.patient_id == pid
            for line in ctx.procedure_lines
        )
    assert Counter(
        tuple(sorted(c.claim_id for c in call.args[0])) for call in icu_spy.call_args_list
    ) == expected_scopes
    for call in icu_spy.call_args_list:
        claims, lines = call.args
        assert all(c is dataset.claims[c.claim_id] for c in claims)
        assert len({c.patient_id for c in claims}) == 1
        assert Counter(line.procedure_line_id for line in lines) == Counter(
            line.procedure_line_id
            for claim in claims for line in dataset.procedure_lines_by_claim[claim.claim_id]
        )
        assert all(line is dataset.procedure_lines[line.procedure_line_id] for line in lines)
    assert Counter(
        tuple(sorted(c.claim_id for c in call.args[0]))
        for call in diagnosis_spy.call_args_list
    ) == expected_scopes
    assert all(
        c.claim_id in dataset.claims and c.patient_id == dataset.claims[c.claim_id].patient_id
        for call in diagnosis_spy.call_args_list for c in call.args[0]
    )
    return result


@pytest.fixture(scope="module")
def computed(synthetic_rows):
    dataset = _ingest(*synthetic_rows)
    reports, summary = _run_with_spies(dataset, bills=False)
    bills = _run_with_spies(dataset, bills=True)
    return dataset, reports, bills, summary


@pytest.fixture
def cached_pipeline(computed, tmp_path, monkeypatch):
    dataset, reports, bills, summary = computed
    patient_payloads = {key: billing._serialize_billing_report(value) for key, value in reports.items()}
    bill_payloads = {key: billing._serialize_billing_report(value) for key, value in bills.items()}
    index = build_cohort_compliance_index(reports)
    db_path = tmp_path / "synthetic-claim-compliance.duckdb"
    con = connect(db_path)
    try:
        init_schema(con)
        build = create_build(
            con, project_root=tmp_path, source_hash="synthetic-claim-compliance",
            config_hash="test", schema_version="v1", feature_set_version="v1",
            benchmark_version="v1", nlp_version="test", build_scope=BILUN_BUILD_SCOPE,
        )
        build_id = build.build_id
        write_json_payload_rows(con, "patient_billing_report_rows", build_id, patient_payloads)
        write_json_payload_rows(con, "patient_bill_billing_report_rows", build_id, bill_payloads)
        upsert_single_json_table(con, "cohort_compliance_index", build_id, index)
        complete_build(
            con, build_id,
            row_counts={
                "patient_billing_report_rows": len(reports),
                "patient_bill_billing_report_rows": len(bills),
                "cohort_compliance_index": 1,
            }, checksums={},
        )
        set_active_build(con, build_id, scope=BILUN_BUILD_SCOPE)
    finally:
        con.close()
    reader = connect(db_path)
    try:
        assert read_json_payload(reader, "cohort_compliance_index", build_id) == index
        assert dict(read_json_payload_rows(reader, "patient_billing_report_rows", build_id)) == patient_payloads
        assert dict(read_json_payload_rows(reader, "patient_bill_billing_report_rows", build_id)) == bill_payloads
    finally:
        reader.close()
    runtime = BilunRuntimeState(
        pipeline_mode="persistent", testing=True, canonical_cache_db_path=db_path,
    )
    monkeypatch.setattr(state, "_runtime", runtime)
    monkeypatch.setattr(billing, "PIPELINE_MODE", None)
    app = FastAPI()
    app.include_router(billing.router, prefix="/api")
    app.include_router(compliance.router, prefix="/api")
    register_exception_handlers(app)
    try:
        with TestClient(app) as client:
            yield client, index, patient_payloads, bill_payloads
    finally:
        if runtime.cache_con is not None:
            runtime.cache_con.close()


def _identity(row):
    return row["patient_id"], row["claim_id"], row["rule_id"], row.get("procedure_line_id")


def _assert_nonfinancial(rows):
    for row in rows:
        assert row["status"] == "violation"
        assert row["finding_type"] == "compliance"
        assert row["kind"] == row["rule_id"]
        assert row["detail"] and row["sut_section_id"]
        assert {key: row[key] for key in _MONEY_FIELDS} == dict.fromkeys(_MONEY_FIELDS)
        if "finding_id" in row:
            expected_id = "claim_compliance:" + ":".join(
                quote(str(value), safe="")
                for value in (
                    row["rule_id"],
                    row["patient_id"],
                    row["claim_id"],
                    row["line_kind"],
                    row.get("line_id") or "",
                )
            )
            assert row["finding_id"] == row["action_id"] == expected_id


def test_normal_ingestion_reports_cache_and_http_scopes(cached_pipeline, computed):
    client, index, patients, bills = cached_pipeline
    dataset = computed[0]
    assert not dataset.claims["C-C"].primary_icd10_available
    assert not dataset.claims["C-D"].primary_icd10_available
    assert dataset.claims["C-A"].primary_icd10_available
    assert dataset.claims["C-G"].primary_icd10_available
    response = client.get("/api/compliance-index")
    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"] == index["rows"]
    rows = [row for row in payload["rows"] if row["surface"] == "claim_compliance"]
    assert {_identity(row) for row in rows} == _EXPECTED_FINDINGS
    assert len(rows) == len({row["action_id"] for row in rows}) == 3
    _assert_nonfinancial(rows)
    for pid, expected in patients.items():
        response = client.get(f"/api/billing-report/{pid}")
        assert response.status_code == 200
        actual = response.json()
        assert actual["claim_compliance"] == expected["claim_compliance"]
        block = actual["claim_compliance"]
        assert {_identity(row) for row in block["findings"]} == {
            identity for identity in _EXPECTED_FINDINGS if identity[0] == pid
        }
        _assert_nonfinancial(block["findings"])
        assert len(block["evaluations"]) == 5 * len(dataset.claims_by_patient[pid])
        for evaluation in block["evaluations"]:
            assert evaluation["patient_id"] == pid
            missing = evaluation["claim_id"] in {"C-C", "C-D"} and evaluation["rule_id"] == DIAGNOSIS_RULE_ID
            assert evaluation["status"] == ("missing_inputs" if missing else "evaluated")
            assert evaluation["missing_inputs"] == (["primary_icd10"] if missing else [])
        assert not any(row.get("rule_id") in {ICU_RULE_ID, DIAGNOSIS_RULE_ID} for row in actual["recommended_actions"])
    for key, expected in bills.items():
        pid, cid = key.split("::")
        response = client.get(f"/api/billing-report/{pid}/bills/{cid}")
        assert response.status_code == 200
        actual = response.json()
        assert (actual["patient_id"], actual["claim_id"], actual["scope"]) == (pid, cid, "bill")
        assert actual["claim_compliance"] == expected["claim_compliance"]
        block = actual["claim_compliance"]
        assert {_identity(row) for row in block["findings"]} == {
            identity for identity in _EXPECTED_FINDINGS if identity[:2] == (pid, cid)
        }
        assert len(block["evaluations"]) == 5
        assert all((row["patient_id"], row["claim_id"]) == (pid, cid) for row in block["evaluations"])
        _assert_nonfinancial(block["findings"])
    assert client.get("/api/billing-report/P2/bills/C-A").status_code == 404


def test_http_filters_pagination_and_null_money(cached_pipeline):
    client, index, _, _ = cached_pipeline
    expected = [row for row in index["rows"] if row["surface"] == "claim_compliance"]
    pages = []
    for offset in (0, 2, 4, 6):
        response = client.get("/api/compliance-index", params={
            "surface": "claim_compliance", "limit": 2, "offset": offset,
        })
        assert response.status_code == 200
        payload = response.json()
        assert payload["rows"] == expected[offset:offset + 2]
        assert payload["n_findings"] == 3
        assert payload["pagination"] == {
            "total_matching": 3, "limit": 2, "offset": offset, "has_more": offset < 2,
        }
        assert payload["billed_at_risk_try"] is None
        assert payload["by_surface"]["claim_compliance"]["billed_try"] is None
        assert payload["claim_compliance"]["counts"] == {
            "evaluated": 33, "missing_inputs": 2, "unavailable": 0,
        }
        assert payload["claim_compliance"]["non_evaluated_total"] == 2
        assert len(payload["claim_compliance"]["details"]) == 2
        assert payload["claim_compliance"]["details_truncated"] is False
        assert payload["claim_compliance"]["evaluations"] == []
        pages.extend(payload["rows"])
    assert pages == expected
    _assert_nonfinancial(pages)
    for query, pids in [
        ([("patient_id", "P2")], {"P2"}),
        ([("patient_id", " P2, P1 "), ("patient_id", "P2")], {"P1", "P2"}),
        ([("patient_id", "missing")], {"missing"}),
    ]:
        response = client.get("/api/compliance-index", params=[("surface", "claim_compliance"), *query])
        assert response.status_code == 200
        payload = response.json()
        matching = [row for row in expected if row["patient_id"] in pids]
        assert payload["rows"] == matching
        assert payload["n_findings"] == payload["pagination"]["total_matching"] == len(matching)
        assert payload["n_patients"] == len(pids)
        assert payload["billed_at_risk_try"] is None
        assert payload["by_surface"]["claim_compliance"]["billed_try"] is None
        expected_counts = (
            {"evaluated": 23, "missing_inputs": 2, "unavailable": 0}
            if pids == {"P1"}
            else {"evaluated": 10, "missing_inputs": 0, "unavailable": 0}
            if pids == {"P2"}
            else {"evaluated": 33, "missing_inputs": 2, "unavailable": 0}
            if pids == {"P1", "P2"}
            else {"evaluated": 0, "missing_inputs": 0, "unavailable": 0}
        )
        assert payload["claim_compliance"]["counts"] == expected_counts
        assert all(row["patient_id"] in pids for row in payload["claim_compliance"]["details"])
    payload = client.get("/api/compliance-index", params={"surface": "materials"}).json()
    assert payload["claim_compliance"]["counts"] == {
        "evaluated": 0, "missing_inputs": 0, "unavailable": 0,
    }
    assert all(row["surface"] == "materials" for row in payload["rows"])

    large_cohort = ["P1", *[f"PX-{i:04d}" for i in range(499)]]
    response = client.post("/api/compliance-index", json={
        "surface": "claim_compliance",
        "patient_id": large_cohort,
        "limit": 100,
        "offset": 0,
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["n_patients"] == 500
    assert payload["n_findings"] == payload["pagination"]["total_matching"] == 2
    assert {row["patient_id"] for row in payload["rows"]} == {"P1"}
    assert payload["claim_compliance"]["counts"] == {
        "evaluated": 23, "missing_inputs": 2, "unavailable": 0,
    }
    for params in ({"surface": "invalid"}, {"limit": 0}, {"limit": 5001}, {"offset": -1}):
        assert client.get("/api/compliance-index", params=params).status_code == 400


def test_stable_projection_and_unchanged_legacy_finances(computed, synthetic_rows):
    dataset, reports, bills, summary = computed
    cache = _cache_input(dataset)
    with patch.object(patient_report, "project_claim_compliance", return_value=ClaimCompliance()) as disabled:
        baseline_reports, baseline_summary = compute_all_billing_reports(cache, max_workers=2)
        baseline_bills = compute_all_bill_billing_reports(cache, max_workers=2)
    assert disabled.call_count == len(reports) + len(bills)
    assert asdict(summary) == asdict(baseline_summary)
    for actual_reports, baseline in ((reports, baseline_reports), (bills, baseline_bills)):
        assert actual_reports.keys() == baseline.keys()
        for key, report in actual_reports.items():
            actual = asdict(report)
            expected = asdict(baseline[key])
            actual.pop("claim_compliance")
            expected.pop("claim_compliance")
            assert actual == expected
    index = build_cohort_compliance_index(reports)
    baseline_index = build_cohort_compliance_index(baseline_reports)
    assert index["billed_at_risk_try"] == baseline_index["billed_at_risk_try"]
    for surface in index["by_surface"]:
        assert index["by_surface"][surface]["billed_try"] == baseline_index["by_surface"][surface]["billed_try"]
        if surface != "claim_compliance":
            assert index["by_surface"][surface] == baseline_index["by_surface"][surface]
    assert [row for row in index["rows"] if row["surface"] != "claim_compliance"] == baseline_index["rows"]
    headers, lines, diagnoses = synthetic_rows
    reordered = _ingest(headers[::-1], lines[::-1], diagnoses[::-1])
    reordered_reports, _ = _run_with_spies(reordered, bills=False)
    reordered_bills = _run_with_spies(reordered, bills=True)
    for actual, repeated in ((reports, reordered_reports), (bills, reordered_bills)):
        for key in actual:
            assert asdict(actual[key].claim_compliance) == asdict(repeated[key].claim_compliance)
    repeated_index = build_cohort_compliance_index(reordered_reports)
    assert repeated_index["claim_compliance"] == index["claim_compliance"]
    assert [row for row in repeated_index["rows"] if row["surface"] == "claim_compliance"] == [
        row for row in index["rows"] if row["surface"] == "claim_compliance"
    ]


def test_duplicate_context_lines_do_not_duplicate_cached_findings(computed, cached_pipeline):
    dataset, reports, _, _ = computed
    client, _, _, _ = cached_pipeline
    ctx = build_patient_claim_context("P1", dataset)
    assert ctx is not None
    duplicate = replace(ctx, procedure_lines=ctx.procedure_lines + (dataset.procedure_lines["A-vent"],))
    with (
        patch.object(
            rule_findings, "detect_icu_bundled_leakage",
            wraps=rule_findings.detect_icu_bundled_leakage,
        ) as icu,
        patch.object(
            rule_findings, "detect_missing_diagnosis",
            wraps=rule_findings.detect_missing_diagnosis,
        ) as diagnosis,
    ):
        projection = claim_compliance.project_claim_compliance(
            "P1", evaluate_rule_findings("P1", duplicate)
        )
    icu.assert_called_once()
    diagnosis.assert_called_once()
    assert sum(line is dataset.procedure_lines["A-vent"] for line in icu.call_args.args[1]) == 2
    assert asdict(projection) == asdict(reports["P1"].claim_compliance)
    cached_rows = client.get("/api/compliance-index", params={
        "surface": "claim_compliance", "patient_id": "P1",
    }).json()["rows"]
    patient_ids = [row["finding_id"] for row in projection.findings]
    cached_ids = [row["finding_id"] for row in cached_rows]
    assert cached_ids == patient_ids
    assert [row["action_id"] for row in cached_rows] == patient_ids
    assert all(row["action_id"] == row["finding_id"] for row in cached_rows)
    assert any(":procedure:" in finding_id for finding_id in cached_ids)
    assert any(":claim:" in finding_id for finding_id in cached_ids)

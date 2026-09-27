from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date
from unittest.mock import patch
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.bilun.api.routes import billing, compliance, wavea_evidence, wavea_gate
from src.bilun.db import (
    BILUN_BUILD_SCOPE,
    complete_build,
    connect,
    create_build,
    get_active_build_id,
    init_schema,
    read_json_payload,
    read_json_payload_row,
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
from src.bilun.domain.billing.focused_rule_projection import (
    FOCUSED_RULE_SPECS,
)
from src.bilun.domain.billing.cohort_runner import (
    compute_all_bill_billing_reports,
    compute_all_billing_reports,
)
from src.bilun.domain.billing.types import ClaimCompliance
from src.bilun.domain.billing.wavea_full_evidence import (
    FullWaveAEvidenceProjection,
    build_full_wavea_evidence_index,
    validate_full_wavea_evidence_detail,
    validate_full_wavea_evidence_index,
)
from src.bilun.domain.billing.wavea_evidence import (
    COMPLETE_EVIDENCE_CAPABILITY,
    ORIGINAL_FIVE_RULE_IDS,
    WaveAEvidenceBlock,
    original_five_report_payload,
)
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
from tests.unit.domain.billing.test_focused_rule_projection import _context as _focused_context

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
_FOCUSED_IDS = {spec.rule_id for spec in FOCUSED_RULE_SPECS}


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
    wavea_details = {pid: dict(report.wavea_evidence_detail) for pid, report in reports.items()}
    wavea_bill_details = {key: dict(report.wavea_evidence_detail) for key, report in bills.items()}
    wavea_index = build_full_wavea_evidence_index(wavea_details)
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
        for detail in wavea_details.values():
            detail["build_id"] = build_id
        for detail in wavea_bill_details.values():
            detail["build_id"] = build_id
        wavea_index["build_id"] = build_id
        write_json_payload_rows(con, "wavea_evidence_detail", build_id, wavea_details)
        write_json_payload_rows(con, "wavea_bill_evidence_detail", build_id, wavea_bill_details)
        upsert_single_json_table(con, "wavea_evidence_index", build_id, wavea_index)
        upsert_single_json_table(con, "cohort_compliance_index", build_id, index)
        complete_build(
            con, build_id,
            row_counts={
                "patient_billing_report_rows": len(reports),
                "patient_bill_billing_report_rows": len(bills),
                "cohort_compliance_index": 1,
                "wavea_evidence_detail": len(wavea_details),
                "wavea_bill_evidence_detail": len(wavea_bill_details),
                "wavea_evidence_index": 1,
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
    app.include_router(wavea_evidence.router, prefix="/api")
    register_exception_handlers(app)
    try:
        with TestClient(app) as client:
            yield client, index, patient_payloads, bill_payloads
    finally:
        if runtime.cache_con is not None:
            runtime.cache_con.close()


def _identity(row):
    return row["patient_id"], row["claim_id"], row["rule_id"], row.get("procedure_line_id")


def _trusted_v2_test_gate(reader, index, build_id):
    """Test route mechanics while production awaits a release attestation."""
    if not isinstance(index, dict) or index.get("build_id") != build_id:
        return False
    try:
        validate_full_wavea_evidence_index(index)
        expected = wavea_gate.declared_patient_report_count(reader, build_id)
    except ValueError:
        return False
    return index["n_patients"] == expected


def test_bill_wavea_drilldown_uses_own_cached_scope_and_checks_preview(cached_pipeline, monkeypatch):
    client, _, _, _ = cached_pipeline
    monkeypatch.setattr(wavea_evidence, "_ready", _trusted_v2_test_gate)
    con = connect(state._runtime.canonical_cache_db_path)
    try:
        build_id = get_active_build_id(con, scope=BILUN_BUILD_SCOPE)
        assert build_id is not None
        detail = read_json_payload_row(con, "wavea_bill_evidence_detail", build_id, "P1::C-A")
        report = read_json_payload_row(con, "patient_bill_billing_report_rows", build_id, "P1::C-A")
    finally:
        con.close()
    assert detail is not None and report is not None

    page = client.get(
        "/api/wavea-evidence/P1",
        params={"scope": "bill", "claim_id": "C-A", "limit": 25, "offset": 25},
    ).json()
    assert page["available"] is True
    assert page["scope"] == "bill" and page["claim_id"] == "C-A"
    assert page["patient_counts"] == detail["counts"]
    assert page["rows"] == detail["evaluations"][25:50]
    assert page["pagination"]["total_matching"] == len(detail["evaluations"])
    assert {row["claim_id"] for row in page["rows"]} == {"C-A"}
    patient_page = client.get(
        "/api/wavea-evidence/P1", params={"claim_id": "C-A", "limit": 25, "offset": 25}
    ).json()
    assert patient_page["scope"] == "patient"
    assert patient_page["patient_counts"] != page["patient_counts"]
    assert client.get("/api/wavea-evidence/P1", params={"scope": "bill"}).status_code == 400
    assert client.get("/api/wavea-evidence/P1", params={"scope": "other"}).status_code == 400
    assert client.get(
        "/api/wavea-evidence/P1", params={"scope": "bill", "claim_id": "other"}
    ).json()["available"] is False

    original_read = wavea_evidence.read_json_payload_row
    bad_report = deepcopy(report)
    bad_report["wavea_coverage"]["evaluation_count"] += 1
    monkeypatch.setattr(
        wavea_evidence,
        "read_json_payload_row",
        lambda reader, table, active_build, key: bad_report
        if table == "patient_bill_billing_report_rows"
        else original_read(reader, table, active_build, key),
    )
    corrupted = client.get(
        "/api/wavea-evidence/P1", params={"scope": "bill", "claim_id": "C-A"}
    ).json()
    assert corrupted["available"] is False
    assert corrupted["counts"] is None


def _expected_compliance_counts(
    patient_payloads: dict[str, dict], patient_ids: set[str]
) -> dict[str, int]:
    statuses = Counter(
        evaluation["status"]
        for pid in patient_ids if pid in patient_payloads
        for evaluation in patient_payloads[pid]["claim_compliance"]["evaluations"]
    )
    return {status: statuses[status] for status in ("evaluated", "missing_inputs", "unavailable")}


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
        assert actual["claim_compliance"] == original_five_report_payload(expected)[
            "claim_compliance"
        ]
        block = actual["claim_compliance"]
        assert {_identity(row) for row in block["findings"]} == {
            identity for identity in _EXPECTED_FINDINGS if identity[0] == pid
        }
        _assert_nonfinancial(block["findings"])
        assert len(block["evaluations"]) == 5 * len(dataset.claims_by_patient[pid])
        assert {row["rule_id"] for row in block["evaluations"]} == ORIGINAL_FIVE_RULE_IDS
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
        assert actual["claim_compliance"] == original_five_report_payload(expected)[
            "claim_compliance"
        ]
        block = actual["claim_compliance"]
        assert {_identity(row) for row in block["findings"]} == {
            identity for identity in _EXPECTED_FINDINGS if identity[:2] == (pid, cid)
        }
        assert len(block["evaluations"]) == 5
        assert all((row["patient_id"], row["claim_id"]) == (pid, cid) for row in block["evaluations"])
        _assert_nonfinancial(block["findings"])
    assert client.get("/api/billing-report/P2/bills/C-A").status_code == 404


def test_http_filters_pagination_and_null_money(cached_pipeline):
    client, index, patients, _ = cached_pipeline
    expected = [row for row in index["rows"] if row["surface"] == "claim_compliance"]
    cohort_counts = _expected_compliance_counts(patients, set(patients))
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
        assert payload["claim_compliance"]["counts"] == cohort_counts
        assert payload["claim_compliance"]["non_evaluated_total"] == (
            cohort_counts["missing_inputs"] + cohort_counts["unavailable"]
        )
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
        expected_counts = _expected_compliance_counts(patients, pids)
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
    assert payload["claim_compliance"]["counts"] == _expected_compliance_counts(
        patients, {"P1"}
    )
    for params in ({"surface": "invalid"}, {"limit": 0}, {"limit": 5001}, {"offset": -1}):
        assert client.get("/api/compliance-index", params=params).status_code == 400


def test_wavea_evidence_hidden_until_completed_build(cached_pipeline):
    client, _, patients, bills = cached_pipeline
    con = connect(state._runtime.canonical_cache_db_path)
    try:
        build_id = get_active_build_id(con, scope=BILUN_BUILD_SCOPE)
        wavea_index = read_json_payload(con, "wavea_evidence_index", build_id)
        wavea_index["capability"] = "draft"
        upsert_single_json_table(con, "wavea_evidence_index", build_id, wavea_index)
    finally:
        con.close()
    for path, stored in (
        ("/api/billing-report/P1", patients["P1"]),
        ("/api/billing-report/P1/bills/C-A", bills["P1::C-A"]),
    ):
        payload = client.get(path).json()
        assert payload["recommended_actions"] == stored["recommended_actions"]
        assert payload["action_count"] == stored["action_count"]
        assert payload["audit_exposure_try"] == stored["audit_exposure_try"]
        assert payload["sgk_uplift_try"] == stored["sgk_uplift_try"]
        for field in ("claim_reviews", "claim_advisories", "financial_findings"):
            assert payload[field] == {
                "available": False,
                "unavailable_reason": "wavea_capability_unavailable",
                "total_rows": None,
                "rows": [],
                "has_more": False,
            }
        assert payload["wavea_coverage"] is None
        assert "wavea_evidence_detail" not in payload
        assert {row["rule_id"] for row in payload["claim_compliance"]["evaluations"]} == ORIGINAL_FIVE_RULE_IDS
        assert not any(
            row["rule_id"] in _FOCUSED_IDS
            for row in payload["claim_compliance"]["findings"] + payload["claim_compliance"]["evaluations"]
        )
    cohort = client.get("/api/compliance-index").json()
    original_index = build_cohort_compliance_index(
        {pid: original_five_report_payload(report) for pid, report in patients.items()}
    )
    assert cohort["rows"] == original_index["rows"]
    assert cohort["claim_compliance"]["counts"] == {
        status: sum(
            row["status"] == status
            for report in patients.values()
            for row in original_five_report_payload(report)["claim_compliance"]["evaluations"]
        )
        for status in ("evaluated", "missing_inputs", "unavailable")
    }
    assert not any(row.get("rule_id") in _FOCUSED_IDS for row in cohort["rows"])
    for path in (
        "/api/wavea-evidence-index",
        "/api/wavea-evidence/P1",
        "/api/wavea-evidence-rows",
    ):
        payload = client.get(path).json()
        assert payload["available"] is False
        assert payload["counts"] is None
        assert payload["rows"] == []
        assert payload["pagination"]["total_matching"] is None


def test_v2_capability_string_toggle_cannot_publish_unattested_evidence(cached_pipeline):
    client, _, _, _ = cached_pipeline
    con = connect(state._runtime.canonical_cache_db_path)
    try:
        build_id = get_active_build_id(con, scope=BILUN_BUILD_SCOPE)
        index = read_json_payload(con, "wavea_evidence_index", build_id)
        assert index["capability"] == "draft"
        index["capability"] = COMPLETE_EVIDENCE_CAPABILITY
        upsert_single_json_table(con, "wavea_evidence_index", build_id, index)
    finally:
        con.close()
    for path in ("/api/wavea-evidence-index", "/api/wavea-evidence/P1", "/api/wavea-evidence-rows"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["available"] is False
    patient = client.get("/api/billing-report/P1").json()
    assert patient["claim_advisories"]["available"] is False
    assert patient["claim_reviews"]["available"] is False
    assert {row["rule_id"] for row in patient["claim_compliance"]["evaluations"]} == ORIGINAL_FIVE_RULE_IDS


def test_v2_explicit_empty_patient_selection_never_expands_to_all(cached_pipeline, monkeypatch):
    client, _, _, _ = cached_pipeline
    monkeypatch.setattr(wavea_evidence, "_ready", _trusted_v2_test_gate)
    all_index = client.get("/api/wavea-evidence-index").json()
    assert all_index["pagination"]["total_matching"] == 2
    for response in (
        client.get("/api/wavea-evidence-index", params={"patient_id": ""}),
        client.post("/api/wavea-evidence-index", json={"patient_id": []}),
    ):
        payload = response.json()
        assert payload["available"] is True
        assert payload["pagination"]["total_matching"] == 0
        assert payload["counts"]["evaluation_count"] == 0
        assert payload["rows"] == []
    all_rows = client.get("/api/wavea-evidence-rows").json()
    assert all_rows["pagination"]["total_matching"] > 0
    for response in (
        client.get("/api/wavea-evidence-rows", params={"patient_id": ""}),
        client.post("/api/wavea-evidence-rows", json={"patient_id": []}),
    ):
        payload = response.json()
        assert payload["available"] is True
        assert payload["pagination"]["total_matching"] == 0
        assert payload["rows"] == []


def test_missing_wavea_index_cannot_expose_focused_cohort_counts(cached_pipeline, monkeypatch):
    client, index, patients, _ = cached_pipeline
    assert sum(
        counts["missing_inputs"]
        for counts in index["claim_compliance"]["counts_by_patient"].values()
    ) > 0
    original_read = compliance.read_cache_json_payload

    def without_wavea_index(reader, table_name, build_id):
        if table_name == "wavea_evidence_index":
            return None
        return original_read(reader, table_name, build_id)

    monkeypatch.setattr(compliance, "read_cache_json_payload", without_wavea_index)
    cohort = client.get("/api/compliance-index").json()
    original_index = build_cohort_compliance_index(
        {pid: original_five_report_payload(report) for pid, report in patients.items()}
    )
    assert cohort["artifacts_available"] is True
    assert cohort["claim_compliance"]["counts"] == {
        status: sum(
            counts[status]
            for counts in original_index["claim_compliance"]["counts_by_patient"].values()
        )
        for status in ("evaluated", "missing_inputs", "unavailable")
    }
    assert cohort["rows"] == original_index["rows"]
    assert not any(row.get("rule_id") in _FOCUSED_IDS for row in cohort["rows"])

    original_rows = compliance.read_cache_json_payload_rows
    monkeypatch.setattr(
        compliance,
        "read_cache_json_payload_rows",
        lambda *args: original_rows(*args)[:-1],
    )
    incomplete = client.get("/api/compliance-index").json()
    assert incomplete["artifacts_available"] is False
    assert incomplete["claim_compliance"] is None
    assert incomplete["rows"] == []


def test_wavea_v2_routes_page_stable_evidence_under_test_only_trusted_gate(cached_pipeline, monkeypatch):
    client, _, _, _ = cached_pipeline
    monkeypatch.setattr(wavea_evidence, "_ready", _trusted_v2_test_gate)
    monkeypatch.setattr(billing, "complete_build_evidence_available", _trusted_v2_test_gate)
    con = connect(state._runtime.canonical_cache_db_path)
    try:
        build_id = get_active_build_id(con, scope=BILUN_BUILD_SCOPE)
        assert build_id is not None
        index = read_json_payload(con, "wavea_evidence_index", build_id)
        detail = read_json_payload_row(con, "wavea_evidence_detail", build_id, "P1")
        detail_p2 = read_json_payload_row(con, "wavea_evidence_detail", build_id, "P2")
    finally:
        con.close()

    summary = client.get("/api/wavea-evidence-index", params={"limit": 1}).json()
    assert summary["available"] is True
    assert summary["pagination"] == {
        "total_matching": 2, "limit": 1, "offset": 0, "has_more": True,
    }
    assert "by_rule" not in summary["counts"]
    assert "by_rule" not in summary["rows"][0]["counts"]
    assert summary["counts"]["evaluation_count"] == sum(
        patient["counts"]["evaluation_count"] for patient in index["patients"].values()
    )
    assert client.post(
        "/api/wavea-evidence-index", json={"limit": 1}
    ).json() == summary
    rule_id = next(iter(index["patients"]["P1"]["counts"]["by_rule"]))
    selected = client.get("/api/wavea-evidence-index", params={"rule_id": rule_id}).json()
    assert client.post(
        "/api/wavea-evidence-index", json={"rule_id": rule_id}
    ).json() == selected
    assert selected["counts"]["by_rule"][rule_id] == {
        status: sum(patient["counts"]["by_rule"][rule_id][status]
                    for patient in index["patients"].values())
        for status in ("evaluated", "missing_inputs", "unavailable")
    }
    assert all(set(row["counts"]["by_rule"]) == {rule_id} for row in selected["rows"])
    unknown = client.get("/api/wavea-evidence-index", params={"patient_id": "missing"}).json()
    assert unknown["available"] is False
    assert unknown["unavailable_reason"] == "requested_patient_not_in_build"
    assert unknown["counts"] is None
    assert client.post(
        "/api/wavea-evidence-index", json={"patient_id": ["missing"]}
    ).json() == unknown

    response = client.get("/api/wavea-evidence/P1", params={"limit": 1})
    assert response.status_code == 200
    page = response.json()
    assert page["available"] is True
    assert page["pagination"]["total_matching"] == len(detail["evaluations"])
    assert page["rows"][0]["evaluation_id"] == detail["evaluations"][0]["evaluation_id"]
    assert "patient_counts" in page and "counts" not in page
    assert client.get("/api/wavea-evidence/P1", params={"kind": "bogus"}).status_code == 400
    assert client.get("/api/wavea-evidence/P999").status_code == 404
    report = client.get("/api/billing-report/P1").json()
    assert report["claim_reviews"]["available"] is True
    assert report["claim_advisories"]["available"] is True
    assert report["financial_findings"]["available"] is True
    assert "wavea_evidence_detail" not in report
    assert all(
        row["confirmed_amount_try"] is None
        for row in report["financial_findings"]["rows"]
    )

    divergent = deepcopy(detail)
    referenced_ids = {
        row["source_evidence_id"]
        for row in (*divergent["reviews"], *divergent["advisories"], *divergent["financial_rows"])
    }
    changed = next(
        row for row in divergent["evaluations"]
        if row["evaluation_id"] not in referenced_ids
        and row["rule_id"] in _FOCUSED_IDS
        and row["evaluation_status"] == "unavailable"
    )
    changed["evaluation_status"] = "missing_inputs"
    divergent["counts"]["by_rule"][changed["rule_id"]]["unavailable"] -= 1
    divergent["counts"]["by_rule"][changed["rule_id"]]["missing_inputs"] += 1
    group = next(
        spec.group for spec in FOCUSED_RULE_SPECS
        if spec.rule_id == changed["rule_id"]
    )
    divergent["counts"]["by_group"][group]["unavailable"] -= 1
    divergent["counts"]["by_group"][group]["missing_inputs"] += 1
    validate_full_wavea_evidence_detail(divergent, "P1")
    monkeypatch.setattr(wavea_evidence, "read_json_payload_row", lambda *_args: divergent)
    index_divergent = client.get("/api/wavea-evidence/P1").json()
    assert index_divergent["available"] is False
    assert index_divergent["counts"] is None

    missing_detail = deepcopy(patient_report.compute_patient_billing_report("P1", claim_context=None).wavea_evidence_detail)
    assert missing_detail is not None
    missing_detail["build_id"] = build_id
    unavailable_index = build_full_wavea_evidence_index({"P1": missing_detail, "P2": detail_p2})
    unavailable_index["build_id"] = build_id
    monkeypatch.setattr(wavea_evidence, "read_json_payload_row", lambda *_args: detail)
    monkeypatch.setattr(wavea_evidence, "read_json_payload", lambda *_args: unavailable_index)
    unavailable_patient = client.get("/api/wavea-evidence/P1").json()
    assert unavailable_patient["available"] is False
    assert unavailable_patient["counts"] is None

    missing_index = build_full_wavea_evidence_index({"P1": missing_detail, "P2": detail_p2})
    missing_index["build_id"] = build_id
    monkeypatch.setattr(wavea_evidence, "read_json_payload", lambda *_args: missing_index)
    monkeypatch.setattr(wavea_evidence, "read_json_payload_row", lambda *_args: missing_detail)
    missing_page = client.get("/api/wavea-evidence/P1").json()
    assert missing_page["available"] is False
    assert missing_page["unavailable_reason"] == "claim_context_unavailable"
    assert missing_page["pagination"]["total_matching"] == 528
    assert len(missing_page["rows"]) == 20
    assert all(row["evaluation_status"] == "missing_inputs" for row in missing_page["rows"])
    assert missing_page["patient_counts"]["evaluation_count"] == 528
    unavailable_cohort_rows = client.get(
        "/api/wavea-evidence-rows", params={"patient_id": "P1"}
    ).json()
    assert unavailable_cohort_rows["available"] is False
    assert unavailable_cohort_rows["counts"] is None
    assert unavailable_cohort_rows["pagination"]["total_matching"] is None

    monkeypatch.setattr(wavea_evidence, "read_json_payload_row", lambda *_args: {"patient_id": "P1"})
    malformed_detail = client.get("/api/wavea-evidence/P1").json()
    assert malformed_detail["available"] is False
    assert malformed_detail["counts"] is None
    monkeypatch.setattr(wavea_evidence, "read_json_payload", lambda *_args: {"build_id": build_id})
    malformed_index = client.get("/api/wavea-evidence-index").json()
    assert malformed_index["available"] is False
    assert malformed_index["counts"] is None
    empty_index = {**index, "patients": {}, "n_patients": 0, "n_patients_unavailable": 0}
    monkeypatch.setattr(wavea_evidence, "read_json_payload", lambda *_args: empty_index)
    inconsistent = client.get("/api/wavea-evidence-index").json()
    assert inconsistent["available"] is False
    assert inconsistent["counts"] is None
    empty_index["counts"] = {
        "by_rule": {}, "by_group": {}, "review_count": 0, "advisory_count": 0,
        "financial_count": 0,
    }
    forged_zero = client.get("/api/wavea-evidence-index").json()
    assert forged_zero["available"] is False
    assert forged_zero["counts"] is None


def test_wavea_true_empty_v2_build_reports_zero_only_under_test_trusted_gate(tmp_path, monkeypatch):
    db_path = tmp_path / "empty-wavea.duckdb"
    con = connect(db_path)
    try:
        init_schema(con)
        build = create_build(
            con, project_root=tmp_path, source_hash="empty-wavea", config_hash="test",
            schema_version="v1", feature_set_version="v1", benchmark_version="v1",
            nlp_version="test", build_scope=BILUN_BUILD_SCOPE,
        )
        index = build_full_wavea_evidence_index({})
        index["build_id"] = build.build_id
        upsert_single_json_table(con, "wavea_evidence_index", build.build_id, index)
        complete_build(
            con, build.build_id,
            row_counts={
                "patient_billing_report_rows": 0,
                "wavea_evidence_detail": 0,
                "wavea_evidence_index": 1,
            },
            checksums={},
        )
        set_active_build(con, build.build_id, scope=BILUN_BUILD_SCOPE)
    finally:
        con.close()
    runtime = BilunRuntimeState(
        pipeline_mode="persistent", testing=True, canonical_cache_db_path=db_path,
    )
    monkeypatch.setattr(state, "_runtime", runtime)
    monkeypatch.setattr(wavea_evidence, "_ready", _trusted_v2_test_gate)
    app = FastAPI()
    app.include_router(wavea_evidence.router, prefix="/api")
    register_exception_handlers(app)
    try:
        with TestClient(app) as client:
            payload = client.get("/api/wavea-evidence-index").json()
        assert payload["available"] is True
        assert payload["counts"] == {
            "by_group": {}, "evaluation_count": 0, "review_count": 0,
            "advisory_count": 0, "financial_count": 0,
        }
        assert payload["pagination"]["total_matching"] == 0
        assert payload["rows"] == []
    finally:
        if runtime.cache_con is not None:
            runtime.cache_con.close()


def test_wavea_routes_share_production_session_gate(cached_pipeline, monkeypatch):
    from src.bilun.api import app as production_app
    from src.bilun.api.auth import hash_password

    monkeypatch.setenv("BILUN_AUTH_USERNAME", "wavea_tester")
    monkeypatch.setenv("BILUN_AUTH_PASSWORD", hash_password("wavea-test-password"))
    monkeypatch.setenv("BILUN_SESSION_SECRET", "wavea-test-secret-long-enough-for-session")
    monkeypatch.setenv("BILUN_AUTH_OPTIONAL", "0")
    client = TestClient(production_app)
    try:
        paths = (
            "/api/wavea-evidence-index",
            "/api/wavea-evidence/P1",
            "/api/wavea-evidence-rows",
        )
        for path in paths:
            unauthenticated = client.get(path)
            assert unauthenticated.status_code == 401
            assert unauthenticated.json()["detail"] == "Authentication required."
        for path in ("/api/wavea-evidence-index", "/api/wavea-evidence-rows"):
            unauthenticated = client.post(path, json={})
            assert unauthenticated.status_code == 401
            assert unauthenticated.json()["detail"] == "Authentication required."
        login = client.post(
            "/api/auth/login",
            json={"username": "wavea_tester", "password": "wavea-test-password"},
        )
        assert login.status_code == 200
        for path in paths:
            authenticated = client.get(path)
            assert authenticated.status_code == 200
        for path in ("/api/wavea-evidence-index", "/api/wavea-evidence-rows"):
            assert client.post(path, json={}).status_code == 200
            assert authenticated.json()["available"] is False
    finally:
        client.close()


def test_financial_and_review_evidence_survive_report_cache_and_api(tmp_path, monkeypatch):
    source = _focused_context()
    claim = replace(
        source.claims[0],
        claim_type="yatis",
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 1),
    )
    ctx = replace(
        source,
        claims=(claim,),
        procedure_lines=(
            replace(source.procedure_lines[0], procedure_code="510090"),
            replace(source.procedure_lines[1], procedure_code="510010"),
        ),
        material_lines=(replace(source.material_lines[0], requires_pre_auth=True, material_type="implant"),),
        drug_lines=(),
    )
    patient = patient_report.compute_patient_billing_report("P1", claim_context=ctx)
    bill_ctx = ctx.slice_for_claim("C1")
    assert bill_ctx is not None
    bill = patient_report.compute_patient_billing_report("P1", claim_context=bill_ctx)
    assert patient.claim_reviews.total_rows >= 1
    assert patient.financial_findings.total_rows == 1
    assert any(
        row["rule_id"] == "tablo15_15_material_preauth_missing"
        for row in patient.claim_reviews.rows
    )
    assert patient.financial_findings.rows[0]["rule_id"] == "yatak_icu_overlap_510010"
    assert patient.financial_findings.rows[0]["confirmed_amount_try"] is None
    for field in ("claim_reviews", "claim_advisories", "financial_findings"):
        assert patient.__getattribute__(field).rows == bill.__getattribute__(field).rows

    empty = FullWaveAEvidenceProjection(
        WaveAEvidenceBlock(), WaveAEvidenceBlock(), WaveAEvidenceBlock(), {}, {}, ()
    )
    with patch.object(patient_report, "project_full_wavea_evidence", return_value=empty), patch.object(
        patient_report, "validate_full_wavea_evidence_detail"
    ):
        without_new_evidence = patient_report.compute_patient_billing_report("P1", claim_context=ctx)
    actual = asdict(patient)
    prior = asdict(without_new_evidence)
    for field in (
        "claim_reviews", "claim_advisories", "financial_findings", "wavea_coverage",
        "wavea_evidence_detail",
    ):
        actual.pop(field)
        prior.pop(field)
    assert actual == prior

    db_path = tmp_path / "wavea-evidence-pipeline.duckdb"
    con = connect(db_path)
    try:
        init_schema(con)
        build = create_build(
            con, project_root=tmp_path, source_hash="wavea-evidence",
            config_hash="test", schema_version="v1", feature_set_version="v1",
            benchmark_version="v1", nlp_version="test", build_scope=BILUN_BUILD_SCOPE,
        )
        build_id = build.build_id
        detail = dict(patient.wavea_evidence_detail)
        detail["build_id"] = build_id
        index = build_full_wavea_evidence_index({"P1": detail})
        index["build_id"] = build_id
        write_json_payload_rows(
            con, "patient_billing_report_rows", build_id,
            {"P1": billing._serialize_billing_report(patient)},
        )
        write_json_payload_rows(
            con, "patient_bill_billing_report_rows", build_id,
            {"P1::C1": billing._serialize_billing_report(bill)},
        )
        write_json_payload_rows(con, "wavea_evidence_detail", build_id, {"P1": detail})
        upsert_single_json_table(con, "wavea_evidence_index", build_id, index)
        upsert_single_json_table(
            con, "cohort_compliance_index", build_id,
            build_cohort_compliance_index({"P1": patient}),
        )
        complete_build(con, build_id, row_counts={
            "patient_billing_report_rows": 1,
            "patient_bill_billing_report_rows": 1,
            "wavea_evidence_detail": 1,
            "wavea_evidence_index": 1,
            "cohort_compliance_index": 1,
        }, checksums={})
        set_active_build(con, build_id, scope=BILUN_BUILD_SCOPE)
    finally:
        con.close()

    runtime = BilunRuntimeState(
        pipeline_mode="persistent", testing=True, canonical_cache_db_path=db_path,
    )
    monkeypatch.setattr(state, "_runtime", runtime)
    monkeypatch.setattr(billing, "PIPELINE_MODE", None)
    monkeypatch.setattr(billing, "complete_build_evidence_available", _trusted_v2_test_gate)
    monkeypatch.setattr(wavea_evidence, "_ready", _trusted_v2_test_gate)
    app = FastAPI()
    app.include_router(billing.router, prefix="/api")
    app.include_router(compliance.router, prefix="/api")
    app.include_router(wavea_evidence.router, prefix="/api")
    register_exception_handlers(app)
    try:
        with TestClient(app) as client:
            patient_payload = client.get("/api/billing-report/P1").json()
            bill_payload = client.get("/api/billing-report/P1/bills/C1").json()
            cohort = client.get("/api/wavea-evidence-index").json()
            reviews = client.get("/api/wavea-evidence/P1", params={"kind": "reviews"}).json()
            financial = client.get(
                "/api/wavea-evidence/P1", params={"kind": "financial_rows"}
            ).json()
            cohort_reviews = client.get(
                "/api/wavea-evidence-rows", params={"kind": "reviews", "limit": 1}
            ).json()
            cohort_financial = client.get(
                "/api/wavea-evidence-rows", params={"kind": "financial_rows", "limit": 1}
            ).json()
            advisories = client.get(
                "/api/wavea-evidence/P1", params={"kind": "advisories"}
            ).json()
            cohort_advisories = client.get(
                "/api/wavea-evidence-rows", params={"kind": "advisories"}
            ).json()
            post_cohort_financial = client.post(
                "/api/wavea-evidence-rows",
                json={"kind": "financial_rows", "patient_id": ["P1"], "limit": 1},
            ).json()
            get_selected_cohort_financial = client.get(
                "/api/wavea-evidence-rows",
                params={"kind": "financial_rows", "patient_id": "P1", "limit": 1},
            ).json()
            exact_financial = client.get(
                "/api/wavea-evidence/P1",
                params={
                    "kind": "financial_rows",
                    "evidence_id": financial["rows"][0]["evidence_id"],
                },
            ).json()
            wrong_evidence_id = client.get(
                "/api/wavea-evidence/P1",
                params={"kind": "financial_rows", "evidence_id": "wavea_financial:unknown"},
            ).json()
            assert client.get(
                "/api/wavea-evidence/P1",
                params={"kind": "reviews", "evidence_id": financial["rows"][0]["evidence_id"]},
            ).status_code == 400
            assert client.get(
                "/api/wavea-evidence/P1", params={"evidence_id": financial["rows"][0]["evidence_id"]}
            ).status_code == 400
            wrong_claim = client.get(
                "/api/wavea-evidence-rows", params={"kind": "financial_rows", "claim_id": "other"}
            ).json()
            beyond_page = client.get(
                "/api/wavea-evidence-rows", params={"kind": "financial_rows", "offset": 1}
            ).json()
            unknown_patient_rows = client.get(
                "/api/wavea-evidence-rows", params={"patient_id": "P999"}
            ).json()
            assert client.get(
                "/api/wavea-evidence-rows", params={"kind": "not-evidence"}
            ).status_code == 400
            compliance_index = client.get("/api/compliance-index").json()
    finally:
        if runtime.cache_con is not None:
            runtime.cache_con.close()
    for field in ("claim_reviews", "claim_advisories", "financial_findings"):
        assert patient_payload[field]["rows"] == bill_payload[field]["rows"]
    assert patient_payload["total_recoverable_try"] == prior["total_recoverable_try"]
    assert patient_payload["audit_exposure_try"] == prior["audit_exposure_try"]
    assert patient_payload["recommended_actions"] == prior["recommended_actions"]
    assert cohort["counts"]["review_count"] == patient.claim_reviews.total_rows
    assert cohort["counts"]["advisory_count"] == patient.claim_advisories.total_rows
    assert cohort["counts"]["financial_count"] == 1
    assert reviews["rows"][0]["source_evidence_id"] == patient_payload["claim_reviews"]["rows"][0]["source_evidence_id"]
    assert financial["rows"][0]["source_evidence_id"] == patient_payload["financial_findings"]["rows"][0]["source_evidence_id"]
    assert financial["rows"][0]["confirmed_amount_try"] is None
    assert cohort_reviews["pagination"]["total_matching"] == patient.claim_reviews.total_rows
    assert cohort_advisories["pagination"]["total_matching"] == patient.claim_advisories.total_rows
    assert cohort_financial["pagination"]["total_matching"] == 1
    assert cohort_reviews["rows"] == reviews["rows"][:1]
    assert cohort_advisories["rows"] == advisories["rows"]
    assert cohort_financial["rows"] == financial["rows"]
    assert post_cohort_financial == get_selected_cohort_financial
    assert exact_financial["rows"] == financial["rows"]
    assert exact_financial["pagination"]["total_matching"] == 1
    assert wrong_evidence_id["available"] is True
    assert wrong_evidence_id["rows"] == []
    assert wrong_evidence_id["pagination"]["total_matching"] == 0
    assert cohort_financial["rows"][0]["confirmed_amount_try"] is None
    assert wrong_claim["pagination"]["total_matching"] == 0
    assert beyond_page["pagination"]["total_matching"] == 1
    assert beyond_page["rows"] == []
    assert unknown_patient_rows["available"] is False
    assert unknown_patient_rows["unavailable_reason"] == "requested_patient_not_in_build"
    assert unknown_patient_rows["counts"] is None
    assert not any(
        row.get("rule_id") in {"tablo15_15_material_preauth_missing", "yatak_icu_overlap_510010"}
        for row in compliance_index["rows"]
    )


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
    report_projection = asdict(reports["P1"].claim_compliance)
    report_projection["evaluations"] = [
        row for row in report_projection["evaluations"] if row["rule_id"] not in _FOCUSED_IDS
    ]
    assert asdict(projection) == report_projection
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

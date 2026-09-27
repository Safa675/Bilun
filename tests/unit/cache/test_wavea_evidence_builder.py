"""The exhaustive evidence blob is written separately from default reports."""

from __future__ import annotations

from datetime import date

import pytest

from src.bilun.api.routes.billing import _serialize_billing_report
from src.bilun.cache.build_streaming import json_ready
from src.bilun.cache.builder import (
    _collect_wavea_bill_details,
    _without_wavea_detail,
    _write_wavea_bill_details,
)
from src.bilun.db import (
    connect,
    init_schema,
    read_json_payload,
    read_json_payload_row,
    upsert_single_json_table,
    write_json_payload_rows,
)
from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.billing.types import BillingActionReport
from src.bilun.domain.billing.wavea_full_evidence import build_full_wavea_evidence_index
from src.bilun.domain.billing.wavea_full_evidence import validate_full_wavea_evidence_detail
from src.bilun.domain.claims.patient_context import PatientClaimContext
from tests.unit._helpers.catalog_stubs import install_yatak_catalog_stub
from tests.unit.domain.prose_rules.test_yatak_icu_overlap import (
    _make_claim_header,
    _make_ctx,
    _make_proc_line,
)

pytestmark = pytest.mark.unit


class _NoDeepcopy:
    def __deepcopy__(self, _memo):
        raise AssertionError("Default report serialization traversed exhaustive evidence")


def test_default_report_serialization_skips_exhaustive_detail_before_copy() -> None:
    report = BillingActionReport(patient_id="P1")
    report.wavea_evidence_detail = {"status_rows": _NoDeepcopy()}

    cached = json_ready(_without_wavea_detail(report))
    api = _serialize_billing_report(report)

    assert "wavea_evidence_detail" not in cached
    assert "wavea_evidence_detail" not in api
    assert report.wavea_evidence_detail["status_rows"].__class__ is _NoDeepcopy

    raw = {"patient_id": "P1", "wavea_evidence_detail": {"status_rows": _NoDeepcopy()}}
    assert _without_wavea_detail(raw) == {"patient_id": "P1"}
    assert "wavea_evidence_detail" in raw


def test_cache_rows_preserve_missing_statuses_without_claim_context_or_headers(tmp_path) -> None:
    no_headers = PatientClaimContext("P2", (), (), (), (), ())
    reports = {
        "P1": compute_patient_billing_report("P1", claim_context=None),
        "P2": compute_patient_billing_report("P2", claim_context=no_headers),
    }
    details = {pid: json_ready(report.wavea_evidence_detail) for pid, report in reports.items()}
    for detail in details.values():
        detail["build_id"] = "B1"
    index = build_full_wavea_evidence_index(details)
    index["build_id"] = "B1"
    assert index["n_patients_unavailable"] == 2
    assert sum(
        statuses["missing_inputs"] for statuses in index["counts"]["by_rule"].values()
    ) == 1056

    con = connect(tmp_path / "missing-context.duckdb")
    try:
        init_schema(con)
        write_json_payload_rows(con, "wavea_evidence_detail", "B1", details)
        upsert_single_json_table(con, "wavea_evidence_index", "B1", index)
        write_json_payload_rows(
            con,
            "patient_billing_report_rows",
            "B1",
            {pid: json_ready(_without_wavea_detail(report)) for pid, report in reports.items()},
        )
        for pid in reports:
            stored = read_json_payload_row(con, "wavea_evidence_detail", "B1", pid)
            assert len(stored["evaluations"]) == 528
            assert stored["available"] is False
            assert stored["counts"]["evaluation_count"] == 528
            assert "wavea_evidence_detail" not in read_json_payload_row(
                con, "patient_billing_report_rows", "B1", pid
            )
        assert read_json_payload(con, "wavea_evidence_index", "B1")["counts"] == index["counts"]
    finally:
        con.close()


def test_bill_detail_is_independently_scoped_when_patient_icu_history_changes_outcome(
    tmp_path, monkeypatch
) -> None:
    install_yatak_catalog_stub(monkeypatch)
    icu = _make_claim_header(claim_id="ICU", department="Yogun Bakim")
    srv = _make_claim_header(
        claim_id="SRV", admission=date(2026, 7, 13), discharge=date(2026, 7, 15),
        department="genel_cerrahi",
    )
    ctx = _make_ctx(
        [icu, srv],
        [
            _make_proc_line(claim_id="ICU", procedure_line_id="ICU-1", procedure_code="510090"),
            _make_proc_line(
                claim_id="SRV", procedure_line_id="SRV-1", procedure_code="510010",
                procedure_date=date(2026, 7, 13),
            ),
        ],
    )
    patient = compute_patient_billing_report("P1", claim_context=ctx)
    srv_ctx = ctx.slice_for_claim("SRV")
    assert srv_ctx is not None
    bill = compute_patient_billing_report("P1", claim_context=srv_ctx)
    assert any(
        row["rule_id"] == "yatak_icu_overlap_510010" and row["claim_id"] == "SRV"
        for row in patient.financial_findings.rows
    )
    assert not any(
        row["rule_id"] == "yatak_icu_overlap_510010" for row in bill.financial_findings.rows
    )
    details = _collect_wavea_bill_details({"P1::SRV": bill}, "B1")
    stored = details["P1::SRV"]
    validate_full_wavea_evidence_detail(stored, "P1")
    assert stored["build_id"] == "B1"
    assert stored["claim_scope_inventory"] == {
        "context_state": "available",
        "claims": [{"claim_id": "SRV", "material_line_ids": []}],
    }
    assert len(stored["evaluations"]) == 528
    assert {row["claim_id"] for row in stored["evaluations"]} == {"SRV"}
    assert patient.wavea_evidence_detail["claim_scope_inventory"]["claims"] == [
        {"claim_id": "ICU", "material_line_ids": []},
        {"claim_id": "SRV", "material_line_ids": []},
    ]
    assert bill.financial_findings.rows == stored["financial_rows"]
    with pytest.raises(ValueError, match="scope"):
        _collect_wavea_bill_details({"P1::ICU": bill}, "B1")
    with pytest.raises(ValueError, match="lacks complete"):
        _collect_wavea_bill_details({"P1::SRV": BillingActionReport(patient_id="P1")}, "B1")
    con = connect(tmp_path / "bill-evidence.duckdb")
    try:
        init_schema(con)
        assert _write_wavea_bill_details(
            con,
            {"P1::SRV": bill},
            "B1",
            {"mode": "synthetic_demo", "is_synthetic": True},
            batch_size=1,
        ) == 1
        persisted = read_json_payload_row(con, "wavea_bill_evidence_detail", "B1", "P1::SRV")
        assert {key: value for key, value in persisted.items() if key != "data_source"} == stored
        assert persisted["data_source"]["mode"] == "synthetic_demo"
        assert _write_wavea_bill_details(con, {}, "B1", {}, batch_size=1) == 0
        assert read_json_payload_row(con, "wavea_bill_evidence_detail", "B1", "P1::SRV") is None
    finally:
        con.close()

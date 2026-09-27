"""The exhaustive evidence blob is written separately from default reports."""

from __future__ import annotations

import pytest

from src.bilun.api.routes.billing import _serialize_billing_report
from src.bilun.cache.build_streaming import json_ready
from src.bilun.cache.builder import _without_wavea_detail
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
from src.bilun.domain.billing.wavea_evidence import build_wavea_evidence_index
from src.bilun.domain.claims.patient_context import PatientClaimContext

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
    index = build_wavea_evidence_index(details)
    index["build_id"] = "B1"
    assert index["n_patients_unavailable"] == 2
    assert sum(
        statuses["missing_inputs"] for statuses in index["counts"]["by_rule"].values()
    ) == 64

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
            assert len(stored["evaluations"]) == 32
            assert stored["available"] is False
            assert stored["counts"]["evaluation_count"] == 32
            assert "wavea_evidence_detail" not in read_json_payload_row(
                con, "patient_billing_report_rows", "B1", pid
            )
        assert read_json_payload(con, "wavea_evidence_index", "B1")["counts"] == index["counts"]
    finally:
        con.close()

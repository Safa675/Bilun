"""API tests for the per-bill billing report endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def _seed_bill_report_cache(db_path: Path) -> str:
    from src.bilun.db import (
        BILUN_BUILD_SCOPE,
        complete_build,
        connect,
        create_build,
        init_schema,
        set_active_build,
        write_json_payload_rows,
    )

    con = connect(db_path)
    try:
        init_schema(con)
        build = create_build(
            con,
            project_root=db_path.parent,
            source_hash="bill-billing",
            config_hash="bill-billing",
            schema_version="v1",
            feature_set_version="v1",
            benchmark_version="v1",
            nlp_version="test",
            build_scope=BILUN_BUILD_SCOPE,
        )
        build_id = build.build_id
        write_json_payload_rows(
            con,
            "patient_bill_billing_report_rows",
            build_id,
            {
                "PAT-1::F-PAT-1-001": {
                    "patient_id": "PAT-1",
                    "total_recoverable_try": 1750.0,
                    "sgk_uplift_try": 1750.0,
                    "action_count": 3,
                    "priority": "high",
                    "exactness_status": "exact",
                },
                "PAT-1::F-PAT-1-002": {
                    "patient_id": "PAT-1",
                    "total_recoverable_try": 0.0,
                    "action_count": 1,
                    "priority": "low",
                    "exactness_status": "exact",
                },
                "PAT-1::F-PAT-1-003": {
                    "patient_id": "PAT-1",
                    "action_count": 0,
                    "priority": "low",
                    "exactness_status": "missing_exact_inputs",
                },
            },
        )
        complete_build(
            con,
            build_id,
            row_counts={"patient_bill_billing_report_rows": 3},
            checksums={},
        )
        set_active_build(con, build_id, scope=BILUN_BUILD_SCOPE)
        return build_id
    finally:
        con.close()


@pytest.fixture
def bill_report_cache(monkeypatch, tmp_path):
    import src.bilun.api.routes.billing as billing_mod
    from src.bilun.shared.runtime import get_api_runtime

    db_path = tmp_path / "bill-billing.duckdb"
    build_id = _seed_bill_report_cache(db_path)

    runtime = get_api_runtime()
    if runtime.cache_con is not None:
        try:
            runtime.cache_con.close()
        except Exception:
            pass

    monkeypatch.setattr(runtime, "canonical_cache_db_path", db_path)
    monkeypatch.setattr(runtime, "cache_con", None)
    monkeypatch.setattr(runtime, "pipeline_mode", "persistent")
    monkeypatch.setattr(billing_mod, "PIPELINE_MODE", "persistent")

    yield {"build_id": build_id, "db_path": db_path}

    if runtime.cache_con is not None:
        try:
            runtime.cache_con.close()
        except Exception:
            pass
    runtime.cache_con = None


def test_bill_billing_report_returns_scoped_payload(bill_report_cache):
    import src.bilun.api.routes.billing as billing_mod

    result = billing_mod.get_bill_billing_report("PAT-1", "F-PAT-1-001")

    assert result["patient_id"] == "PAT-1"
    assert result["claim_id"] == "F-PAT-1-001"
    assert result["scope"] == "bill"
    assert result["total_recoverable_try"] == 1750.0
    assert result["priority"] == "high"


def test_bill_cache_response_preserves_missing_versus_computed_zero(bill_report_cache):
    from src.bilun.api.routes.billing import get_bill_billing_report
    from src.bilun.api.schemas import BillingReportResponse

    missing = BillingReportResponse.model_validate(
        get_bill_billing_report("PAT-1", "F-PAT-1-003")
    ).model_dump(mode="json")
    zero = BillingReportResponse.model_validate(
        get_bill_billing_report("PAT-1", "F-PAT-1-002")
    ).model_dump(mode="json")
    assert missing["total_recoverable_try"] is None
    assert missing["sgk_uplift_try"] is None
    assert missing["copay"]["patient_copay_waived_total_try"] is None
    assert zero["total_recoverable_try"] == 0.0


@pytest.mark.parametrize("amount", [None, 0.0, 12.5])
def test_domain_serializer_keeps_uncomputed_and_zero_money(amount):
    from src.bilun.api.routes.billing import _serialize_billing_report
    from src.bilun.api.schemas import BillingReportResponse
    from src.bilun.domain.billing.types import BillingActionReport, CopayOptimization

    report = BillingActionReport(
        patient_id="SYNTHETIC-SERIALIZER",
        total_recoverable_try=amount,
        sgk_uplift_try=amount,
        copay=CopayOptimization(patient_copay_waived_total_try=amount),
    )
    payload = _serialize_billing_report(report)
    response = BillingReportResponse.model_validate(payload).model_dump(mode="json")
    assert payload["total_recoverable_try"] == amount
    assert response["total_recoverable_try"] == amount
    assert response["sgk_uplift_try"] == amount
    assert response["copay"]["patient_copay_waived_total_try"] == amount
    assert response["lab"]["normative_cost_try"] is None


def _medula_entries(scope: str, nonempty: bool) -> list[dict]:
    if not nonempty:
        return []
    entries = [{
        "patient_id": "PAT-1", "claim_id": "F-PAT-1-001",
        "rejection_event_id": "REJ-1102", "sonuc_kodu": "1102",
        "playbook_id": "1102_uncontracted_facility", "rebill_permitted": False,
    }]
    if scope == "patient":
        entries.append({
            "patient_id": "PAT-1", "claim_id": "F-PAT-1-002",
            "rejection_event_id": "REJ-1688", "sonuc_kodu": "1688",
            "playbook_id": "1688_molecular_microbiology", "rebill_permitted": True,
        })
    return entries


@pytest.mark.parametrize("scope", ["patient", "bill"])
@pytest.mark.parametrize("nonempty", [False, True])
@pytest.mark.parametrize("representation", ["live", "cached", "cached_stale_counts"])
def test_medula_counts_survive_live_and_cache_serialization(scope, nonempty, representation):
    from copy import deepcopy

    from src.bilun.api.routes.billing import _serialize_billing_report
    from src.bilun.api.schemas import BillingReportResponse
    from src.bilun.cache.build_streaming import json_ready
    from src.bilun.domain.billing.types import BillingActionReport, MedulaRejectionPlaybook

    entries = _medula_entries(scope, nonempty)
    report = BillingActionReport(
        patient_id="PAT-1", medula_rejection_playbook=MedulaRejectionPlaybook(entries=entries),
        medula_playbook_entry_count=len(entries),
    )
    source = report if representation == "live" else json_ready(report)
    if representation == "cached_stale_counts":
        source["medula_rejection_playbook"].update(entry_count=0, rebill_permitted_count=99)
        source["medula_playbook_entry_count"] = 99
    before = deepcopy(source)
    payload = _serialize_billing_report(source)
    response = BillingReportResponse.model_validate(payload).model_dump(mode="json")
    for output in (payload, response):
        block = output["medula_rejection_playbook"]
        assert block["entries"] == entries
        assert block["entry_count"] == len(entries)
        assert block["rebill_permitted_count"] == sum(row["rebill_permitted"] for row in entries)
        assert output["medula_playbook_entry_count"] == len(entries)
        if nonempty:
            assert block["entries"][0]["sonuc_kodu"] == "1102"
            assert block["entries"][0]["rebill_permitted"] is False
    assert source == before


@pytest.mark.parametrize("scope", ["patient", "bill"])
@pytest.mark.parametrize("nonempty", [False, True])
def test_medula_counts_on_actual_patient_and_bill_cache_endpoints(bill_report_cache, scope, nonempty):
    from src.bilun.api.routes.billing import get_bill_billing_report, get_patient_billing_report
    from src.bilun.api.schemas import BillingReportResponse
    from src.bilun.cache.build_streaming import json_ready
    from src.bilun.db import connect, write_json_payload_rows
    from src.bilun.domain.billing.types import BillingActionReport, MedulaRejectionPlaybook

    entries = _medula_entries(scope, nonempty)
    cached = json_ready(BillingActionReport(
        patient_id="PAT-1", medula_rejection_playbook=MedulaRejectionPlaybook(entries=entries),
        medula_playbook_entry_count=len(entries),
    ))
    assert "entry_count" not in cached["medula_rejection_playbook"]
    table = "patient_billing_report_rows" if scope == "patient" else "patient_bill_billing_report_rows"
    key = "PAT-1" if scope == "patient" else "PAT-1::F-PAT-1-001"
    con = connect(bill_report_cache["db_path"])
    try:
        write_json_payload_rows(con, table, bill_report_cache["build_id"], {key: cached})
    finally:
        con.close()
    result = (get_patient_billing_report("PAT-1") if scope == "patient"
              else get_bill_billing_report("PAT-1", "F-PAT-1-001"))
    response = BillingReportResponse.model_validate(result).model_dump(mode="json")
    block = response["medula_rejection_playbook"]
    assert block["entries"] == entries
    assert block["entry_count"] == len(entries)
    assert block["rebill_permitted_count"] == sum(row["rebill_permitted"] for row in entries)
    assert response["medula_playbook_entry_count"] == len(entries)
    assert response["patient_id"] == "PAT-1"
    if scope == "bill":
        assert response["claim_id"] == "F-PAT-1-001" and response["scope"] == "bill"
        assert all(row["claim_id"] == "F-PAT-1-001" for row in entries)
    if nonempty:
        assert block["entries"][0]["rejection_event_id"] == "REJ-1102"
        assert block["entries"][0]["rebill_permitted"] is False
    # No signed Wave A capability is fabricated to exercise these legacy blocks.
    assert response["claim_reviews"]["available"] is False


def test_bill_billing_report_distinct_per_bill(bill_report_cache):
    import src.bilun.api.routes.billing as billing_mod

    first = billing_mod.get_bill_billing_report("PAT-1", "F-PAT-1-001")
    second = billing_mod.get_bill_billing_report("PAT-1", "F-PAT-1-002")

    assert first["total_recoverable_try"] != second["total_recoverable_try"]
    assert second["total_recoverable_try"] == 0.0


def test_bill_billing_report_unknown_bill_raises(bill_report_cache):
    import src.bilun.api.routes.billing as billing_mod
    from src.bilun.shared.exceptions import PatientNotFound

    with pytest.raises(PatientNotFound):
        billing_mod.get_bill_billing_report("PAT-1", "F-PAT-1-999")

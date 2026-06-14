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
            },
        )
        complete_build(
            con,
            build_id,
            row_counts={"patient_bill_billing_report_rows": 2},
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

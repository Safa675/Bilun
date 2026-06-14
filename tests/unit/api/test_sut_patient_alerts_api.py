"""Regression tests for paginated SUT patient alerts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from src.bilun.db import patient_alerts as cache_store

pytestmark = pytest.mark.unit


class _GuardLegacyPayloadFetch:
    def __init__(self, inner):
        self._inner = inner

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        if normalized.startswith(
            "select payload_json from patient_alerts_payload where build_id = ? limit 1"
        ):
            raise AssertionError("legacy payload_json should stay inside DuckDB")
        if params is None:
            return self._inner.execute(query)
        return self._inner.execute(query, params)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _legacy_alert_payload() -> dict:
    patients = [
        {
            "patient_id": "PAT-ALPHA",
            "n_diagnoses": 3,
            "icd10_chapters": ["C", "E"],
            "copay_exemption": {
                "exempt": True,
                "n_qualifying": 3,
                "qualifying_diagnoses": [
                    {"icd10": "E11.9", "disease": "Diabetes", "range": "E10-E14"},
                    {
                        "icd10": "C50.9",
                        "disease": "Memenin Malıgn Neoplazmı",
                        "range": "C50.9",
                    },
                ],
                "action": "Waive outpatient copay",
            },
            "surcharge_exposure": {
                "n_applicable": 7,
                "exposure_rate": 0.7,
                "top_rules": [
                    {"code": "A1", "name": "Rule A"},
                    {"code": "A2", "name": "Rule B"},
                ],
                "action": "Do not charge surcharge",
            },
            "copay_rate_exposure": {
                "n_applicable": 6,
                "mean_rate": 90.0,
                "top_procedures": [
                    {"code": "X1", "name": "Proc X", "rate_pct": 100.0},
                ],
                "action": "Apply capped copay rate",
            },
        },
        {
            "patient_id": "PAT-BETA",
            "n_diagnoses": 2,
            "icd10_chapters": ["I"],
            "copay_exemption": {
                "exempt": False,
                "n_qualifying": 0,
                "qualifying_diagnoses": [],
                "action": None,
            },
            "surcharge_exposure": {
                "n_applicable": 0,
                "exposure_rate": 0.0,
                "top_rules": [],
                "action": None,
            },
            "copay_rate_exposure": {
                "n_applicable": 0,
                "mean_rate": 0.0,
                "top_procedures": [],
                "action": None,
            },
        },
        {
            "patient_id": "PAT-GAMMA",
            "n_diagnoses": 4,
            "icd10_chapters": ["J", "K"],
            "copay_exemption": {
                "exempt": True,
                "n_qualifying": 1,
                "qualifying_diagnoses": [
                    {"icd10": "J45.9", "disease": "Asthma", "range": "J45-J46"},
                ],
                "action": "Waive outpatient copay",
            },
            "surcharge_exposure": {
                "n_applicable": 3,
                "exposure_rate": 0.3,
                "top_rules": [{"code": "B1", "name": "Rule C"}],
                "action": "Do not charge surcharge",
            },
            "copay_rate_exposure": {
                "n_applicable": 0,
                "mean_rate": 0.0,
                "top_procedures": [],
                "action": None,
            },
        },
        {
            "patient_id": "PAT-DELTA",
            "n_diagnoses": 1,
            "icd10_chapters": ["M"],
            "copay_exemption": {
                "exempt": False,
                "n_qualifying": 0,
                "qualifying_diagnoses": [],
                "action": None,
            },
            "surcharge_exposure": {
                "n_applicable": 0,
                "exposure_rate": 0.0,
                "top_rules": [],
                "action": None,
            },
            "copay_rate_exposure": {
                "n_applicable": 2,
                "mean_rate": 40.0,
                "top_procedures": [
                    {"code": "Y1", "name": "Proc Y", "rate_pct": 50.0},
                ],
                "action": "Apply capped copay rate",
            },
        },
    ]
    return {
        "patients": patients,
        "summary": {
            "n_total_patients": 4,
            "n_exempt_patients": 2,
            "exemption_rate": 0.5,
            "n_patients_with_surcharge_flags": 2,
            "n_patients_with_copay_rate_flags": 2,
            "total_surcharge_flags": 10,
            "total_copay_rate_flags": 8,
        },
    }


def _seed_legacy_patient_alert_cache(db_path: Path) -> str:
    from src.bilun.db import (
        BILUN_BUILD_SCOPE,
        complete_build,
        connect,
        create_build,
        init_schema,
        set_active_build,
        upsert_single_json_table,
    )

    con = connect(db_path)
    try:
        init_schema(con)
        build = create_build(
            con,
            project_root=db_path.parent,
            source_hash="sut-alerts",
            config_hash="sut-alerts",
            schema_version="v1",
            feature_set_version="v1",
            benchmark_version="v1",
            nlp_version="test",
            build_scope=BILUN_BUILD_SCOPE,
        )
        build_id = build.build_id

        upsert_single_json_table(
            con,
            "cohort_optimization_summary",
            build_id,
            {"copay_exemptions": {"n_total_patients": 4}},
        )
        upsert_single_json_table(
            con,
            "cohort_recovery_summary",
            build_id,
            {"n_patients": 4, "grand_total_recoverable": 100.0},
        )
        upsert_single_json_table(
            con,
            "patient_alerts_payload",
            build_id,
            _legacy_alert_payload(),
        )

        complete_build(
            con,
            build_id,
            row_counts={
                "cohort_optimization_summary": 1,
                "cohort_recovery_summary": 1,
                "patient_alerts_payload": 1,
            },
            checksums={},
        )
        set_active_build(con, build_id, scope=BILUN_BUILD_SCOPE)
        return build_id
    finally:
        con.close()


@pytest.fixture
def legacy_alert_cache(monkeypatch, tmp_path):
    import src.bilun.api.routes.chat as chat_mod
    import src.bilun.api.routes.alerts as sut_mod
    from src.bilun.shared.runtime import get_api_runtime

    db_path = tmp_path / "sut-alerts.duckdb"
    build_id = _seed_legacy_patient_alert_cache(db_path)

    runtime = get_api_runtime()
    old_con = runtime.cache_con
    if old_con is not None:
        try:
            old_con.close()
        except Exception:
            pass

    monkeypatch.setattr(runtime, "canonical_cache_db_path", db_path)
    monkeypatch.setattr(runtime, "cache_con", None)
    monkeypatch.setattr(runtime, "pipeline_mode", "hybrid")
    monkeypatch.setattr(sut_mod, "PIPELINE_MODE", "hybrid")
    monkeypatch.setattr(chat_mod, "_rate_window", {})

    yield {"build_id": build_id, "db_path": db_path}

    new_con = runtime.cache_con
    if new_con is not None:
        try:
            new_con.close()
        except Exception:
            pass
    runtime.cache_con = None


def test_patient_alerts_backfills_legacy_blob_and_returns_paginated_response(
    legacy_alert_cache,
):
    import src.bilun.api.routes.alerts as sut_mod
    import src.bilun.shared.state as state_mod

    response = sut_mod.get_patient_alerts()

    assert response["summary"]["n_total_patients"] == 4
    assert response["summary"]["n_patients_with_surcharge_flags"] is None
    assert response["summary"]["surcharge_exactness_status"] == "missing_exact_inputs"
    assert [patient["patient_id"] for patient in response["patients"]] == [
        "PAT-ALPHA",
        "PAT-GAMMA",
        "PAT-BETA",
        "PAT-DELTA",
    ]
    assert response["pagination"] == {
        "total_matching": 4,
        "limit": 100,
        "offset": 0,
        "has_more": False,
    }
    assert response["query"] == {
        "category": "exemptions",
        "status": "all",
        "search": "",
    }
    assert response["patients"][0]["copay_exemption"]["qualifying_diagnoses"][1]["disease"] == (
        "Memenin Malign Neoplazmı"
    )

    con = state_mod._get_cache_con()
    row_count = con.execute(
        "SELECT COUNT(*) FROM patient_alert_rows WHERE build_id = ?",
        [legacy_alert_cache["build_id"]],
    ).fetchone()[0]
    summary_row = con.execute(
        "SELECT payload_json FROM patient_alerts_summary WHERE build_id = ?",
        [legacy_alert_cache["build_id"]],
    ).fetchone()

    assert row_count == 4
    assert json.loads(summary_row[0])["n_total_patients"] == 4


def test_patient_alert_summary_backfill_avoids_fetching_legacy_payload_json(
    legacy_alert_cache,
):
    import src.bilun.shared.state as state_mod

    con = state_mod._get_cache_con()
    con.execute(
        "DELETE FROM patient_alerts_summary WHERE build_id = ?",
        [legacy_alert_cache["build_id"]],
    )

    guarded = _GuardLegacyPayloadFetch(con)
    assert cache_store.ensure_patient_alert_summary(
        guarded, legacy_alert_cache["build_id"]
    )

    summary = con.execute(
        "SELECT payload_json FROM patient_alerts_summary WHERE build_id = ?",
        [legacy_alert_cache["build_id"]],
    ).fetchone()
    assert json.loads(summary[0])["n_total_patients"] == 4


def test_patient_alerts_backfill_avoids_fetching_legacy_payload_json(
    legacy_alert_cache,
):
    import src.bilun.shared.state as state_mod

    con = state_mod._get_cache_con()
    con.execute(
        "DELETE FROM patient_alert_rows WHERE build_id = ?",
        [legacy_alert_cache["build_id"]],
    )
    con.execute(
        "DELETE FROM patient_alerts_summary WHERE build_id = ?",
        [legacy_alert_cache["build_id"]],
    )

    guarded = _GuardLegacyPayloadFetch(con)
    assert cache_store.ensure_patient_alert_tables(
        guarded, legacy_alert_cache["build_id"]
    )

    row_count = con.execute(
        "SELECT COUNT(*) FROM patient_alert_rows WHERE build_id = ?",
        [legacy_alert_cache["build_id"]],
    ).fetchone()[0]
    assert row_count == 4


def test_patient_alerts_support_category_status_search_limit_and_offset(
    legacy_alert_cache,
):
    import src.bilun.api.routes.alerts as sut_mod

    first_page = sut_mod.get_patient_alerts(
        category="exemptions",
        status="exempt",
        limit=1,
        offset=0,
    )
    second_page = sut_mod.get_patient_alerts(
        category="exemptions",
        status="exempt",
        limit=1,
        offset=1,
    )
    searched = sut_mod.get_patient_alerts(
        category="exemptions",
        status="all",
        search="delta",
    )
    gated = sut_mod.get_patient_alerts(
        category="surcharge",
        status="flagged",
    )

    assert first_page["pagination"] == {
        "total_matching": 2,
        "limit": 1,
        "offset": 0,
        "has_more": True,
    }
    assert [patient["patient_id"] for patient in first_page["patients"]] == ["PAT-ALPHA"]
    assert [patient["patient_id"] for patient in second_page["patients"]] == ["PAT-GAMMA"]

    assert searched["query"] == {
        "category": "exemptions",
        "status": "all",
        "search": "delta",
    }
    assert [patient["patient_id"] for patient in searched["patients"]] == ["PAT-DELTA"]
    assert gated["pagination"]["total_matching"] == 0
    assert gated["patients"] == []


@pytest.mark.parametrize(
    ("kwargs", "detail"),
    [
        ({"category": "unknown"}, "Invalid patient alerts category"),
        ({"category": "exemptions", "status": "flagged"}, "Invalid status"),
        ({"limit": 0}, "limit"),
        ({"limit": 101}, "limit"),
        ({"offset": -1}, "offset"),
    ],
)
def test_patient_alerts_validate_query_params(legacy_alert_cache, kwargs, detail):
    import src.bilun.api.routes.alerts as sut_mod
    from src.bilun.shared.exceptions import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        sut_mod.get_patient_alerts(**kwargs)

    assert exc_info.value.status_code == 400
    assert detail in exc_info.value.message


def test_patient_alerts_raise_503_when_no_backfill_source_exists(legacy_alert_cache):
    import src.bilun.api.routes.alerts as sut_mod
    import src.bilun.shared.state as state_mod
    from src.bilun.shared.exceptions import ServiceUnavailableError

    con = state_mod._get_cache_con()
    con.execute(
        "DELETE FROM patient_alerts_payload WHERE build_id = ?",
        [legacy_alert_cache["build_id"]],
    )

    with pytest.raises(ServiceUnavailableError) as exc_info:
        sut_mod.get_patient_alerts()

    assert exc_info.value.status_code == 503
    assert "backfill" in exc_info.value.message.lower()


def test_optimizer_chat_context_reads_runtime_data_without_row_backfill(
    legacy_alert_cache,
):
    # Original test checked `_fetch_db_context`; chat context was refactored to
    # `_fetch_runtime_data`, which no longer includes patient_alerts_summary.
    # This regression guard now verifies the runtime-data fetch does not
    # trigger patient_alert_rows backfill.
    import src.bilun.api.routes.chat as chat_mod
    import src.bilun.shared.state as state_mod

    ctx = chat_mod._fetch_runtime_data("SUT Optimizer", None)

    assert "optimization_summary" in ctx
    assert ctx["optimization_summary"]["summary"]["copay_exemptions"]["n_total_patients"] == 4

    con = state_mod._get_cache_con()
    row_count = con.execute(
        "SELECT COUNT(*) FROM patient_alert_rows WHERE build_id = ?",
        [legacy_alert_cache["build_id"]],
    ).fetchone()[0]
    assert row_count == 0

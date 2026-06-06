"""Regression tests for concurrent SUT cache-backed endpoint reads."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.unit

SYNTHETIC_DATA_SOURCE = {
    "mode": "synthetic_demo",
    "label": "Synthetic SUT demo claim data",
    "claim_source": "data/synthetic/sut/claims",
    "clinical_source": "data/synthetic/sut/clean",
    "is_synthetic": True,
    "notice": "Demo data only. Rule calculations are exact for these synthetic claim lines.",
}


def _seed_sut_cache(
    db_path: Path,
    *,
    use_row_billing: bool = True,
    include_data_source: bool = True,
) -> str:
    from src.bilun.db import (
        BILUN_BUILD_SCOPE,
        complete_build,
        connect,
        create_build,
        init_schema,
        set_active_build,
        upsert_single_json_table,
        write_json_payload_rows,
        write_dataframe,
    )

    con = connect(db_path)
    try:
        init_schema(con)
        build = create_build(
            con,
            project_root=db_path.parent,
            source_hash="sut-test",
            config_hash="sut-test",
            schema_version="v1",
            feature_set_version="v1",
            benchmark_version="v1",
            nlp_version="test",
            build_scope=BILUN_BUILD_SCOPE,
        )
        build_id = build.build_id

        optimization_summary = {
            "copay_exemptions": {
                "n_exempt_patients": 1,
                "n_total_patients": 1,
                "exemption_rate": 1.0,
                "top_diseases": [],
                "methodology": "test",
            },
            "surcharge_exposure": {"n_total_patients": 1, "total_surcharge_flags": 1},
            "copay_rate_exposure": {
                "n_total_patients": 1,
                "n_patients_with_copay_rate_flags": 1,
                "total_copay_rate_flags": 1,
            },
        }
        if include_data_source:
            optimization_summary["data_source"] = SYNTHETIC_DATA_SOURCE
        upsert_single_json_table(
            con,
            "cohort_optimization_summary",
            build_id,
            optimization_summary,
        )
        upsert_single_json_table(
            con,
            "patient_alerts_payload",
            build_id,
            {
                "patients": [
                    {
                        "patient_id": "P1",
                        "n_diagnoses": 1,
                        "icd10_chapters": ["E"],
                        "copay_exemption": {
                            "exempt": True,
                            "n_qualifying": 1,
                            "qualifying_diagnoses": [],
                            "action": "Waive outpatient copay",
                        },
                        "surcharge_exposure": {
                            "n_applicable": 1,
                            "exposure_rate": 1.0,
                            "top_rules": [],
                            "action": "Do not charge surcharge",
                        },
                        "copay_rate_exposure": {
                            "n_applicable": 1,
                            "mean_rate": 0.1,
                            "max_rate": 0.1,
                            "top_rules": [],
                            "action": "Cap copay rate",
                        },
                    }
                ],
                "summary": {
                    "n_total_patients": 1,
                    "n_exempt_patients": 1,
                    "exemption_rate": 1.0,
                    "total_surcharge_flags": 1,
                    "n_patients_with_copay_rate_flags": 1,
                    "total_copay_rate_flags": 1,
                },
            },
        )
        recovery_summary = {
            "n_patients": 1,
            "grand_total_recoverable": 42.0,
            "total_lab_savings": 10.0,
            "total_copay_savings": 7.0,
            "total_strategy_savings": 20.0,
            "savings_by_category": {"lab": 10.0},
            "priority_distribution": {"high": 1},
            "top_patients": [{"patient_id": "P1", "total_recoverable_try": 42.0}],
        }
        if include_data_source:
            recovery_summary["data_source"] = SYNTHETIC_DATA_SOURCE
        upsert_single_json_table(
            con,
            "cohort_recovery_summary",
            build_id,
            recovery_summary,
        )
        billing_payload = {
            "P1": {
                "patient_id": "P1",
                "total_recoverable_try": 42.0,
                "action_count": 2,
                "priority": "high",
                "lab": {"normative_cost_try": 10.0, "flagged_tests": []},
                "copay": {"is_exempt": True, "total_copay_savings_try": 7.0},
                "billing_strategy": {"recommendations": [], "total_strategy_savings_try": 20.0},
                "materials": {"flagged_items": [], "non_reimbursable_count": 0},
            }
        }
        if include_data_source:
            billing_payload["P1"]["data_source"] = SYNTHETIC_DATA_SOURCE
        if use_row_billing:
            write_json_payload_rows(
                con,
                "patient_billing_report_rows",
                build_id,
                billing_payload,
            )
        else:
            upsert_single_json_table(
                con,
                "patient_billing_reports",
                build_id,
                billing_payload,
            )
        write_dataframe(
            con,
            "patient_diagnoses",
            build_id,
            pl.DataFrame(
                [{"patient_id": "P1", "diagnoses_json": json.dumps(["E11.9"])}]
            ),
        )
        write_dataframe(
            con,
            "patient_meta",
            build_id,
            pl.DataFrame(
                [
                    {
                        "patient_id": "P1",
                        "age": 62,
                        "sex": "E",
                        "sex_raw": "E",
                        "weight_kg": 72.0,
                        "doctor_code": "D1",
                        "comorbidity_conditions_json": "[]",
                        "data_completeness": 1.0,
                        "regime_state": "Stable",
                    }
                ]
            ),
        )
        outcome_payload = {
            "patient_id": "P1",
            "BILUN_claim_totals": {
                "patient_id": "P1",
                "total_billed_try": 42.0,
                "exactness_status": "exact",
                "source": "claim_lines",
            },
        }
        if include_data_source:
            outcome_payload["data_source"] = SYNTHETIC_DATA_SOURCE
        write_dataframe(
            con,
            "patient_outcome_base",
            build_id,
            pl.DataFrame(
                [
                    {
                        "patient_id": "P1",
                        "payload_json": json.dumps(outcome_payload),
                    }
                ]
            ),
        )

        complete_build(
            con,
            build_id,
            row_counts={
                "cohort_optimization_summary": 1,
                "patient_alerts_payload": 1,
                "cohort_recovery_summary": 1,
                (
                    "patient_billing_report_rows"
                    if use_row_billing
                    else "patient_billing_reports"
                ): 1,
                "patient_diagnoses": 1,
                "patient_meta": 1,
                "patient_outcome_base": 1,
            },
            checksums={},
        )
        set_active_build(con, build_id, scope=BILUN_BUILD_SCOPE)
        return build_id
    finally:
        con.close()


@pytest.fixture
def sut_cache_fixture(monkeypatch, tmp_path):
    import src.bilun.api.routes.alerts as sut_alerts_mod
    import src.bilun.api.routes.billing as sut_billing_mod
    import src.bilun.api.routes.optimization as sut_opt_mod
    import src.bilun.api.routes.patients as sut_patients_mod
    from src.bilun.shared.runtime import get_api_runtime

    db_path = tmp_path / "sut-cache.duckdb"
    build_id = _seed_sut_cache(db_path)

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
    # Each SUT submodule snapshots PIPELINE_MODE at import (`from ... import`),
    # so each binding needs to be patched separately for the read path.
    monkeypatch.setattr(sut_alerts_mod, "PIPELINE_MODE", "hybrid")
    monkeypatch.setattr(sut_opt_mod, "PIPELINE_MODE", "hybrid")
    monkeypatch.setattr(sut_billing_mod, "PIPELINE_MODE", "hybrid")
    monkeypatch.setattr(sut_patients_mod, "PIPELINE_MODE", "hybrid")

    yield {"build_id": build_id, "db_path": db_path}

    new_con = runtime.cache_con
    if new_con is not None:
        try:
            new_con.close()
        except Exception:
            pass
    runtime.cache_con = None


def _run_parallel(fn, *, workers: int = 5, rounds: int = 3):
    results = []
    for _ in range(rounds):
        with ThreadPoolExecutor(max_workers=workers) as executor:
            results.extend(executor.map(lambda _idx: fn(), range(workers)))
    return results


def test_patient_alerts_succeeds_under_parallel_reads(sut_cache_fixture):
    import src.api.routes.sut as sut_mod

    results = _run_parallel(sut_mod.get_patient_alerts)

    assert all(result["summary"]["n_total_patients"] == 1 for result in results)


def test_optimization_summary_succeeds_under_parallel_reads(sut_cache_fixture):
    import src.api.routes.sut as sut_mod

    results = _run_parallel(sut_mod.get_optimization_summary)

    assert all(result["copay_exemptions"]["n_total_patients"] == 1 for result in results)
    assert all(result["data_source"]["mode"] == "synthetic_demo" for result in results)
    assert all(result["data_source"]["is_synthetic"] is True for result in results)


def test_revenue_recovery_succeeds_under_parallel_reads(sut_cache_fixture):
    import src.api.routes.sut as sut_mod

    results = _run_parallel(sut_mod.get_revenue_recovery)

    assert all(result["n_patients"] == 1 for result in results)
    assert all(result["data_source"]["mode"] == "synthetic_demo" for result in results)


def test_patient_optimization_succeeds_under_parallel_reads(sut_cache_fixture):
    import src.api.routes.sut as sut_mod

    results = _run_parallel(lambda: sut_mod.get_patient_optimization("P1"))

    assert all(result["patient_id"] == "P1" for result in results)
    assert all(result["data_source"]["mode"] == "synthetic_demo" for result in results)


def test_billing_report_succeeds_under_parallel_reads(sut_cache_fixture):
    import src.api.routes.sut as sut_mod

    results = _run_parallel(lambda: sut_mod.get_patient_billing_report("P1"))

    assert all(result["patient_id"] == "P1" for result in results)
    assert all(result["data_source"]["mode"] == "synthetic_demo" for result in results)


def test_sut_patient_listing_includes_data_source(sut_cache_fixture):
    import src.api.routes.sut as sut_mod

    result = sut_mod.get_sut_patients()

    assert result["patients"] == ["P1"]
    assert result["data_source"]["mode"] == "synthetic_demo"


def test_sut_patient_outcome_includes_claim_totals_and_data_source(sut_cache_fixture):
    import src.api.routes.sut as sut_mod

    result = sut_mod.get_sut_patient_outcome("P1", include_expensive=False)

    assert result["BILUN_claim_totals"]["exactness_status"] == "exact"
    assert result["data_source"]["mode"] == "synthetic_demo"


def test_billing_report_falls_back_to_legacy_monolith(monkeypatch, tmp_path):
    import src.api.routes.sut as sut_mod
    import src.bilun.api.routes.alerts as sut_alerts_mod
    import src.bilun.api.routes.billing as sut_billing_mod
    import src.bilun.api.routes.optimization as sut_opt_mod
    from src.bilun.shared.runtime import get_api_runtime

    db_path = tmp_path / "legacy-sut-cache.duckdb"
    _seed_sut_cache(db_path, use_row_billing=False)

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
    monkeypatch.setattr(sut_alerts_mod, "PIPELINE_MODE", "hybrid")
    monkeypatch.setattr(sut_opt_mod, "PIPELINE_MODE", "hybrid")
    monkeypatch.setattr(sut_billing_mod, "PIPELINE_MODE", "hybrid")

    try:
        result = sut_mod.get_patient_billing_report("P1")
        assert result["patient_id"] == "P1"
        assert result["total_recoverable_try"] == 42.0
        assert result["data_source"]["mode"] == "synthetic_demo"
    finally:
        new_con = runtime.cache_con
        if new_con is not None:
            try:
                new_con.close()
            except Exception:
                pass
        runtime.cache_con = None


def test_missing_cache_provenance_returns_unavailable(monkeypatch, tmp_path):
    import src.api.routes.sut as sut_mod
    import src.bilun.api.routes.billing as sut_billing_mod
    import src.bilun.api.routes.optimization as sut_opt_mod
    from src.bilun.shared.runtime import get_api_runtime

    db_path = tmp_path / "missing-provenance-sut-cache.duckdb"
    _seed_sut_cache(db_path, include_data_source=False)

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
    monkeypatch.setattr(sut_opt_mod, "PIPELINE_MODE", "hybrid")
    monkeypatch.setattr(sut_billing_mod, "PIPELINE_MODE", "hybrid")

    try:
        summary = sut_mod.get_optimization_summary()
        billing = sut_mod.get_patient_billing_report("P1")
        patient = sut_mod.get_patient_optimization("P1")

        assert summary["data_source"]["mode"] == "unavailable"
        assert billing["data_source"]["mode"] == "unavailable"
        assert patient["data_source"]["mode"] == "unavailable"
        assert summary["data_source"]["is_synthetic"] is None
    finally:
        new_con = runtime.cache_con
        if new_con is not None:
            try:
                new_con.close()
            except Exception:
                pass
        runtime.cache_con = None

"""API tests for the per-bill optimization endpoint."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from src.bilun.domain.claims.loader import load_sut_claim_dataset

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def dataset():
    """The committed claim dataset. A load error fails the tests that use it; it never skips them."""
    return load_sut_claim_dataset()


def _pick_patient_with_claims(dataset) -> tuple[str, str]:
    pid = next(p for p, claims in dataset.claims_by_patient.items() if claims)
    return pid, dataset.claims_by_patient[pid][0].claim_id


def _seed_diagnoses_cache(db_path: Path, patient_id: str) -> str:
    from src.bilun.db import (
        BILUN_BUILD_SCOPE,
        complete_build,
        connect,
        create_build,
        init_schema,
        set_active_build,
        write_dataframe,
    )

    con = connect(db_path)
    try:
        init_schema(con)
        build = create_build(
            con,
            project_root=db_path.parent,
            source_hash="bill-opt",
            config_hash="bill-opt",
            schema_version="v1",
            feature_set_version="v1",
            benchmark_version="v1",
            nlp_version="test",
            build_scope=BILUN_BUILD_SCOPE,
        )
        build_id = build.build_id
        write_dataframe(
            con,
            "patient_diagnoses",
            build_id,
            pl.DataFrame([{"patient_id": patient_id, "diagnoses_json": json.dumps(["E11.9"])}]),
        )
        complete_build(
            con,
            build_id,
            row_counts={"patient_diagnoses": 1},
            checksums={},
        )
        set_active_build(con, build_id, scope=BILUN_BUILD_SCOPE)
        return build_id
    finally:
        con.close()


@pytest.fixture
def bill_opt_cache(monkeypatch, tmp_path, dataset):
    import src.bilun.api.routes.optimization as opt_mod
    from src.bilun.shared.runtime import get_api_runtime

    patient_id, claim_id = _pick_patient_with_claims(dataset)
    db_path = tmp_path / "bill-opt.duckdb"
    build_id = _seed_diagnoses_cache(db_path, patient_id)

    runtime = get_api_runtime()
    if runtime.cache_con is not None:
        try:
            runtime.cache_con.close()
        except Exception:
            pass

    monkeypatch.setattr(runtime, "canonical_cache_db_path", db_path)
    monkeypatch.setattr(runtime, "cache_con", None)
    monkeypatch.setattr(runtime, "pipeline_mode", "persistent")
    monkeypatch.setattr(opt_mod, "PIPELINE_MODE", "persistent")

    yield {"build_id": build_id, "patient_id": patient_id, "claim_id": claim_id}

    if runtime.cache_con is not None:
        try:
            runtime.cache_con.close()
        except Exception:
            pass
    runtime.cache_con = None


def test_bill_optimization_returns_scoped_payload(bill_opt_cache):
    import src.bilun.api.routes.optimization as opt_mod

    pid = bill_opt_cache["patient_id"]
    claim_id = bill_opt_cache["claim_id"]
    result = opt_mod.get_bill_optimization(pid, claim_id)

    assert result["patient_id"] == pid
    assert result["claim_id"] == claim_id
    assert result["scope"] == "bill"
    # standard optimization sections are present
    assert "copay_exemptions" in result
    assert "surcharge_exposure" in result
    assert "drg_unbundling" in result


def test_bill_optimization_unknown_bill_raises(bill_opt_cache):
    import src.bilun.api.routes.optimization as opt_mod
    from src.bilun.shared.exceptions import PatientNotFound

    pid = bill_opt_cache["patient_id"]
    with pytest.raises(PatientNotFound):
        opt_mod.get_bill_optimization(pid, "F-DOES-NOT-EXIST-999")

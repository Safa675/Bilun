"""Tests for /api/patients/{patient_id}/claims* endpoints."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


def _fake_dataset():
    """Minimal fake SUT claim dataset for the route under test."""
    header = SimpleNamespace(
        claim_id="CLM-001",
        patient_id="PAT-TEST-01",
        episode_id="EPS-001",
        claim_type="outpatient",
        facility_tier="1",
        provider_type="physician",
        department="cardiology",
        admission_date=None,
        discharge_date=None,
        claim_start_date=date(2024, 1, 15),
        claim_end_date=date(2024, 1, 15),
        primary_icd10="I10",
        package_candidate=False,
        expected_total_billed_try=Decimal("1200.00"),
        expected_total_payable_try=Decimal("960.00"),
        expected_denial_reason="",
        scenario_tag="demo",
        occupational_context="none",
    )
    procedure = SimpleNamespace(
        procedure_line_id="PRC-001",
        procedure_date=date(2024, 1, 15),
        procedure_code="99213",
        procedure_name="Office Visit",
        procedure_category="evaluation",
        quantity=1,
        unit_price_try=Decimal("800.00"),
        billed_amount_try=Decimal("800.00"),
        expected_payable_try=Decimal("640.00"),
        is_package_included=False,
        package_code="",
        denial_reason_expected="",
        rule_trace_expected="",
    )
    material = SimpleNamespace(
        material_line_id="MAT-001",
        material_date=date(2024, 1, 15),
        material_code="STENT-001",
        material_name="Drug Eluting Stent",
        material_type="cardiac",
        specialty_category="interventional_cardiology",
        quantity=1,
        unit_price_try=Decimal("300.00"),
        billed_amount_try=Decimal("300.00"),
        expected_payable_try=Decimal("240.00"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    drug = SimpleNamespace(
        drug_claim_line_id="DRG-001",
        prescription_id="RX-001",
        drug_claim_date=date(2024, 1, 15),
        drug_name="Metformin",
        drug_code="A10BA02",
        barkod="1234567890123",
        equivalence_group="generic",
        quantity=30,
        unit_price_try=Decimal("3.50"),
        billed_amount_try=Decimal("105.00"),
        expected_payable_try=Decimal("84.00"),
        discount_tier_expected=Decimal("0.00"),
        denial_reason_expected="",
        rule_trace_expected="",
    )
    return SimpleNamespace(
        claims_by_patient={"PAT-TEST-01": (header,)},
        procedure_lines_by_claim={"CLM-001": (procedure,)},
        material_lines_by_claim={"CLM-001": (material,)},
        drug_lines_by_claim={"CLM-001": (drug,)},
    )


def test_list_patient_claims(api_client):
    with patch(
        "src.bilun.api.routes.patients._load_claim_dataset",
        return_value=_fake_dataset(),
    ):
        response = api_client.get("/api/patients/PAT-TEST-01/claims")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["patient_id"] == "PAT-TEST-01"
    assert data["total"] == 1
    assert len(data["claims"]) == 1
    claim = data["claims"][0]
    assert claim["claim_id"] == "CLM-001"
    assert claim["episode_id"] == "EPS-001"
    assert claim["claim_type"] == "outpatient"
    assert claim["expected_total_billed_try"] == 1200.00
    assert claim["expected_total_payable_try"] == 960.00
    assert claim["recoverable_try"] is None
    assert claim["priority"] is None
    assert "data_source" in data


@pytest.mark.parametrize(
    "rollup,expected",
    [
        (None, None),
        ({}, None),
        ({"total_recoverable_try": None}, None),
        ({"total_recoverable_try": 0.0}, 0.0),
        ({"total_recoverable_try": 12.5}, 12.5),
    ],
)
def test_claim_summary_keeps_missing_rollup_amount_distinct_from_zero(rollup, expected):
    from src.bilun.api.routes.patients import _serialize_claim_summary

    header = _fake_dataset().claims_by_patient["PAT-TEST-01"][0]
    assert _serialize_claim_summary(header, rollup=rollup)["recoverable_try"] == expected


def test_list_patient_claims_not_found(api_client):
    with patch(
        "src.bilun.api.routes.patients._load_claim_dataset",
        return_value=_fake_dataset(),
    ):
        response = api_client.get("/api/patients/PAT-MISSING/claims")

    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "patient_not_found"


def test_get_patient_claim_detail(api_client):
    with patch(
        "src.bilun.api.routes.patients._load_claim_dataset",
        return_value=_fake_dataset(),
    ):
        response = api_client.get("/api/patients/PAT-TEST-01/claims/CLM-001")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["claim_id"] == "CLM-001"
    assert data["patient_id"] == "PAT-TEST-01"
    assert data["primary_icd10"] == "I10"
    assert data["expected_total_billed_try"] == 1200.00
    assert len(data["procedures"]) == 1
    assert data["procedures"][0]["procedure_code"] == "99213"
    assert len(data["materials"]) == 1
    assert data["materials"][0]["material_code"] == "STENT-001"
    assert len(data["drugs"]) == 1
    assert data["drugs"][0]["drug_code"] == "A10BA02"
    assert "data_source" in data


def test_get_patient_claim_detail_wrong_patient(api_client):
    with patch(
        "src.bilun.api.routes.patients._load_claim_dataset",
        return_value=_fake_dataset(),
    ):
        response = api_client.get("/api/patients/PAT-OTHER/claims/CLM-001")

    assert response.status_code == 404


def test_get_patient_claim_detail_unknown_claim(api_client):
    with patch(
        "src.bilun.api.routes.patients._load_claim_dataset",
        return_value=_fake_dataset(),
    ):
        response = api_client.get("/api/patients/PAT-TEST-01/claims/CLM-UNKNOWN")

    assert response.status_code == 404


def test_list_patient_claims_dataset_unavailable(api_client):
    with patch(
        "src.bilun.api.routes.patients._load_claim_dataset",
        return_value=None,
    ):
        response = api_client.get("/api/patients/PAT-TEST-01/claims")

    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "service_unavailable"


def _seed_claims_with_bill_rollups(db_path) -> str:
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
            source_hash="claims-rollups",
            config_hash="claims-rollups",
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
                "PAT-TEST-01::CLM-001": {
                    "total_recoverable_try": 1750.0,
                    "priority": "high",
                },
            },
        )
        complete_build(
            con,
            build_id,
            row_counts={"patient_bill_billing_report_rows": 1},
            checksums={},
        )
        set_active_build(con, build_id, scope=BILUN_BUILD_SCOPE)
        return build_id
    finally:
        con.close()


def test_list_patient_claims_includes_bill_rollups(api_client, monkeypatch, tmp_path):
    import src.bilun.api.routes.patients as patients_mod
    from src.bilun.shared.runtime import get_api_runtime

    db_path = tmp_path / "claims-rollups.duckdb"
    _seed_claims_with_bill_rollups(db_path)

    runtime = get_api_runtime()
    if runtime.cache_con is not None:
        try:
            runtime.cache_con.close()
        except Exception:
            pass

    monkeypatch.setattr(runtime, "canonical_cache_db_path", db_path)
    monkeypatch.setattr(runtime, "cache_con", None)
    monkeypatch.setattr(runtime, "pipeline_mode", "hybrid")
    monkeypatch.setattr(patients_mod, "PIPELINE_MODE", "hybrid")

    with patch(
        "src.bilun.api.routes.patients._load_claim_dataset",
        return_value=_fake_dataset(),
    ):
        response = api_client.get("/api/patients/PAT-TEST-01/claims")

    assert response.status_code == 200, response.text
    claim = response.json()["claims"][0]
    assert claim["recoverable_try"] == 1750.0
    assert claim["priority"] == "high"

    if runtime.cache_con is not None:
        try:
            runtime.cache_con.close()
        except Exception:
            pass
    runtime.cache_con = None

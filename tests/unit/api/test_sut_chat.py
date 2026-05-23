"""Regression tests for the SUT-owned chat endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


def test_sut_chat_streams_sut_only_context(monkeypatch):
    import src.bilun.api.routes.chat as sut_chat_mod
    from src.bilun.api import app

    captured: dict[str, object] = {}

    monkeypatch.setattr(sut_chat_mod, "_check_rate_limit", lambda _ip: True)
    monkeypatch.setattr(
        sut_chat_mod,
        "get_optimization_summary",
        lambda: {
            "copay_exemptions": {
                "n_exempt_patients": 5,
                "n_total_patients": 12,
                "exemption_rate": 0.4167,
            },
            "surcharge_exposure": {
                "exactness_status": "missing_exact_inputs",
                "unavailable_reason": "Needs exact billed procedure lines.",
                "required_inputs_missing": ["billed_procedure_codes"],
            },
            "copay_rate_exposure": {"exactness_status": "missing_exact_inputs"},
            "drg_unbundling": {"exactness_status": "missing_exact_inputs"},
            "drug_discount_validation": {"exactness_status": "missing_exact_inputs"},
        },
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_bilun_patient_outcome",
        lambda patient_id, include_expensive=True: {
            "patient_id": patient_id,
            "drg_summary": {
                "pricing_status": "unknown_date",
                "required_inputs_missing": ["visit_date"],
            },
            "expensive_analytics": {"state": "ready", "included": include_expensive},
        },
    )
    monkeypatch.setattr(
        sut_chat_mod,
        "get_patient_optimization",
        lambda patient_id: {
            "patient_id": patient_id,
            "n_diagnoses": 2,
            "icd10_chapters": ["E", "I"],
            "copay_exemptions": {"exempt": True, "n_qualifying": 1, "qualifying_diagnoses": []},
            "surcharge_exposure": {"exactness_status": "missing_exact_inputs"},
            "copay_rate_exposure": {"exactness_status": "missing_exact_inputs"},
            "drg_unbundling": {"exactness_status": "missing_exact_inputs"},
        },
    )

    async def fake_stream_chat_response(messages, runtime_context="", extra_params=None):
        captured["messages"] = messages
        captured["runtime_context"] = runtime_context
        captured["extra_params"] = extra_params
        yield "SUT "
        yield "ready"

    monkeypatch.setattr(sut_chat_mod, "stream_chat_response", fake_stream_chat_response)

    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "Summarize this patient."}],
                "patient_id": "P-001",
                "active_tab": "SUT Patient Workspace",
            },
        )

    assert response.status_code == 200
    assert 'data: "SUT "' in response.text
    assert 'data: "ready"' in response.text
    assert 'data: "[DONE]"' in response.text
    assert captured["messages"] == [{"role": "user", "content": "Summarize this patient."}]
    runtime_context = str(captured["runtime_context"])
    assert '"product": "BILUN"' in runtime_context
    assert '"active_tab": "SUT Patient Workspace"' in runtime_context
    assert "Patient ID: P-001" in runtime_context
    assert "Copay exempt: YES" in runtime_context
    assert "[exactness: unknown_date]" in runtime_context
    assert "visit_date" in runtime_context


def test_removed_estimate_native_sut_routes_return_404():
    from src.bilun.api import app

    with TestClient(app) as client:
        assert client.get("/api/sut/drg-pricing").status_code == 404
        assert client.get("/api/sut/exposure-summary").status_code == 404
        assert client.post(
            "/api/sut/copay-simulate",
            json={
                "facility_tier": "devlet",
                "patient_category": "normal",
                "n_visits": 1,
                "n_prescriptions": 1,
                "rx_cost": 10.0,
            },
        ).status_code == 404
